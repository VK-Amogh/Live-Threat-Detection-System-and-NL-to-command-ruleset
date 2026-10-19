"""Explainable dry run: put a synthetic object through the real rule engine and say why a rule would (not) alert.

No camera, GPU or model is involved. The path is chosen from what the rule asks for (stand in a zone, cross a line,
approach a zone, a crowd crossing a line), the track is fed to `RuleEngine` frame by frame at the live processing
rate, and every leaf condition is then evaluated on the final frame so the answer reads like a checklist.
"""
from __future__ import annotations

from typing import Any

from td_contracts import Observation, ObservedTrack, RuleSpec, RuleWhen
from .engine import RuleEngine
from .geometry import centroid
from .readback import describe_when
from .state import Fire, RuleState

FPS = 5.0
MAX_STEPS = 700
DEFAULT_SIZE = (60.0, 160.0)   # width, height of the synthetic box in pixels


def _leaves(spec: RuleSpec) -> list[RuleWhen]:
    return list(spec.when.leaves()) if spec.when is not None else []


def _duration(spec: RuleSpec, requested: float | None) -> float:
    dwell = max([leaf.seconds or 0.0 for leaf in _leaves(spec) if leaf.type == "dwell_at_least"], default=0.0)
    window = max([min(leaf.window_s or 0.0, 20.0) for leaf in _leaves(spec) if leaf.type == "unique_count_at_least"], default=0.0)
    wanted = max(dwell, window, requested or 0.0) + max(spec.min_hold_s, 1.5) + 2.0
    return min(wanted, MAX_STEPS / FPS)


def _track(track_id: int, spec: RuleSpec, foot: tuple[float, float], velocity: tuple[float, float], first_seen: float, ts: float, conf: float) -> ObservedTrack:
    w, h = DEFAULT_SIZE
    return ObservedTrack(
        track_id=track_id, cls=spec.entity, conf=conf,
        bbox=(foot[0] - w / 2, foot[1] - h, foot[0] + w / 2, foot[1]),
        foot=foot, velocity=velocity, first_seen=first_seen, last_seen=ts)


