"""Compile, activate, replay and persist the documented driveway rule fixture."""

import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid
from datetime import datetime

from dateutil.zoneinfo import get_zonefile_instance
from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src"), str(ROOT)]
from app import database, main, pipeline, rule_routes
from td_contracts import Observation, RuleSpec
from services.rules.engine import RuleEngine
from services.rules.state import Fire, RuleState


def main_demo():
    os.environ["INITIAL_ADMIN_USERNAME"] = "fixture@example.test"
    os.environ["INITIAL_ADMIN_PASSWORD"] = "fixture-only-password"
    with tempfile.TemporaryDirectory(prefix="safespace-driveway-") as temp:
        root = Path(temp)
        (root / "media").mkdir()
        (root / "uploads").mkdir()
        database.DB_PATH = root / "demo.db"
        main.STORAGE = pipeline.STORAGE = rule_routes.STORAGE = root
        rule_routes.INTERNAL_TOKEN = "fixture-worker-key"
        main.ATTEMPTS.clear()
        with TestClient(main.app) as client:
            login = client.post("/api/v1/auth/login", json={"username": "fixture@example.test",
                "password": "fixture-only-password", "device_name": "demo", "client_type": "web"})
            login.raise_for_status()
            camera = client.post("/api/v1/cameras", json={"name": "Driveway", "source_type": "WEBCAM",
                "connection_uri": "0"}).json()
            camera_id = camera["id"]
            geometry = {"snapshot_width": 640, "snapshot_height": 480,
                        "zones": {"driveway": [[20, 20], [200, 20], [200, 200], [20, 200]]},
                        "lines": {}, "homography": None}
            response = client.put(f"/api/v1/cameras/{camera_id}/geometry", json=geometry)
            response.raise_for_status()
            request = "Alert me when a person stays in the driveway for 3 seconds between midnight and 5 a.m."
            compiled = client.post("/api/v1/rules/compile", json={"camera_id": camera_id, "text": request})
            compiled.raise_for_status()
            draft = compiled.json()
            spec = RuleSpec.model_validate(draft["spec"])
            assert spec.entity == "person" and {node.type for node in spec.when.leaves()} == {
                "in_zone", "dwell_at_least", "time_window"}
            assert draft["support_level"] == "SUPPORTED" and draft["can_activate"]
            active = client.post(f"/api/v1/rules/{spec.rule_id}/activate", json={
                "expected_version": spec.version, "confirmed_readback_hash": draft["readback_hash"]})
            active.raise_for_status()
            rule = RuleSpec.model_validate(active.json()["spec"])
            engine = RuleEngine({"driveway": geometry["zones"]["driveway"]}, {})
            state = RuleState()
            tz = get_zonefile_instance().get("Asia/Kolkata")
            start = datetime(2026, 10, 16, 2, 0, tzinfo=tz).timestamp()
            fires = []
            for second in range(5):
                ts = start + second
                observation = Observation(camera_id=camera_id, ts=ts, frame_id=second + 1,
                    tracks=[{"track_id": 12, "cls": "person", "conf": .87,
                             "bbox": [80, 60, 120, 100], "foot": [100, 100],
                             "velocity": [0, 0], "first_seen": start, "last_seen": ts}],
                    model_versions={"detector": "fixture@yolo26n", "tracker": "bytetrack"})
                fires.extend(result for result in engine.evaluate(rule, observation, state) if isinstance(result, Fire))
            assert len(fires) == 1 and fires[0].ts == start + 3
            fire = fires[0]
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                f"{rule.rule_id}:{rule.version}:{camera_id}:{fire.tracks}:{fire.episode_start:.3f}"))
            folder = root / "media" / event_id
            folder.mkdir()
            pixels = io.BytesIO()
            Image.new("RGB", (640, 480), "grey").save(pixels, format="JPEG")
            (folder / "frame.jpg").write_bytes(pixels.getvalue())
            payload = {"event_id": event_id, "camera_id": camera_id, "rule_id": rule.rule_id,
                       "rule_version": rule.version, "ts": fire.ts, "episode_start": fire.episode_start,
                       "tracks": list(fire.tracks), "model_versions": observation.model_versions,
                       "confidence": fire.confidence, "uncertainty": "Single camera angle",
                       "needs_visual_review": False, "evidence_bbox": [80, 60, 120, 100]}
            headers = {"Authorization": "Bearer fixture-worker-key", "Idempotency-Key": event_id}
            first = client.post("/api/v1/internal/rule-events", json=payload, headers=headers)
            first.raise_for_status()
            repeated = client.post("/api/v1/internal/rule-events", json=payload, headers=headers)
            repeated.raise_for_status()
            assert first.json()["created"] and not repeated.json()["created"]
            sample = ROOT / "storage/validation/rules/review_clips/v001_converted_3_0.mp4"
            shutil.copyfile(sample, folder / "clip.mp4")
            clip = client.post(f"/api/v1/internal/events/{event_id}/clip", headers=headers)
            clip.raise_for_status()
            changes = client.get("/api/v1/changes?after=0").json()["items"]
            assert len(changes) == 2 and changes[0]["id"] == changes[1]["id"] == event_id
            result = {"request": request, "compile": {"entity": spec.entity,
                      "when": spec.when.model_dump(mode="json", by_alias=True, exclude_none=True),
                      "support_level": draft["support_level"], "status": spec.status,
                      "readback": draft["readback"]},
                      "activation": {"rule_version": rule.version, "status": rule.status},
                      "replay": {"track_id": 12, "seconds_until_fire": fire.ts - start,
                                 "events_fired": len(fires)},
                      "persistence": {"event_id": event_id, "initial_change_seq": changes[0]["change_seq"],
                                      "clip_change_seq": changes[1]["change_seq"],
                                      "duplicate_created": repeated.json()["created"]}}
            destination = ROOT / "tests/example_driveway_output.json"
            destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main_demo()
