"""Visual verification of rule candidates, owned by the API process.

Both camera paths hand `vlm`-policy candidates here: the phone path in-process, the RTSP worker through
POST /internal/rule-events with `verification.status == "candidate"`. One consumer asks the local VLM a forced-choice
question (services/rules/verify_questions.py) through the shared priority gateway, so chat and compilation never wait
behind it and it never waits behind them. Outcomes:

  verified      the positive option was chosen        -> published as an alert
  rejected      a negative option was chosen          -> audit log only
  unverifiable  abstain / bad output / timeout / VLM down / no evidence -> the rule's on_unverifiable policy
  expired       stale, queue overflow, or the camera moved -> audit log only

The queue is bounded: when full, the lowest-severity, oldest candidate is evicted as expired, so a flood of low-priority
candidates can never delay a high-severity one."""

import asyncio
import base64
import json
import logging
import time

import httpx

from td_contracts import RuleEvent, RuleSpec, RuleVerification
from services.rules.verify_questions import QUESTIONS, load_pack, render
from .llm_gateway import GATEWAY, P0_ALERT_SUMMARY, ollama_runtime
from .settings import OLLAMA_URL, STORAGE

LOG = logging.getLogger(__name__)
QUEUE_MAX = 8
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
HEALTH_TTL_S = 5.0
KEEP_ALIVE = "30m"


def _model() -> str:
    from .chat import settings
    return settings()["ollama_model"]


