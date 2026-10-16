"""One process per camera: capture once, preserve legacy alerts, evaluate rules."""

import argparse
import os
from pathlib import Path
import signal
import threading
import time
import uuid

import cv2
import httpx
import yaml
from dotenv import load_dotenv

from td_contracts import CameraGeometry, CameraHealthEvent, RuleEvent, RuleSpec
from .capture import frames
from .detect import CameraDetector
from .engine import RuleEngine
from .evidence import EvidenceBuffer
from .outbox import RuleOutbox
from .registry import CapabilityRegistry
from .state import Fire, RuleState


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class CameraWorker:
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
        self.api = os.getenv("SAFESPACE_API_URL", "http://127.0.0.1:8000").rstrip("/")
        self.token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
        if not self.token:
            raise RuntimeError("INTERNAL_SERVICE_TOKEN is required")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.stop = threading.Event()
        self.rules: list[RuleSpec] = []
        self.states: dict[tuple[str, int], RuleState] = {}
        self.engine = RuleEngine({}, {})
        self.last_rules_fetch = 0.0
        self.last_frame_ts = time.time()
        self.outage_emitted = False
        self.disconnected = False
        self.source = self._source()
        detector = self.config["detector"]
        self.detector = CameraDetector(camera_id, ROOT / detector["weights"], detector["tracker"],
                                       float(detector["confidence"]), int(detector["image_size"]))
        storage = self.config["storage"]
        self.evidence = EvidenceBuffer(ROOT / "storage/media", float(self.config["camera"]["process_fps"]),
                                       float(storage["pre_roll_s"]), float(storage["post_roll_s"]))
        self.outbox = RuleOutbox(ROOT / "storage/outbox" / f"rules_{camera_id}.db", self.api, self.token)
        self.sender = threading.Thread(target=self.outbox.run, daemon=True)

    def _source(self):
        with httpx.Client(timeout=10) as client:
            response = client.get(self.api + "/api/v1/internal/cameras", headers=self.headers)
            response.raise_for_status()
        for camera in response.json():
            if camera["id"] == self.camera_id:
                return camera["source"]
        raise RuntimeError("Camera is not active")

    def refresh_rules(self, client: httpx.Client):
        if time.monotonic() - self.last_rules_fetch < 5:
            return
        self.last_rules_fetch = time.monotonic()
        response = client.get(self.api + "/api/v1/internal/rules", params={"camera_id": self.camera_id}, headers=self.headers)
        response.raise_for_status()
        payload = response.json()
        geometry = payload["geometry"]
        if geometry:
            configured = CameraGeometry.model_validate(geometry)
            self.engine = RuleEngine(configured.zones, configured.lines, configured.homography)
        else:
            self.engine = RuleEngine({}, {})
        registry = CapabilityRegistry(ROOT, self.detector.classes, set(geometry["zones"]) if geometry else set(),
                                      set(geometry["lines"]) if geometry else set(),
                                      bool(geometry and geometry["homography"]))
        candidates = [RuleSpec.model_validate(row["spec"]) for row in payload["rules"]]
        self.rules = [rule for rule in candidates if registry.assess(rule.entity, rule.when)[2]]
        keys = {(rule.rule_id, rule.version) for rule in self.rules}
        self.states = {key: value for key, value in self.states.items() if key in keys}

    def _legacy(self, client: httpx.Client, jpeg: bytes, ts: float):
        response = client.post(self.api + "/api/v1/internal/live-frame", headers=self.headers,
                               data={"camera_id": self.camera_id, "frame_ts": str(ts)},
                               files={"file": ("frame.jpg", jpeg, "image/jpeg")})
        response.raise_for_status()
        return response.json()["created_event_ids"]

    def run(self):
        self.sender.start()
        last_process = 0.0
        interval = 1 / float(self.config["camera"]["process_fps"])
        with httpx.Client(timeout=60) as client:
            for frame_id, ts, frame in frames(self.source, self.stop.is_set):
                if frame is None:
                    self.disconnected = True
                    if ts - self.last_frame_ts > 5 and not self.outage_emitted:
                        self.outage_emitted = True
                        event = CameraHealthEvent(
                            event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"health:{self.camera_id}:{self.last_frame_ts:.3f}")),
                            camera_id=self.camera_id, ts=ts, reason="No frames for more than five seconds")
                        self.outbox.enqueue_health(event)
                    continue
                if time.monotonic() - last_process < interval:
                    continue
                if self.disconnected:
                    detector = self.config["detector"]
                    self.detector = CameraDetector(self.camera_id, ROOT / detector["weights"], detector["tracker"],
                                                   float(detector["confidence"]), int(detector["image_size"]))
                    self.disconnected = False
                last_process = time.monotonic()
                self.last_frame_ts = ts
                self.outage_emitted = False
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    continue
                jpeg = encoded.tobytes()
                for event_id in self.evidence.append(ts, jpeg):
                    self.outbox.enqueue_clip(event_id)
                try:
                    for event_id in self._legacy(client, jpeg, ts):
                        self.evidence.start(event_id, ts, jpeg)
                except (httpx.HTTPError, KeyError):
                    # Existing threat inference may be offline; programmable detection continues.
                    pass
                try:
                    self.refresh_rules(client)
                except (httpx.HTTPError, ValueError):
                    pass
                observation = self.detector.observe(frame, frame_id, ts)
                for rule in self.rules:
                    state = self.states.setdefault((rule.rule_id, rule.version), RuleState())
                    for outcome in self.engine.evaluate(rule, observation, state):
                        if not isinstance(outcome, Fire):
                            continue
                        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                            f"{rule.rule_id}:{rule.version}:{self.camera_id}:{outcome.tracks}:{outcome.episode_start:.3f}"))
                        self.evidence.start(event_id, ts, jpeg)
                        relevant = [track.bbox for track in observation.tracks if track.track_id in outcome.tracks]
                        bounds = (round(min(box[0] for box in relevant)), round(min(box[1] for box in relevant)),
                                  round(max(box[2] for box in relevant)), round(max(box[3] for box in relevant))) if relevant else None
                        event = RuleEvent(event_id=event_id, camera_id=self.camera_id,
                                          rule_id=rule.rule_id, rule_version=rule.version,
                                          ts=ts, episode_start=outcome.episode_start, tracks=list(outcome.tracks),
                                          model_versions=observation.model_versions, confidence=outcome.confidence,
                                          uncertainty="Single camera angle; detector confidence is not a probability of intent.",
                                          needs_visual_review=rule.needs_visual_review, evidence_bbox=bounds)
                        self.outbox.enqueue_event(event)
        self.outbox.stopped.set()
        self.sender.join(timeout=5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-id", required=True)
    args = parser.parse_args()
    worker = CameraWorker(args.camera_id)
    signal.signal(signal.SIGTERM, lambda *_: worker.stop.set())
    signal.signal(signal.SIGINT, lambda *_: worker.stop.set())
    worker.run()


if __name__ == "__main__":
    main()
