"""Replay a recorded clip through the real rule runtime offline and write the alerts it would have produced.

Timestamps are deterministic (start epoch + frame index / source fps), so two runs over the same clip, rules, geometry and
weights give identical alerts and a change can be compared with the baseline. Visual-check (vlm) rules are recorded as
`candidate` alerts: the Gemma check belongs to the API process, so offline results are the pre-verification rate; the
verified rate comes from storage/logs/rule_gate.jsonl of a live or API-driven run.

  python scripts/eval/rules_replay.py --clip storage/recordings/cam_x/2026-10-16/a.mp4 --camera-id cam_x \
      --rules rules.json --geometry geometry.json --out storage/eval/rules/baseline

`rules.json` is a list of RuleSpec objects (status "active"); `geometry.json` is a CameraGeometry (optional).
Writes <out>/<clip stem>.alerts.json with the alerts, track-quality counts and per-stage timings.
"""

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import CameraGeometry, RuleSpec
from services.rules.evidence import EvidenceBuffer
from services.rules.runtime import RuleRuntime, build_detector

START_EPOCH = 1_760_000_000.0


class ReplayEvidence(EvidenceBuffer):
    """Same interface, but never transcodes clips: a replay needs the frames, not the video files."""

    def _write_clip(self, event_id, pieces):
        return None


def replay(clip: Path, camera_id: str, rules: list[RuleSpec], geometry: CameraGeometry | None, fps: float) -> dict:
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    capture = cv2.VideoCapture(str(clip))
    if not capture.isOpened():
        raise SystemExit(f"cannot open {clip}")
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    stride = max(1, round(source_fps / fps))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    detector = build_detector(camera_id, config)
    with tempfile.TemporaryDirectory() as scratch:
        evidence = ReplayEvidence(Path(scratch), fps, float(config["storage"]["pre_roll_s"]), 0.0)
        runtime = RuleRuntime(camera_id, config, evidence, "Replay")
        runtime.configure(rules, geometry)
        alerts, flagged, timings, index = [], 0, {"detect_ms": [], "runtime_ms": []}, 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            index += 1
            if (index - 1) % stride:
                continue
            ts = START_EPOCH + (index - 1) / source_fps
            jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
            evidence.append(ts, jpeg)
            started = time.perf_counter()
            observation = detector.observe(frame, index, ts)
            middle = time.perf_counter()
            flagged += sum(1 for track in observation.tracks if track.flags)
            for event in runtime.process(frame, observation, ts, jpeg):
                alerts.append({"rule": event.rule_id, "t_s": round(ts - START_EPOCH, 3), "status": event.verification.status if event.verification else "verified",
                               "tracks": event.tracks, "confidence": round(event.confidence, 3), "checks": event.verification.checks if event.verification else []})
            timings["detect_ms"].append((middle - started) * 1000)
            timings["runtime_ms"].append((time.perf_counter() - middle) * 1000)
        runtime.drain_health()
    capture.release()
    summary = {name: {"p50": round(statistics.median(values), 1), "p95": round(sorted(values)[int(0.95 * (len(values) - 1))], 1)}
               for name, values in timings.items() if values}
    return {"clip": clip.stem, "duration_s": round(total / source_fps, 2), "processed_fps": fps, "frames": len(timings["detect_ms"]),
            "flagged_tracks": flagged, "timing_ms": summary, "alerts": alerts}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--geometry", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fps", type=float, default=5.0)
    args = parser.parse_args()
    rules = [RuleSpec.model_validate({**item, "camera_id": args.camera_id, "status": "active"}) for item in json.loads(args.rules.read_text(encoding="utf-8"))]
    geometry = CameraGeometry.model_validate_json(args.geometry.read_text(encoding="utf-8")) if args.geometry else None
    result = replay(args.clip, args.camera_id, rules, geometry, args.fps)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.clip.stem}.alerts.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("clip", "duration_s", "frames", "flagged_tracks", "timing_ms")}), f"alerts={len(result['alerts'])}")


if __name__ == "__main__":
    main()
