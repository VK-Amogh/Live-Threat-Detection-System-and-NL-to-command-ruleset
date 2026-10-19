from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class RetrievalPlan(BaseModel):
    intent: Literal[
        "live_now",
        "historical_incidents",
        "timeline_recordings",
        "rules_status",
        "system_status",
        "mixed",
    ] = "mixed"
    camera_ids: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    severities: List[str] = Field(default_factory=list)
    statuses: List[str] = Field(default_factory=list)
    time_from: Optional[float] = None
    time_to: Optional[float] = None
    sources: List[
        Literal[
            "incidents",
            "recordings",
            "screenshots",
            "live_frames",
            "rulesets",
            "system",
        ]
    ] = Field(default_factory=lambda: ["incidents", "live_frames", "rulesets"])
    needs_visual_describe: bool = False
    limit: int = Field(default=12, ge=1, le=50)


class EvidenceItemOut(BaseModel):
    id: str
    kind: Literal[
        "incident",
        "recording_segment",
        "screenshot",
        "live_frame",
        "ruleset",
        "system",
    ]
    camera_id: Optional[str] = None
    camera_name: Optional[str] = None
    ts: Optional[float] = None
    label: str
    summary: str
    media_url: Optional[str] = None
    clip_url: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    confidence: Optional[float] = None


class ConversationSummaryOut(BaseModel):
    id: str
    title: str
    created_at: float
    updated_at: float
    message_count: int = 0
    last_message_preview: Optional[str] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=4000)
    provider: Optional[str] = Field(default=None, pattern="^(ollama|groq)$")
    event_ids: List[str] = Field(default_factory=list, max_length=20)
    camera_id: Optional[str] = None
    category: Optional[str] = None
    after: Optional[str] = None
    before: Optional[str] = None
    include_images: bool = False
    scope_sources: Optional[List[str]] = None


class ChatCoverage(BaseModel):
    cameras_with_data: List[str] = Field(default_factory=list)
    cameras_without_data: List[str] = Field(default_factory=list)
    note: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    event_ids: List[str] = Field(default_factory=list)
    filters_used: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    coverage: ChatCoverage
    provider: Optional[str] = None
    model: Optional[str] = None
    media: List[Dict[str, Any]] = Field(default_factory=list)
    cited: List[Dict[str, Any]] = Field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