class Verifier:
    def __init__(self):
        self.items: list[tuple[RuleEvent, RuleSpec]] = []
        self.cancelled: set[str] = set()
        self.cameras_cancelled: dict[str, float] = {}
        self.on_done = None                       # async (event, spec) -> None, set by rule_routes
        self.wake: asyncio.Event | None = None
        self.task: asyncio.Task | None = None
        self.health = (0.0, False)
        self.completed = {"verified": 0, "rejected": 0, "unverifiable": 0, "expired": 0}

    # --- intake ---------------------------------------------------------------------------------------------

    def _ensure_started(self):
        if self.task is None or self.task.done():
            self.wake = asyncio.Event()
            self.task = asyncio.create_task(self._run())
            asyncio.create_task(self.warm())

    @staticmethod
    def _rank(item) -> tuple[int, float]:
        return SEVERITY_RANK[item[1].severity], item[0].ts

    def submit(self, event: RuleEvent, spec: RuleSpec) -> bool:
        self._ensure_started()
        if any(queued.event_id == event.event_id for queued, _ in self.items):
            return True
        self.items.append((event, spec))
        if len(self.items) > QUEUE_MAX:
            victim = max(self.items, key=lambda item: (SEVERITY_RANK[item[1].severity], -item[0].ts))   # lowest severity, then oldest
            self.items.remove(victim)
            asyncio.create_task(self._finish(victim[0], victim[1], "expired", "verification queue full"))
        self.wake.set()
        return True

    def cancel_camera(self, camera_id: str):
        """The camera view moved: nothing queued or in flight for it can still show what the rule saw."""
        self.cameras_cancelled[camera_id] = time.time()
        for event, spec in [item for item in self.items if item[0].camera_id == camera_id]:
            self.items.remove((event, spec))
            asyncio.create_task(self._finish(event, spec, "expired", "camera view changed"))

    # --- model access ---------------------------------------------------------------------------------------

    async def ollama_up(self) -> bool:
        checked, up = self.health
        if time.monotonic() - checked < HEALTH_TTL_S:
            return up
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                up = (await client.get(f"{OLLAMA_URL}/api/tags")).status_code == 200
        except httpx.HTTPError:
            up = False
        self.health = (time.monotonic(), up)
        return up

    async def warm(self):
        """Load the model with the same runtime options as chat so the first real verification does not pay a reload."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                await client.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": _model(), "stream": False, "think": False, "keep_alive": KEEP_ALIVE,
                    "messages": [{"role": "user", "content": "ok"}], "options": {**ollama_runtime(), "num_predict": 1}})
        except httpx.HTTPError:
            pass

    async def _ask(self, rendered, images: list[bytes]) -> dict:
        body = {"model": _model(), "stream": False, "think": False, "keep_alive": KEEP_ALIVE, "format": rendered.schema,
                "messages": [{"role": "user", "content": rendered.prompt,
                              "images": [base64.b64encode(image).decode("ascii") for image in images]}],
                "options": {**ollama_runtime(), "temperature": 0, "num_predict": 160}}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=5)) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json=body)
            response.raise_for_status()
        return json.loads(response.json()["message"]["content"])

    # --- worker ---------------------------------------------------------------------------------------------

    async def _run(self):
        while True:
            if not self.items:
                self.wake.clear()
                await self.wake.wait()
                continue
            item = min(self.items, key=self._rank)
            self.items.remove(item)
            try:
                await self._verify(*item)
            except Exception as exc:                      # a bad candidate must never stop the queue
                LOG.exception("rule verification failed")
                await self._finish(item[0], item[1], "unverifiable", f"verification error: {type(exc).__name__}")

    def _moved_since(self, event: RuleEvent) -> bool:
        return self.cameras_cancelled.get(event.camera_id, 0.0) >= event.ts

    async def _verify(self, event: RuleEvent, spec: RuleSpec):
        policy = spec.verification
        if time.time() - event.ts > policy.max_candidate_age_s:
            return await self._finish(event, spec, "expired", "candidate too old when its turn came")
        if self._moved_since(event):
            return await self._finish(event, spec, "expired", "camera view changed")
        if policy.vlm_question not in QUESTIONS:
            return await self._finish(event, spec, "unverifiable", f"no question template '{policy.vlm_question}'")
        if not await self.ollama_up():
            return await self._finish(event, spec, "unverifiable", "visual check unavailable (model not running)")
        label = next((leaf.object.anchor for leaf in spec.when.leaves() if leaf.object is not None and leaf.object.anchor), "the object")
        object_box = None
        try:
            from . import database as db
            geometry, _ = db.get_geometry(event.camera_id)
            anchor = (geometry or {}).get("anchors", {}).get(label)
            if anchor:
                object_box, label = tuple(anchor["bbox"]), anchor.get("label") or label
        except Exception:
            pass
        try:
            images = await asyncio.to_thread(load_pack, STORAGE / "media" / event.event_id, object_box)
        except (OSError, ValueError, KeyError):
            images = []
        if not images:
            return await self._finish(event, spec, "unverifiable", "no evidence frames were saved")
        rendered = render(policy.vlm_question, label, seed=int(event.ts * 1000) % (2 ** 31))
        started = time.monotonic()
        try:
            async with GATEWAY.slot(priority=P0_ALERT_SUMMARY):
                if self._moved_since(event):
                    return await self._finish(event, spec, "expired", "camera view changed")
                output = await asyncio.wait_for(self._ask(rendered, images), policy.timeout_s)
            outcome = rendered.decode(output)
        except asyncio.TimeoutError:
            return await self._finish(event, spec, "unverifiable", f"visual check timed out after {policy.timeout_s:g} s")
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            return await self._finish(event, spec, "unverifiable", f"visual check gave an unusable answer: {str(exc)[:80]}")
        except httpx.HTTPError as exc:
            self.health = (0.0, False)
            return await self._finish(event, spec, "unverifiable", f"visual check failed: {type(exc).__name__}")
        evidence = [str(fact)[:120] for fact in (output.get("visible_evidence") or [])][:4]
        vlm = {"model": _model(), "outcome": outcome, "answer": str(output.get("answer")), "option_order": list(rendered.order),
               "latency_ms": round((time.monotonic() - started) * 1000, 1), "visible_evidence": evidence}
        if self._moved_since(event):
            return await self._finish(event, spec, "expired", "camera view changed", vlm)
        status = {"positive": "verified", "negative": "rejected", "abstain": "unverifiable"}[outcome]
        reason = None if status == "verified" else ("the visual check could not tell" if status == "unverifiable" else "the visual check disagreed")
        await self._finish(event, spec, status, reason, vlm)

    # --- outcomes -------------------------------------------------------------------------------------------

    async def _finish(self, event: RuleEvent, spec: RuleSpec, status: str, reason: str | None = None, vlm: dict | None = None):
        self.completed[status] += 1
        previous = event.verification
        verification = RuleVerification(status=status, method="vlm", checks=[*previous.checks, *(["visual check: " + f for f in (vlm or {}).get("visible_evidence", [])])],
                                        reason=reason, candidate_ts=previous.candidate_ts,
                                        verified_ts=time.time() if status == "verified" else None, vlm=vlm)
        event = event.model_copy(update={"verification": verification})
        if status in ("verified", "unverifiable") and self.on_done is not None:
            await self.on_done(event, spec)
        else:
            self.audit(event, status, reason)

    @staticmethod
    def audit(event: RuleEvent, status: str, reason: str | None):
        """Candidates that never became alerts stay inspectable: this is how false-alert rates are measured honestly."""
        try:
            path = STORAGE / "logs" / "rule_gate.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"logged_at": time.time(), "event_id": event.event_id, "rule_id": event.rule_id,
                                         "camera_id": event.camera_id, "status": status, "reason": reason,
                                         "verification": event.verification.model_dump(mode="json")}) + "\n")
        except OSError:
            LOG.warning("could not write the rule gate audit log")


VERIFIER = Verifier()
