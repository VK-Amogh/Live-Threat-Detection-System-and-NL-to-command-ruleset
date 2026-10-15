from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.enums import Severity

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)
    device_name: str = Field(..., min_length=1, max_length=100)
    client_type: str = Field(default='web', pattern='^(web|mobile)$')

class LoginResponse(BaseModel):
    device_id: str
    device_name: str
    device_token: Optional[str] = Field(default=None, description="Returned if cookie is not used")

class PairingCodeCreateResponse(BaseModel):
    code: str = Field(..., description="10-minute single use pairing code")
    qr_payload: str = Field(..., description="Payload format for QR pairing")
    expires_in: int = Field(default=600, description="Seconds until expiration")

class PairDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(..., min_length=4, max_length=32)
    device_name: str = Field(..., min_length=1, max_length=100)

class PairDeviceResponse(BaseModel):
    device_id: str
    device_name: str
    device_token: str = Field(..., description="Opaque bearer token stored securely on mobile")

class UserOut(BaseModel):
    id: str
    username: str
    role: str
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
