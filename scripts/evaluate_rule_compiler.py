"""Run all golden natural-language requests through the configured local Gemma."""

import argparse
import json
import sys
import time
from pathlib import Path

import yaml
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT / "services")]
from rules.compiler import RuleCompiler


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="Comma-separated 1-based golden case numbers for debugging")
    args = parser.parse_args()
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    classes = set(YOLO(str(ROOT / config["detector"]["weights"])).names.values())
    compiler = RuleCompiler.from_config(classes, {"driveway", "porch"}, {"gate"}, False)
    all_cases = json.loads((ROOT / "tests/golden_rules.json").read_text(encoding="utf-8"))
    selected = [int(item) for item in args.only.split(",")] if args.only else list(range(1, len(all_cases) + 1))
    cases = [(number, all_cases[number - 1]) for number in selected]
    report = ROOT / "tests/golden_rules_results.md"
    lines = ["# Golden rule compiler results", "", "Measured against the local configured LLM and detector class list.", ""]
    successes = 0
    valid = 0
    for position, (index, case) in enumerate(cases, 1):
        started = time.perf_counter()
        try:
            result = compiler.compile(case["text"], "replay-cam")
            result.spec.model_validate(result.spec.model_dump(mode="json", by_alias=True))
            valid += 1
            leaves = sorted(node.type for node in result.spec.when.leaves()) if result.spec.when else []
            expected = sorted(case.get("types", []))
            root_ok = True
            if case.get("root") == "any":
                root_ok = result.spec.when is not None and result.spec.when.any is not None
            elif case.get("root") == "not":
                root_ok = result.spec.when is not None and (
                    result.spec.when.not_ is not None or
                    result.spec.when.all is not None and any(child.not_ is not None for child in result.spec.when.all)
                )
            correct = (result.support_level == case["level"] and
                       (case["level"] == "UNSUPPORTED" or
                        result.spec.entity == case["entity"] and leaves == expected and root_ok and
                        result.can_activate == case.get("can_activate", True)))
            detail = result.problems or [result.readback or "No readback"]
        except Exception as exc:
            correct = False
            detail = [f"{type(exc).__name__}: {exc}"]
        successes += correct
        elapsed = time.perf_counter() - started
        lines += [f"{index}. {'PASS' if correct else 'FAIL'} ({elapsed:.1f}s): {case['text']}", f"   - {'; '.join(detail)}", ""]
        report.write_text("\n".join(lines + [f"Current: {successes}/{position} correct; {valid}/{position} valid.", ""]), encoding="utf-8")
        print(f"{position}/{len(cases)} case {index} {'PASS' if correct else 'FAIL'} {elapsed:.1f}s: {case['text']}", flush=True)
    lines += [f"Result: {valid}/{len(cases)} schema valid; {successes}/{len(cases)} correct ({successes / len(cases):.0%}).", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    return 0 if valid == len(cases) and successes / len(cases) >= .9 else 1


if __name__ == "__main__":
    raise SystemExit(run())
