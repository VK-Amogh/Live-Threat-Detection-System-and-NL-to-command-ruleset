from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import Severity


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    device_name: str = Field(default="Control Center", min_length=1, max_length=100)
    client_type: str = Field(default="web", pattern="^(web|mobile)$")
    installation_id: Optional[str] = Field(default=None, max_length=128)
    role: Optional[str] = Field(default="control", pattern="^(control|camera)$")
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    local_ip: Optional[str] = None


class LoginResponse(BaseModel):
    device_id: str
    device_name: str
    device_token: Optional[str] = Field(default=None, description="Returned if cookie is not used")
    camera_id: Optional[str] = None
    scope: str = "admin"
    role: str = "control"
    user: Optional[dict[str, Any]] = None
    server_id: Optional[str] = None
    expires_at: Optional[float] = None


class PairingCodeCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(default="control", pattern="^(control|camera)$", description="control = admin console, camera = CCTV phone")


class PairingCodeCreateResponse(BaseModel):
    code: str = Field(..., description="10-minute single use pairing code")
    qr_payload: str = Field(..., description="The pairing link; encode it as a QR code")
    link: Optional[str] = Field(default=None, description="safespace://pair link carrying the code, routes and TLS pins")
    role: str = "control"
    routes: list[dict[str, Any]] = Field(default_factory=list)
    expires_in: int = Field(default=600, description="Seconds until expiration")


class PairDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(..., min_length=4, max_length=32)
    device_name: str = Field(..., min_length=1, max_length=100)
    installation_id: Optional[str] = Field(default=None, max_length=128)
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None


class PairDeviceResponse(BaseModel):
    device_id: str
    device_name: str
    device_token: str = Field(..., description="Opaque bearer token stored securely on mobile")
    scope: str = "admin"
    role: str = "control"
    camera_id: Optional[str] = None
    server_id: Optional[str] = None
    expires_at: Optional[float] = None


class UserOut(BaseModel):
    id: str
    username: str
    role: str
    display_name: Optional[str] = None
    disabled: bool = False
    created_at: str


class DeviceOut(BaseModel):
    id: str
    name: str
    created_at: str
    last_seen_at: Optional[str] = None
    notify_enabled: bool = True
    min_severity: Severity = Severity.MEDIUM


class DeviceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notify_enabled: Optional[bool] = None
    min_severity: Optional[Severity] = None


class WsTicketResponse(BaseModel):
    ticket: str = Field(..., description="Short-lived single-use WebSocket ticket")
    expires_in: int = Field(default=30, description="Seconds until ticket expires")
