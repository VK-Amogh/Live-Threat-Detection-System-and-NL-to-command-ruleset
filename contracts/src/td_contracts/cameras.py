from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import SourceType


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    source_type: SourceType = SourceType.WEBCAM
    connection_uri: Optional[str] = Field(
        default=None, description="Device index (e.g. '0'), file path, or RTSP URL"
    )


class CameraUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    connection_uri: Optional[str] = None
    enabled: Optional[bool] = None
    capture_profile: Optional[str] = None


class CameraOut(BaseModel):
    id: str
    name: str
    source_type: SourceType
    connection_uri: Optional[str] = None
    enabled: bool = True
    is_online: bool = False
    created_at: str
    status: str = "offline"
    fps: float = 0.0
    width: int = 0
    height: int = 0
    viewer_count: int = 0
    device_id: Optional[str] = None
    battery_pct: Optional[int] = None
    charging: Optional[bool] = None
    temp_c: Optional[float] = None
    wifi_rssi: Optional[int] = None
    recording_active: bool = False
    stealth_mode: bool = False
    torch_enabled: bool = False
    lens_facing: str = "back"
    capture_profile: str = "normal"
    active_rules_count: int = 0
    geometry: Optional[dict[str, Any]] = None


class CameraStatusOut(BaseModel):
    camera_id: str
    status: str = Field(..., description="STREAMING, IDLE, ERROR, OFFLINE")
    progress_ms: Optional[int] = None
    viewer_count: int = 0
    fps: float = 0.0
