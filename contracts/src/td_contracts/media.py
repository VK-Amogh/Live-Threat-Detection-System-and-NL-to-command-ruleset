from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecordingSegmentOut(BaseModel):
    segment_id: str
    camera_id: str
    start_ts: float
    end_ts: float
    duration_s: float
    url: str
    size_bytes: int
    width: int
    height: int
    fps: float
    codec: str = "h264"
    has_events: bool = False
    event_count: int = 0


class TimelineGapOut(BaseModel):
    start_ts: float
    end_ts: float
    duration_s: float


class TimelineOut(BaseModel):
    camera_id: str
    from_ts: float
    to_ts: float
    segments: list[RecordingSegmentOut] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    snapshots: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[TimelineGapOut] = Field(default_factory=list)


class SnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["stream", "full"] = "stream"
    note: Optional[str] = None


class SnapshotOut(BaseModel):
    snapshot_id: str
    camera_id: str
    ts: float
    kind: str
    url: str
    width: int
    height: int
    size_bytes: int
    source_event_id: Optional[str] = None


class ClipExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_ts: float
    to_ts: float
    include_overlay: bool = False


class ClipExportOut(BaseModel):
    export_id: str
    camera_id: str
    start_ts: float
    end_ts: float
    duration_s: float
    url: str
    size_bytes: int
    created_at: float


class StorageSummaryOut(BaseModel):
    total_bytes: int
    free_bytes: int
    used_bytes: int
    recordings_bytes: int
    snapshots_bytes: int
    exports_bytes: int
    recordings_count: int = 0
    snapshots_count: int = 0
    exports_count: int = 0
    retention_policy: dict[str, Any] = Field(default_factory=dict)
