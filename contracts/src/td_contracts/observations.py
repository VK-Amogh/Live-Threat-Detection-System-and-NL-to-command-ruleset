"""Validated output of one processed camera frame."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObservedTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id: int = Field(ge=0)
    cls: str = Field(min_length=1)
    conf: float = Field(ge=0, le=1)
    bbox: tuple[float, float, float, float]
    foot: tuple[float, float]
    velocity: tuple[float, float]
    first_seen: float
    last_seen: float
    score: float | None = Field(default=None, ge=0, le=1)      # mean detector confidence over the recent track window
    flags: list[str] = Field(default_factory=list)              # plausibility flags, e.g. "oversized", "border"
    keypoints: list[tuple[float, float, float]] | None = None   # 17 COCO keypoints (x, y, confidence), people only

    @model_validator(mode="after")
    def valid_geometry(self):
        if self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
            raise ValueError("bbox must have positive area")
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must not exceed last_seen")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_change: dict[str, float] = Field(default_factory=dict)   # share of each watched zone that differs from its baseline (0..1)

    camera_id: str = Field(min_length=1)
    ts: float = Field(ge=0)
    frame_id: int = Field(ge=0)
    tracks: list[ObservedTrack]
    model_versions: dict[str, str]

    @model_validator(mode="after")
    def valid_tracks(self):
        if any(track.last_seen != self.ts for track in self.tracks):
            raise ValueError("all tracks must belong to the observation timestamp")
        ids = [track.track_id for track in self.tracks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate track IDs in one observation")
        return self
