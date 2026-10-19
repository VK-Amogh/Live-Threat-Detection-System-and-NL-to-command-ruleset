"""Pure rule evaluator over validated observations and geometry."""

from datetime import datetime, time
from math import hypot

from dateutil.zoneinfo import get_zonefile_instance

from td_contracts import Observation, ObservedTrack, RuleSpec, RuleWhen
from . import interactions
from .geometry import box_coverage, box_iou, centroid, cross_direction, crosses_line, distance_to_polygon, homography_point, in_polygon
from .state import AnchorState, Fire, Health, RuleState, TrackState, ZoneTrack

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GEOMETRY_TYPES = {"in_zone", "line_cross", "unique_count_at_least", "moving_toward", "distance_below", "enters_zone",
                  "exits_zone", "near_object", "touches_object", "sits_on", "picks_up", "object_absent", "count_in_zone_at_least", "zone_changes"}
IMPULSE_TYPES = {"line_cross", "enters_zone", "exits_zone"}
CAMERA_LEVEL_TYPES = {"object_absent", "time_window", "count_in_zone_at_least", "zone_changes"}
EPISODE_CAMERA_TYPES = {"object_absent", "count_in_zone_at_least", "zone_changes"}   # alert once until the condition clears
ZONE_CONFIRM_S = 0.6        # a zone flip must persist this long before it counts as an entry or exit
ZONE_ORIGIN_S = 0.4         # a track must have been seen on the other side this long for an entry or exit to count
LOST_EXIT_S = 0.8           # a track that vanishes inside a door zone for this long has gone out through it
EXIT_WINDOW_S = 3.0         # exits_zone stays true this long after the exit is confirmed
STEP_HOLD_S = 0.8           # a non-impulse sequence step must hold this long before the sequence advances
SEQUENCE_DONE_S = 2.0       # a completed sequence stays true this long so the normal hold logic can fire it
ANCHOR_MATCH_IOU = 0.3
ANCHOR_OCCLUDED_COVERAGE = 0.2
ZONE_CHANGE_FIRE = 0.30      # share of a watched zone that must differ from its baseline
DOOR_REACH_REL = 0.12        # when people are in view, one must stand within this many body heights of the zone for a change to be a door opening
CLASS_MEMORY_S = 20.0        # a remembered object is kept this long when nothing hides it ...
CLASS_HIDDEN_MEMORY_S = 600.0  # ... and much longer while a person stands over it (a seated person covers the chair)


