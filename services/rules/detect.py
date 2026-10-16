"""Ultralytics tracking adapter for a single consecutive camera stream."""

import hashlib
from pathlib import Path

from ultralytics import YOLO

from td_contracts import Observation
from .observe import ObservationBuilder


class CameraDetector:
    def __init__(self, camera_id: str, weights: Path, tracker: str, confidence: float, image_size: int):
        self.model = YOLO(str(weights))
        digest = hashlib.sha256(weights.read_bytes()).hexdigest()[:12]
        self.builder = ObservationBuilder(camera_id, f"{weights.name}@{digest}", tracker)
        self.tracker = tracker
        self.confidence = confidence
        self.image_size = image_size
        self.classes = set(self.model.names.values())

    def observe(self, frame, frame_id: int, ts: float) -> Observation:
        result = self.model.track(frame, persist=True, tracker=self.tracker, conf=self.confidence,
                                  imgsz=self.image_size, verbose=False)[0]
        boxes = []
        if result.boxes.id is not None:
            for item in result.boxes:
                bbox = tuple(float(v) for v in item.xyxy[0].tolist())
                boxes.append((int(item.id.item()), result.names[int(item.cls.item())], float(item.conf.item()), bbox))
        return self.builder.build(frame_id, ts, boxes)
