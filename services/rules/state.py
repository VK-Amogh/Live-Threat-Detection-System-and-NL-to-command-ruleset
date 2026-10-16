"""Small per-camera rule state; never stores video pixels."""

from dataclasses import dataclass, field


@dataclass
class TrackState:
    last_foot: tuple[float, float] | None = None
    last_seen: float = 0.0
    first_seen: float = 0.0
    held_since: float | None = None
    zone_since: dict[str, float] = field(default_factory=dict)
    cooldown_until: float = 0.0
    fired_episode: bool = False


@dataclass
class RuleState:
    tracks: dict[int, TrackState] = field(default_factory=dict)
    count_crossings: dict[str, list[tuple[float, int]]] = field(default_factory=dict)
    camera_held_since: float | None = None
    camera_cooldown_until: float = 0.0
    count_armed: bool = True
    count_bucket_fired: int | None = None
    last_observation_ts: float | None = None
    outage_emitted: bool = False


@dataclass(frozen=True)
class Fire:
    rule_id: str
    camera_id: str
    ts: float
    tracks: tuple[int, ...]
    confidence: float
    episode_start: float


@dataclass(frozen=True)
class Health:
    camera_id: str
    ts: float
    reason: str
