"""Replay and edge-case tests for the pure programmable rule engine."""

import json
import sys
from datetime import datetime
from pathlib import Path

from dateutil.zoneinfo import get_zonefile_instance


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT / "services")]
from td_contracts import Observation, RuleSpec, RuleWhen
from rules.engine import RuleEngine
from rules.state import Fire, Health, RuleState


def spec(when, *, min_hold=1.5, cooldown=120, support="SUPPORTED", camera_id="cam"):
    return RuleSpec(rule_id="r_test", camera_id=camera_id, version=1, name="test", entity="person",
                    when=RuleWhen.model_validate(when), min_hold_s=min_hold, cooldown_s=cooldown,
                    support_level=support, status="active")


def obs(ts, positions=(), *, frame_id=None):
    tracks = []
    for track_id, x, y, first_seen, vx, vy in positions:
        tracks.append({"track_id": track_id, "cls": "person", "conf": .9,
                       "bbox": [x - 5, y - 10, x + 5, y], "foot": [x, y],
                       "velocity": [vx, vy], "first_seen": first_seen, "last_seen": ts})
    return Observation(camera_id="cam", ts=ts, frame_id=frame_id or round(ts * 10),
                       tracks=tracks, model_versions={"detector": "fixture", "tracker": "fixture"})


ZONE = [(0, 0), (20, 0), (20, 20), (0, 20)]


def test_recorded_observations_fire_exactly_once_for_zone_and_dwell():
    path = ROOT / "tests/fixtures/rules/observations.jsonl"
    recorded = [Observation.model_validate_json(line) for line in path.read_text().splitlines()]
    engine = RuleEngine({"center": [(800, 680), (900, 680), (900, 735), (800, 735)]}, {})
    zone = spec({"type": "in_zone", "zone": "center"}, camera_id="replay-cam")
    dwell = spec({"all": [{"type": "in_zone", "zone": "center"}, {"type": "dwell_at_least", "seconds": 3}]}, camera_id="replay-cam")
    for rule in (zone, dwell):
        state = RuleState()
        fires = [event for observation in recorded for event in engine.evaluate(rule, observation, state) if isinstance(event, Fire)]
        assert len(fires) == 1
        assert fires[0].tracks == (1,)
        assert fires[0].ts >= (3 if rule is dwell else 1.5)


def test_flicker_and_id_switch_keep_one_episode():
    engine = RuleEngine({"z": ZONE}, {})
    rule = spec({"type": "in_zone", "zone": "z"})
    for sequence in (
        [obs(0, [(1, 10, 10, 0, 0, 0)]), obs(.6, [(1, 10, 10, 0, 0, 0)]), obs(.8), obs(1.4, [(1, 11, 10, 0, 0, 0)]), obs(1.6, [(1, 11, 10, 0, 0, 0)])],
        [obs(0, [(1, 10, 10, 0, 0, 0)]), obs(.8, [(2, 11, 10, .8, 0, 0)]), obs(1.6, [(2, 11, 10, .8, 0, 0)])],
    ):
        state = RuleState()
        fires = [event for observation in sequence for event in engine.evaluate(rule, observation, state) if isinstance(event, Fire)]
        assert len(fires) == 1


def test_cooldown_and_outage_freeze():
    engine = RuleEngine({"z": ZONE}, {})
    rule = spec({"type": "in_zone", "zone": "z"})
    state = RuleState()
    sequence = [obs(0, [(1, 10, 10, 0, 0, 0)]), obs(.8, [(1, 10, 10, 0, 0, 0)]), obs(1.6, [(1, 10, 10, 0, 0, 0)]),
                obs(2, [(1, 40, 10, 0, 0, 0)]), obs(2.5, [(1, 10, 10, 0, 0, 0)]),
                obs(3.3, [(1, 10, 10, 0, 0, 0)]), obs(4.1, [(1, 10, 10, 0, 0, 0)])]
    fires = [event for observation in sequence for event in engine.evaluate(rule, observation, state) if isinstance(event, Fire)]
    assert len(fires) == 1
    assert isinstance(engine.check_health("cam", 10, state), Health)
    assert engine.check_health("cam", 11, state) is None
    assert engine.evaluate(rule, obs(11, [(1, 10, 10, 0, 0, 0)]), state) == []


