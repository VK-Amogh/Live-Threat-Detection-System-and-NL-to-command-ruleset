"""Phase 0 smoke benchmark for programmable rules.

Runs the configured tracking model beside the installed threat pipeline and
probes the configured local LLM with schema output and three real video frames.
Results are saved to tests/benchmarks.md; a failing probe exits nonzero.
"""

import argparse
import base64
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/rules.yaml"
REPORT = ROOT / "tests/benchmarks.md"
STATE = ROOT / "storage/benchmarks/rules_runtime.json"
CLIPS = sorted((ROOT / "TestVideos").glob("*.avi"))


def frames(limit: int):
    if not CLIPS:
        raise RuntimeError("No TestVideos AVI clips are available")
    capture = cv2.VideoCapture(str(CLIPS[0]))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {CLIPS[0]}")
    try:
        collected = []
        while len(collected) < limit:
            ok, frame = capture.read()
            if not ok:
                break
            collected.append(frame)
        if len(collected) < min(limit, 3):
            raise RuntimeError("Clip has too few readable frames")
        return collected
    finally:
        capture.release()


def detector_probe(config: dict, count: int):
    from ultralytics import YOLO

    spec = config["detector"]
    path = ROOT / spec["weights"]
    if not path.is_file():
        raise RuntimeError(f"Rule detector weights missing: {path}")
    model = YOLO(str(path))
    classes = list(model.names.values())
    if "person" not in classes:
        raise RuntimeError("Rule detector does not support person")
    samples = frames(count)
    print(f"Tracking {len(samples)} frames from {CLIPS[0].name}", flush=True)
    track_times = []
    track_ids = set()
    threat_times = []
    threat_errors = []
    sys.path[:0] = [str(ROOT / "services/inference"), str(ROOT / "contracts/src")]
    import server as threat

    threat.load_models()
    if not threat.MODELS:
        raise RuntimeError(f"No existing threat models loaded: {threat.ERRORS}")
    for frame in samples:
        started = time.perf_counter()
        result = model.track(
            frame,
            persist=True,
            tracker=spec["tracker"],
            conf=float(spec["confidence"]),
            imgsz=int(spec["image_size"]),
            verbose=False,
        )[0]
        track_times.append(time.perf_counter() - started)
        if result.boxes.id is not None:
            track_ids.update(int(item) for item in result.boxes.id.tolist())
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Could not encode a video frame")
        started = time.perf_counter()
        try:
            threat.predict(encoded.tobytes(), "rules-benchmark")
        except Exception as exc:
            threat_errors.append(f"{type(exc).__name__}: {exc}")
            break
        threat_times.append(time.perf_counter() - started)
    if threat_errors:
        raise RuntimeError("Existing threat inference failed beside rule tracking: " + threat_errors[0])
    total = sum(track_times) + sum(threat_times)
    steady_total = sum(track_times[1:]) + sum(threat_times[1:])
    steady_fps = (len(samples) - 1) / steady_total if steady_total else 0.0
    return {
        "clip": CLIPS[0].name,
        "frames": len(samples),
        "rule_classes": classes,
        "track_ids_seen": len(track_ids),
        "tracking_median_ms": round(statistics.median(track_times) * 1000, 1),
        "threat_median_ms": round(statistics.median(threat_times) * 1000, 1),
        "combined_fps": round(len(samples) / total, 2),
        "steady_fps": round(steady_fps, 2),
        "meets_configured_fps": steady_fps >= float(config["camera"]["process_fps"]),
        "threat_models": [entry[0] for entry in threat.MODELS],
        "threat_warnings": threat.ERRORS,
    }


def llm_probe(config: dict):
    spec = config["llm"]
    samples = frames(3)
    images = []
    for frame in samples:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            raise RuntimeError("Could not encode a vision probe frame")
        images.append(base64.b64encode(encoded.tobytes()).decode("ascii"))
    schema = {
        "type": "object",
        "properties": {
            "image_count": {"type": "integer"},
            "visible_evidence": {"type": "string"},
            "uncertainty": {"type": "string"},
        },
        "required": ["image_count", "visible_evidence", "uncertainty"],
        "additionalProperties": False,
    }
    body = {
        "model": spec["model"],
        "stream": False,
        "format": schema,
        "options": {"temperature": 0, "num_gpu": int(spec["num_gpu"])},
        "messages": [
            {"role": "system", "content": "Describe only visible facts. Return JSON matching the supplied schema."},
            {"role": "user", "content": "These are three separate camera frames. State their count and describe what is visible. Say what is unclear.", "images": images},
        ],
    }
    started = time.perf_counter()
    response = httpx.post(f"{spec['base_url'].rstrip('/')}/api/chat", json=body, timeout=float(spec["timeout_s"]))
    response.raise_for_status()
    content = response.json()["message"]["content"]
    output = json.loads(content)
    if set(output) != set(schema["required"]) or output["image_count"] != 3 or not output["visible_evidence"].strip():
        raise RuntimeError(f"Gemma response failed schema/vision check: {output}")
    return {
        "model": spec["model"],
        "images": 3,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "output": output,
    }


def write_report(state):
    sections = [
        "# Programmable rules: Phase 0 runtime benchmark",
        "",
        f"Measured at {state['updated_at']} on this machine. The bundled AVI is a functional probe, not night-footage accuracy evidence.",
        "",
    ]
    for name in ("detector", "llm"):
        item = state.get(name)
        sections += [f"## {name.title()}", ""]
        if item is None:
            sections += ["Not run.", ""]
        elif "error" in item:
            sections += [f"**FAILED:** {item['error']}", ""]
        else:
            sections += ["```json", json.dumps(item, indent=2), "```", ""]
    sections += [
        "## Gate",
        "",
        "PASS" if all(state.get(name) and "error" not in state[name] for name in ("detector", "llm")) and state["detector"].get("meets_configured_fps") else "FAIL — later phases must wait for both probes and configured FPS to pass.",
        "",
    ]
    REPORT.write_text("\n".join(sections), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=("detector", "llm"), required=True)
    parser.add_argument("--frames", type=int, default=12)
    args = parser.parse_args()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    try:
        state[args.probe] = detector_probe(config, args.frames) if args.probe == "detector" else llm_probe(config)
        print(json.dumps(state[args.probe], indent=2), flush=True)
    except Exception as exc:
        state[args.probe] = {"error": f"{type(exc).__name__}: {exc}"}
        print(state[args.probe]["error"], file=sys.stderr, flush=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    write_report(state)
    return 1 if "error" in state[args.probe] else 0


if __name__ == "__main__":
    raise SystemExit(main())
