"""Small per-camera rule state; never stores video pixels."""

from dataclasses import dataclass, field


@dataclass
class ZoneTrack:
    """Confirmed inside/outside state of one track against one zone, with the evidence needed for an entry or exit."""
    inside: bool | None = None
    since: float = 0.0
    pending: tuple[bool, float] | None = None
    entered_at: float | None = None
    exited_at: float | None = None
    last_inside: bool | None = None      # membership in the most recent frame, without the confirmation delay


@dataclass
class TrackState:
    last_foot: tuple[float, float] | None = None
    last_h: float = 0.0
    last_seen: float = 0.0
    first_seen: float = 0.0
    held_since: float | None = None
    false_since: float | None = None
    zone_since: dict[str, float] = field(default_factory=dict)
    zone_gap: dict[str, float] = field(default_factory=dict)
    zones: dict[str, ZoneTrack] = field(default_factory=dict)
    near_at: dict[str, float] = field(default_factory=dict)
    hips: list[tuple[float, float, float]] = field(default_factory=list)
    seq: dict[int, list] = field(default_factory=dict)
    cooldown_until: float = 0.0
    fired_episode: bool = False
    lost_handled: bool = False
    last_score: float = 0.9


@dataclass
class AnchorState:
    """Presence of a user-confirmed object. Absence only accumulates while the anchor is visible-capable (not occluded)."""
    present: bool = True
    absent_since: float | None = None
    occluded: bool = False
    last_present: float | None = None
    box: tuple[float, float, float, float] | None = None

    def absent_for(self, ts: float) -> float:
        return 0.0 if self.absent_since is None else ts - self.absent_since


@dataclass
class RuleState:
    tracks: dict[int, TrackState] = field(default_factory=dict)
    anchors: dict[str, AnchorState] = field(default_factory=dict)
    count_crossings: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    camera_held_since: float | None = None
    camera_cooldown_until: float = 0.0
    camera_fired: bool = False
    count_armed: bool = True
    count_bucket_fired: int | None = None
    last_observation_ts: float | None = None
    outage_emitted: bool = False
    scope_cooldown_until: dict[str, float] = field(default_factory=dict)
    zone_change_last: dict[str, bool] = field(default_factory=dict)   # last judged answer per watched zone
    cls_memory: dict[str, list] = field(default_factory=dict)   # class -> [[box, last_seen]] of objects seen before a person hid them
    fire_times: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class Fire:
    rule_id: str
    camera_id: str
    ts: float
    tracks: tuple[int, ...]
    confidence: float
    episode_start: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Health:
    camera_id: str
    ts: float
    reason: str
