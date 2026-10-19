"""Authenticated phone camera ingest, local recording, and per-camera rule state."""

import asyncio
import os
import subprocess
import time
import uuid

import cv2
import imageio_ffmpeg
import numpy as np
import yaml

from td_contracts import CameraGeometry, CameraHealthEvent, RuleEvent, RuleSpec
from services.rules.detect import CameraDetector
from services.rules.evidence import EvidenceBuffer
from services.rules.audit import dropped_clauses
from services.rules.registry import CapabilityRegistry
from services.rules.runtime import RuleRuntime
from . import database as db, pipeline, rule_routes
from .security import now
from .settings import ROOT, STORAGE


SESSIONS: dict[str, "PhoneCameraSession"] = {}
MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_CAMERAS = 4


class PhoneCameraSession:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
        self.queue: asyncio.Queue[tuple[float, bytes]] = asyncio.Queue(maxsize=2)
        self.task: asyncio.Task | None = None
        self.stopping = False
        self.detector: CameraDetector | None = None
        self.rules: list[RuleSpec] = []
        self.intervals: list[float] = []
        self.dropped_frames = 0
        self.last_rules_fetch = 0.0
        self.frame_id = 0
        self.last_frame_ts = 0.0
        self.last_received = 0.0
        self.outage_emitted = False
        self.last_error: str | None = None
        self.threat_error: str | None = None
        self.threat_task: asyncio.Task | None = None
        self.inference_failed_since: float | None = None
        self.inference_health_emitted = False
        self.pending_clips: set[str] = set()
        self.recorder: subprocess.Popen | None = None
        self.recording_id: str | None = None
        self.recording_started = 0.0
        self.recording_size: tuple[int, int] | None = None
        self.last_record_ts: float | None = None
        storage = self.config["storage"]
        self.evidence = EvidenceBuffer(STORAGE / "media", 4.0,
                                       float(storage["pre_roll_s"]), float(storage["post_roll_s"]))
        self.runtime = RuleRuntime(camera_id, self.config, self.evidence, "Single phone camera view")

    def start(self):
        if self.task is None or self.task.done():
            self.stopping = False
            self.task = asyncio.create_task(self.run())

    async def submit(self, data: bytes, capture_ts: str | None = None):
        # A slow GPU never creates an unbounded backlog of stale camera frames.
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                self.dropped_frames += 1
            except asyncio.QueueEmpty:
                pass
        self.last_received = time.time()
        # Dwell and crossing times follow when the phone captured the frame, within two seconds of arrival: a network
        # burst must not squeeze minutes of footage into one second.
        stamp = self.last_received
        try:
            if capture_ts:
                stamp = min(self.last_received, max(self.last_received - 2.0, float(capture_ts) / 1000.0))
        except ValueError:
            pass
        self.queue.put_nowait((max(stamp, self.last_frame_ts + 0.001), data))

    async def stop(self):
        if self.task:
            self.stopping = True
            await self.task
        self.task = None
        await pipeline.release(self._source_id())

    def _ensure_source(self) -> dict | None:
        """The live source incidents attach to. Cameras that join by enrollment or pairing publish through the media hub and
        never go through the legacy register call, so without this the weapon/violence detector never saw their frames."""
        camera = db.get("camera", self.camera_id)
        if camera is None:
            return None
        source = db.get("source", camera.get("_active_source_id") or "")
        if source and source["status"] == "RUNNING":
            return source
        from td_contracts import SourceRecord
        source = SourceRecord(id=uuid.uuid4().hex, filename=camera.get("name", self.camera_id), kind="live",
                              camera_id=self.camera_id, status="RUNNING", created_at=now()).model_dump()
        source["_started_epoch"] = time.time()
        db.put("source", source)
        camera["_active_source_id"] = source["id"]
        db.put("camera", camera)
        return source

    def end_source(self) -> None:
        camera = db.get("camera", self.camera_id) or {}
        source = db.get("source", camera.get("_active_source_id") or "")
        if source and source["status"] == "RUNNING":
            source["status"] = "CANCELED"
            db.put("source", source)

    def _source_id(self):
        camera = db.get("camera", self.camera_id) or {}
        return camera.get("_active_source_id", self.camera_id)

    def _open_recording(self, width: int, height: int, ts: float):
        self.recording_id = uuid.uuid4().hex
        folder = STORAGE / "recordings" / self.camera_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{self.recording_id}.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-y",
                   "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
                   "-r", "4", "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", "ultrafast", "-crf", "27", "-pix_fmt", "yuv420p",
                   "-movflags", "+frag_keyframe+empty_moov", str(target)]
        self.recorder = subprocess.Popen(command, stdin=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.recording_started = ts
        self.recording_size = (width, height)
        self.last_record_ts = None
        db.put("recording", {"id": self.recording_id, "camera_id": self.camera_id,
                             "started_at": now(), "ended_at": None, "status": "RECORDING",
                             "filename": target.name})

    def _close_recording(self):
        if self.recorder:
            try:
                if self.recorder.stdin:
                    self.recorder.stdin.close()
                self.recorder.wait(timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                self.recorder.kill()
                self.recorder.wait()
            recording = db.get("recording", self.recording_id)
            if recording:
                recording["status"] = "READY" if self.recorder.returncode == 0 else "FAILED"
                recording["ended_at"] = now()
                db.put("recording", recording)
            self.recorder = None
            self.recording_id = None
            self.recording_size = None
            self.last_record_ts = None

    def _record(self, frame, ts: float):
        height, width = frame.shape[:2]
        width -= width % 2
        height -= height % 2
        frame = frame[:height, :width]
        if self.recorder is None or ts - self.recording_started >= 300 or self.recording_size != (width, height):
            self._close_recording()
            self._open_recording(width, height, ts)
        try:
            copies = 1 if self.last_record_ts is None else max(1, min(20, round((ts - self.last_record_ts) * 4)))
            raw = frame.tobytes()
            for _ in range(copies):
                self.recorder.stdin.write(raw)
            self.last_record_ts = ts
        except (BrokenPipeError, OSError):
            self._close_recording()
            raise RuntimeError("Phone recording failed; check laptop disk space")

    async def _refresh_rules(self):
        if time.monotonic() - self.last_rules_fetch < 5:
            return
        self.last_rules_fetch = time.monotonic()
        geometry, _ = db.get_geometry(self.camera_id)
        configured = CameraGeometry.model_validate(geometry) if geometry else None
        zones = configured.zones if configured else {}
        lines = configured.lines if configured else {}
        homography = configured.homography if configured else None
        registry = CapabilityRegistry(ROOT, self.detector.classes, set(zones),
                                      set(lines), homography is not None, anchors=configured.anchors if configured else None)
        rows = [row for row in db.list_rules(self.camera_id) if row["status"] == "active"]
        candidates = [(RuleSpec.model_validate_json(row["spec_json"]), row.get("text")) for row in rows]
        roles = configured.zone_roles if configured else {}
        # A stored natural-language rule whose text asks for more than its conditions check is never run.
        self.rules = [rule for rule, text in candidates
                      if registry.assess(rule.entity, rule.when)[2] and not dropped_clauses(text, rule, registry, roles)]
        self.runtime.configure(self.rules, configured)

    async def _rules(self, frame, jpeg: bytes, ts: float):
        try:
            if self.detector is None:
                conf = self.config["detector"]
                self.detector = await asyncio.to_thread(
                    CameraDetector, self.camera_id, ROOT / conf["weights"], conf["tracker"],
                    float(conf["confidence"]), int(conf["image_size"]),
                    float(conf.get("tracker_conf", conf["confidence"])), self.config.get("quality"))
            await self._refresh_rules()
            self.frame_id += 1
            observation = await asyncio.to_thread(self.detector.observe, frame, self.frame_id, ts)
        except Exception:
            self.inference_failed_since = self.inference_failed_since or ts
            if ts - self.inference_failed_since > 5 and not self.inference_health_emitted:
                event = CameraHealthEvent(event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                    f"inference:{self.camera_id}:{self.inference_failed_since:.3f}")),
                    camera_id=self.camera_id, ts=ts, kind="inference_failure",
                    reason="Phone camera rule detector has failed for more than five seconds")
                await rule_routes.ingest_health_event(event, event.event_id)
                self.inference_health_emitted = True
            raise
        self.inference_failed_since = None
        self.inference_health_emitted = False
        events = await asyncio.to_thread(self.runtime.process, frame, observation, ts, jpeg)
        fired_rules = [event.rule_id for event in events]
        for event in events:
            await rule_routes.ingest_rule_event(event, event.event_id)
        for health in self.runtime.drain_health():
            await rule_routes.ingest_health_event(health, health.event_id)
        try:
            from .media.hub import HUB
            HUB.publish_overlay(self.camera_id, observation, fired_rules)
        except Exception:
            pass

    async def _process_threat(self, data: bytes, source: dict, ts: float):
        try:
            result = await asyncio.wait_for(pipeline.process_frame(data, source,
                max(0, round((ts - source.get("_started_epoch", ts)) * 1000))), timeout=3)
            self.threat_error = None
            try:
                from .media.hub import HUB
                HUB.publish_threats(self.camera_id, result)
            except Exception:
                pass
        except Exception as exc:
            self.threat_error = f"Threat detector unavailable: {type(exc).__name__}"

    async def run(self):
        try:
            while not self.stopping:
                try:
                    ts, data = await asyncio.wait_for(self.queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    if self.last_received and time.time() - self.last_received > 5 and not self.outage_emitted:
                        self.outage_emitted = True
                        event = CameraHealthEvent(event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                            f"health:{self.camera_id}:{self.last_frame_ts:.3f}")), camera_id=self.camera_id,
                            ts=time.time(), reason="No phone frames for more than five seconds")
                        try:
                            await rule_routes.ingest_health_event(event, event.event_id)
                        except Exception:
                            self.outage_emitted = False
                    continue
                try:
                    errors: list[str] = []
                    frame = await asyncio.to_thread(cv2.imdecode, np.frombuffer(data, dtype="uint8"), cv2.IMREAD_COLOR)
                    if frame is None:
                        continue
                    preview = STORAGE / "previews" / f"{self.camera_id}.jpg"
                    preview.parent.mkdir(parents=True, exist_ok=True)
                    pending = preview.with_suffix(".tmp")
                    pending.write_bytes(data)
                    os.replace(pending, preview)
                    if self.last_frame_ts and 0 < ts - self.last_frame_ts < 5:
                        self.intervals.append(ts - self.last_frame_ts)
                        del self.intervals[:-30]
                        self.evidence.fps = max(1.0, min(15.0, 1.0 / sorted(self.intervals)[len(self.intervals) // 2]))
                    self.last_frame_ts = ts
                    self.outage_emitted = False
                    camera = db.get("camera", self.camera_id)
                    if camera and not camera.get("is_online"):
                        camera["is_online"] = True
                        db.put("camera", camera)
                    with db.connection() as con:
                        con.execute("""INSERT INTO camera_health(camera_id,last_frame_ts,updated_at) VALUES(?,?,?)
                            ON CONFLICT(camera_id) DO UPDATE SET last_frame_ts=excluded.last_frame_ts,updated_at=excluded.updated_at""",
                                    (self.camera_id, ts, now()))
                    try:
                        self.pending_clips.update(await asyncio.to_thread(self.evidence.append, ts, data))
                    except Exception as exc:
                        errors.append(f"Evidence clip unavailable: {type(exc).__name__}")
                    for event_id in list(self.pending_clips):
                        try:
                            await rule_routes.attach_clip(event_id)
                            self.pending_clips.discard(event_id)
                        except Exception:
                            errors.append("Evidence update pending")
                    try:
                        await self._rules(frame, data, ts)
                    except Exception as exc:
                        errors.append(f"Rule detector unavailable: {type(exc).__name__}")
                    source = self._ensure_source()
                    if source and source["status"] == "RUNNING" and (self.threat_task is None or self.threat_task.done()):
                        self.threat_task = asyncio.create_task(self._process_threat(data, source, ts))
                    self.last_error = "; ".join(errors + ([self.threat_error] if self.threat_error else [])) or None
                except Exception as exc:
                    self.last_error = f"Camera processing failed: {type(exc).__name__}: {str(exc)[:100]}"
                finally:
                    self.queue.task_done()
        finally:
            if self.threat_task and not self.threat_task.done():
                await self.threat_task
            await asyncio.to_thread(self._close_recording)


async def shutdown():
    for camera_id, session in list(SESSIONS.items()):
        await session.stop()
        SESSIONS.pop(camera_id, None)
