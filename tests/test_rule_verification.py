"""Verification queue behaviour and how verified / unverifiable events become incidents. The model is mocked."""

import asyncio
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src"), str(ROOT)]
from app import database, main, pipeline, rule_routes, rule_verify
from td_contracts import RuleEvent, RuleSpec, RuleVerification
from services.rules.evidence import EvidenceBuffer


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setattr(pipeline, "STORAGE", tmp_path)
    monkeypatch.setattr(rule_routes, "STORAGE", tmp_path)
    monkeypatch.setattr(rule_verify, "STORAGE", tmp_path)
    monkeypatch.setattr(rule_routes, "INTERNAL_TOKEN", "worker-secret")
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin@gmail.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin123")
    (tmp_path / "media").mkdir()
    (tmp_path / "uploads").mkdir()
    main.ATTEMPTS.clear()
    main.TICKETS.clear()
    with TestClient(main.app) as api:
        yield api


def frame_bytes(shade=120):
    return cv2.imencode(".jpg", np.full((120, 160, 3), shade, dtype="uint8"))[1].tobytes()


def spec(severity="medium", on_unverifiable="hold_for_review", timeout_s=8.0, method="vlm"):
    return RuleSpec.model_validate({
        "rule_id": "r1", "camera_id": "cam", "version": 1, "name": "Sits on chair", "entity": "person", "severity": severity,
        "when": {"type": "in_zone", "zone": "z"}, "support_level": "SUPPORTED", "status": "active",
        "verification": {"method": method, "vlm_question": "sits_on", "timeout_s": timeout_s, "on_unverifiable": on_unverifiable}})


def candidate(media, event_id, ts=None, camera="cam"):
    ts = time.time() if ts is None else ts
    folder = media / "media" / event_id
    evidence = EvidenceBuffer(media / "media", 5, 2, 0.4)
    evidence.write_pack(event_id, [(ts - 0.4 + i * 0.2, frame_bytes(100 + i), (20, 20, 80, 100)) for i in range(4)])
    (folder / "frame.jpg").write_bytes(frame_bytes())
    return RuleEvent(event_id=event_id, camera_id=camera, rule_id="r1", rule_version=1, ts=ts, episode_start=ts - 1, tracks=[1],
                     model_versions={"detector": "t"}, confidence=.8, uncertainty="fixture",
                     verification=RuleVerification(status="candidate", method="vlm", checks=["held 1.0 s"], candidate_ts=ts))


class Harness:
    """A verifier whose model, health and storage are fakes."""

    def __init__(self, tmp_path, answer="positive", delay=0.0, up=True):
        self.published, self.verifier = [], rule_verify.Verifier()
        self.answer, self.delay, self.up, self.release = answer, delay, up, None
        self.verifier.on_done = self.done
        self.verifier.ollama_up = self.fake_up
        self.verifier._ask = self.fake_ask
        self.verifier.warm = self.fake_warm

    async def done(self, event, spec):
        self.published.append(event)

    async def fake_up(self):
        return self.up

    async def fake_warm(self):
        return None

    async def fake_ask(self, rendered, images):
        assert 1 <= len(images) <= 3
        if self.release is not None:
            await self.release.wait()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.answer == "garbage":
            return {"answer": "Z"}
        letter = next(l for l, kind in rendered.letters.items() if kind == self.answer)
        return {"answer": letter, "visible_evidence": ["a person is seated"]}

    async def settle(self, count=1, seconds=3.0):
        deadline = time.monotonic() + seconds
        while sum(self.verifier.completed.values()) < count and time.monotonic() < deadline:
            await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def fake_model_and_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(rule_verify, "_model", lambda: "gemma-test")
    monkeypatch.setattr(rule_verify, "STORAGE", tmp_path)


def run(coro):
    return asyncio.run(coro)


def test_positive_answer_verifies_and_records_the_visual_check(tmp_path):
    async def scenario():
        harness = Harness(tmp_path)
        harness.verifier.submit(candidate(tmp_path, "e1"), spec())
        await harness.settle()
        return harness
    harness = run(scenario())
    event = harness.published[0]
    assert event.verification.status == "verified" and event.verification.verified_ts is not None
    assert event.verification.vlm["model"] == "gemma-test" and event.verification.vlm["outcome"] == "positive"
    assert event.verification.vlm["latency_ms"] >= 0 and any("a person is seated" in c for c in event.verification.checks)


