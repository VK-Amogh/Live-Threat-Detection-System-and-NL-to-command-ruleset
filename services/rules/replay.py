"""Replay a clip into Observation JSONL and a diagnostic overlay video."""

import argparse
import json
import sys
from pathlib import Path

import cv2
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "contracts/src"))
sys.path.insert(0, str(ROOT / "services"))
from rules.detect import CameraDetector


def replay(source: Path, camera_id: str, output: Path):
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    detector = config["detector"]
    adapter = CameraDetector(camera_id, ROOT / detector["weights"], detector["tracker"],
                             float(detector["confidence"]), int(detector["image_size"]))
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Cannot open {source}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, round(source_fps / float(config["camera"]["process_fps"])))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output / "overlay.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), source_fps / stride, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Cannot create overlay video")
    observations = 0
    track_counts = {}
    index = 0
    try:
        with (output / "observations.jsonl").open("w", encoding="utf-8") as stream:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if index % stride == 0:
                    observation = adapter.observe(frame, index, index / source_fps)
                    stream.write(observation.model_dump_json() + "\n")
                    for track in observation.tracks:
                        track_counts[track.track_id] = track_counts.get(track.track_id, 0) + 1
                        x1, y1, x2, y2 = map(int, track.bbox)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.circle(frame, tuple(map(int, track.foot)), 3, (0, 255, 255), -1)
                        cv2.putText(frame, f"{track.cls} #{track.track_id}", (x1, max(18, y1 - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    writer.write(frame)
                    if observations == 0:
                        cv2.imwrite(str(output / "first_frame.jpg"), frame)
                    observations += 1
                index += 1
    finally:
        capture.release()
        writer.release()
    result = {"source": str(source), "observations": observations,
              "tracks_seen": len(track_counts), "tracks_in_at_least_3_frames": sum(n >= 3 for n in track_counts.values()),
              "jsonl": str(output / "observations.jsonl"), "overlay": str(output / "overlay.mp4")}
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--camera-id", default="replay-cam")
    parser.add_argument("--output", type=Path, default=ROOT / "storage/validation/rules")
    args = parser.parse_args()
    print(json.dumps(replay(args.source, args.camera_id, args.output), indent=2))
