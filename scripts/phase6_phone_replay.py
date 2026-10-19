"""Replay a recorded detector track into the rule activated on a test phone.

Run against an isolated SafeSpace API with SAFESPACE_STORAGE set. This is a
functional client-delivery probe, not a camera accuracy benchmark.
"""

import json
import os
from pathlib import Path
import sys
import time
import uuid

import cv2
import httpx
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import Observation, RuleEvent, RuleSpec
from services.rules.engine import RuleEngine
from services.rules.state import Fire, RuleState


def main():
    load_dotenv(ROOT / ".env")
    storage = Path(os.environ["SAFESPACE_STORAGE"])
    camera_id = (storage / "camera_id.txt").read_text(encoding="utf-8").strip()
    token = os.environ["INTERNAL_SERVICE_TOKEN"]
    client = httpx.Client(base_url=os.getenv("SAFESPACE_API_URL", "http://127.0.0.1:8000"),
                          headers={"Authorization": f"Bearer {token}"}, timeout=30)
    response = client.get("/api/v1/internal/rules", params={"camera_id": camera_id})
    response.raise_for_status()
    payload = response.json()
    rules = [RuleSpec.model_validate(row["spec"]) for row in payload["rules"]]
    if len(rules) != 1 or rules[0].status != "active":
        raise RuntimeError("Expected exactly one phone-activated rule")
    rule = rules[0]
    if rule.entity != "person" or {leaf.type for leaf in rule.when.leaves()} != {"entity_present"}:
        raise RuntimeError("The phone rule does not match the person replay fixture")
    engine = RuleEngine({}, {})
    state = RuleState()
    fixture = ROOT / "tests/fixtures/rules/observations.jsonl"
    observations = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]
    start = time.time() + 0.2
    fires = []
    result = None
    for row in observations:
        offset = row["ts"]
        time.sleep(max(0, start + offset - time.time()))
        row["camera_id"] = camera_id
        row["ts"] = start + offset
        row["tracks"] = [track for track in row["tracks"] if track["track_id"] == 1]
        for track in row["tracks"]:
            track["first_seen"] += start
            track["last_seen"] += start
        observation = Observation.model_validate(row)
        for outcome in engine.evaluate(rule, observation, state):
            if isinstance(outcome, Fire):
                fires.append(outcome)
                event_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                    f"{rule.rule_id}:{rule.version}:{camera_id}:{outcome.tracks}:{outcome.episode_start:.3f}"))
                folder = storage / "media" / event_id
                folder.mkdir(parents=True, exist_ok=True)
                clip = cv2.VideoCapture(str(ROOT / "TestVideos/v001_converted 3.avi"))
                clip.set(cv2.CAP_PROP_POS_MSEC, offset * 1000)
                ok, frame = clip.read()
                clip.release()
                if not ok or not cv2.imwrite(str(folder / "frame.jpg"), frame):
                    raise RuntimeError("Could not write replay keyframe")
                track = observation.tracks[0]
                event = RuleEvent(event_id=event_id, camera_id=camera_id,
                    rule_id=rule.rule_id, rule_version=rule.version,
                    ts=outcome.ts, episode_start=outcome.episode_start,
                    tracks=list(outcome.tracks), model_versions=observation.model_versions,
                    confidence=outcome.confidence, uncertainty="Recorded AVI replay",
                    evidence_bbox=tuple(round(v) for v in track.bbox))
                posted_at = time.time()
                headers = {"Idempotency-Key": event_id}
                first = client.post("/api/v1/internal/rule-events",
                    json=event.model_dump(mode="json"), headers=headers)
                first.raise_for_status()
                repeat = client.post("/api/v1/internal/rule-events",
                    json=event.model_dump(mode="json"), headers=headers)
                repeat.raise_for_status()
                result = {"camera_id": camera_id, "rule_id": rule.rule_id,
                    "rule_version": rule.version, "fixture": "TestVideos/v001_converted 3.avi",
                    "track_id": track.track_id, "episode_start_epoch": outcome.episode_start,
                    "event_start_epoch": outcome.ts, "api_post_epoch": posted_at,
                    "api_ack_epoch": time.time(), "event_id": event_id,
                    "change_seq": first.json()["event"]["change_seq"],
                    "first_created": first.json()["created"],
                    "repeat_created": repeat.json()["created"]}
    if len(fires) != 1 or result is None:
        raise RuntimeError(f"Expected one event from the recorded track, got {len(fires)}")
    source = cv2.VideoCapture(str(ROOT / "TestVideos/v001_converted 3.avi"))
    fps = source.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(source.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
    clip_path = storage / "media" / result["event_id"] / "clip.mp4"
    writer = cv2.VideoWriter(str(clip_path), cv2.VideoWriter_fourcc(*"mp4v"), fps,
                             (width, height))
    if not writer.isOpened():
        source.release()
        raise RuntimeError("Could not write replay clip")
    while True:
        ok, frame = source.read()
        if not ok:
            break
        writer.write(frame)
    source.release()
    writer.release()
    attached = client.post(f"/api/v1/internal/events/{result['event_id']}/clip")
    attached.raise_for_status()
    result["clip_change_seq"] = attached.json()["event"]["change_seq"]
    result["clip_update_created"] = attached.json()["created"]
    destination = storage / "phone_replay_result.json"
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (storage / "phone_replay_results.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(result) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
