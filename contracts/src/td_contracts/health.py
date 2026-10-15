from typing import Any, Dict
from pydantic import BaseModel, Field

class LiveHealthResponse(BaseModel):
    status: str = "ok"

class HealthResponse(BaseModel):
    status: str = Field(..., description="ok | degraded | down")
    components: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