class RuleEngine:
    def __init__(self, zones: dict[str, list[tuple[float, float]]],
                 lines: dict[str, tuple[tuple[float, float], tuple[float, float]]],
                 homography: list[list[float]] | None = None,
                 anchors: dict | None = None, quality: dict | None = None, zone_roles: dict | None = None):
        self.zone_roles = zone_roles or {}
        self._zone_change: dict[str, float] = {}
        self._now = 0.0
        self.zones = zones
        self.lines = lines
        self.homography = homography
        self.anchors = anchors or {}
        self.quality = quality or {}
        self._tracks: list[ObservedTrack] = []
        self._actors: set[str] = set()

    def _schedule_allows(self, schedule: dict | None, ts: float) -> bool:
        if not schedule:
            return True
        tz_name = schedule.get("timezone", "local")
        zone = None
        if tz_name and tz_name != "local":
            zone = get_zonefile_instance().get(tz_name)
        dt = datetime.fromtimestamp(ts, zone) if zone else datetime.fromtimestamp(ts).astimezone()
        days = [d.lower()[:3] for d in (schedule.get("days") or _DAY_NAMES)]
        start_str = schedule.get("start_time", "00:00")
        end_str = schedule.get("end_time", "23:59")
        try:
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
        except ValueError:
            return True
        current = dt.time().replace(tzinfo=None)
        day_name = _DAY_NAMES[dt.weekday()]
        if start <= end:
            if day_name not in days:
                return False
            return start <= current <= end
        else:
            # Overnight window (e.g., 22:00 -> 06:00)
            if current >= start:
                return day_name in days
            if current <= end:
                prev_day = _DAY_NAMES[(dt.weekday() - 1) % 7]
                return day_name in days or prev_day in days
            return False

    def _time_window(self, node: RuleWhen, ts: float) -> bool:
        zone = get_zonefile_instance().get(node.tz)
        current = datetime.fromtimestamp(ts, zone).time().replace(tzinfo=None)
        start, end = time.fromisoformat(node.start), time.fromisoformat(node.end)
        return start <= current < end if start < end else current >= start or current < end

    # --- track plausibility -----------------------------------------------------------------------------------

    def track_ok(self, track: ObservedTrack) -> bool:
        """A detection that is implausible for its class (tiny score, filling the frame, no skeleton) is not a track.

        Thresholds come from config/rules.yaml `quality:`; with none configured every track passes."""
        config = self.quality.get(track.cls) or self.quality.get("default") or {}
        if track.score is not None and track.score < config.get("min_track_score", 0):
            return False
        if "oversized" in track.flags or "border" in track.flags:
            return False
        if config.get("require_pose_support") and "no_pose_support" in track.flags:
            # Someone in a doorway is partly hidden by the door or its frame and often side-on, so the pose model finds no
            # full skeleton for a few frames (measured: 0.8 s of a real entry). Only there is the skeleton requirement waived;
            # the score and size gates still apply, and a "person" without a skeleton anywhere else is still not vouched for.
            return self._in_door(track)
        return True

    def _in_door(self, track: ObservedTrack) -> bool:
        centre = ((track.bbox[0] + track.bbox[2]) / 2, (track.bbox[1] + track.bbox[3]) / 2)
        return any(self.zone_roles.get(name) == "door" and (in_polygon(track.foot, polygon) or in_polygon(centre, polygon))
                   for name, polygon in self.zones.items())

    # --- anchors ----------------------------------------------------------------------------------------------

    def _update_anchors(self, spec: RuleSpec, state: RuleState, ts: float):
        """Presence of each user-confirmed object the rule refers to. Absence accumulates only while the object's
        region is not covered by a person, so standing in front of it never counts as it disappearing."""
        people = [t for t in self._tracks if t.cls == "person"]
        for name in {leaf.object.anchor for leaf in spec.when.leaves() if leaf.object is not None and leaf.object.anchor}:
            anchor = self.anchors.get(name)
            if anchor is None:
                continue
            item = state.anchors.setdefault(name, AnchorState(box=tuple(anchor.bbox)))
            best, best_iou = None, 0.0
            for track in self._tracks:
                if track.cls == anchor.cls:
                    overlap = box_iou(track.bbox, anchor.bbox)
                    if overlap > best_iou:
                        best, best_iou = track, overlap
            item.occluded = any(box_coverage(person.bbox, anchor.bbox) > ANCHOR_OCCLUDED_COVERAGE for person in people)
            if best is not None and best_iou >= ANCHOR_MATCH_IOU:
                item.present, item.absent_since, item.last_present, item.box = True, None, ts, tuple(best.bbox)
            elif item.occluded:
                item.present, item.absent_since = False, None
            else:
                item.present = False
                item.absent_since = ts if item.absent_since is None else item.absent_since

    def _update_class_memory(self, spec: RuleSpec, state: RuleState, ts: float):
        """Objects named by class ("a chair") are remembered: once someone sits down the detector stops seeing the chair,
        but the rule still has to know where it was."""
        people = [t for t in self._tracks if t.cls == "person"]
        for cls in {leaf.object.cls for leaf in spec.when.leaves() if leaf.object is not None and leaf.object.cls}:
            memory = state.cls_memory.setdefault(cls, [])
            for track in [t for t in self._tracks if t.cls == cls]:
                best = max(memory, key=lambda entry: max(box_iou(track.bbox, entry[0]), box_coverage(entry[0], track.bbox)), default=None)
                if best is not None and (box_iou(track.bbox, best[0]) >= 0.4 or box_coverage(best[0], track.bbox) >= 0.7):
                    covered = any(box_coverage(person.bbox, best[0]) > ANCHOR_OCCLUDED_COVERAGE for person in people)
                    if not covered:                      # a seated person hides the backrest: the detector's box shrinks, the chair did not
                        best[0] = tuple(track.bbox)
                    best[1] = ts
                else:
                    memory.append([tuple(track.bbox), ts])
            keep = []
            for entry in memory:
                hidden = any(box_coverage(person.bbox, entry[0]) > ANCHOR_OCCLUDED_COVERAGE for person in people)
                age = ts - entry[1]
                if entry[1] == ts or age <= CLASS_MEMORY_S or (hidden and age <= CLASS_HIDDEN_MEMORY_S):
                    keep.append(entry)
            state.cls_memory[cls] = keep[-16:]

    def _remembered(self, cls: str, state: RuleState) -> list[tuple[str, tuple]]:
        return [(f"{cls}:m{index}", entry[0]) for index, entry in enumerate(state.cls_memory.get(cls, [])) if entry[1] != self._now]

    def _object_boxes(self, node: RuleWhen, track: ObservedTrack, state: RuleState) -> list[tuple[str, tuple]]:
        ref = node.object
        if ref.anchor:
            anchor = self.anchors.get(ref.anchor)
            if anchor is None:
                return []
            item = state.anchors.get(ref.anchor)
            return [(ref.anchor, item.box if item is not None and item.box else tuple(anchor.bbox))]
        return [(f"{ref.cls}:m{index}", entry[0]) for index, entry in enumerate(state.cls_memory.get(ref.cls, []))]   # memory holds every one, seen now or not

    def _seat_siblings(self, node: RuleWhen, box, state: RuleState) -> list[tuple]:
        if not node.object.anchor:
            return [entry[0] for entry in state.cls_memory.get(node.object.cls, []) if tuple(entry[0]) != tuple(box)]
        own = self.anchors[node.object.anchor]
        return [tuple(a.bbox) for name, a in self.anchors.items() if name != node.object.anchor and a.cls == own.cls]

    # --- zone transitions -------------------------------------------------------------------------------------

    def _step_zone(self, zone_track: ZoneTrack, inside: bool, ts: float, door: bool = False):
        zone_track.last_inside = inside
        if zone_track.inside is None:
            zone_track.inside, zone_track.since = inside, ts      # born here: no origin evidence either way ...
            if inside and door:
                zone_track.entered_at = ts                        # ... except in a doorway, where someone who appears has just come in
            return
        if inside == zone_track.inside:
            zone_track.pending = None
            return
        if zone_track.pending is None or zone_track.pending[0] != inside:
            zone_track.pending = (inside, ts)
        if ts - zone_track.pending[1] >= ZONE_CONFIRM_S:
            before = zone_track.pending[1] - zone_track.since
            zone_track.inside, zone_track.since, zone_track.pending = inside, zone_track.pending[1], None
            if door:
                # A door is where people appear and vanish. Walking into or out of its image area says nothing about
                # direction (someone walking TOWARD a far door also "enters" it), so only appearing counts as coming in
                # and only vanishing counts as going out.
                zone_track.entered_at = zone_track.exited_at = None
                return
            seen_long_enough = before >= ZONE_ORIGIN_S
            if inside:
                zone_track.entered_at, zone_track.exited_at = (ts if seen_long_enough else None), None
            else:
                zone_track.exited_at, zone_track.entered_at = (ts if seen_long_enough else None), None

    def _update_transitions(self, spec: RuleSpec, track: ObservedTrack, state: TrackState, ts: float):
        for zone in {leaf.zone for leaf in spec.when.leaves() if leaf.type in ("enters_zone", "exits_zone")}:
            if zone in self.zones:
                self._step_zone(state.zones.setdefault(zone, ZoneTrack()), in_polygon(track.foot, self.zones[zone]), ts,
                                door=self.zone_roles.get(zone) == "door")

    # --- conditions -------------------------------------------------------------------------------------------

    def _condition(self, node: RuleWhen, track: ObservedTrack | None, previous: tuple[float, float] | None,
                   state: TrackState | None, ts: float, rule_state: RuleState) -> bool:
        if node.all is not None:
            return all(self._condition(child, track, previous, state, ts, rule_state) for child in node.all)
        if node.any is not None:
            return any(self._condition(child, track, previous, state, ts, rule_state) for child in node.any)
        if node.not_ is not None:
            return not self._condition(node.not_, track, previous, state, ts, rule_state)
        if node.sequence is not None:
            return self._sequence(node, track, previous, state, ts, rule_state)
        if node.type == "time_window":
            return self._time_window(node, ts)
        if node.type == "entity_present":
            return track is not None
        if node.type == "object_absent":
            item = rule_state.anchors.get(node.object.anchor) if node.object and node.object.anchor else None
            return item is not None and item.absent_for(ts) >= (node.seconds or 0)
        if node.type == "zone_changes":
            value = self._zone_change.get(node.zone, 0.0)
            if value < 0:                      # a person hides the zone: nothing can be judged, so keep the previous answer
                return rule_state.zone_change_last.get(node.zone, False)
            polygon = self.zones.get(node.zone)
            people = [t for t in self._tracks if t.cls == "person"]
            if value >= ZONE_CHANGE_FIRE and polygon and people and not any(
                    distance_to_polygon(t.foot, polygon) <= DOOR_REACH_REL * max(1.0, t.bbox[3] - t.bbox[1]) for t in people):
                value = 0.0                    # people are in view but none is at the door: a reflection or shadow, not someone opening it
            rule_state.zone_change_last[node.zone] = value >= ZONE_CHANGE_FIRE
            return value >= ZONE_CHANGE_FIRE
        if node.type == "count_in_zone_at_least":
            inside = [t for t in self._tracks if t.cls in self._actors
                      and (not node.zone or (node.zone in self.zones and in_polygon(t.foot, self.zones[node.zone])))]
            return len(inside) >= node.count
        if track is None:
            return False
        if node.type == "in_zone":
            return node.zone in self.zones and in_polygon(track.foot, self.zones[node.zone])
        if node.type == "line_cross":
            if previous is None or node.line not in self.lines:
                return False
            if node.direction in ("a_to_b", "b_to_a"):
                return cross_direction(previous, track.foot, self.lines[node.line]) == node.direction
            return crosses_line(previous, track.foot, self.lines[node.line])
        if node.type == "enters_zone":
            zone = state.zones.get(node.zone) if state else None
            return zone is not None and zone.inside is True and zone.entered_at is not None
        if node.type == "exits_zone":
            zone = state.zones.get(node.zone) if state else None
            return zone is not None and zone.inside is False and zone.exited_at is not None and ts - zone.exited_at <= EXIT_WINDOW_S
        if node.type in ("near_object", "touches_object", "sits_on", "picks_up"):
            return self._person_object(node, track, state, ts, rule_state)
        if node.type == "unique_count_at_least":
            if previous is not None and node.line in self.lines and crosses_line(previous, track.foot, self.lines[node.line]):
                crossings = rule_state.count_crossings.setdefault(node.line, [])
                if not any(ident == track.track_id for _, ident in crossings):
                    crossings.append((ts, track.track_id))
            crossings = rule_state.count_crossings.setdefault(node.line, [])
            crossings[:] = [(when, ident) for when, ident in crossings if ts - when <= node.window_s]
            return len({ident for _, ident in crossings}) >= node.count
        if node.type == "dwell_at_least":
            if state is None:
                return False
            start = min(state.zone_since.values()) if state.zone_since else state.first_seen
            return ts - start >= node.seconds
        if node.type == "moving_toward":
            if node.zone not in self.zones:
                return False
            target = centroid(self.zones[node.zone])
            vx, vy = track.velocity
            dx, dy = target[0] - track.foot[0], target[1] - track.foot[1]
            height = max(1.0, track.bbox[3] - track.bbox[1])
            # Jitter is not approach: the speed must be at least a quarter of the person's height per second.
            return vx * dx + vy * dy > 0 and hypot(vx, vy) >= max(5, 0.25 * height) and hypot(dx, dy) > 5
        if node.type == "distance_below":
            if self.homography is None or node.zone not in self.zones:
                return False
            world_point = homography_point(track.foot, self.homography)
            world_zone = [homography_point(point, self.homography) for point in self.zones[node.zone]]
            return distance_to_polygon(world_point, world_zone) < node.meters
        raise ValueError(f"Unknown condition: {node.type}")

    def _person_object(self, node: RuleWhen, track: ObservedTrack, state: TrackState, ts: float, rule_state: RuleState) -> bool:
        boxes = self._object_boxes(node, track, rule_state)
        if node.type == "near_object":
            return any(interactions.near(track, box) for _, box in boxes)
        if node.type == "touches_object":
            return any(interactions.touches(track, box) for _, box in boxes)
        if node.type == "sits_on":
            for _, box in boxes:
                ok, hips, torso = interactions.seated_on(track, box, self._seat_siblings(node, box, rule_state))
                if hips is not None:
                    state.hips = [h for h in state.hips if ts - h[0] <= 1.2] + [(ts, hips[0], hips[1])]
                if ok and self._stationary(state, torso, ts):
                    return True
            return False
        # picks_up: the person was at the object, and the object's region is now empty and unobstructed
        for name, box in boxes:
            if interactions.near(track, box, gap_rel=0.3):
                state.near_at[name] = ts
            item = rule_state.anchors.get(name)
            if item is not None and item.absent_for(ts) >= 1.0 and ts - state.near_at.get(name, -1e9) <= 8.0:
                return True
        return False

    @staticmethod
    def _stationary(state: TrackState, torso: float, ts: float) -> bool:
        """Hips moved less than 15% of the torso over the recent window (needs a few samples spanning 0.6 s)."""
        if len(state.hips) < 3 or state.hips[-1][0] - state.hips[0][0] < 0.6:
            return False
        first, last = state.hips[0], state.hips[-1]
        return hypot(last[1] - first[1], last[2] - first[2]) <= 0.15 * torso

    def _sequence(self, node: RuleWhen, track, previous, state, ts: float, rule_state: RuleState) -> bool:
        if track is None or state is None:
            return False
        progress = state.seq.setdefault(id(node), [0, None, None, None])   # step, started, completed, step_since
        if progress[2] is not None:
            if ts - progress[2] <= SEQUENCE_DONE_S:
                return True
            progress[:] = [0, None, None, None]
        if progress[1] is not None and node.within_s and ts - progress[1] > node.within_s:
            progress[:] = [0, None, None, None]
        child = node.sequence[progress[0]]
        if self._condition(child, track, previous, state, ts, rule_state):
            impulse = child.type in IMPULSE_TYPES
            progress[3] = ts if progress[3] is None else progress[3]
            if impulse or ts - progress[3] >= STEP_HOLD_S:
                progress[1] = ts if progress[0] == 0 else progress[1]
                progress[0] += 1
                progress[3] = None
                if progress[0] == len(node.sequence):
                    progress[2] = ts
                    return True
        else:
            progress[3] = None
        return False

    # --- per-track state --------------------------------------------------------------------------------------

    def _update_zone_dwell(self, spec: RuleSpec, track: ObservedTrack, state: TrackState, ts: float):
        tolerance = spec.episode.gap_tolerance_s
        zones = {node.zone for node in spec.when.leaves() if node.type == "in_zone"}
        for zone in zones:
            if zone in self.zones and in_polygon(track.foot, self.zones[zone]):
                state.zone_since.setdefault(zone, ts)
                state.zone_gap.pop(zone, None)
            elif zone in state.zone_since:
                outside_since = state.zone_gap.setdefault(zone, ts)
                if ts - outside_since > tolerance:       # a brief step out of the zone does not restart a dwell
                    state.zone_since.pop(zone, None)
                    state.zone_gap.pop(zone, None)

    def _state_for(self, tracks: dict[int, TrackState], track: ObservedTrack, ts: float, current_ids: set[int], tolerance: float) -> TrackState:
        if track.track_id in tracks:
            return tracks[track.track_id]
        # Carry an episode across a nearby tracker ID switch within the flicker tolerance.
        radius = max(30.0, 0.5 * (track.bbox[3] - track.bbox[1]))
        for old_id, old in list(tracks.items()):
            if old_id in current_ids:
                continue
            if old.last_foot and 0 <= ts - old.last_seen <= tolerance and hypot(track.foot[0] - old.last_foot[0], track.foot[1] - old.last_foot[1]) <= max(30.0, 0.5 * old.last_h, radius):
                tracks[track.track_id] = tracks.pop(old_id)
                return tracks[track.track_id]
        state = TrackState(first_seen=track.first_seen)
        tracks[track.track_id] = state
        return state

    @staticmethod
    def _reset_track(item: TrackState):
        item.held_since = item.false_since = None
        item.zone_since.clear()
        item.zone_gap.clear()
        item.zones.clear()
        item.near_at.clear()
        item.hips.clear()
        item.seq.clear()
        item.fired_episode = False

    def check_health(self, camera_id: str, now_ts: float, state: RuleState) -> Health | None:
        if state.last_observation_ts is not None and now_ts - state.last_observation_ts > 5 and not state.outage_emitted:
            state.outage_emitted = True
            return Health(camera_id, now_ts, "No frames for more than five seconds")
        return None

    # --- episodes ---------------------------------------------------------------------------------------------

    @staticmethod
    def _scope_key(spec: RuleSpec) -> str | None:
        """None: only the per-person cooldown applies. Otherwise one alert per cooldown for the whole key."""
        scope = spec.episode.cooldown_scope
        if scope == "actor":
            return None
        if scope == "rule":
            return "*"
        for leaf in spec.when.leaves():
            if leaf.zone:
                return f"zone:{leaf.zone}"
            if leaf.line:
                return f"line:{leaf.line}"
            if leaf.object is not None:
                return f"object:{leaf.object.anchor or leaf.object.cls}"
        return "*"

    def _lost_exits(self, spec: RuleSpec, state: RuleState, ts: float, current_ids: set[int], leaves, scope_key) -> list[Fire]:
        """"Goes out through the door": a track that vanishes while inside a door zone has left through it.

        Only rules that are exactly an exits_zone on a door zone (optionally with a time window) qualify; the person is gone, so
        there is no track left to evaluate anything else about."""
        exits = [leaf for leaf in leaves if leaf.type == "exits_zone" and self.zone_roles.get(leaf.zone) == "door"]
        others = [leaf for leaf in leaves if leaf.type not in ("exits_zone", "time_window")]
        if not exits or others:
            return []
        fires = []
        for track_id, item in list(state.tracks.items()):
            if track_id in current_ids or item.lost_handled or ts - item.last_seen < LOST_EXIT_S:
                continue
            item.lost_handled = True
            if item.last_seen - item.first_seen < 0.6:
                continue                                         # a flicker, not a person
            for leaf in exits:
                zone = item.zones.get(leaf.zone)
                if zone is None or not (zone.last_inside or zone.inside):      # last seen in the doorway: the delayed state may not have caught up
                    continue
                scope_ready = scope_key is None or ts >= state.scope_cooldown_until.get(scope_key, 0.0)
                if scope_ready and ts >= item.cooldown_until and self._under_cap(spec, state, ts) and self._time_ok(spec, ts):
                    fires.append(Fire(spec.rule_id, spec.camera_id, ts, (track_id,), item.last_score, item.last_seen))
                    item.cooldown_until = ts + spec.cooldown_s
                    if scope_key is not None:
                        state.scope_cooldown_until[scope_key] = ts + spec.cooldown_s
                    state.fire_times.append(ts)
                    break
        return fires

    def _time_ok(self, spec: RuleSpec, ts: float) -> bool:
        return all(self._time_window(leaf, ts) for leaf in spec.when.leaves() if leaf.type == "time_window")

    @staticmethod
    def _under_cap(spec: RuleSpec, state: RuleState, ts: float) -> bool:
        state.fire_times = [when for when in state.fire_times if ts - when < 3600]
        return len(state.fire_times) < spec.alert.max_alerts_per_hour

    # --- evaluation -------------------------------------------------------------------------------------------

    def _uses_geometry(self, spec: RuleSpec) -> bool:
        return any(leaf.type in GEOMETRY_TYPES for leaf in spec.when.leaves())

    def evaluate(self, spec: RuleSpec, observation: Observation, state: RuleState,
                 suspended: bool = False, low_quality: bool = False) -> list[Fire | Health]:
        if spec.status != "active" or spec.when is None or spec.camera_id != observation.camera_id:
            return []
        ts = observation.ts
        if not self._schedule_allows(spec.schedule, ts):
            state.last_observation_ts = ts
            return []
        if suspended and self._uses_geometry(spec):
            # The camera moved: drawn geometry no longer lines up with the scene, so nothing may start or finish.
            state.tracks.clear()
            state.anchors.clear()
            state.camera_held_since = None
            state.last_observation_ts = ts
            return []
        if low_quality:
            # A blurred frame is neither evidence for nor against: hold every episode where it is.
            state.last_observation_ts = ts
            return []
        if state.last_observation_ts is not None and ts - state.last_observation_ts > 5:
            gap = ts - state.last_observation_ts
            for item in state.tracks.values():
                if item.held_since is not None:
                    item.held_since += gap
                item.zone_since = {zone: entered + gap for zone, entered in item.zone_since.items()}
                item.first_seen += gap
                item.last_foot = None
                item.last_seen = ts
            if state.camera_held_since is not None:
                state.camera_held_since += gap
            state.last_observation_ts = ts
            if not state.outage_emitted:
                state.outage_emitted = True
                return [Health(observation.camera_id, ts, "No frames for more than five seconds")]
            state.outage_emitted = False
            return []
        state.last_observation_ts = ts
        state.outage_emitted = False
        self._tracks = [track for track in observation.tracks if self.track_ok(track)]
        actors = spec.actor_classes()
        self._actors = actors
        self._now = ts
        self._zone_change = dict(observation.zone_change)
        results = []
        leaves = list(spec.when.leaves())
        self._update_anchors(spec, state, ts)
        self._update_class_memory(spec, state, ts)
        camera_absence = any(node.not_ is not None and node.not_.type == "entity_present" for node in (spec.when.all or [spec.when]))
        camera_object = all(leaf.type in CAMERA_LEVEL_TYPES for leaf in leaves) and any(leaf.type in EPISODE_CAMERA_TYPES for leaf in leaves)
        if camera_absence or camera_object:
            present = any(track.cls in actors for track in self._tracks)
            if (camera_object or not present) and self._condition(spec.when, None, None, None, ts, state):
                state.camera_held_since = ts if state.camera_held_since is None else state.camera_held_since
                locked = camera_object and state.camera_fired      # an object that is gone alerts once, until it is back
                if (not locked and ts - state.camera_held_since >= spec.min_hold_s and ts >= state.camera_cooldown_until
                        and self._under_cap(spec, state, ts)):
                    results.append(Fire(spec.rule_id, spec.camera_id, ts, (), 1.0, state.camera_held_since))
                    state.camera_cooldown_until = ts + spec.cooldown_s
                    state.camera_fired = True
                    state.fire_times.append(ts)
            else:
                state.camera_held_since = None
                state.camera_fired = False
            return results
        count_mode = any(node.type == "unique_count_at_least" for node in leaves)
        for node in leaves:
            if node.type == "unique_count_at_least":
                crossings = state.count_crossings.setdefault(node.line, [])
                crossings[:] = [(when, ident) for when, ident in crossings if ts - when <= node.window_s]
        count_tracks = []
        current_ids = {track.track_id for track in self._tracks}
        tolerance = spec.episode.gap_tolerance_s
        scope_key = self._scope_key(spec)
        impulse = any(node.type in IMPULSE_TYPES for node in leaves)
        dwell = max((node.seconds for node in leaves if node.type == "dwell_at_least"), default=0)
        for track in self._tracks:
            if track.cls not in actors:
                continue
            item = self._state_for(state.tracks, track, ts, current_ids, tolerance)
            item.lost_handled = False
            item.last_score = track.score or track.conf
            gap = ts - item.last_seen
            previous = item.last_foot if gap <= tolerance else None
            if gap > tolerance:
                self._reset_track(item)
            self._update_zone_dwell(spec, track, item, ts)
            self._update_transitions(spec, track, item, ts)
            matches = self._condition(spec.when, track, previous, item, ts, state)
            item.last_foot, item.last_seen, item.last_h = track.foot, ts, track.bbox[3] - track.bbox[1]
            if count_mode:
                if matches:
                    count_tracks.append(track)
                continue
            if matches:
                item.false_since = None
                item.held_since = item.held_since if item.held_since is not None else ts
                held = ts - item.held_since >= max(spec.min_hold_s, dwell) if not impulse and not dwell else (
                    ts - item.first_seen >= min(spec.min_hold_s, 0.6) if impulse else True)   # a crossing is one frame: a few frames of track age suffices
                scope_ready = scope_key is None or ts >= state.scope_cooldown_until.get(scope_key, 0.0)
                if held and ts >= item.cooldown_until and not item.fired_episode and scope_ready and self._under_cap(spec, state, ts):
                    episode_start = min(item.zone_since.values()) if dwell and item.zone_since else item.held_since
                    results.append(Fire(spec.rule_id, spec.camera_id, ts, (track.track_id,), track.score or track.conf, episode_start))
                    item.cooldown_until = ts + spec.cooldown_s
                    item.fired_episode = True
                    if scope_key is not None:
                        state.scope_cooldown_until[scope_key] = ts + spec.cooldown_s
                    state.fire_times.append(ts)
            elif item.held_since is not None and tolerance > 0:
                # Hysteresis: a short run of false frames does not end the episode (and so cannot re-arm a duplicate alert).
                item.false_since = ts if item.false_since is None else item.false_since
                if ts - item.false_since > tolerance:
                    item.held_since = item.false_since = None
                    item.fired_episode = False
            else:
                item.held_since = None
                item.fired_episode = False
        if not count_mode:
            results.extend(self._lost_exits(spec, state, ts, current_ids, leaves, scope_key))
        if count_mode:
            bucket = int(ts // 3600)
            if count_tracks and state.count_armed and ts >= state.camera_cooldown_until and state.count_bucket_fired != bucket and self._under_cap(spec, state, ts):
                ids = tuple(sorted({ident for crossings in state.count_crossings.values() for _, ident in crossings}))
                results.append(Fire(spec.rule_id, spec.camera_id, ts, ids, min(track.conf for track in count_tracks), ts))
                state.camera_cooldown_until = ts + spec.cooldown_s
                state.count_armed = False
                state.count_bucket_fired = bucket
                state.fire_times.append(ts)
            elif not count_tracks:
                state.count_armed = True
        return results
