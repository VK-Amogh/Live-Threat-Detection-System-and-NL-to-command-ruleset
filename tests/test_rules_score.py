"""The evaluation scorer: matching, honest intervals, and event-level regression diffs."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rules_score", ROOT / "scripts/eval/rules_score.py")
rules_score = importlib.util.module_from_spec(spec)
sys.modules["rules_score"] = rules_score
spec.loader.exec_module(rules_score)

EVENT = {"rule": "door", "start_s": 10.0, "completion_s": 12.0}


def test_matching_counts_misses_false_alerts_and_duplicates():
    alerts = [{"rule": "door", "t_s": 12.5}, {"rule": "door", "t_s": 13.0}, {"rule": "door", "t_s": 40.0}, {"rule": "chair", "t_s": 12.0}]
    result = rules_score.match(alerts, [EVENT, {"rule": "door", "start_s": 60.0, "completion_s": 61.0}])
    assert [m["latency_s"] for m in result["matched"]] == [0.5]
    assert result["duplicates"] == [1] and sorted(result["false_alerts"]) == [2, 3] and result["missed"] == [1]


def test_an_alert_before_the_event_started_or_long_after_it_ended_does_not_match():
    for t in (7.0, 20.0):
        assert rules_score.match([{"rule": "door", "t_s": t}], [EVENT])["matched"] == []


def test_intervals_are_honest_about_small_samples():
    low, _ = rules_score.wilson(30, 30)
    assert 0.88 < low < 0.90                                         # 30/30 only supports precision >= ~0.89
    assert rules_score.wilson(0, 0) == (0.0, 1.0)
    assert rules_score.rule_of_three_upper(4) == 0.75               # 0 false alerts in 4 h only supports <= 0.75 per hour
    assert rules_score.rule_of_three_upper(15) == 0.2 and rules_score.rule_of_three_upper(0) is None


def test_scoring_and_regression_diff():
    labels = {"a": {"events": [EVENT, {"rule": "door", "start_s": 30.0, "completion_s": 31.0}]}, "empty": {"negative": True, "events": []}}
    good = {"a": {"duration_s": 3600, "alerts": [{"rule": "door", "t_s": 12.4}, {"rule": "door", "t_s": 31.2}]}, "empty": {"duration_s": 7200, "alerts": []}}
    report = rules_score.score(good, labels)
    assert report["rules"]["door"]["tp"] == 2 and report["rules"]["door"]["fn"] == 0 and report["false_alerts"] == 0
    assert report["hours"] == 3.0 and report["negative_hours"] == 2.0
    assert report["false_alerts_per_hour_upper_95"] == 1.0           # 3 h of footage, none false: <= 1/h at 95%
    worse = {"a": {"duration_s": 3600, "alerts": [{"rule": "door", "t_s": 12.4}, {"rule": "door", "t_s": 50.0}]}, "empty": {"duration_s": 7200, "alerts": [{"rule": "door", "t_s": 5.0}]}}
    after = rules_score.score(worse, labels)
    regression = rules_score.diff(report, after)
    assert [e["start_s"] for e in regression["newly_missed"]] == [30.0] and len(regression["new_false_alerts"]) == 2
    assert "MISSED now" in rules_score.markdown(after, regression)
