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

    @model_validator(mode="after")
    def valid_geometry(self):
        if self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
            raise ValueError("bbox must have positive area")
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must not exceed last_seen")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
