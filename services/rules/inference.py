"""Keep camera capture running through transient detector memory pressure."""

import logging
import uuid

import torch

from td_contracts import CameraHealthEvent


LOG = logging.getLogger(__name__)


class ResilientInference:
    def __init__(self, camera_id, detector, report_health):
        self.camera_id = camera_id
        self.detector = detector
        self.report_health = report_health
        self.failed_since = None
        self.health_sent = False

    def observe(self, frame, frame_id, ts):
        try:
            observation = self.detector.observe(frame, frame_id, ts)
        except (MemoryError, RuntimeError) as exc:
            if not isinstance(exc, MemoryError) and "out of memory" not in str(exc).lower():
                raise
            if self.failed_since is None:
                self.failed_since = ts
                LOG.warning("Rule detector ran out of memory on %s", self.camera_id)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if ts - self.failed_since >= 5 and not self.health_sent:
                event = CameraHealthEvent(
                    event_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                        f"inference:{self.camera_id}:{self.failed_since:.3f}")),
                    camera_id=self.camera_id, ts=ts, kind="inference_failure",
                    reason="Rule detector unavailable after repeated out-of-memory errors")
                self.report_health(event)
                self.health_sent = True
            return None
        self.failed_since = None
        self.health_sent = False
        return observation
