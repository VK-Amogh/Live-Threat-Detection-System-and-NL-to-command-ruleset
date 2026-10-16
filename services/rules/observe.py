"""Track history and observation construction; no detector-specific objects."""

from collections import deque

from td_contracts import Observation, ObservedTrack


class ObservationBuilder:
    def __init__(self, camera_id: str, detector_version: str, tracker: str):
        self.camera_id = camera_id
        self.versions = {"detector": detector_version, "tracker": tracker}
        self.history: dict[int, deque[tuple[float, tuple[float, float]]]] = {}
        self.first_seen: dict[int, float] = {}

    def build(self, frame_id: int, ts: float, boxes: list[tuple[int, str, float, tuple[float, float, float, float]]]) -> Observation:
        tracks = []
        live = set()
        for track_id, cls, conf, bbox in boxes:
            live.add(track_id)
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
                                        velocity=velocity, first_seen=self.first_seen[track_id], last_seen=ts))
        for old in list(self.history):
            history = self.history[old]
            if old not in live and history and ts - history[-1][0] > 60:
                self.history.pop(old, None)
                self.first_seen.pop(old, None)
        return Observation(camera_id=self.camera_id, ts=ts, frame_id=frame_id, tracks=tracks, model_versions=self.versions)
