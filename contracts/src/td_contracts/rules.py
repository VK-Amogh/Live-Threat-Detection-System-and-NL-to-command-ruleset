"""Closed, validated rule language. This is data, never executable code."""

from __future__ import annotations

from datetime import time
from typing import Literal
from dateutil.zoneinfo import get_zonefile_instance

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConditionType = Literal[
    "entity_present", "in_zone", "line_cross", "unique_count_at_least",
    "dwell_at_least", "moving_toward", "distance_below", "time_window",
]


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

    @model_validator(mode="after")
    def valid_node(self):
        branches = [self.all is not None, self.any is not None, self.not_ is not None, self.type is not None]
        if sum(branches) != 1:
            raise ValueError("rule node needs exactly one condition or combinator")
        if self.all is not None and not self.all or self.any is not None and not self.any:
            raise ValueError("all/any needs at least one child")
        args = {name for name in ("zone", "line", "seconds", "count", "window_s", "meters", "start", "end", "tz") if getattr(self, name) is not None}
        expected = {
            "entity_present": set(),
            "in_zone": {"zone"},
            "line_cross": {"line"},
            "unique_count_at_least": {"line", "count", "window_s"},
            "dwell_at_least": {"seconds"},
            "moving_toward": {"zone"},
            "distance_below": {"zone", "meters"},
            "time_window": {"start", "end", "tz"},
        }
        if self.type is None:
            if args:
                raise ValueError("combinators cannot have condition arguments")
        elif args != expected[self.type]:
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
            for child in self.all or self.any or ([self.not_] if self.not_ else []):
                yield from child.leaves()

    def depth(self) -> int:
        if self.type is not None:
            return 1
        return 1 + max(child.depth() for child in self.all or self.any or ([self.not_] if self.not_ else []))


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

    @model_validator(mode="after")
    def valid_activation(self):
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
