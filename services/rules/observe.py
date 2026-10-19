"""Track history and observation construction; no detector-specific objects."""

from collections import deque

from td_contracts import Observation, ObservedTrack


SCORE_WINDOW_S = 2.0
BORDER_PX = 3


class ObservationBuilder:
    def __init__(self, camera_id: str, detector_version: str, tracker: str, quality: dict | None = None):
        self.camera_id = camera_id
        self.versions = {"detector": detector_version, "tracker": tracker}
        self.quality = quality or {}
        self.history: dict[int, deque[tuple[float, tuple[float, float]]]] = {}
        self.scores: dict[int, deque[tuple[float, float]]] = {}
        self.first_seen: dict[int, float] = {}

    def _flags(self, cls: str, bbox, frame_size: tuple[int, int] | None) -> list[str]:
        """Plausibility flags: a box that fills the frame or touches most borders is rarely a whole, ordinary object."""
        if frame_size is None:
            return []
        config = self.quality.get(cls) or self.quality.get("default") or {}
        width, height = frame_size
        flags = []
        coverage = max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (width * height)
        if coverage > config.get("max_frame_coverage", 1.01):
            flags.append("oversized")
        contacts = sum((bbox[0] <= BORDER_PX, bbox[1] <= BORDER_PX, bbox[2] >= width - BORDER_PX, bbox[3] >= height - BORDER_PX))
        if contacts >= config.get("max_border_contacts", 5):
            flags.append("border")
        if contacts >= 1:
            flags.append("cropped")         # cut off by a frame edge (someone walking in or out of view)
        return flags

    def build(self, frame_id: int, ts: float, boxes: list[tuple[int, str, float, tuple[float, float, float, float]]],
              frame_size: tuple[int, int] | None = None) -> Observation:
        tracks = []
        live = set()
        for track_id, cls, conf, bbox in boxes:
            live.add(track_id)
            scores = self.scores.setdefault(track_id, deque())
            scores.append((ts, conf))
            while scores and ts - scores[0][0] > SCORE_WINDOW_S:
                scores.popleft()
            foot = ((bbox[0] + bbox[2]) / 2, bbox[3])
            history = self.history.setdefault(track_id, deque())
            history.append((ts, foot))
            while history and ts - history[0][0] > 60:
                history.popleft()
            self.first_seen.setdefault(track_id, ts)
            recent = list(history)[-5:]
            if len(recent) >= 2 and recent[-1][0] > recent[0][0]:
                elapsed = recent[-1][0] - recent[0][0]
                velocity = ((recent[-1][1][0] - recent[0][1][0]) / elapsed, (recent[-1][1][1] - recent[0][1][1]) / elapsed)
            else:
                velocity = (0.0, 0.0)
            tracks.append(ObservedTrack(track_id=track_id, cls=cls, conf=conf, bbox=bbox, foot=foot,
                                        velocity=velocity, first_seen=self.first_seen[track_id], last_seen=ts,
                                        score=sum(c for _, c in scores) / len(scores), flags=self._flags(cls, bbox, frame_size)))
        for old in list(self.history):
            history = self.history[old]
            if old not in live and history and ts - history[-1][0] > 60:
                self.history.pop(old, None)
                self.scores.pop(old, None)
                self.first_seen.pop(old, None)
        return Observation(camera_id=self.camera_id, ts=ts, frame_id=frame_id, tracks=tracks, model_versions=self.versions)
