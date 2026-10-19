from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import EventStatus, HumanAction, MediaKind, Severity, VerifiedBy

class TrackRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    track_id: int
    class_name: str = Field(..., alias="class")
    first_frame: Optional[int] = None
    last_frame: Optional[int] = None

class MediaItemIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: MediaKind
    role: str = Field(..., description="peak, first, last, context")
    path: str = Field(..., description="Relative storage path")
    sha256: str
    bytes: int
    width: int
    height: int
    offset_ms: Optional[int] = None

class MediaItemOut(BaseModel):
    id: str
    kind: MediaKind
    role: str
    url: str
    width: int
    height: int
    offset_ms: Optional[int] = None

class EvidenceInfo(BaseModel):
    hits: int
    window: int
    sample_fps: int

class YoloModelRef(BaseModel):
    name: str
    sha256: Optional[str] = None
    tracker: Optional[str] = None

class VlmModelRef(BaseModel):
    name: str
    version: Optional[str] = None

class ModelsInfo(BaseModel):
    yolo: YoloModelRef
    vlm: Optional[VlmModelRef] = None

class ReasoningOut(BaseModel):
    confidence: float
    uncertainty: str
    evidence_insufficient: bool = False
    visible_facts: List[str] = Field(default_factory=list)
    cannot_determine: List[str] = Field(default_factory=list)

class FeedbackOut(BaseModel):
    id: str
    client_action_id: str
    action: HumanAction
    note: Optional[str] = None
    created_at: str
    user_id: Optional[str] = None

class CameraRef(BaseModel):
    id: str
    name: str

class CategoryRef(BaseModel):
    key: str
    label: str

class EventIngest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_version: int = Field(default=1)
    event_id: str
    camera_id: str
    video_source_id: Optional[str] = None
    detected_at: str
    first_seen_at: str
    last_seen_at: str
    media_offset_ms: Optional[int] = None
    yolo_class_raw: str
    category: str
    yolo_confidence: float = Field(..., ge=0.0, le=1.0)
    peak_confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Severity
    evidence: EvidenceInfo
    track_refs: List[TrackRef] = Field(default_factory=list)
    media: List[MediaItemIngest] = Field(default_factory=list)
    model: Dict[str, Any]
    verify: bool = True

class EventExtendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    last_seen_at: str
    peak_confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: Optional[EvidenceInfo] = None
    track_refs: Optional[List[TrackRef]] = None
    media: Optional[List[MediaItemIngest]] = None

class EventOut(BaseModel):
    id: str
    rule_id: Optional[str] = None
    rule_version: Optional[int] = None
    uncertainty: Optional[str] = None
    needs_visual_review: bool = False
    evidence_bbox: Optional[tuple[int, int, int, int]] = None
    verification: Optional[dict] = None
    review_possible_false_positive: Optional[bool] = None
    camera: CameraRef
    category: CategoryRef
    status: EventStatus
    status_reason: Optional[str] = None
    verified_by: VerifiedBy
    ai_disagrees: bool = False
    severity: Severity
    yolo_confidence: float
    peak_confidence: float
    reasoning: Optional[ReasoningOut] = None
    summary: Optional[str] = None
    first_seen_at: str
    last_seen_at: str
    media_offset_ms: Optional[int] = None
    track_refs: List[TrackRef] = Field(default_factory=list)
    media: List[MediaItemOut] = Field(default_factory=list)
    models: Optional[ModelsInfo] = None
    feedback: List[FeedbackOut] = Field(default_factory=list)
    change_seq: int
    created_at: str
    updated_at: str

class HumanVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client_action_id: str
    action: HumanAction
    note: Optional[str] = None
    corrected_category: Optional[str] = None

class ChangesResponse(BaseModel):
    items: List[EventOut] = Field(default_factory=list)
    next_after: int
    has_more: bool
    head_seq: int