def test_line_cross_and_unique_count_are_impulses():
    engine = RuleEngine({}, {"gate": ((10, 0), (10, 150))})
    crossing = spec({"type": "line_cross", "line": "gate"})
    state = RuleState()
    assert engine.evaluate(crossing, obs(0, [(1, 5, 10, 0, 0, 0)]), state) == []
    assert engine.evaluate(crossing, obs(.8, [(1, 8, 10, 0, 0, 0)]), state) == []
    assert engine.evaluate(crossing, obs(1.6, [(1, 9, 10, 0, 0, 0)]), state) == []
    fires = engine.evaluate(crossing, obs(2, [(1, 15, 10, 0, 10, 0)]), state)
    assert len(fires) == 1 and fires[0].tracks == (1,)

    count = spec({"type": "unique_count_at_least", "line": "gate", "count": 4, "window_s": 60}, cooldown=0)
    state = RuleState()
    before = [(ident, 5, ident * 30, 0, 0, 0) for ident in range(1, 5)]
    after = [(ident, 15, ident * 30, 0, 10, 0) for ident in range(1, 5)]
    assert engine.evaluate(count, obs(0, before), state) == []
    assert engine.evaluate(count, obs(.8, before), state) == []
    fires = engine.evaluate(count, obs(1.6, after), state)
    assert len(fires) == 1 and fires[0].tracks == (1, 2, 3, 4)
    assert engine.evaluate(count, obs(3, after), state) == []

    # A count episode stays deduplicated within its hour even with no cooldown.
    assert engine.evaluate(count, obs(4), state) == []
    assert engine.evaluate(count, obs(4.5, [(5, 5, 140, 4.5, 0, 0)]), state) == []
    assert engine.evaluate(count, obs(5, [(5, 15, 140, 4.5, 10, 0)]), state) == []


def test_time_movement_distance_and_absence():
    zone = {"z": [(0, 0), (10, 0), (10, 10), (0, 10)]}
    engine = RuleEngine(zone, {}, [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    tz = get_zonefile_instance().get("Asia/Kolkata")
    during = datetime(2026, 10, 16, 1, 0, tzinfo=tz).timestamp()
    outside = datetime(2026, 10, 16, 6, 0, tzinfo=tz).timestamp()
    window = spec({"all": [{"type": "entity_present"}, {"type": "time_window", "start": "00:00", "end": "05:00", "tz": "Asia/Kolkata"}]}, min_hold=0)
    assert len(engine.evaluate(window, obs(during, [(1, 5, 5, during, 0, 0)]), RuleState())) == 1
    assert engine.evaluate(window, obs(outside, [(1, 5, 5, outside, 0, 0)]), RuleState()) == []

    toward = spec({"type": "moving_toward", "zone": "z"})
    state = RuleState()
    assert engine.evaluate(toward, obs(0, [(1, -20, 5, 0, 10, 0)]), state) == []
    assert engine.evaluate(toward, obs(.8, [(1, -18, 5, 0, 10, 0)]), state) == []
    assert len(engine.evaluate(toward, obs(1.6, [(1, -15, 5, 0, 10, 0)]), state)) == 1

    near = spec({"type": "distance_below", "zone": "z", "meters": 2}, min_hold=0, support="EXPERIMENTAL")
    assert len(engine.evaluate(near, obs(0, [(1, 11, 5, 0, 0, 0)]), RuleState())) == 1
    assert RuleEngine(zone, {}).evaluate(near, obs(0, [(1, 11, 5, 0, 0, 0)]), RuleState()) == []

    absent = spec({"not": {"type": "entity_present"}})
    state = RuleState()
    assert engine.evaluate(absent, obs(0), state) == []
    assert len(engine.evaluate(absent, obs(2), state)) == 1
