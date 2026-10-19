"""Score rule alerts against labelled event intervals, with intervals instead of flattering point estimates.

Inputs (one pair per clip, matched by file stem):
  <alerts>/<clip>.alerts.json   written by scripts/eval/rules_replay.py: {"clip", "duration_s", "alerts": [{"rule", "t_s", "status"}]}
  <labels>/<clip>.json          {"clip", "negative": false, "events": [{"rule", "start_s", "completion_s", "notes"}]}
                                `negative: true` marks footage in which nothing the rules look for happens (hours count toward FP/hour).

Matching: an alert matches an event of the same rule when start_s - lead <= t <= completion_s + tolerance. One alert per event
(greedy, in time order); further alerts for an already matched event are DUPLICATES, alerts matching nothing are FALSE ALERTS,
events with no alert are MISSED. Latency is alert time minus completion_s.

Claims made to the user must quote the interval bound (Wilson lower bound for precision/recall, rule-of-three upper bound for
false alerts per hour when none were seen), never the point estimate: 30/30 correct only supports precision >= 0.89, and
0 false alerts in 4 h only supports <= 0.75 per hour.

  python scripts/eval/rules_score.py --alerts storage/eval/rules/run1 --labels tests/fixtures/rules/labels --out storage/eval/rules/run1
  python scripts/eval/rules_score.py ... --baseline storage/eval/rules/baseline/report.json     # event-level regression diff
"""

import argparse
import json
from collections import defaultdict
from math import sqrt
from pathlib import Path

