from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.cameras import CameraOut
from td_contracts.enums import EventStatus, JobStatus

class EventIngestResponse(BaseModel):
    event_id: str
    result: str = Field(..., description="created | duplicate")
    status: EventStatus
    change_seq: int

class InternalConfigOut(BaseModel):
    config_version: int
    cameras: List[CameraOut] = Field(default_factory=list)
    enabled_categories: List[str] = Field(default_factory=list)

class JobClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: str

class JobClaimResponse(BaseModel):
    job_id: Optional[str] = None
    lease_token: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None

class JobProgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str
    progress_pct: float = Field(..., ge=0.0, le=100.0)
    stage: str

class JobCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lease_token: str
    status: JobStatus
    error_message: Optional[str] = None

class WorkerHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: str
    uptime_seconds: float
    model_name: str
    fps: float
    queue_depths: Dict[str, int] = Field(default_factory=dict)
    last_error: Optional[str] = None
