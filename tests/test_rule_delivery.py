"""Durable queue and delayed evidence behavior."""

import io
import sys
import time
from pathlib import Path

import httpx
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT)]
from td_contracts import RuleEvent
from services.rules.evidence import EvidenceBuffer
from services.rules.outbox import RuleOutbox


def jpeg(color):
    output = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(output, format="JPEG")
    return output.getvalue()


def test_outbox_keeps_event_until_api_acknowledges(tmp_path):
    outbox = RuleOutbox(tmp_path / "outbox.db", "http://test", "secret")
    event = RuleEvent(event_id="event-1", camera_id="cam", rule_id="r1", rule_version=2,
                      ts=100, episode_start=97, tracks=[12], model_versions={"detector": "test"},
                      confidence=.8, uncertainty="fixture")
    outbox.enqueue_event(event)
    outbox.enqueue_event(event)
    assert outbox.pending_count() == 1
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, json={"ok": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert outbox.flush_once(client) is False
        assert outbox.pending_count() == 1
        with outbox._db() as db:
            db.execute("UPDATE pending SET next_at=0")
        assert outbox.flush_once(client) is True
    assert outbox.pending_count() == 0
    assert all(call.headers["Idempotency-Key"] == "event-1" for call in calls)


def test_outbox_recovers_after_network_drop_and_process_restart(tmp_path):
    path = tmp_path / "outbox.db"
    outbox = RuleOutbox(path, "http://test", "secret")
    event = RuleEvent(event_id="event-restart", camera_id="cam", rule_id="r1", rule_version=2,
                      ts=100, episode_start=97, tracks=[12], model_versions={"detector": "test"},
                      confidence=.8, uncertainty="fixture")
    outbox.enqueue_event(event)

    def disconnected(request):
        raise httpx.ConnectError("network down", request=request)

    with httpx.Client(transport=httpx.MockTransport(disconnected)) as client:
        assert outbox.flush_once(client) is False
    assert outbox.pending_count() == 1

    restarted = RuleOutbox(path, "http://test", "secret")
    with restarted._db() as db:
        db.execute("UPDATE pending SET next_at=0")
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))) as client:
        assert restarted.flush_once(client) is True
    assert restarted.pending_count() == 0


def test_evidence_has_pre_and_post_roll(tmp_path):
    evidence = EvidenceBuffer(tmp_path, fps=5, pre_roll_s=1, post_roll_s=.4)
    evidence.append(0, jpeg("red"))
    evidence.append(.2, jpeg("green"))
    evidence.start("event-1", .2, jpeg("green"))
    assert (tmp_path / "event-1/frame.jpg").is_file()
    assert evidence.append(.4, jpeg("blue")) == []
    assert evidence.append(.6, jpeg("yellow")) == ["event-1"]
    clip = tmp_path / "event-1/clip.mp4"
    assert clip.is_file() and clip.stat().st_size > 0
