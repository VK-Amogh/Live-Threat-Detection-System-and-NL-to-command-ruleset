"""Run one reproducible, real local-Gemma visual-review probe."""

import json
from pathlib import Path
import sys
import time

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import ReviewResult
from services.reasoner.frames import selected_frames
from services.reasoner.prompts import SYSTEM, validate_review
from services.rules.llm import LocalLLM


def main():
    clip = ROOT / "TestVideos/v001_converted 3.avi"
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["llm"]
    llm = LocalLLM(config["base_url"], config["model"], float(config["timeout_s"]), int(config["num_gpu"]))
    images = selected_frames(clip)
    started = time.monotonic()
    record = {"clip": clip.name, "model": config["model"], "images": len(images)}
    try:
        output = llm.describe(images, SYSTEM, "Describe only visible evidence in these sampled frames.",
                              ReviewResult.model_json_schema())
        record.update(result=validate_review(output).model_dump(), status="PASS")
    except Exception as exc:
        record.update(status="FAIL", error=f"{type(exc).__name__}: {str(exc)[:200]}")
    record["elapsed_s"] = round(time.monotonic() - started, 2)
    destination = ROOT / "tests/reasoner_probe.json"
    destination.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
