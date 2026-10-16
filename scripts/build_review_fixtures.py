"""Derive short review probes from repository AVIs without treating them as new footage."""

import json
from pathlib import Path
import sys

import cv2
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import RuleSpec, RuleWhen
from services.rules.detect import CameraDetector
from services.rules.engine import RuleEngine
from services.rules.state import Fire, RuleState


def main():
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["detector"]
    output = ROOT / "storage/validation/rules/review_clips"
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for source in sorted((ROOT / "TestVideos").glob("*.avi")):
        probe = cv2.VideoCapture(str(source))
        fps = probe.get(cv2.CAP_PROP_FPS) or 30
        total = round(probe.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps
        probe.release()
        for segment in range(6):
            length = min(2.6, duration)
            start = max(0, (duration - length) * segment / 5)
            destination = output / f"{source.stem.replace(' ', '_')}_{segment}.mp4"
            capture = cv2.VideoCapture(str(source))
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(start * fps))
            ok, first = capture.read()
            if not ok:
                capture.release()
                continue
            height, width = first.shape[:2]
            writer = cv2.VideoWriter(str(destination), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            detector = CameraDetector("probe", ROOT / config["weights"], config["tracker"],
                                      float(config["confidence"]), int(config["image_size"]))
            rule = RuleSpec(rule_id="r_fixture", camera_id="probe", version=1, name="Person visible",
                            entity="person", when=RuleWhen(type="entity_present"),
                            support_level="SUPPORTED", status="active")
            state = RuleState()
            fires = []
            frames = round(length * fps)
            try:
                for index in range(frames):
                    frame = first if index == 0 else capture.read()[1]
                    if frame is None:
                        break
                    writer.write(frame)
                    if index % max(1, round(fps / 5)) == 0:
                        observation = detector.observe(frame, index + 1, start + index / fps)
                        fires.extend(item for item in RuleEngine({}, {}).evaluate(rule, observation, state)
                                     if isinstance(item, Fire))
            finally:
                writer.release()
                capture.release()
            manifest.append({"clip": str(destination.relative_to(ROOT)), "source": source.name,
                             "source_offset_s": round(start, 2), "rule_fired": bool(fires)})
            print(f"{source.name} segment {segment}: {'FLAGGED' if fires else 'no rule fire'}", flush=True)
    path = ROOT / "tests/reasoner_fixture_manifest.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Flagged: {sum(item['rule_fired'] for item in manifest)}/{len(manifest)}")


if __name__ == "__main__":
    main()
