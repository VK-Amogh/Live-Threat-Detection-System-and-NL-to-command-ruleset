"""Evaluate the local visual summary on every rule-flagged AVI excerpt."""

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
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["llm"]
    llm = LocalLLM(config["base_url"], config["model"], float(config["timeout_s"]), int(config["num_gpu"]))
    manifest = json.loads((ROOT / "tests/reasoner_fixture_manifest.json").read_text(encoding="utf-8"))
    selected = [item for item in manifest if item["rule_fired"]]
    destination = ROOT / "tests/reasoner_20_results.json"
    results = json.loads(destination.read_text(encoding="utf-8")) if destination.exists() else []
    done = {item["clip"] for item in results if item["status"] == "PASS"}
    for index, item in enumerate(selected, 1):
        if item["clip"] in done:
            continue
        started = time.monotonic()
        record = {**item, "model": config["model"]}
        output = None
        try:
            images = selected_frames(ROOT / item["clip"])
            output = llm.describe(images, SYSTEM,
                                  "Rule: person visible for at least 1.5 seconds. Describe only visible evidence across the sampled frames.",
                                  ReviewResult.model_json_schema())
            record.update(status="PASS", result=validate_review(output).model_dump(), images=len(images))
        except Exception as exc:
            record.update(status="FAIL", error=f"{type(exc).__name__}: {str(exc)[:200]}")
            if output is not None:
                record["rejected_candidate"] = output
        record["elapsed_s"] = round(time.monotonic() - started, 2)
        results.append(record)
        destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"{index}/{len(selected)} {Path(item['clip']).name}: {record['status']} in {record['elapsed_s']}s", flush=True)
    latest = {item["clip"]: item for item in results}
    safe = sum(latest.get(item["clip"], {}).get("status") == "PASS" for item in selected)
    print(f"Safe structured summaries: {safe}/{len(selected)}", flush=True)
    return 0 if safe == len(selected) and len(selected) >= 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
