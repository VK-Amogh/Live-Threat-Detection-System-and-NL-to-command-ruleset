from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import EventStatus, VerifiedBy, VlmStatus

class VlmModelSpec(BaseModel):
    name: str
    digest: Optional[str] = None

class VlmResultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_visible: str = Field(..., description="yes | no | uncertain")
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: str
    evidence_insufficient: bool = False
    visible_facts: List[str] = Field(default_factory=list)
    cannot_determine: List[str] = Field(default_factory=list)
    summary: str

class VlmVerificationIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=1)
    verification_id: str
    vlm: VlmModelSpec
    status: VlmStatus
    latency_ms: int
    frames_used: List[str] = Field(default_factory=list)
    result: Optional[VlmResultPayload] = None

class VlmVerificationResponse(BaseModel):
    event_id: str
    status: EventStatus
    verified_by: VerifiedBy
    change_seq: int
    applied: bool