LEAD_S = 1.0
TOLERANCE_S = 3.0


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval; (0, 1) when there is no data."""
    if total == 0:
        return 0.0, 1.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    spread = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def rule_of_three_upper(hours: float) -> float | None:
    """With zero events in `hours` of footage, the 95% upper bound on the rate per hour."""
    return 3.0 / hours if hours > 0 else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def match(alerts: list[dict], events: list[dict], tolerance_s: float = TOLERANCE_S, lead_s: float = LEAD_S) -> dict:
    matched, taken = [], set()
    false_alerts, duplicates = [], []
    for index, alert in sorted(enumerate(alerts), key=lambda item: item[1]["t_s"]):
        window = [i for i, event in enumerate(events) if event["rule"] == alert["rule"]
                  and event["start_s"] - lead_s <= alert["t_s"] <= event["completion_s"] + tolerance_s]
        free = [i for i in window if i not in taken]
        if free:
            chosen = free[0]
            taken.add(chosen)
            matched.append({"alert": index, "event": chosen, "latency_s": round(alert["t_s"] - events[chosen]["completion_s"], 3)})
        elif window:
            duplicates.append(index)
        else:
            false_alerts.append(index)
    return {"matched": matched, "false_alerts": false_alerts, "duplicates": duplicates,
            "missed": [i for i in range(len(events)) if i not in taken]}


def load(directory: Path, suffix: str) -> dict[str, dict]:
    return {path.name[: -len(suffix)]: json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob(f"*{suffix}"))}


def score(alert_runs: dict[str, dict], labels: dict[str, dict]) -> dict:
    rules: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "dup": 0, "latency": []})
    hours_total, hours_negative = 0.0, 0.0
    detail = {"events": [], "false_alert_list": []}
    for clip, labelled in labels.items():
        run = alert_runs.get(clip)
        if run is None:
            continue
        hours = run.get("duration_s", 0.0) / 3600
        hours_total += hours
        hours_negative += hours if labelled.get("negative") or not labelled.get("events") else 0.0
        result = match(run["alerts"], labelled.get("events", []))
        done = {item["event"]: item for item in result["matched"]}
        for index, event in enumerate(labelled.get("events", [])):
            entry = rules[event["rule"]]
            if index in done:
                entry["tp"] += 1
                entry["latency"].append(done[index]["latency_s"])
            else:
                entry["fn"] += 1
            detail["events"].append({"clip": clip, "rule": event["rule"], "start_s": event["start_s"], "matched": index in done})
        for index in result["false_alerts"]:
            alert = run["alerts"][index]
            rules[alert["rule"]]["fp"] += 1
            detail["false_alert_list"].append({"clip": clip, "rule": alert["rule"], "t_s": alert["t_s"]})
        for index in result["duplicates"]:
            rules[run["alerts"][index]["rule"]]["dup"] += 1
    summary = {}
    for rule, c in sorted(rules.items()):
        precision, recall = wilson(c["tp"], c["tp"] + c["fp"]), wilson(c["tp"], c["tp"] + c["fn"])
        summary[rule] = {**{k: c[k] for k in ("tp", "fp", "fn", "dup")},
                         "precision": c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None, "precision_95": precision,
                         "recall": c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None, "recall_95": recall,
                         "duplicate_rate": c["dup"] / (c["tp"] + c["dup"]) if c["tp"] + c["dup"] else None,
                         "latency_p50_s": percentile(c["latency"], 0.5), "latency_p95_s": percentile(c["latency"], 0.95)}
    false_total = sum(c["fp"] for c in rules.values())
    return {"rules": summary, "hours": round(hours_total, 3), "negative_hours": round(hours_negative, 3), "false_alerts": false_total,
            "false_alerts_per_hour": false_total / hours_total if hours_total else None,
            "false_alerts_per_hour_upper_95": rule_of_three_upper(hours_total) if false_total == 0 else None, **detail}


def diff(baseline: dict, current: dict) -> dict:
    """Event-level regression check: what used to be caught and now is not, and alerts that are new. Small datasets make
    this more trustworthy than a percentage threshold."""
    was = {(e["clip"], e["rule"], e["start_s"]): e["matched"] for e in baseline["events"]}
    lost = [e for e in current["events"] if was.get((e["clip"], e["rule"], e["start_s"])) and not e["matched"]]
    gained = [e for e in current["events"] if was.get((e["clip"], e["rule"], e["start_s"])) is False and e["matched"]]
    old_false = {(a["clip"], a["rule"], round(a["t_s"])) for a in baseline["false_alert_list"]}
    new_false = [a for a in current["false_alert_list"] if (a["clip"], a["rule"], round(a["t_s"])) not in old_false]
    return {"newly_missed": lost, "newly_caught": gained, "new_false_alerts": new_false}


def fmt(value, digits=2):
    return "n/a" if value is None else f"{value:.{digits}f}"


def markdown(report: dict, regression: dict | None) -> str:
    lines = ["# Rule evaluation", "",
             f"Footage scored: {report['hours']:.2f} h ({report['negative_hours']:.2f} h with nothing to find). False alerts: {report['false_alerts']}.", ""]
    rate = report["false_alerts_per_hour"]
    if rate is not None:
        bound = report["false_alerts_per_hour_upper_95"]
        lines.append(f"False alerts per camera-hour: {fmt(rate)}" + (f" (none seen: the 95% upper bound is {fmt(bound)} per hour)" if bound else "") + "\n")
    lines += ["| Rule | TP | FP | FN | Dup | Precision (95% interval) | Recall (95% interval) | Latency p50 / p95 (s) |", "|---|---|---|---|---|---|---|---|"]
    for rule, r in report["rules"].items():
        lines.append(f"| {rule} | {r['tp']} | {r['fp']} | {r['fn']} | {r['dup']} | {fmt(r['precision'])} ({fmt(r['precision_95'][0])}–{fmt(r['precision_95'][1])}) | "
                     f"{fmt(r['recall'])} ({fmt(r['recall_95'][0])}–{fmt(r['recall_95'][1])}) | {fmt(r['latency_p50_s'], 1)} / {fmt(r['latency_p95_s'], 1)} |")
    lines += ["", "Quote the lower interval bound, not the point estimate, when reporting results.", ""]
    if regression is not None:
        lines += ["## Against the baseline", f"- newly missed events: {len(regression['newly_missed'])}", f"- newly caught events: {len(regression['newly_caught'])}",
                  f"- new false alerts: {len(regression['new_false_alerts'])}", ""]
        for item in regression["newly_missed"]:
            lines.append(f"  - MISSED now: {item['clip']} {item['rule']} @ {item['start_s']}s")
        for item in regression["new_false_alerts"]:
            lines.append(f"  - NEW false alert: {item['clip']} {item['rule']} @ {item['t_s']}s")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--alerts", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    report = score(load(args.alerts, ".alerts.json"), load(args.labels, ".json"))
    regression = diff(json.loads(args.baseline.read_text(encoding="utf-8")), report) if args.baseline else None
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out / "report.md").write_text(markdown(report, regression), encoding="utf-8")
    print(markdown(report, regression))


if __name__ == "__main__":
    main()
