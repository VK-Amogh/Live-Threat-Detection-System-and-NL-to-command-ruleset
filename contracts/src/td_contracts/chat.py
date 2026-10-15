from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1)

class ChatCoverage(BaseModel):
    cameras_with_data: List[str] = Field(default_factory=list)
    cameras_without_data: List[str] = Field(default_factory=list)
    note: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    event_ids: List[str] = Field(default_factory=list)
    filters_used: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    coverage: ChatCoverage
