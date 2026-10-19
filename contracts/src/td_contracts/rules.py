"""Closed, validated rule language. This is data, never executable code."""

from __future__ import annotations

from datetime import time
from typing import Any, Literal
from dateutil.zoneinfo import get_zonefile_instance

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConditionType = Literal[
    "entity_present", "in_zone", "line_cross", "unique_count_at_least",
    "dwell_at_least", "moving_toward", "distance_below", "time_window",
    # v2: transitions, person-object relations (anchors / detector classes) and object state
    "enters_zone", "exits_zone", "near_object", "touches_object", "sits_on", "picks_up", "object_absent",
    "count_in_zone_at_least", "zone_changes",
]


class ObjectRef(BaseModel):
    """A specific object (a user-confirmed anchor) or any instance of a detector class."""

    model_config = ConfigDict(extra="forbid")

    anchor: str | None = None
    cls: str | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.anchor is None) == (self.cls is None):
            raise ValueError("object needs exactly one of anchor or cls")
        return self


class RuleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all: list[RuleWhen] | None = None
    any: list[RuleWhen] | None = None
    not_: RuleWhen | None = Field(default=None, alias="not")
    type: ConditionType | None = None
    zone: str | None = None
    line: str | None = None
    seconds: float | None = Field(default=None, gt=0, le=3600)
    count: int | None = Field(default=None, ge=1, le=100)
    window_s: float | None = Field(default=None, gt=0, le=86400)
    meters: float | None = Field(default=None, gt=0, le=1000)
    start: str | None = None
    end: str | None = None
    tz: str | None = None
    direction: Literal["a_to_b", "b_to_a", "any"] | None = None
    object: ObjectRef | None = None
    sequence: list[RuleWhen] | None = None
    within_s: float | None = Field(default=None, gt=0, le=3600)

    @model_validator(mode="after")
    def valid_node(self):
        branches = [self.all is not None, self.any is not None, self.not_ is not None, self.sequence is not None, self.type is not None]
        if sum(branches) != 1:
            raise ValueError("rule node needs exactly one condition or combinator")
        if self.all is not None and not self.all or self.any is not None and not self.any or self.sequence is not None and len(self.sequence) < 2:
            raise ValueError("all/any needs at least one child, sequence at least two")
        args = {name for name in ("zone", "line", "seconds", "count", "window_s", "meters", "start", "end", "tz", "direction", "object", "within_s") if getattr(self, name) is not None}
        optional = {"line_cross": {"direction"}, "count_in_zone_at_least": {"zone"}}.get(self.type or "", set())
        expected = {
            "entity_present": set(),
            "in_zone": {"zone"},
            "line_cross": {"line"},
            "unique_count_at_least": {"line", "count", "window_s"},
            "dwell_at_least": {"seconds"},
            "moving_toward": {"zone"},
            "distance_below": {"zone", "meters"},
            "time_window": {"start", "end", "tz"},
            "enters_zone": {"zone"},
            "exits_zone": {"zone"},
            "near_object": {"object"},
            "touches_object": {"object"},
            "sits_on": {"object"},
            "picks_up": {"object"},
            "object_absent": {"object", "seconds"},
            "count_in_zone_at_least": {"count"},
            "zone_changes": {"zone"},
        }
        if self.type is None:
            if args - ({"within_s"} if self.sequence is not None else set()):
                raise ValueError("combinators cannot have condition arguments")
        elif not expected[self.type] <= args <= expected[self.type] | optional:
            raise ValueError(f"{self.type} requires exactly {sorted(expected[self.type])}")
        if self.type == "time_window":
            try:
                if time.fromisoformat(self.start) == time.fromisoformat(self.end):
                    raise ValueError("time window must have nonzero duration")
                if self.tz not in get_zonefile_instance().zones:
                    raise ValueError(f"unknown IANA zone {self.tz}")
            except ValueError as exc:
                raise ValueError(f"invalid time window: {exc}") from exc
        return self

    def leaves(self):
        if self.type is not None:
            yield self
        else:
            for child in self.all or self.any or self.sequence or ([self.not_] if self.not_ else []):
                yield from child.leaves()

    def depth(self) -> int:
        if self.type is not None:
            return 1
        return 1 + max(child.depth() for child in self.all or self.any or self.sequence or ([self.not_] if self.not_ else []))


class Verification(BaseModel):
    """How a candidate becomes an alert. geometry/pose: deterministic evidence only; vlm: also a forced-choice visual check."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["geometry", "pose", "vlm"] = "geometry"
    vlm_question: str | None = None
    timeout_s: float = Field(default=8.0, gt=0, le=60)
    on_unverifiable: Literal["hold_for_review", "send_unverified", "drop"] = "hold_for_review"
    max_candidate_age_s: float = Field(default=20.0, gt=0, le=300)


class EpisodePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cooldown_scope: Literal["rule", "rule_zone", "actor"] = "rule_zone"
    gap_tolerance_s: float = Field(default=1.0, ge=0, le=10)


class AlertPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destinations: list[Literal["dashboard", "push"]] = Field(default_factory=lambda: ["dashboard", "push"])
    max_alerts_per_hour: int = Field(default=12, ge=1, le=600)


class CostEstimate(BaseModel):
    """Derived by the compiler, never user supplied."""

    model_config = ConfigDict(extra="forbid")

    stages: list[Literal["detect", "track", "pose", "anchor_embed", "vlm"]]
    gpu_extra: Literal["none", "pose", "pose+vlm", "vlm"]
    expected_latency_s: float | None = None
    basis: str


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    entity: str = Field(min_length=1)
    when: RuleWhen | None
    min_hold_s: float = Field(default=1.5, ge=0, le=60)
    cooldown_s: float = Field(default=120, ge=0, le=86400)
    needs_visual_review: bool = False
    action: Literal["notify_user"] = "notify_user"
    support_level: Literal["SUPPORTED", "EXPERIMENTAL", "UNSUPPORTED"]
    status: Literal["draft", "active", "disabled"] = "draft"
    unsupported_reason: str | None = None
    ruleset_id: str | None = None
    schedule: dict[str, Any] | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    modes: list[str] = Field(default_factory=list)
    schema_version: Literal[1, 2] = 1
    entities: list[str] = Field(default_factory=list)
    verification: Verification | None = None
    episode: EpisodePolicy = Field(default_factory=EpisodePolicy)
    alert: AlertPolicy = Field(default_factory=AlertPolicy)
    cost: CostEstimate | None = None
    feasibility: Literal["GEOMETRIC", "POSE", "TEMPORAL_VLM", "NEEDS_SETUP", "UNVERIFIABLE"] | None = None
    reliability: Literal["HIGH", "MEDIUM", "LOW"] | None = None

    def actor_classes(self) -> set[str]:
        return set(self.entities) | {self.entity}

    @model_validator(mode="after")
    def valid_activation(self):
        if self.verification is not None and self.verification.method == "vlm" and not self.verification.vlm_question:
            raise ValueError("a vlm verification needs a question template id")
        if self.when is not None and (self.when.depth() > 5 or sum(1 for _ in self.when.leaves()) > 16):
            raise ValueError("rule expression is too complex")
        if self.status == "active" and (self.support_level == "UNSUPPORTED" or self.when is None):
            raise ValueError("unsupported or empty rule cannot activate")
        return self


class RuleCompileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: RuleSpec
    readback: str | None
    readback_hash: str | None = None
    support_level: Literal["SUPPORTED", "EXPERIMENTAL", "UNSUPPORTED"]
    problems: list[str]
    can_activate: bool
    needs_setup: list[str] = Field(default_factory=list)
