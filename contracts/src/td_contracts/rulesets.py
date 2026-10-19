from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


DayOfWeek = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SecurityMode = Literal["HOME", "AWAY", "NIGHT", "DISARMED"]


class RuleSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timezone: str = "local"
    days: list[DayOfWeek] = Field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    )
    start_time: str = Field(default="00:00", pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(default="23:59", pattern=r"^\d{2}:\d{2}$")


class RulesetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=120)
    source_type: Literal["nl", "template", "builder"] = "nl"
    text: Optional[str] = Field(default=None, max_length=1000)
    description: Optional[str] = Field(default=None, max_length=1000, description="Free-text note; shown with the ruleset")
    mode: Optional[str] = Field(default=None, description="Single security mode shortcut; equivalent to modes=[mode]")
    template_id: Optional[str] = None
    camera_ids: list[str] = Field(..., min_length=1)
    zone_id: Optional[str] = None
    line_id: Optional[str] = None
    rule_type: Optional[
        Literal[
            "presence_in_zone",
            "dwell_in_zone",
            "line_cross",
            "count_threshold",
            "stationary_object",
            "absence",
        ]
    ] = None
    target_classes: list[str] = Field(default_factory=lambda: ["person"])
    dwell_seconds: float = Field(default=1.5, ge=0.0, le=3600.0)
    min_count: int = Field(default=1, ge=1, le=100)
    direction: Optional[Literal["A_TO_B", "B_TO_A", "ANY"]] = None
    cooldown_seconds: float = Field(default=120.0, ge=0.0, le=86400.0)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    schedule: Optional[RuleSchedule] = None
    modes: list[str] = Field(default_factory=lambda: ["HOME", "AWAY", "NIGHT"])
    needs_visual_review: bool = False


class RulesetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    camera_ids: Optional[list[str]] = None
    cooldown_seconds: Optional[float] = Field(default=None, ge=0.0, le=86400.0)
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None
    schedule: Optional[RuleSchedule] = None
    modes: Optional[list[str]] = None
    needs_visual_review: Optional[bool] = None


class RulesetArmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Optional[int] = Field(default=None, ge=1)
    confirmed_readback_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    acknowledge_experimental: bool = False


class RulesetModeActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: SecurityMode


class RulesetDryRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera_id: Optional[str] = None
    source_id: Optional[str] = None
    from_ts: Optional[float] = None
    to_ts: Optional[float] = None
    stride: int = Field(default=3, ge=1, le=30)


class RulesetOut(BaseModel):
    ruleset_id: str
    id: Optional[str] = Field(default=None, description="Same as ruleset_id (the field the apps use)")
    description: Optional[str] = None
    template_id: Optional[str] = None
    mode: Optional[str] = Field(default=None, description="Modes joined with '/', for display")
    readback_text: Optional[str] = Field(default=None, description="Same as readback (the field the apps use)")
    name: str
    source_type: str
    spec: dict[str, Any] = Field(default_factory=dict)
    readback: str
    readback_hash: str
    support_level: str
    camera_ids: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    schedule: Optional[dict[str, Any]] = None
    modes: list[str] = Field(default_factory=list)
    status: str = "draft"
    version: int = 1
    problems: list[str] = Field(default_factory=list)
    can_activate: bool = True
    created_at: float
    updated_at: float


class RuleTemplateOut(BaseModel):
    id: str
    name: str
    description: str
    rule_type: str
    target_classes: list[str] = Field(default_factory=list)
    zone_required: bool = False
    dwell_seconds: float = 0.0
    min_count: int = 1
    direction: Optional[str] = None
    cooldown_seconds: float = 60.0
    severity: str = "medium"
    schedule_default: Optional[dict[str, Any]] = None
    modes: list[str] = Field(default_factory=list)
