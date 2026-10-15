from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from td_contracts.events import EventOut

class WsHelloData(BaseModel):
    device_id: str
    head_seq: int
    server_time: str
    heartbeat_s: int = 20

class WsEventData(BaseModel):
    event: EventOut

class WsCameraStatusData(BaseModel):
    camera_id: str
    status: str
    progress_ms: Optional[int] = None

class WsSystemHealthData(BaseModel):
    component: str
    status: str

class WsResyncRequiredData(BaseModel):
    reason: str

class WsEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: int = Field(default=1)
    type: str = Field(..., description="hello | event.created | event.updated | camera.status | system.health | ping | pong | resync_required")
    sent_at: str
    data: Dict[str, Any] = Field(default_factory=dict)
