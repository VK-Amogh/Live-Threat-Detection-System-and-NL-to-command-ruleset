"""Pure rule evaluator over validated observations and geometry."""

from datetime import datetime, time
from math import hypot

from dateutil.zoneinfo import get_zonefile_instance

from td_contracts import Observation, ObservedTrack, RuleSpec, RuleWhen
from .geometry import centroid, crosses_line, distance_to_polygon, homography_point, in_polygon
from .state import Fire, Health, RuleState, TrackState


class RuleEngine:
    def __init__(self, zones: dict[str, list[tuple[float, float]]],
                 lines: dict[str, tuple[tuple[float, float], tuple[float, float]]],
                 homography: list[list[float]] | None = None):
        self.zones = zones
        self.lines = lines
        self.homography = homography

    def _time_window(self, node: RuleWhen, ts: float) -> bool:
        zone = get_zonefile_instance().get(node.tz)
        current = datetime.fromtimestamp(ts, zone).time().replace(tzinfo=None)
        start, end = time.fromisoformat(node.start), time.fromisoformat(node.end)
        return start <= current < end if start < end else current >= start or current < end

    def _condition(self, node: RuleWhen, track: ObservedTrack | None, previous: tuple[float, float] | None,
                   state: TrackState | None, ts: float, rule_state: RuleState) -> bool:
        if node.all is not None:
            return all(self._condition(child, track, previous, state, ts, rule_state) for child in node.all)
        if node.any is not None:
            return any(self._condition(child, track, previous, state, ts, rule_state) for child in node.any)
        if node.not_ is not None:
            return not self._condition(node.not_, track, previous, state, ts, rule_state)
        if node.type == "time_window":
            return self._time_window(node, ts)
        if node.type == "entity_present":
            return track is not None
        if track is None:
            return False
        if node.type == "in_zone":
            return in_polygon(track.foot, self.zones[node.zone])
        if node.type == "line_cross":
            return previous is not None and crosses_line(previous, track.foot, self.lines[node.line])
        if node.type == "unique_count_at_least":
            if previous is not None and crosses_line(previous, track.foot, self.lines[node.line]):
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
            target = centroid(self.zones[node.zone])
            vx, vy = track.velocity
            dx, dy = target[0] - track.foot[0], target[1] - track.foot[1]
            return vx * dx + vy * dy > 0 and hypot(vx, vy) >= 5 and hypot(dx, dy) > 5
        if node.type == "distance_below":
            if self.homography is None:
                return False
            world_point = homography_point(track.foot, self.homography)
            world_zone = [homography_point(point, self.homography) for point in self.zones[node.zone]]
            return distance_to_polygon(world_point, world_zone) < node.meters
        raise ValueError(f"Unknown condition: {node.type}")

    def _update_zone_dwell(self, spec: RuleSpec, track: ObservedTrack, state: TrackState, ts: float):
        zones = {node.zone for node in spec.when.leaves() if node.type == "in_zone"}
        for zone in zones:
            if in_polygon(track.foot, self.zones[zone]):
                state.zone_since.setdefault(zone, ts)
            else:
                state.zone_since.pop(zone, None)

    def _state_for(self, tracks: dict[int, TrackState], track: ObservedTrack, ts: float, current_ids: set[int]) -> TrackState:
        if track.track_id in tracks:
            return tracks[track.track_id]
        # Carry an episode across a nearby tracker ID switch within the flicker tolerance.
        for old_id, old in list(tracks.items()):
            if old_id in current_ids:
                continue
            if old.last_foot and 0 <= ts - old.last_seen <= 1 and hypot(track.foot[0] - old.last_foot[0], track.foot[1] - old.last_foot[1]) <= 30:
                tracks[track.track_id] = tracks.pop(old_id)
                return tracks[track.track_id]
        state = TrackState(first_seen=track.first_seen)
        tracks[track.track_id] = state
        return state

    def check_health(self, camera_id: str, now_ts: float, state: RuleState) -> Health | None:
        if state.last_observation_ts is not None and now_ts - state.last_observation_ts > 5 and not state.outage_emitted:
            state.outage_emitted = True
            return Health(camera_id, now_ts, "No frames for more than five seconds")
        return None

    def evaluate(self, spec: RuleSpec, observation: Observation, state: RuleState) -> list[Fire | Health]:
        if spec.status != "active" or spec.when is None or spec.camera_id != observation.camera_id:
            return []
        ts = observation.ts
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
        results = []
        camera_absence = any(node.not_ is not None and node.not_.type == "entity_present" for node in (spec.when.all or [spec.when]))
        if camera_absence:
            present = any(track.cls == spec.entity for track in observation.tracks)
            if not present and self._condition(spec.when, None, None, None, ts, state):
                state.camera_held_since = ts if state.camera_held_since is None else state.camera_held_since
                if ts - state.camera_held_since >= spec.min_hold_s and ts >= state.camera_cooldown_until:
                    results.append(Fire(spec.rule_id, spec.camera_id, ts, (), 1.0, state.camera_held_since))
                    state.camera_cooldown_until = ts + spec.cooldown_s
            else:
                state.camera_held_since = None
            return results
        count_mode = any(node.type == "unique_count_at_least" for node in spec.when.leaves())
        for node in spec.when.leaves():
            if node.type == "unique_count_at_least":
                crossings = state.count_crossings.setdefault(node.line, [])
                crossings[:] = [(when, ident) for when, ident in crossings if ts - when <= node.window_s]
        count_tracks = []
        current_ids = {track.track_id for track in observation.tracks}
        for track in observation.tracks:
            if track.cls != spec.entity:
                continue
            item = self._state_for(state.tracks, track, ts, current_ids)
            gap = ts - item.last_seen
            previous = item.last_foot if gap <= 1 else None
            if gap > 1:
                item.held_since = None
                item.zone_since.clear()
                item.fired_episode = False
            self._update_zone_dwell(spec, track, item, ts)
            matches = self._condition(spec.when, track, previous, item, ts, state)
            item.last_foot, item.last_seen = track.foot, ts
            if count_mode:
                if matches:
                    count_tracks.append(track)
                continue
            if matches:
                item.held_since = item.held_since if item.held_since is not None else ts
                impulse = any(node.type == "line_cross" for node in spec.when.leaves())
                dwell = max((node.seconds for node in spec.when.leaves() if node.type == "dwell_at_least"), default=0)
                held = ts - item.held_since >= max(spec.min_hold_s, dwell) if not impulse and not dwell else (
                    ts - item.first_seen >= spec.min_hold_s if impulse else True)
                if held and ts >= item.cooldown_until and not item.fired_episode:
                    episode_start = min(item.zone_since.values()) if dwell and item.zone_since else item.held_since
                    results.append(Fire(spec.rule_id, spec.camera_id, ts, (track.track_id,), track.conf, episode_start))
                    item.cooldown_until = ts + spec.cooldown_s
                    item.fired_episode = True
            else:
                item.held_since = None
                item.fired_episode = False
        if count_mode:
            bucket = int(ts // 3600)
            if count_tracks and state.count_armed and ts >= state.camera_cooldown_until and state.count_bucket_fired != bucket:
                ids = tuple(sorted({ident for crossings in state.count_crossings.values() for _, ident in crossings}))
                results.append(Fire(spec.rule_id, spec.camera_id, ts, ids, min(track.conf for track in count_tracks), ts))
                state.camera_cooldown_until = ts + spec.cooldown_s
                state.count_armed = False
                state.count_bucket_fired = bucket
            elif not count_tracks:
                state.count_armed = True
        return results