def test_negative_answer_is_audited_and_never_published(tmp_path):
    async def scenario():
        harness = Harness(tmp_path, answer="negative")
        harness.verifier.submit(candidate(tmp_path, "e2"), spec())
        await harness.settle()
        return harness
    harness = run(scenario())
    assert harness.published == [] and harness.verifier.completed["rejected"] == 1
    logged = [json.loads(line) for line in (tmp_path / "logs/rule_gate.jsonl").read_text().splitlines()]
    assert logged[0]["status"] == "rejected" and logged[0]["event_id"] == "e2"


@pytest.mark.parametrize("scenario_kwargs, reason", [
    ({"answer": "abstain"}, "could not tell"),
    ({"answer": "garbage"}, "unusable answer"),
    ({"delay": 5.0}, "timed out"),
    ({"up": False}, "unavailable"),
])
def test_anything_short_of_a_clear_yes_is_unverifiable_never_verified(tmp_path, scenario_kwargs, reason):
    async def scenario():
        harness = Harness(tmp_path, **scenario_kwargs)
        harness.verifier.submit(candidate(tmp_path, "e3"), spec(timeout_s=0.2))
        await harness.settle()
        return harness
    harness = run(scenario())
    assert [e.verification.status for e in harness.published] == ["unverifiable"]
    assert reason in harness.published[0].verification.reason


def test_missing_evidence_is_unverifiable(tmp_path):
    async def scenario():
        harness = Harness(tmp_path)
        event = candidate(tmp_path, "e4")
        (tmp_path / "media/e4/pack.json").unlink()
        harness.verifier.submit(event, spec())
        await harness.settle()
        return harness
    harness = run(scenario())
    assert harness.published[0].verification.status == "unverifiable" and "evidence" in harness.published[0].verification.reason


def test_stale_candidates_expire_instead_of_alerting_late(tmp_path):
    async def scenario():
        harness = Harness(tmp_path)
        harness.verifier.submit(candidate(tmp_path, "e5", ts=time.time() - 60), spec())
        await harness.settle()
        return harness
    harness = run(scenario())
    assert harness.published == [] and harness.verifier.completed["expired"] == 1


def test_a_full_queue_evicts_the_lowest_severity_oldest_candidate_first(tmp_path):
    async def scenario():
        harness = Harness(tmp_path)
        harness.release = asyncio.Event()                       # hold the first candidate inside the model call
        now = time.time()
        harness.verifier.submit(candidate(tmp_path, "busy", ts=now), spec("medium"))
        await asyncio.sleep(0.2)
        for index in range(rule_verify.QUEUE_MAX):
            harness.verifier.submit(candidate(tmp_path, f"low{index}", ts=now + index * 0.01), spec("low"))
        harness.verifier.submit(candidate(tmp_path, "urgent", ts=now + 1), spec("critical"))
        await asyncio.sleep(0.1)
        queued = [event.event_id for event, _ in harness.verifier.items]
        expired = harness.verifier.completed["expired"]
        harness.release.set()
        await harness.settle(count=1 + rule_verify.QUEUE_MAX, seconds=5)
        return harness, queued, expired
    harness, queued, expired = run(scenario())
    assert len(queued) <= rule_verify.QUEUE_MAX and "urgent" in queued and "low0" not in queued and expired >= 1
    order = [event.event_id for event in harness.published]
    assert order.index("urgent") < order.index("low1")          # the critical candidate is served ahead of older low ones


def test_a_moved_camera_expires_what_is_queued_for_it(tmp_path):
    async def scenario():
        harness = Harness(tmp_path)
        harness.release = asyncio.Event()
        now = time.time()
        harness.verifier.submit(candidate(tmp_path, "busy2", ts=now), spec())
        await asyncio.sleep(0.2)
        harness.verifier.submit(candidate(tmp_path, "waiting", ts=now + 0.01), spec())
        harness.verifier.cancel_camera("cam")
        harness.release.set()
        await harness.settle(count=2, seconds=5)
        return harness
    harness = run(scenario())
    assert harness.published == [] and harness.verifier.completed["expired"] == 2


# --- how a verification outcome becomes (or does not become) an incident ----------------------------------------------------

def publish(client, tmp_path, status, *, on_unverifiable="hold_for_review", severity="high", method="vlm", event_id="p1"):
    camera = client.post("/api/v1/auth/login", json={"username": "admin@gmail.com", "password": "admin123", "device_name": "t", "client_type": "web"})
    assert camera.status_code == 200
    created = client.post("/api/v1/cameras", json={"name": "Cam", "source_type": "WEBCAM", "connection_uri": "0"}).json()
    event = candidate(tmp_path, event_id, camera=created["id"])
    verification = event.verification.model_copy(update={"status": status, "method": method, "reason": "cannot tell" if status == "unverifiable" else None,
                                                         "verified_ts": time.time() if status == "verified" else None})
    event = event.model_copy(update={"verification": verification})
    return asyncio.run(rule_routes.publish_rule_event(event, spec(severity, on_unverifiable, method=method))), event


