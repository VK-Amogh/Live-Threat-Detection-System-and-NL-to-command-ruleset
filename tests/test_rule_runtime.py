"""Shared rule runtime: blur gate, camera-motion guard, verification candidates with evidence packs, and question templates."""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT), str(ROOT / "tests")]
from td_contracts import CameraGeometry, Observation, RuleSpec
from services.rules.evidence import EvidenceBuffer
from services.rules.runtime import RuleRuntime
from services.rules.scene_guard import SceneGuard, sharpness
from services.rules.verify_questions import QUESTIONS, load_pack, render

CONFIG = {"quality": {"blur_min_laplacian_var": 100}, "scene_guard": {"enabled": False}}
GEOMETRY = CameraGeometry(snapshot_width=320, snapshot_height=240, zones={"z": [(0, 0), (320, 0), (320, 240), (0, 240)]})


def textured(seed=0, width=320, height=240):
    rng = np.random.RandomState(seed)
    frame = np.full((height, width, 3), 90, dtype="uint8")
    for _ in range(160):
        center = (int(rng.randint(0, width)), int(rng.randint(0, height)))
        cv2.circle(frame, center, int(rng.randint(3, 14)), tuple(int(c) for c in rng.randint(0, 255, 3)), -1)
    return frame


def jpeg(frame):
    return cv2.imencode(".jpg", frame)[1].tobytes()


def observation(ts, x=160):
    return Observation.model_validate({"camera_id": "cam", "ts": ts, "frame_id": round(ts * 10), "model_versions": {"detector": "t", "tracker": "t"},
                                       "tracks": [{"track_id": 1, "cls": "person", "conf": .9, "score": .9, "bbox": [x - 20, 60, x + 20, 200], "foot": [x, 200],
                                                   "velocity": [0, 0], "first_seen": 0.0, "last_seen": ts, "flags": []}]})


def rule(**extra):
    return RuleSpec.model_validate({"rule_id": "r1", "camera_id": "cam", "version": 1, "name": "in z", "entity": "person",
                                    "when": {"type": "in_zone", "zone": "z"}, "min_hold_s": 0.4, "cooldown_s": 60,
                                    "support_level": "SUPPORTED", "status": "active", **extra})


def drive(runtime, evidence, frames):
    events = []
    for ts, frame in frames:
        evidence.append(ts, jpeg(frame))
        events += runtime.process(frame, observation(ts), ts, jpeg(frame))
    return events


def steps(stop, dt=0.2):
    return [round(i * dt, 3) for i in range(int(stop / dt) + 1)]


