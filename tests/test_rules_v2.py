"""Engine tests for the v2 rule primitives: directions, transitions, hysteresis, scoped episodes, pose and anchors."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT / "services")]
from td_contracts import Anchor, Observation, RuleSpec, RuleWhen
from rules.engine import RuleEngine
from rules.state import Fire, RuleState


def spec(when, *, entity="person", min_hold=1.5, cooldown=120, scope="rule_zone", **extra):
    return RuleSpec.model_validate({"rule_id": "r_t", "camera_id": "cam", "version": 1, "name": "t", "entity": entity, "when": when,
                                    "min_hold_s": min_hold, "cooldown_s": cooldown, "support_level": "SUPPORTED", "status": "active",
                                    "episode": {"cooldown_scope": scope}, **extra})


def track(ident, x, y, ts, *, cls="person", first=0.0, h=40, w=10, score=None, flags=(), keypoints=None, bbox=None):
    return {"track_id": ident, "cls": cls, "conf": .9, "bbox": bbox or [x - w / 2, y - h, x + w / 2, y], "foot": [x, y],
            "velocity": [0, 0], "first_seen": first, "last_seen": ts, "score": score, "flags": list(flags), "keypoints": keypoints}


def obs(ts, tracks=()):
    return Observation.model_validate({"camera_id": "cam", "ts": ts, "frame_id": round(ts * 10), "tracks": list(tracks),
                                       "model_versions": {"detector": "t", "tracker": "t"}})


def run(engine, rule, frames, state=None, **kwargs):
    state = state or RuleState()
    return [f for frame in frames for f in engine.evaluate(rule, frame, state, **kwargs) if isinstance(f, Fire)]


def steps(start, stop, dt=0.2):
    n = round((stop - start) / dt)
    return [round(start + i * dt, 3) for i in range(n + 1)]


ZONE = [(0, 0), (40, 0), (40, 40), (0, 40)]


def test_line_direction_matters():
    engine = RuleEngine({}, {"gate": ((10, 0), (10, 150))})
    # Side B lies along the normal (-dy, dx), i.e. toward smaller x for this line; so 15 -> 5 is a_to_b.
    for direction, xs, expected in (("a_to_b", (15, 15, 5), 1), ("a_to_b", (5, 5, 15), 0), ("b_to_a", (5, 5, 15), 1), ("any", (5, 5, 15), 1)):
        rule = spec({"type": "line_cross", "line": "gate", "direction": direction}, min_hold=0.4)
        frames = [obs(0, [track(1, xs[0], 50, 0)]), obs(.4, [track(1, xs[1], 50, .4)]), obs(.8, [track(1, xs[2], 50, .8)])]
        assert len(run(engine, rule, frames)) == expected, (direction, xs)


def test_entry_needs_origin_outside_the_zone():
    engine = RuleEngine({"room": ZONE}, {})
    rule = spec({"type": "enters_zone", "zone": "room"}, min_hold=0.4)
    walks_in = [obs(t, [track(1, -30 + max(0, t - 1.0) * 80 if t < 1.6 else 20, 20, t)]) for t in steps(0, 3)]
    assert len(run(engine, rule, walks_in)) == 1
    born_inside = [obs(t, [track(2, 20, 20, t)]) for t in steps(0, 3)]
    assert run(engine, rule, born_inside) == []                      # mid-room re-detection is not an entry


def test_exit_is_confirmed_after_leaving():
    engine = RuleEngine({"room": ZONE}, {})
    rule = spec({"type": "exits_zone", "zone": "room"}, min_hold=0.4)
    frames = [obs(t, [track(1, 20 if t < 1.5 else 90, 20, t)]) for t in steps(0, 3.5)]
    assert len(run(engine, rule, frames)) == 1


def test_one_false_frame_does_not_restart_the_hold_or_duplicate():
    engine = RuleEngine({"z": ZONE}, {})
    rule = spec({"type": "in_zone", "zone": "z"}, min_hold=1.0, cooldown=0)
    frames = [obs(t, [track(1, 20 if abs(t - 0.6) > 1e-6 else 90, 20, t)]) for t in steps(0, 3)]   # one frame outside at 0.6
    assert len(run(engine, rule, frames)) == 1


def test_id_churn_gives_one_alert_per_cooldown_not_one_per_id():
    engine = RuleEngine({"z": ZONE}, {})
    frames = []
    for ident, start in ((1, 0), (2, 10), (3, 20), (4, 30), (5, 40)):
        frames += [obs(start + t, [track(ident, 20, 20, start + t, first=start)]) for t in steps(0, 2.5)]
    assert len(run(engine, spec({"type": "in_zone", "zone": "z"}), frames)) == 1
    assert len(run(engine, spec({"type": "in_zone", "zone": "z"}, scope="actor"), frames)) == 5


def test_hourly_cap_limits_alerts():
    engine = RuleEngine({"z": ZONE}, {})
    rule = spec({"type": "in_zone", "zone": "z"}, min_hold=0.4, cooldown=0, scope="actor", alert={"max_alerts_per_hour": 2})
    frames = []
    for i in range(5):
        start = i * 10
        frames += [obs(start + t, [track(10 + i, 20, 20, start + t, first=start)]) for t in steps(0, 1.0)]
    assert len(run(engine, rule, frames)) == 2


def test_implausible_tracks_never_alert():
    quality = {"person": {"min_track_score": 0.5}}
    engine = RuleEngine({"z": ZONE}, {}, quality=quality)
    rule = spec({"type": "in_zone", "zone": "z"}, min_hold=0.4)
    for bad in ({"score": 0.3}, {"flags": ["oversized"]}, {"flags": ["border"]}):
        assert run(engine, rule, [obs(t, [track(1, 20, 20, t, **bad)]) for t in steps(0, 2)]) == []
    assert len(run(engine, rule, [obs(t, [track(1, 20, 20, t, score=0.8)]) for t in steps(0, 2)])) == 1


def test_blurred_frames_and_camera_motion_hold_everything():
    engine = RuleEngine({"z": ZONE}, {})
    rule = spec({"type": "in_zone", "zone": "z"}, min_hold=1.0)
    frames = [obs(t, [track(1, 20, 20, t)]) for t in steps(0, 3)]
    assert run(engine, rule, frames, low_quality=True) == []
    assert run(engine, rule, frames, suspended=True) == []
    assert len(run(engine, rule, frames)) == 1


def kps(**points):
    names = {"ls": 5, "rs": 6, "lw": 9, "rw": 10, "le": 7, "re": 8, "lh": 11, "rh": 12, "lk": 13, "rk": 14}
    out = [(0.0, 0.0, 0.0)] * 17
    for key, (x, y) in points.items():
        out[names[key]] = (float(x), float(y), 0.9)
    return out


CHAIR = Anchor(cls="chair", bbox=(100, 100, 180, 200), label="chair by window")
SEATED = kps(ls=(125, 100), rs=(155, 100), lh=(125, 145), rh=(155, 145), lk=(120, 150), rk=(160, 150))
STANDING = kps(ls=(125, 60), rs=(155, 60), lh=(125, 105), rh=(155, 105), lk=(125, 150), rk=(155, 150))


def test_sitting_needs_pose_posture_not_box_overlap():
    engine = RuleEngine({}, {}, anchors={"c1": CHAIR})
    rule = spec({"type": "sits_on", "object": {"anchor": "c1"}}, min_hold=1.0)
    person = dict(x=140, y=200, h=160, w=70)
    def frames(points, ident=1):
        return [obs(t, [track(ident, keypoints=points, ts=t, **person)]) for t in steps(0, 3)]
    assert len(run(engine, rule, frames(SEATED))) == 1
    assert run(engine, rule, frames(STANDING)) == []                 # same overlapping boxes, standing posture
    assert run(engine, rule, frames(None)) == []                     # no skeleton: cannot tell, so no alert


def test_sitting_picks_the_nearest_of_two_chairs():
    other = Anchor(cls="chair", bbox=(200, 100, 280, 200))
    engine = RuleEngine({}, {}, anchors={"c1": CHAIR, "c2": other})
    rule = spec({"type": "sits_on", "object": {"anchor": "c2"}}, min_hold=1.0)
    person = dict(x=140, y=200, h=160, w=70)
    assert run(engine, rule, [obs(t, [track(1, keypoints=SEATED, ts=t, **person)]) for t in steps(0, 3)]) == []


def test_touch_needs_a_hand_inside_the_object():
    engine = RuleEngine({}, {}, anchors={"c1": CHAIR})
    rule = spec({"type": "touches_object", "object": {"anchor": "c1"}}, min_hold=0.4)
    person = dict(x=200, y=200, h=160, w=60)
    touching = kps(lw=(170, 150), le=(185, 120))                     # wrist on the backrest
    away = kps(lw=(230, 150), le=(220, 120))
    assert len(run(engine, rule, [obs(t, [track(1, keypoints=touching, ts=t, **person)]) for t in steps(0, 2)])) == 1
    assert run(engine, rule, [obs(t, [track(1, keypoints=away, ts=t, **person)]) for t in steps(0, 2)]) == []


BAG = Anchor(cls="backpack", bbox=(200, 200, 260, 260), label="bag")


def test_object_absent_ignores_occlusion_by_a_person():
    engine = RuleEngine({}, {}, anchors={"bag": BAG})
    rule = spec({"type": "object_absent", "object": {"anchor": "bag"}, "seconds": 2}, entity="backpack", min_hold=0, cooldown=0)
    bag = lambda t: track(7, 230, 260, t, cls="backpack", bbox=[200, 200, 260, 260])
    removed = [obs(t, [bag(t)] if t < 1 else []) for t in steps(0, 5)]
    assert len(run(engine, rule, removed)) == 1
    blocked = [obs(t, [track(9, 230, 300, t, bbox=[190, 150, 270, 300])] if t >= 1 else [bag(t)]) for t in steps(0, 5)]
    assert run(engine, rule, blocked) == []                          # a person standing in front is not the bag disappearing


def test_picks_up_needs_person_at_the_object_then_an_empty_spot():
    engine = RuleEngine({}, {}, anchors={"bag": BAG})
    rule = spec({"type": "picks_up", "object": {"anchor": "bag"}}, min_hold=0.4, cooldown=0)
    def person(t, x):
        return track(9, x, 262, t, bbox=[x - 20, 140, x + 20, 262])
    frames = []
    for t in steps(0, 8):
        bag_here = t < 2
        near = [person(t, 275)] if t < 3.5 else [person(t, 400)]   # beside the bag, then walks away with it
        frames.append(obs(t, near + ([track(7, 230, 260, t, cls="backpack", bbox=[200, 200, 260, 260])] if bag_here else [])))
    assert len(run(engine, rule, frames)) == 1
    never_near = [obs(t, [person(t, 500)]) for t in steps(0, 8)]
    assert run(engine, rule, never_near) == []


def test_sequence_cross_then_dwell_in_order():
    engine = RuleEngine({"z": [(20, 0), (60, 0), (60, 60), (20, 60)]}, {"gate": ((10, 0), (10, 150))})
    rule = spec({"sequence": [{"type": "line_cross", "line": "gate"}, {"type": "in_zone", "zone": "z"}], "within_s": 30}, min_hold=0.5)
    path = [obs(t, [track(1, 5 + 40 * max(0, t - 1.0) if t < 1.6 else 40, 30, t)]) for t in steps(0, 5)]
    assert len(run(engine, rule, path)) == 1
    only_inside = [obs(t, [track(2, 40, 30, t)]) for t in steps(0, 5)]
    assert run(engine, rule, only_inside) == []                      # never crossed first: wrong order


def test_a_person_who_appears_in_a_doorway_has_come_in():
    walk = [obs(t, [track(1, 20, 20, t)]) for t in steps(0, 3)]            # first seen inside the zone, never seen outside it
    rule = spec({"type": "enters_zone", "zone": "z"}, min_hold=0.4)
    assert len(run(RuleEngine({"z": ZONE}, {}, zone_roles={"z": "door"}), rule, walk)) == 1
    assert run(RuleEngine({"z": ZONE}, {}, zone_roles={"z": "area"}), rule, walk) == []     # elsewhere, appearing mid-room is not an entry
    assert run(RuleEngine({"z": ZONE}, {}), rule, walk) == []


def test_a_chair_the_detector_loses_when_someone_sits_on_it_is_still_known():
    engine = RuleEngine({}, {})
    rule = spec({"type": "sits_on", "object": {"cls": "chair"}}, min_hold=1.0)
    chair = lambda t: track(5, 140, 200, t, cls="chair", bbox=[100, 100, 180, 200])
    person = lambda t: track(1, 140, 200, t, h=160, w=70, keypoints=SEATED)
    frames = [obs(t, [chair(t), person(t)]) for t in steps(0, 0.6)] + [obs(t, [person(t)]) for t in steps(0.8, 4)]   # the chair disappears behind them
    assert len(run(engine, rule, frames)) == 1
    never_seen = [obs(t, [person(t)]) for t in steps(0, 4)]
    assert run(RuleEngine({}, {}), rule, never_seen) == []                  # no chair ever seen: nothing to sit on


def test_a_changing_zone_fires_once_and_settles():
    engine = RuleEngine({"door": ZONE}, {}, zone_roles={"door": "door"})
    rule = spec({"type": "zone_changes", "zone": "door"}, entity="person", min_hold=0.4, cooldown=0)
    def frame(t, change):
        return Observation.model_validate({"camera_id": "cam", "ts": t, "frame_id": 1, "model_versions": {"detector": "t", "tracker": "t"},
                                           "tracks": [], "zone_change": {"door": change}})
    frames = [frame(t, 0.02) for t in steps(0, 1)] + [frame(t, 0.6) for t in steps(1.2, 3)] + [frame(t, 0.02) for t in steps(3.2, 4.4)]
    assert len(run(engine, rule, frames)) == 1
    assert run(RuleEngine({"door": ZONE}, {}), rule, [frame(t, 0.1) for t in steps(0, 3)]) == []


DOOR = {"door": [(100, 0), (200, 0), (200, 100), (100, 100)]}


def door_engine(**kwargs):
    return RuleEngine(DOOR, {}, zone_roles={"door": "door"}, **kwargs)


def test_walking_into_a_door_zones_image_area_is_neither_coming_in_nor_going_out():
    """A door far from the camera: someone walking TOWARD it crosses its image area, which says nothing about direction."""
    walk_toward = [obs(t, [track(1, 150, 200 - 90 * min(1.0, t / 2), t)]) for t in steps(0, 3)]       # from below the zone up into it
    coming = spec({"type": "enters_zone", "zone": "door"}, min_hold=0.4)
    going = spec({"type": "exits_zone", "zone": "door"}, min_hold=0.4)
    assert run(door_engine(), coming, walk_toward) == []
    assert run(door_engine(), going, walk_toward) == []                         # still standing in the doorway when the clip ends


def test_vanishing_inside_a_door_zone_is_going_out_and_vanishing_elsewhere_is_not():
    going = spec({"type": "exits_zone", "zone": "door"}, min_hold=0.4)
    left_through = [obs(t, [track(1, 150, 60, t)]) for t in steps(0, 2)] + [obs(t) for t in steps(2.2, 4)]
    fires = run(door_engine(), going, left_through)
    assert len(fires) == 1 and fires[0].tracks == (1,) and fires[0].ts >= 2.8     # gone for 0.8 s after the last sighting
    walked_away = [obs(t, [track(1, 150, 60, t)]) for t in steps(0, 1)] + [obs(t, [track(1, 400, 300, t)]) for t in steps(1.2, 2.4)] + [obs(t) for t in steps(2.6, 5)]
    assert run(door_engine(), going, walked_away) == []                           # left the doorway on foot, then out of view elsewhere
    flicker = [obs(0, [track(1, 150, 60, 0)]), obs(0.2, [track(1, 150, 60, 0.2)])] + [obs(t) for t in steps(0.4, 3)]
    assert run(door_engine(), going, flicker) == []                               # a track that lived 0.2 s is a flicker, not a person


def test_a_doorway_exempts_people_from_the_skeleton_requirement_nowhere_else():
    engine = door_engine(quality={"person": {"require_pose_support": True}})
    from td_contracts import ObservedTrack
    in_door = ObservedTrack.model_validate(track(1, 150, 80, 1.0, flags=["no_pose_support"]))
    elsewhere = ObservedTrack.model_validate(track(2, 400, 300, 1.0, flags=["no_pose_support"]))
    with_skeleton = ObservedTrack.model_validate(track(3, 400, 300, 1.0, flags=["pose_supported"]))
    assert engine.track_ok(in_door) and not engine.track_ok(elsewhere) and engine.track_ok(with_skeleton)


def test_a_chair_box_that_shrinks_when_someone_sits_does_not_move_the_seat():
    """Measured on real video: the detector's chair box went from backrest-to-floor to seat-and-legs once the man sat down."""
    engine = RuleEngine({}, {})
    rule = spec({"type": "sits_on", "object": {"cls": "chair"}}, min_hold=1.0)
    full, shrunk = [100, 100, 180, 200], [100, 135, 180, 200]               # the sitter hides the backrest: the box loses its top
    person = lambda t: track(1, 140, 200, t, h=160, w=70, keypoints=SEATED)
    chair = lambda t, box: track(5, 140, 200, t, cls="chair", bbox=box)
    frames = [obs(t, [chair(t, full)]) for t in steps(0, 0.6)] + [obs(t, [chair(t, shrunk), person(t)]) for t in steps(0.8, 4)]
    assert len(run(engine, rule, frames)) == 1