def simulate(spec: RuleSpec, zones: dict, lines: dict, homography=None, synthetic: dict | None = None) -> dict[str, Any]:
    synthetic = synthetic or {}
    result: dict[str, Any] = {"rule_id": spec.rule_id, "matched": False, "reasons": [], "sub_results": [], "simulated_seconds": 0.0}
    if spec.when is None:
        result["reasons"].append(spec.unsupported_reason or "This rule has no executable conditions, so it can never alert.")
        return result

    conf = float(synthetic.get("confidence") or 0.92)
    leaves = _leaves(spec)
    kinds = {leaf.type for leaf in leaves}
    zone_names = [leaf.zone for leaf in leaves if leaf.zone in zones]
    line_names = [leaf.line for leaf in leaves if leaf.line in lines]
    center = centroid(zones[zone_names[0]]) if zone_names else (320.0, 300.0)
    notes: list[str] = []

    # Build the path: positions at each simulated frame, for one or several tracks.
    duration = _duration(spec, synthetic.get("dwell_seconds"))
    steps = int(duration * FPS)
    paths: dict[int, list[tuple[float, float]]] = {}
    if line_names and ("line_cross" in kinds or "unique_count_at_least" in kinds):
        (ax, ay), (bx, by) = lines[line_names[0]]
        mid = ((ax + bx) / 2, (ay + by) / 2)
        dx, dy = bx - ax, by - ay
        norm = max((dx * dx + dy * dy) ** 0.5, 1.0)
        nx, ny = -dy / norm, dx / norm            # unit normal to the line
        crowd = max([leaf.count or 1 for leaf in leaves if leaf.type == "unique_count_at_least"], default=1)
        crossing_frames = int(1.6 * FPS)
        for index in range(crowd):
            start_frame = int(index * 0.6 * FPS) + 1
            points = []
            for frame in range(steps):
                progress = min(max((frame - start_frame) / crossing_frames, 0.0), 1.0)
                offset = -45 + 90 * progress
                points.append((mid[0] + nx * offset + index * 6, mid[1] + ny * offset))
            paths[index + 1] = points
        notes.append(f"{crowd} test {spec.entity}(s) walk across line '{line_names[0]}'")
    elif "moving_toward" in kinds and zone_names:
        for frame in range(steps):
            progress = min(frame / max(steps * 0.6, 1.0), 1.0)
            paths.setdefault(1, []).append((center[0] - 160 * (1 - progress), center[1]))
        notes.append(f"one test {spec.entity} walks toward zone '{zone_names[0]}'")
    else:
        spot = center
        if not zone_names and synthetic.get("bbox"):
            x1, y1, x2, y2 = synthetic["bbox"]
            spot = ((x1 + x2) / 2, y2)
        paths[1] = [spot] * steps
        notes.append(f"one test {spec.entity} stands " + (f"inside zone '{zone_names[0]}'" if zone_names else "in view"))

    # The schedule is reported separately: the point of a test is whether the CONDITIONS would alert, not what time it is.
    tested = spec.model_copy(update={"status": "active", "schedule": None})
    engine = RuleEngine(zones, lines, homography)
    state = RuleState()
    start_ts = 1_000_000.0
    fired_at: float | None = None
    last_tracks: list[ObservedTrack] = []
    for frame in range(steps):
        ts = start_ts + frame / FPS
        tracks = []
        for track_id, path in paths.items():
            if frame >= len(path):
                continue
            prev = path[frame - 1] if frame else path[frame]
            velocity = ((path[frame][0] - prev[0]) * FPS, (path[frame][1] - prev[1]) * FPS)
            tracks.append(_track(track_id, spec, path[frame], velocity, start_ts, ts, conf))
        last_tracks = tracks
        observation = Observation(camera_id=spec.camera_id, ts=ts, frame_id=frame, tracks=tracks,
                                  model_versions={"detector": "synthetic", "tracker": "synthetic"})
        for outcome in engine.evaluate(tested, observation, state):
            if isinstance(outcome, Fire) and fired_at is None:
                fired_at = ts - start_ts
        if fired_at is not None:
            break
    result["simulated_seconds"] = round(((ts - start_ts) if steps else 0.0) + 1 / FPS, 2)
    result["matched"] = fired_at is not None

    # Checklist: each leaf on the final frame, in the words of the readback.
    final_ts = start_ts + max(steps - 1, 0) / FPS if fired_at is None else start_ts + fired_at
    focus = next((t for t in last_tracks), None)
    item = state.tracks.get(focus.track_id) if focus else None
    for leaf in leaves:
        try:
            ok = bool(engine._condition(leaf, focus, None, item, final_ts, state))
        except Exception:
            ok = False
        phrase = describe_when(leaf)
        result["sub_results"].append({"predicate": phrase, "matched": ok, "reason": _why(leaf, ok, zones, lines, fired_at, duration)})

    if fired_at is not None:
        result["reasons"].append(f"Would alert about {fired_at:.1f} s after the first test {spec.entity} appears ({'; '.join(notes)}).")
    else:
        failed = [s for s in result["sub_results"] if not s["matched"]]
        if failed:
            result["reasons"].extend(f"Not met: {s['predicate']} — {s['reason']}" for s in failed)
        else:
            result["reasons"].append("Every condition holds at the end of the test, but the hold time or cooldown was not reached.")
        result["reasons"].append("Test: " + "; ".join(notes) + ".")
    if spec.schedule:
        result["reasons"].append("The rule only runs inside its schedule (" + _schedule_text(spec.schedule) + "); this test ignores the time of day.")
    return result


def _why(leaf: RuleWhen, ok: bool, zones: dict, lines: dict, fired_at: float | None, duration: float) -> str:
    if ok:
        return "satisfied"
    if leaf.type in ("in_zone", "moving_toward", "distance_below") and leaf.zone not in zones:
        return f"zone '{leaf.zone}' is not drawn for this camera"
    if leaf.type in ("line_cross", "unique_count_at_least") and leaf.line not in lines:
        return f"line '{leaf.line}' is not drawn for this camera"
    if leaf.type == "dwell_at_least":
        return f"the test object did not stay {leaf.seconds:g} s within the simulated {duration:.0f} s"
    if leaf.type == "time_window":
        return "outside this time window"
    return "not satisfied by the test object"


def _schedule_text(schedule: dict) -> str:
    days = ", ".join(d.title() for d in (schedule.get("days") or [])) or "every day"
    return f"{schedule.get('start_time', '00:00')}–{schedule.get('end_time', '23:59')}, {days}"
