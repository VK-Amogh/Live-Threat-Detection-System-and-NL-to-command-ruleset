"""Review extraction and conservative structured-response checks."""

import json
import sys
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from services.reasoner.frames import selected_frames
from services.reasoner.prompts import validate_review
from services.reasoner.loop import review_once
from services.rules.llm import LocalLLM


def test_extracts_spaced_images_from_recorded_clip():
    images = selected_frames(ROOT / "TestVideos/v001_converted 3.avi", (50, 50, 150, 150))
    assert len(images) == 3
    assert all(cv2.imdecode(__import__("numpy").frombuffer(image, dtype="uint8"), cv2.IMREAD_COLOR) is not None for image in images)


@pytest.mark.parametrize("claim", ["The person is trying to steal the car.",
                                    "The owner stands beside a car.",
                                    "A suspicious person scratches the vehicle.",
                                    "The scene is indoors.",
                                    "Possibly dogs are near the chairs."])
def test_rejects_intent_identity_or_proxy_action(claim):
    with pytest.raises(ValueError):
        validate_review({"visible_evidence": claim, "uncertainty": "Hands are unclear.",
                         "possible_false_positive": True})


def test_accepts_only_visible_evidence():
    result = validate_review({"visible_evidence": "A person is visible near a car in two frames.",
                              "uncertainty": "The person's hands and the area behind the car are not visible.",
                              "possible_false_positive": True})
    assert result.possible_false_positive


def test_llm_outage_retries_without_stopping_review_process(tmp_path):
    folder = tmp_path / "evt_test"
    folder.mkdir()
    writer = cv2.VideoWriter(str(folder / "clip.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 5, (64, 48))
    for _ in range(5):
        writer.write(np.zeros((48, 64, 3), dtype="uint8"))
    writer.release()
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path.endswith("/claim"):
            return httpx.Response(200, json={"job": {"claim_token": 123.0, "event": {
                "id": "evt_test", "category": {"label": "Person visible"}, "track_refs": [],
                "first_seen_at": "2026-10-16T00:00:00Z", "last_seen_at": "2026-10-16T00:00:03Z"}}})
        return httpx.Response(200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert review_once(client, "http://test", "secret",
                           LocalLLM("http://127.0.0.1:1", "offline", .2), tmp_path)
    assert calls[-1].url.path.endswith("/evt_test/retry")
    assert json.loads(calls[-1].content)["reason"]
