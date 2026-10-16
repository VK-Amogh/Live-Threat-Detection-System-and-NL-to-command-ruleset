"""Rule management, camera geometry and worker event wire contracts."""

from typing import Literal
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CameraGeometry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: dict[str, list[tuple[float, float]]] = Field(default_factory=dict)
    lines: dict[str, tuple[tuple[float, float], tuple[float, float]]] = Field(default_factory=dict)
    homography: list[list[float]] | None = None
    snapshot_width: int = Field(gt=0)
    snapshot_height: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_geometry(self):
        for name, polygon in self.zones.items():
            if not name or len(polygon) < 3 or len({tuple(point) for point in polygon}) < 3:
                raise ValueError("zones need a name and at least three distinct points")
            if any(not isfinite(x) or not isfinite(y) or not 0 <= x <= self.snapshot_width or not 0 <= y <= self.snapshot_height for x, y in polygon):
                raise ValueError("zone point outside snapshot")
        for name, (a, b) in self.lines.items():
            if not name or a == b:
                raise ValueError("lines need a name and two distinct points")
            if any(not isfinite(x) or not isfinite(y) or not 0 <= x <= self.snapshot_width or not 0 <= y <= self.snapshot_height for x, y in (a, b)):
                raise ValueError("line point outside snapshot")
        if self.homography is not None and (len(self.homography) != 3 or any(len(row) != 3 for row in self.homography)):
            raise ValueError("homography must be a 3x3 matrix")
        if self.homography is not None:
            h = self.homography
            if not all(isfinite(value) for row in h for value in row):
                raise ValueError("homography must contain finite numbers")
            determinant = (h[0][0] * (h[1][1] * h[2][2] - h[1][2] * h[2][1])
                           - h[0][1] * (h[1][0] * h[2][2] - h[1][2] * h[2][0])
                           + h[0][2] * (h[1][0] * h[2][1] - h[1][1] * h[2][0]))
            if abs(determinant) < 1e-12:
                raise ValueError("homography must be invertible")
        return self


class RuleCompileRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    camera_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=1000)
    needs_visual_review: bool = False


class RuleActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    confirmed_readback_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledge_experimental: bool = False


class RuleStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["active", "disabled"]
    expected_version: int = Field(ge=1)


class RuleEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    rule_id: str = Field(min_length=1)
    rule_version: int = Field(ge=1)
    ts: float = Field(ge=0)
    episode_start: float = Field(ge=0)
    status: Literal["DETECTED"] = "DETECTED"
    tracks: list[int]
    model_versions: dict[str, str]
    confidence: float = Field(ge=0, le=1)
    uncertainty: str
    needs_visual_review: bool = False
    evidence_bbox: tuple[int, int, int, int] | None = None


class ReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible_evidence: str = Field(min_length=1, max_length=1200)
    uncertainty: str = Field(min_length=1, max_length=1200)
    possible_false_positive: bool


class ReviewFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_token: float
    reason: str = Field(min_length=1, max_length=200)


class ReviewCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_token: float
    result: ReviewResult


class CameraHealthEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    ts: float = Field(ge=0)
    reason: str = Field(min_length=1)
