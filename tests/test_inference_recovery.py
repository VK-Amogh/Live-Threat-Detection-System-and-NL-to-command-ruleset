"""Detector memory pressure must not stop capture or duplicate health alerts."""

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from services.rules.inference import ResilientInference


class IntermittentDetector:
    def __init__(self):
        self.calls = 0

    def observe(self, frame, frame_id, ts):
        self.calls += 1
        if self.calls <= 3 or self.calls == 5:
            raise RuntimeError("CUDA out of memory")
        return {"frame_id": frame_id, "ts": ts}


def test_oom_skips_frames_reports_once_and_recovers(monkeypatch):
    monkeypatch.setattr("services.rules.inference.torch.cuda.is_available", lambda: False)
    health = []
    adapter = ResilientInference("cam1", IntermittentDetector(), health.append)
    assert adapter.observe(None, 1, 0) is None
    assert adapter.observe(None, 2, 5) is None
    assert adapter.observe(None, 3, 6) is None
    assert len(health) == 1 and health[0].kind == "inference_failure"
    assert adapter.observe(None, 4, 7) == {"frame_id": 4, "ts": 7}
    assert adapter.observe(None, 5, 8) is None
    assert len(health) == 1
    assert adapter.observe(None, 6, 9) == {"frame_id": 6, "ts": 9}


def test_unrelated_inference_error_is_not_hidden():
    class BrokenDetector:
        def observe(self, *_):
            raise RuntimeError("Invalid tensor shape")

    adapter = ResilientInference("cam1", BrokenDetector(), lambda _: None)
    with pytest.raises(RuntimeError, match="Invalid tensor shape"):
        adapter.observe(None, 1, 0)
