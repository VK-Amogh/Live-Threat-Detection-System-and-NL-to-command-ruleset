"""One rule runtime for every camera path: blur gate -> scene guard -> pose -> rule engine -> verification candidates.

The phone path (services/api/app/mobile_camera.py) and the RTSP/webcam worker (services/rules/worker.py) both call
`RuleRuntime.process`, so a fix lands once. Detection and its error handling stay with the caller; this class turns an
Observation into RuleEvents whose `verification` says what evidence backs them:

* geometry/pose rules are emitted at once as `verified` (deterministic evidence, quality-gated tracks);
* vlm rules are emitted as `candidate` after a short evidence pack (2 frames before, the trigger frame, up to 2 after)
  is written to storage/media/<event_id>/pack.json; the API decides whether the visual check passes.
"""

import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from td_contracts import Anchor, CameraGeometry, CameraHealthEvent, Observation, RuleEvent, RuleSpec, RuleVerification
from .engine import RuleEngine
from .evidence import EvidenceBuffer
from .pose import PoseEstimator, skeleton_ok
from .readback import describe_when
from .scene_guard import SceneGuard, sharpness
from .zone_watch import ZoneWatcher
from .state import Fire, RuleState

ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger(__name__)
POSE_TYPES = {"touches_object", "sits_on"}
PACK_BEFORE, PACK_AFTER, PACK_WAIT_S = 2, 2, 1.0
MOVED_EVENT_MIN_GAP_S = 600.0


@dataclass
class _Pending:
    event_id: str
    event: RuleEvent
    tracks: tuple[int, ...]
    frames: list = field(default_factory=list)       # (ts, jpeg, bbox | None)
    after: int = 0
    deadline: float = 0.0


def build_detector(camera_id: str, config: dict):
    """Detector adapter built from config/rules.yaml (imported lazily so tests need not load ultralytics)."""
    from .detect import CameraDetector
    detector = config["detector"]
    return CameraDetector(camera_id, ROOT / detector["weights"], detector["tracker"], float(detector["confidence"]),
                          int(detector["image_size"]), tracker_conf=float(detector.get("tracker_conf", detector["confidence"])),
                          quality=config.get("quality"))


def scaled_geometry(geometry: CameraGeometry, sx: float, sy: float):
    """Zones, lines, anchors and homography re-expressed for a frame of another size (same shape)."""
    zones = {name: [(x * sx, y * sy) for x, y in polygon] for name, polygon in geometry.zones.items()}
    lines = {name: ((a[0] * sx, a[1] * sy), (b[0] * sx, b[1] * sy)) for name, (a, b) in geometry.lines.items()}
    anchors = {name: Anchor(cls=a.cls, label=a.label, bbox=(a.bbox[0] * sx, a.bbox[1] * sy, a.bbox[2] * sx, a.bbox[3] * sy))
               for name, a in geometry.anchors.items()}
    homography = None
    if geometry.homography is not None:       # H maps pixels to the ground plane: H' = H * diag(1/sx, 1/sy, 1)
        homography = [[row[0] / sx, row[1] / sy, row[2]] for row in geometry.homography]
    return zones, lines, homography, anchors


def union_box(boxes: dict[int, tuple] | None, tracks) -> tuple | None:
    chosen = [boxes[t] for t in tracks if boxes and t in boxes]
    if not chosen:
        return None
    return (round(min(b[0] for b in chosen)), round(min(b[1] for b in chosen)),
            round(max(b[2] for b in chosen)), round(max(b[3] for b in chosen)))


