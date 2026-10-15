from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=4000)
    provider: Optional[str] = Field(default=None, pattern='^(ollama|groq)$')
    event_ids: List[str] = Field(default_factory=list, max_length=20)
    camera_id: Optional[str] = None
    category: Optional[str] = None
    after: Optional[str] = None
    before: Optional[str] = None
    include_images: bool = False

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
    provider: Optional[str] = None
    model: Optional[str] = None
    media: List[Dict[str, Any]] = Field(default_factory=list)