def test_verified_visual_event_is_an_ai_verified_alert_with_the_rules_severity(client, tmp_path):
    result, event = publish(client, tmp_path, "verified")
    saved = result["event"]
    assert result["created"] and saved["category"]["key"] == "RULE_ALERT" and saved["severity"] == "HIGH"
    assert saved["verified_by"] == "AI" and saved["status"] == "DETECTED" and saved["verification"]["status"] == "verified"


def test_held_unverifiable_event_stays_quiet_on_the_phone(client, tmp_path):
    result, _ = publish(client, tmp_path, "unverifiable")
    saved = result["event"]
    assert saved["category"]["key"] == "RULE_UNVERIFIED" and saved["status"] == "NEEDS_REVIEW" and saved["severity"] == "LOW"
    assert "cannot tell" in saved["status_reason"]
    # held for review must stay findable: it is a different category, not a hidden one
    listed = {event["id"]: event for event in client.get("/api/v1/events").json()}
    assert listed[saved["id"]]["category"]["key"] == "RULE_UNVERIFIED" and listed[saved["id"]]["status"] == "NEEDS_REVIEW"
    assert listed[saved["id"]]["verification"]["status"] == "unverifiable"


def test_a_moved_camera_is_reported_and_cancels_pending_checks(client, tmp_path):
    from td_contracts import CameraHealthEvent
    client.post("/api/v1/auth/login", json={"username": "admin@gmail.com", "password": "admin123", "device_name": "t", "client_type": "web"})
    created = client.post("/api/v1/cameras", json={"name": "Cam", "source_type": "WEBCAM", "connection_uri": "0"}).json()
    health = CameraHealthEvent(event_id="moved-1", camera_id=created["id"], ts=time.time(), kind="camera_moved", reason="Camera view changed (view shifted 9.0%)")

    async def report():
        return await rule_routes.ingest_health_event(health, "moved-1")

    asyncio.run(report())
    listed = {event["id"]: event for event in client.get("/api/v1/events").json()}
    assert listed["moved-1"]["category"] == {"key": "CAMERA_MOVED", "label": "Camera view changed"}
    assert rule_verify.VERIFIER.cameras_cancelled[created["id"]] > 0


def test_send_unverified_is_still_a_rule_alert_but_marked(client, tmp_path):
    result, _ = publish(client, tmp_path, "unverifiable", on_unverifiable="send_unverified")
    saved = result["event"]
    assert saved["category"]["key"] == "RULE_ALERT" and saved["status"] == "NEEDS_REVIEW" and saved["status_reason"].startswith("Unverified")
    assert saved["severity"] == "HIGH"


def test_dropped_and_rejected_candidates_create_nothing(client, tmp_path):
    result, _ = publish(client, tmp_path, "unverifiable", on_unverifiable="drop", event_id="p3")
    assert result == {"event": None, "created": False}
    result, _ = publish(client, tmp_path, "rejected", event_id="p4")
    assert result == {"event": None, "created": False}
    assert client.get("/api/v1/events").json() == []


def test_a_candidate_cannot_be_posted_for_a_rule_without_a_visual_policy(client, tmp_path, monkeypatch):
    client.post("/api/v1/auth/login", json={"username": "admin@gmail.com", "password": "admin123", "device_name": "t", "client_type": "web"})
    created = client.post("/api/v1/cameras", json={"name": "Cam", "source_type": "WEBCAM", "connection_uri": "0"}).json()
    plain = RuleSpec.model_validate({"rule_id": "r1", "camera_id": created["id"], "version": 1, "name": "x", "entity": "person",
                                     "when": {"type": "in_zone", "zone": "z"}, "support_level": "SUPPORTED", "status": "active"})
    database.put_rule({"id": "r1", "camera_id": created["id"], "text": "x", "spec_json": plain.model_dump_json(by_alias=True), "readback": "x",
                       "readback_hash": "a" * 64, "can_activate": 1, "status": "active", "version": 1, "updated_at": "2026-10-17T00:00:00Z"})
    event = candidate(tmp_path, "p5", camera=created["id"])
    response = client.post("/api/v1/internal/rule-events", content=event.model_dump_json(), headers={
        "Authorization": "Bearer worker-secret", "Idempotency-Key": "p5", "Content-Type": "application/json"})
    assert response.status_code == 422 and "visual verification policy" in response.json()["detail"]
