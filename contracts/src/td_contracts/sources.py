from typing import Optional
from pydantic import BaseModel, Field
from td_contracts.enums import JobStatus

class SourceUploadResponse(BaseModel):
    source_id: str
    filename: str
    status: JobStatus = JobStatus.PENDING
    message: str

class SourceOut(BaseModel):
    id: str
    camera_id: Optional[str] = None
    filename: str
    status: JobStatus
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    created_at: str

class SourceProgressOut(BaseModel):
    source_id: str
    status: JobStatus
    progress_pct: float
    current_fps: Optional[float] = None
