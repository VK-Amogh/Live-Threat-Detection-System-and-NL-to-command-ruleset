"""The demo rules on the two real test videos in `ruleset testing/` (steady phone, 478x850).

Video 12.28.20: a man walks in from the left edge, sits on the chair, stands up and leaves to the left.
Video 12.28.32 (12.30.05 is a byte-identical copy): the man walks to the glass door, opens it, goes out, the door closes.

The fixes for door entry, sitting and door opening were made while looking at these same videos, so this guards against
regression on them; it is not a blind accuracy measurement. Skipped when the videos, detector or pose weights are missing.
"""

import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
VIDEOS = ROOT / "ruleset testing"
V_SIT = VIDEOS / "WhatsApp Video 2026-10-17 at 12.28.20 PM.mp4"
V_DOOR = VIDEOS / "WhatsApp Video 2026-10-17 at 12.28.32 PM.mp4"
needs = pytest.mark.skipif(not (V_SIT.exists() and V_DOOR.exists() and (ROOT / "weights/yolo26n.pt").exists() and (ROOT / "weights/yolo26n-pose.pt").exists()),
                           reason="test videos or weights not present")


def replay(video: Path, door_polygon):
    import cv2
    import yaml
    from td_contracts import CameraGeometry, RuleSpec
    from services.rules.evidence import EvidenceBuffer
    from services.rules.runtime import RuleRuntime, build_detector

    class NoClips(EvidenceBuffer):
        def _write_clip(self, event_id, pieces):
            return None

    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    geometry = CameraGeometry(snapshot_width=int(cap.get(3)), snapshot_height=int(cap.get(4)), zones={"door": door_polygon}, zone_roles={"door": "door"})

    def rule(rid, when, hold):
        return RuleSpec.model_validate({"rule_id": rid, "camera_id": "cam", "version": 1, "name": rid, "entity": "person", "when": when, "min_hold_s": hold,
                                        "cooldown_s": 60, "support_level": "EXPERIMENTAL", "status": "active"})

    rules = [rule("comes_in", {"type": "enters_zone", "zone": "door"}, 1.5), rule("goes_out", {"type": "exits_zone", "zone": "door"}, 1.5),
             rule("sits", {"type": "sits_on", "object": {"cls": "chair"}}, 1.0), rule("door_opens", {"type": "zone_changes", "zone": "door"}, 0.4)]
    alerts = {rule.rule_id: [] for rule in rules}
    detector = build_detector("cam", config)
    with tempfile.TemporaryDirectory() as scratch:
        evidence = NoClips(Path(scratch), 5, 2, 0.0)
        runtime = RuleRuntime("cam", config, evidence, "video")
        runtime.configure(rules, geometry)
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            index += 1
            if (index - 1) % max(1, round(fps / 5)):
                continue
            ts = 1_760_000_000.0 + (index - 1) / fps
            jpeg = cv2.imencode(".jpg", frame)[1].tobytes()
            evidence.append(ts, jpeg)
            for event in runtime.process(frame, detector.observe(frame, index, ts), ts, jpeg):
                alerts[event.rule_id].append(round((index - 1) / fps, 1))
    return alerts


@needs
def test_walking_in_sitting_and_leaving_each_alert_once_at_the_right_time():
    alerts = replay(V_SIT, [(0, 0), (150, 0), (150, 850), (0, 850)])        # the entry is at the left edge of the frame
    assert len(alerts["comes_in"]) == 1 and 3.0 <= alerts["comes_in"][0] <= 4.5, alerts       # he steps into view at 3.2 s
    assert len(alerts["sits"]) == 1 and 6.0 <= alerts["sits"][0] <= 9.5, alerts               # seated from about 5.6 s to 9 s
    assert len(alerts["goes_out"]) == 1 and 11.0 <= alerts["goes_out"][0] <= 13.0, alerts     # he leaves to the left at about 11 s
    assert alerts["door_opens"] == [], alerts                                                 # walking through the strip is not a door opening


@needs
def test_going_out_through_a_door_is_not_coming_in_and_the_door_opening_is_seen():
    alerts = replay(V_DOOR, [(150, 25), (385, 25), (385, 705), (150, 705)])  # the glass door in the middle of the frame
    assert alerts["comes_in"] == [], alerts                                  # nobody comes in: he walks toward the door and out
    assert alerts["sits"] == [], alerts
    assert len(alerts["door_opens"]) == 1 and 5.0 <= alerts["door_opens"][0] <= 7.0, alerts   # the door swings open at about 5.4-6.7 s
    assert len(alerts["goes_out"]) == 1 and 9.5 <= alerts["goes_out"][0] <= 11.0, alerts      # last seen in the doorway at 9 s
