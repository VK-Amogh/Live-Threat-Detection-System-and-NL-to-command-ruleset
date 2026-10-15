from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import SourceType

class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    source_type: SourceType = SourceType.WEBCAM
    connection_uri: Optional[str] = Field(default=None, description="Device index (e.g. '0'), file path, or RTSP URL")

class CameraUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    connection_uri: Optional[str] = None
    enabled: Optional[bool] = None

class CameraOut(BaseModel):
    id: str
    name: str
    source_type: SourceType
    connection_uri: Optional[str] = None
    enabled: bool = True
    is_online: bool = False
    created_at: str

class CameraStatusOut(BaseModel):
    camera_id: str
    status: str = Field(..., description="STREAMING, IDLE, ERROR, OFFLINE")
    progress_ms: Optional[int] = None