class RuleRuntime:
    def __init__(self, camera_id: str, config: dict, evidence: EvidenceBuffer, view: str = "Single camera view"):
        self.camera_id = camera_id
        self.config = config
        self.evidence = evidence
        self.view = view
        self.quality = config.get("quality") or {}
        self.rules: list[RuleSpec] = []
        self.states: dict[tuple[str, int], RuleState] = {}
        self.engine = RuleEngine({}, {}, quality=self.quality)
        guard = config.get("scene_guard") or {}
        self.guard = SceneGuard(float(guard.get("max_shift_rel", 0.04)), int(guard.get("min_matches", 12))) if guard.get("enabled", True) else None
        # Two tolerances: rules that compare picture content (door opens) need a steady camera; rules that follow detections
        # (comes in, sits on) only need the drawn zone to be roughly where it was, so ordinary hand movement is allowed.
        self.guard_loose = SceneGuard(float(guard.get("loose_shift_rel", 0.15)), int(guard.get("min_matches", 12))) if guard.get("enabled", True) else None
        self.suspended_loose = False
        self.strict_rules: set[str] = set()
        self.pose: PoseEstimator | None = None
        self.pose_config = config.get("pose") or {}
        self.geometry_signature: str | None = None
        self.pending: dict[str, _Pending] = {}
        self.health: list[CameraHealthEvent] = []
        self.suspended = False
        self.last_moved_event = -1e18
        self.needs_pose = False
        self.geometry: CameraGeometry | None = None
        self.frame_size: tuple[int, int] | None = None
        self.size_mismatch = False
        self.pose_warned = False
        self.watcher = ZoneWatcher()
        self.last_zone_change: dict[str, float] = {}
        self.watch_zones: set[str] = set()

    # --- configuration ----------------------------------------------------------------------------------------

    def configure(self, rules: list[RuleSpec], geometry: CameraGeometry | None):
        self.geometry = geometry
        self._build_engine()
        self.rules = rules
        keys = {(rule.rule_id, rule.version) for rule in rules}
        self.states = {key: value for key, value in self.states.items() if key in keys}
        signature = geometry.model_dump_json() if geometry else ""
        if signature != self.geometry_signature:
            self.geometry_signature = signature
            for guard in (self.guard, self.guard_loose):
                if guard is not None:
                    guard.reset((geometry.snapshot_width, geometry.snapshot_height) if geometry else None)
        wants_skeleton = any(leaf.type in POSE_TYPES for rule in rules if rule.when for leaf in rule.when.leaves())
        # With quality.<class>.require_pose_support, every rule about that class also needs skeletons to vouch for its tracks.
        vouching = any((self.quality.get(cls) or {}).get("require_pose_support") for rule in rules for cls in rule.actor_classes() if cls == "person")
        self.needs_pose = wants_skeleton or vouching
        self.watch_zones = {leaf.zone for rule in rules if rule.when for leaf in rule.when.leaves() if leaf.type == "zone_changes"}
        self.strict_rules = {rule.rule_id for rule in rules if rule.when and any(leaf.type == "zone_changes" for leaf in rule.when.leaves())}

    def _build_engine(self):
        """Geometry is drawn on a snapshot, but detections arrive in live-frame pixels. Same shape at another resolution:
        scale the geometry. A different shape (a rotated phone, another aspect): the drawing no longer applies."""
        geometry = self.geometry
        if geometry is None:
            self.engine, self.size_mismatch = RuleEngine({}, {}, quality=self.quality), False
            return
        zones, lines, homography, anchors = geometry.zones, geometry.lines, geometry.homography, geometry.anchors
        self.size_mismatch = False
        if self.frame_size is not None:
            sx, sy = self.frame_size[0] / geometry.snapshot_width, self.frame_size[1] / geometry.snapshot_height
            if abs(sx - sy) / max(sx, sy) > 0.05:
                self.size_mismatch = True
            elif abs(sx - 1) > 0.005 or abs(sy - 1) > 0.005:
                zones, lines, homography, anchors = scaled_geometry(geometry, sx, sy)
        self.engine = RuleEngine(zones, lines, homography, anchors=anchors, quality=self.quality, zone_roles=geometry.zone_roles)

    def _pose_estimator(self) -> PoseEstimator | None:
        if self.pose is None and self.needs_pose:
            weights = ROOT / self.pose_config.get("weights", "weights/yolo26n-pose.pt")
            if PoseEstimator.installed(weights):
                self.pose = PoseEstimator(weights, int(self.pose_config.get("imgsz", 640)), float(self.pose_config.get("conf", 0.3)))
            elif not self.pose_warned:
                self.pose_warned = True
                LOG.warning("pose weights %s are missing: skeleton checks are skipped (python scripts/fetch_pose_weights.py)", weights)
        return self.pose

    # --- per frame --------------------------------------------------------------------------------------------

    def drain_health(self) -> list[CameraHealthEvent]:
        items, self.health = self.health, []
        return items

    def _guard(self, frame, ts: float, low_quality: bool) -> bool:
        size = (frame.shape[1], frame.shape[0])
        if size != self.frame_size:
            self.frame_size = size
            self._build_engine()
        was = self.suspended
        was_loose = self.suspended_loose
        if self.size_mismatch:
            self.suspended = self.suspended_loose = True
            status = type("Status", (), {"reason": "the live frame has a different shape from the one the geometry was drawn on"})()
        elif self.guard is not None and not low_quality:
            status = self.guard.update(frame)
            self.suspended = status.suspended
            self.suspended_loose = self.guard_loose.update(frame).suspended
        else:
            return self.suspended
        uses_geometry = any(rule.when is not None and self.engine._uses_geometry(rule) for rule in self.rules)
        newly = (self.suspended_loose and not was_loose) or (self.suspended and not was and bool(self.strict_rules))
        if newly and uses_geometry and ts - self.last_moved_event >= MOVED_EVENT_MIN_GAP_S:
            self.last_moved_event = ts
            self.health.append(CameraHealthEvent(
                event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"moved:{self.camera_id}:{ts:.3f}")), camera_id=self.camera_id, ts=ts,
                kind="camera_moved", reason=f"Camera view changed ({status.reason or 'moved'}); zone and object rules are paused until it is steady"))
        if self.suspended_loose:
            for pending in list(self.pending.values()):      # a moved camera invalidates what the evidence frames were meant to show
                pending.event.verification.status = "expired"
                self.pending.pop(pending.event_id, None)
        return self.suspended

    def process(self, frame, observation: Observation, ts: float, jpeg: bytes) -> list[RuleEvent]:
        blur_floor = self.quality.get("blur_min_laplacian_var")
        low_quality = bool(blur_floor) and sharpness(frame) < float(blur_floor)
        suspended = self._guard(frame, ts, low_quality)
        pose = self._pose_estimator() if self.needs_pose and not low_quality else None
        if pose is not None:
            observation = pose.attach(frame, observation)
        if self.watch_zones:
            if suspended:
                self.watcher.reset()                      # a moved camera makes the old baseline meaningless
            elif not low_quality:
                people = [track.bbox for track in observation.tracks if track.cls == "person"]
                observation = observation.model_copy(update={"zone_change": self.watcher.measure(frame, self.engine.zones, self.watch_zones, ts, people)})
        self.last_zone_change = dict(observation.zone_change)
        boxes = {track.track_id: tuple(track.bbox) for track in observation.tracks}
        self.evidence.annotate(ts, boxes)
        events = self._advance_packs(ts, jpeg, boxes)
        for rule in self.rules:
            state = self.states.setdefault((rule.rule_id, rule.version), RuleState())
            rule_suspended = suspended if rule.rule_id in self.strict_rules else self.suspended_loose
            for outcome in self.engine.evaluate(rule, observation, state, suspended=rule_suspended, low_quality=low_quality):
                if isinstance(outcome, Fire):
                    emitted = self._fire(rule, outcome, observation, ts, jpeg)
                    if emitted is not None:
                        events.append(emitted)
        return events

    # --- candidates and evidence ------------------------------------------------------------------------------

    def _fire(self, rule: RuleSpec, outcome: Fire, observation: Observation, ts: float, jpeg: bytes) -> RuleEvent | None:
        event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{rule.rule_id}:{rule.version}:{self.camera_id}:{outcome.tracks}:{outcome.episode_start:.3f}"))
        self.evidence.start(event_id, ts, jpeg)
        boxes = {track.track_id: tuple(track.bbox) for track in observation.tracks}
        subjects = [track for track in observation.tracks if track.track_id in outcome.tracks]
        checks = [f"conditions held {max(0.0, ts - outcome.episode_start):.1f} s: {describe_when(rule.when)}"]
        for track in subjects:
            checks.append(f"{track.cls} #{track.track_id} mean detector score {track.score:.2f}" if track.score is not None else f"{track.cls} #{track.track_id}")
            if track.keypoints and skeleton_ok(track.keypoints):
                checks.append(f"{track.cls} #{track.track_id} has a coherent skeleton")
        method = rule.verification.method if rule.verification else "geometry"
        needs_vlm = method == "vlm"
        verification = RuleVerification(status="candidate" if needs_vlm else "verified", method=method, checks=checks,
                                        candidate_ts=ts, verified_ts=None if needs_vlm else ts)
        event = RuleEvent(event_id=event_id, camera_id=self.camera_id, rule_id=rule.rule_id, rule_version=rule.version,
                          ts=ts, episode_start=outcome.episode_start, tracks=list(outcome.tracks),
                          model_versions=observation.model_versions, confidence=max(0.0, min(1.0, outcome.confidence)),
                          uncertainty=f"{self.view}; detector confidence cannot establish intent.",
                          needs_visual_review=rule.needs_visual_review, evidence_bbox=union_box(boxes, outcome.tracks),
                          verification=verification)
        if not needs_vlm:
            return event
        recent = self.evidence.recent(PACK_BEFORE + 1)
        pending = _Pending(event_id, event, outcome.tracks, deadline=ts + PACK_WAIT_S,
                           frames=[(t, j, union_box(b, outcome.tracks)) for t, j, b in recent])
        self.pending[event_id] = pending
        return None

    def _advance_packs(self, ts: float, jpeg: bytes, boxes: dict[int, tuple]) -> list[RuleEvent]:
        ready = []
        for pending in list(self.pending.values()):
            if pending.frames and ts > pending.frames[-1][0]:
                pending.frames.append((ts, jpeg, union_box(boxes, pending.tracks)))
                pending.after += 1
            if pending.after >= PACK_AFTER or ts >= pending.deadline:
                self.pending.pop(pending.event_id, None)
                self.evidence.write_pack(pending.event_id, pending.frames)
                ready.append(pending.event)
        return ready