def test_geometry_rule_is_verified_with_its_evidence(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", CONFIG, evidence)
    runtime.configure([rule()], GEOMETRY)
    base = textured()
    events = drive(runtime, evidence, [(t, base) for t in steps(2)])
    assert len(events) == 1
    verification = events[0].verification
    assert verification.status == "verified" and verification.method == "geometry" and verification.verified_ts is not None
    assert any("mean detector score" in check for check in verification.checks)
    assert events[0].evidence_bbox is not None


def test_visual_candidate_waits_for_its_evidence_pack(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", CONFIG, evidence)
    runtime.configure([rule(verification={"method": "vlm", "vlm_question": "sits_on"})], GEOMETRY)
    base = textured()
    seen = []
    fire_ts = None
    for t in steps(3):
        evidence.append(t, jpeg(base))
        emitted = runtime.process(base, observation(t, x=160 + int(t * 10)), t, jpeg(base))
        if runtime.pending and fire_ts is None:
            fire_ts = t
        seen += [(t, event) for event in emitted]
    assert len(seen) == 1 and fire_ts is not None
    when, event = seen[0]
    assert event.verification.status == "candidate" and event.verification.method == "vlm" and when > fire_ts
    pack = json.loads((tmp_path / event.event_id / "pack.json").read_text())["frames"]
    assert 3 <= len(pack) <= 5 and all(item["bbox"] for item in pack)
    assert pack[0]["bbox"] != pack[-1]["bbox"]                     # each frame carries the subject box of that frame
    images = load_pack(tmp_path / event.event_id)
    assert len(images) == 3 and all(cv2.imdecode(np.frombuffer(i, dtype="uint8"), cv2.IMREAD_COLOR) is not None for i in images)


def test_blurred_or_blank_frames_never_start_an_alert(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", CONFIG, evidence)
    runtime.configure([rule()], GEOMETRY)
    blank = np.full((240, 320, 3), 20, dtype="uint8")
    assert sharpness(blank) < 1 < sharpness(textured())
    assert drive(runtime, evidence, [(t, blank) for t in steps(3)]) == []


def test_scene_guard_suspends_on_motion_and_resumes_when_steady():
    guard = SceneGuard(max_shift_rel=0.04, min_matches=12)
    base = textured(3)
    moved = np.roll(base, 40, axis=1)
    assert not guard.update(base).suspended
    assert not guard.update(base).suspended
    assert not guard.update(moved).suspended                         # one moved frame is not enough
    assert guard.update(moved).suspended
    assert guard.update(base).suspended and guard.update(base).suspended
    assert not guard.update(base).suspended                          # three steady frames resume


def test_scene_guard_notices_a_rotated_phone():
    guard = SceneGuard()
    guard.reset((320, 240))                                         # geometry was drawn in landscape
    portrait = textured(5, width=240, height=320)
    assert not guard.update(portrait).suspended
    assert guard.update(portrait).suspended and "orientation" in guard.reason


def test_runtime_pauses_geometry_rules_and_reports_the_move_once(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", {"quality": {}, "scene_guard": {"enabled": True, "max_shift_rel": 0.04}}, evidence)
    runtime.configure([rule(min_hold_s=1.0)], GEOMETRY)          # a bump during the hold window must stop the alert
    base, moved = textured(7), np.roll(textured(7), 90, axis=1)          # 28% of the width: beyond even the loose tolerance
    frames = [(0.0, base), (0.2, base), (0.4, moved), (0.6, moved), (0.8, moved), (1.0, moved), (1.2, moved), (1.4, moved), (1.6, moved), (1.8, moved)]
    assert drive(runtime, evidence, frames) == []
    health = runtime.drain_health()
    assert len(health) == 1 and health[0].kind == "camera_moved"


def test_question_templates_shuffle_decode_and_abstain():
    for question_id in QUESTIONS:
        first = render(question_id, "the chair", seed=1)
        assert sorted(first.letters.values()) == ["abstain", "negative", "negative", "positive"] and first.order[-1] == "abstain"
        assert any(render(question_id, "x", seed=s).order != first.order for s in range(2, 40))     # position is not fixed
        letter = next(l for l, kind in first.letters.items() if kind == "positive")
        assert first.decode({"answer": letter.lower()}) == "positive"
        assert first.decode({"answer": next(l for l, k in first.letters.items() if k == "abstain")}) == "abstain"
        for bad in ({"answer": "Z"}, {"answer": ""}, {}):
            try:
                first.decode(bad)
            except ValueError:
                continue
            raise AssertionError("an unusable answer was accepted")
    assert "the chair" in render("sits_on", "the chair", seed=1).prompt


def test_geometry_is_scaled_to_the_live_frame_and_paused_when_the_shape_differs(tmp_path):
    left_half = CameraGeometry(snapshot_width=320, snapshot_height=240, zones={"z": [(0, 0), (160, 0), (160, 240), (0, 240)]})
    rule_in_z = rule(min_hold_s=0.4)

    def run(width, height, x):
        evidence = EvidenceBuffer(tmp_path / f"{width}-{x}", 5, 2, 0.4)
        runtime = RuleRuntime("cam", {"quality": {}, "scene_guard": {"enabled": False}}, evidence)
        runtime.configure([rule_in_z], left_half)
        frame = textured(1, width=width, height=height)
        events = []
        for t in steps(1.4):
            evidence.append(t, jpeg(frame))
            obs = Observation.model_validate({"camera_id": "cam", "ts": t, "frame_id": 1, "model_versions": {"detector": "t", "tracker": "t"},
                                              "tracks": [{"track_id": 1, "cls": "person", "conf": .9, "bbox": [x - 20, height - 120, x + 20, height - 40],
                                                          "foot": [x, height - 40], "velocity": [0, 0], "first_seen": 0.0, "last_seen": t}]})
            events += runtime.process(frame, obs, t, jpeg(frame))
        return events, runtime

    inside, _ = run(640, 480, 200)          # x=200 of 640 is x=100 of 320: inside the drawn half
    outside, _ = run(640, 480, 400)         # x=400 of 640 is x=200 of 320: outside
    assert len(inside) == 1 and outside == []
    rotated, runtime = run(240, 320, 100)   # a portrait frame for a landscape drawing: the drawing does not apply
    assert rotated == [] and runtime.size_mismatch and runtime.drain_health()[0].kind == "camera_moved"


def test_require_pose_support_makes_the_runtime_load_pose_and_gates_tracks_without_a_skeleton(tmp_path):
    from types import SimpleNamespace
    from services.rules.engine import RuleEngine
    from services.rules.pose import PoseEstimator, skeleton_ok
    from services.rules.state import RuleState

    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", {"quality": {"person": {"require_pose_support": True}}, "scene_guard": {"enabled": False}}, evidence)
    runtime.configure([rule()], GEOMETRY)
    assert runtime.needs_pose                                   # a plain "person in zone" rule now needs skeletons to vouch for its tracks
    runtime.configure([rule(entity="car")], GEOMETRY)
    assert not runtime.needs_pose                               # other classes are not asked for one

    skeleton = [(0.0, 0.0, 0.9)] * 17                           # a coherent person: nose, shoulders and hips are confident
    class FakePose:
        def predict(self, frame, **kwargs):
            data = SimpleNamespace(tolist=lambda: [[list(point) for point in skeleton]])
            boxes = SimpleNamespace(xyxy=SimpleNamespace(tolist=lambda: [[100.0, 60.0, 140.0, 200.0]]))
            return [SimpleNamespace(keypoints=SimpleNamespace(data=data), boxes=boxes)]
    estimator = object.__new__(PoseEstimator)
    estimator.model, estimator.imgsz, estimator.conf = FakePose(), 640, 0.3
    assert skeleton_ok(skeleton) and not skeleton_ok([(0.0, 0.0, 0.2)] * 17) and not skeleton_ok(None)

    def person(ident, box, flags=()):
        return {"track_id": ident, "cls": "person", "conf": .9, "score": .9, "bbox": box, "foot": [(box[0] + box[2]) / 2, box[3]],
                "velocity": [0, 0], "first_seen": 0.0, "last_seen": 1.0, "flags": list(flags)}
    observation = Observation.model_validate({"camera_id": "cam", "ts": 1.0, "frame_id": 1, "model_versions": {"detector": "t", "tracker": "t"},
                                              "tracks": [person(1, [100, 60, 140, 200], ["oversized"]), person(2, [200, 60, 240, 200])]})
    attached = estimator.attach(textured(), observation)
    first, second = attached.tracks
    assert "pose_supported" in first.flags and "oversized" not in first.flags      # a real, very close person is rescued
    assert "no_pose_support" in second.flags                                        # a "person" with no skeleton is not
    engine = RuleEngine({}, {}, quality={"person": {"require_pose_support": True}})
    assert engine.track_ok(first) and not engine.track_ok(second)


def test_zone_watcher_sees_a_door_move_but_not_a_lighting_change():
    from services.rules.zone_watch import ZoneWatcher
    watcher = ZoneWatcher()
    door = {"door": [(100, 40), (220, 40), (220, 220), (100, 220)]}
    base = textured(11)
    assert watcher.measure(base, door, {"door"}, 0.0) == {"door": 0.0}
    brighter = np.clip(base.astype(np.int16) + 35, 0, 255).astype("uint8")             # auto-exposure moves every pixel together
    assert watcher.measure(brighter, door, {"door"}, 0.2)["door"] < 0.05
    opened = base.copy()
    cv2.rectangle(opened, (100, 40), (220, 220), (230, 230, 230), -1)                  # the door leaf is gone: a different picture
    cv2.circle(opened, (160, 130), 40, (10, 10, 10), -1)
    assert watcher.measure(opened, door, {"door"}, 0.4)["door"] > 0.5
    watcher.measure(opened, door, {"door"}, 20.0)                                       # left open for a while: that becomes normal
    assert watcher.measure(opened, door, {"door"}, 20.2)["door"] < 0.05
    assert watcher.measure(base, door, {"door"}, 20.4)["door"] > 0.3                    # and closing it is a change again


def test_runtime_alerts_when_the_door_area_changes(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", {"quality": {}, "scene_guard": {"enabled": False}}, evidence)
    door_zone = CameraGeometry(snapshot_width=320, snapshot_height=240, zones={"door": [(100, 40), (220, 40), (220, 220), (100, 220)]}, zone_roles={"door": "door"})
    watcher_rule = RuleSpec.model_validate({"rule_id": "r_open", "camera_id": "cam", "version": 1, "name": "door opens", "entity": "person", "when": {"type": "zone_changes", "zone": "door"},
                                            "min_hold_s": 0.4, "cooldown_s": 60, "support_level": "EXPERIMENTAL", "status": "active"})
    runtime.configure([watcher_rule], door_zone)
    base = textured(21)
    opened = base.copy()
    cv2.rectangle(opened, (100, 40), (220, 220), (225, 225, 225), -1)
    cv2.circle(opened, (150, 120), 35, (15, 15, 15), -1)
    events = []
    for t in steps(3):
        frame = base if t < 1.0 else opened
        evidence.append(t, jpeg(frame))
        events += runtime.process(frame, Observation.model_validate({"camera_id": "cam", "ts": t, "frame_id": 1, "tracks": [], "model_versions": {"detector": "t", "tracker": "t"}}), t, jpeg(frame))
    assert len(events) == 1 and events[0].verification.status == "verified" and events[0].tracks == []


def test_hand_movement_pauses_door_opening_but_not_detection_based_rules(tmp_path):
    evidence = EvidenceBuffer(tmp_path, 5, 2, 0.4)
    runtime = RuleRuntime("cam", {"quality": {}, "scene_guard": {"enabled": True, "max_shift_rel": 0.04, "loose_shift_rel": 0.15}}, evidence)
    opens = RuleSpec.model_validate({"rule_id": "r_open", "camera_id": "cam", "version": 1, "name": "opens", "entity": "person", "when": {"type": "zone_changes", "zone": "z"},
                                     "min_hold_s": 0.4, "support_level": "EXPERIMENTAL", "status": "active"})
    runtime.configure([rule(), opens], GEOMETRY)
    base, nudged = textured(31), np.roll(textured(31), 40, axis=1)         # 12.5% of the width
    for t, frame in ((0.0, base), (0.2, base), (0.4, nudged), (0.6, nudged), (0.8, nudged)):
        evidence.append(t, jpeg(frame))
        runtime.process(frame, observation(t), t, jpeg(frame))
    assert runtime.suspended and not runtime.suspended_loose              # strict: paused; loose: still running
    assert runtime.strict_rules == {"r_open"}


def test_zone_watcher_ignores_people_and_judges_exposure_on_the_background():
    from services.rules.zone_watch import ZoneWatcher
    watcher = ZoneWatcher()
    door = {"door": [(100, 40), (220, 40), (220, 220), (100, 220)]}
    base = textured(41)
    assert watcher.measure(base, door, {"door"}, 0.0, []) == {"door": 0.0}
    # a dark person walks into the doorway while the phone raises its exposure: the background is brighter, the person darker
    scene = np.clip(base.astype(np.int16) + 25, 0, 255).astype("uint8")
    cv2.rectangle(scene, (120, 60), (190, 220), (8, 8, 8), -1)
    person_box = [(112, 52, 198, 224)]
    assert watcher.measure(scene, door, {"door"}, 0.2, person_box)["door"] < 0.1       # not a door opening
    covered = [(95, 35, 225, 225)]
    assert watcher.measure(scene, door, {"door"}, 0.4, covered)["door"] == -1.0       # a person hides the zone: unknown, not "no change"
    unchanged = watcher.measure(np.clip(base.astype(np.int16) + 25, 0, 255).astype("uint8"), door, {"door"}, 0.6, [])
    assert unchanged["door"] < 0.1                                                    # the person's pixels were never learned as background