def test_a_door_opening_needs_someone_at_the_door_or_nobody_in_view():
    engine = door_engine()
    rule = spec({"type": "zone_changes", "zone": "door"}, entity="person", min_hold=0.4, cooldown=0)
    def frame(t, change, people):
        return Observation.model_validate({"camera_id": "cam", "ts": t, "frame_id": 1, "model_versions": {"detector": "t", "tracker": "t"},
                                           "tracks": people, "zone_change": {"door": change}})
    far = [track(1, 400, 500, 0.0, h=300)]                                           # in view, but nowhere near the door
    near = [track(1, 150, 105, 0.0, h=300)]                                          # at the door
    assert run(engine, rule, [frame(t, 0.6, [track(1, 400, 500, t, h=300)]) for t in steps(0, 2)]) == []
    assert len(run(door_engine(), rule, [frame(t, 0.6, [track(1, 150, 105, t, h=300)]) for t in steps(0, 2)])) == 1
    assert len(run(door_engine(), rule, [frame(t, 0.6, []) for t in steps(0, 2)])) == 1          # nobody in view: the door moved by itself
    # a person hiding the zone (-1) neither starts nor ends an alert
    state = RuleState()
    seq = [frame(t, 0.6, []) for t in steps(0, 1)] + [frame(t, -1.0, []) for t in steps(1.2, 2.4)] + [frame(t, 0.6, []) for t in steps(2.6, 4)]
    assert len([f for o in seq for f in door_engine().evaluate(rule, o, state) if isinstance(f, Fire)]) == 1
