"""Shared inference and operator API contracts."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class Detection(BaseModel):
    class_name: str
    confidence: float = Field(ge=0, le=1)
    box: list[float] = Field(min_length=4, max_length=4)
    model: str
    category: str | None = None
    severity: str | None = None


class FrameResult(BaseModel):
    detections: list[Detection]
    threat_detected: bool
    inference_ms: float
    width: int
    height: int
    models: list[str]
    covered_classes: list[str]
    created_event_ids: list[str] = Field(default_factory=list)
    source_id: str | None = None


class SourceRecord(BaseModel):
    id: str
    filename: str
    kind: Literal['image', 'video', 'live']
    camera_id: str | None = None
    status: str
    created_at: str
    progress_pct: float = 0
    frames_analyzed: int = 0
    event_ids: list[str] = Field(default_factory=list)
    result: FrameResult | None = None
    error: str | None = None
    media_url: str | None = None


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str
    new_password: str = Field(min_length=10, max_length=256)


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chat_provider: Literal['ollama', 'groq'] = 'ollama'
    ollama_model: str = 'gemma4:e2b'
    groq_model: str = 'qwen/qwen3.8-27b'


class SystemSnapshot(BaseModel):
    timestamp: str
    status: str
    counts: dict[str, int]
    inference: dict[str, Any]
    chat: dict[str, Any]
    training: dict[str, Any]
    resources: dict[str, Any]
