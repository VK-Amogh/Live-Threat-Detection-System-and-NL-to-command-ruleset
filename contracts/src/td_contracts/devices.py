from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class DeviceEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: str = Field(..., min_length=4, max_length=128)
    enrollment_code: str = Field(..., min_length=4, max_length=128)
    device_name: str = Field(..., min_length=1, max_length=100)
    role: Literal["camera", "control"] = "camera"
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    local_ip: Optional[str] = None


class DeviceEnrollResponse(BaseModel):
    device_id: str
    camera_id: str
    device_name: str
    role: str
    scope: str
    token: str
    expires_at: float
    server_id: str
    server_name: str
    urls: list[str] = Field(default_factory=list)
    route: Optional[str] = Field(default=None, description="How this device reached the server: loopback | trusted_lan | ibus_lan | tailnet | relay")


class DeviceRecordOut(BaseModel):
    device_id: str
    installation_id: str
    name: str
    role: str
    camera_id: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    battery_pct: Optional[int] = None
    charging: Optional[bool] = None
    temp_c: Optional[float] = None
    wifi_rssi: Optional[int] = None
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    local_ip: Optional[str] = None
    fps: Optional[float] = None
    dropped_frames: Optional[int] = 0
    queue_depth: Optional[int] = 0
    capture_profile: Optional[str] = "normal"
    stealth_mode: bool = False
    torch_enabled: bool = False
    lens_facing: str = "back"
    status: str = "offline"
    last_seen: Optional[float] = None
    created_at: float


class DeviceCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "set_profile",
        "toggle_torch",
        "switch_lens",
        "enter_stealth",
        "exit_stealth",
        "take_full_snapshot",
        "ping",
        "disconnect",
        "reconnect",
        "revoke_token",
    ]
    params: dict[str, Any] = Field(default_factory=dict)


class ApkTokenResponse(BaseModel):
    token: str
    url: str
    qr_payload: str
    expires_in: int = 600
    expires_at: float
    apk_ready: bool = False
    apk_size_bytes: Optional[int] = None


class AuditEntryOut(BaseModel):
    id: int
    ts: float
    actor_user: Optional[str] = None
    actor_device: Optional[str] = None
    ip: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    detail: dict[str, Any] = Field(default_factory=dict)
