"""Run the real local compiler for one configured camera example."""

import json
import sys
from pathlib import Path

import yaml
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT / "services")]
from rules.compiler import RuleCompiler


def main():
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    classes = set(YOLO(str(ROOT / config["detector"]["weights"])).names.values())
    text = "Alert me when a person stays in the driveway for 3 seconds between midnight and 5 a.m."
    result = RuleCompiler.from_config(classes, {"driveway"}, set(), False).compile(text, "replay-cam")
    output = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    target = ROOT / "storage/validation/rules/compile.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0 if result.can_activate else 1


if __name__ == "__main__":
    raise SystemExit(main())
