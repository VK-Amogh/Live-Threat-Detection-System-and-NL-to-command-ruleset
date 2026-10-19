"""Chat digest of uploaded videos: question recognition, time windows, key frames and the streamed answer."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src"), str(ROOT)]
from app import chat, video_digest as vd  # noqa: E402
from td_contracts.chat import ChatRequest  # noqa: E402

NOW = datetime(2026, 10, 17, 13, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))


@pytest.mark.parametrize("question,expected", [
    ("summarize all the videos uploaded in past 1 hour", True),
    ("Summarise every clip uploaded in the last half an hour", True),
    ("which videos did we upload today", True),
    ("what is the latest video", True),
    ("give me a summary of the last 3 videos", True),
    ("list all videos uploaded in the past 2 days", True),
    ("Summarize the most recent incident and what the footage shows.", False),
    ("show me the footage of the knife incident", False),
    ("What is happening right now on the live cameras?", False),
    ("Which rulesets and camera rules are currently active?", False),
    ("play the clip from camera 2", False),
])
def test_only_questions_about_the_uploaded_videos_take_the_digest_path(question, expected):
    assert vd.wants(question) is expected


@pytest.mark.parametrize("question,label,minutes", [
    ("videos uploaded in the past 1 hour", "the past hour", 60),
    ("videos uploaded in the last 30 minutes", "the past 30 minutes", 30),
    ("summarise every clip uploaded in the last half an hour", "the past 30 minutes", 30),
    ("all videos uploaded in the past 2 days", "the past 2 days", 2880),
    ("videos from the last two hours", "the past 2 hours", 120),
])
def test_time_windows_are_read_from_the_question(question, label, minutes):
    window = vd.parse_window(question, NOW)
    assert window.label == label and window.explicit
    assert (window.end - window.start).total_seconds() == minutes * 60


def test_counts_today_and_the_default_window():
    assert vd.parse_window("summarize the last 3 videos", NOW).limit == 3
    assert vd.parse_window("what is the latest video", NOW).limit == 1
    today = vd.parse_window("videos uploaded today", NOW)
    assert today.start == NOW.replace(hour=0, minute=0) and today.label == "today"
    default = vd.parse_window("summarize all the videos", NOW)
    assert not default.explicit and (default.end - default.start) == timedelta(hours=24)


def source(ident, minutes_ago, kind="video", **extra):
    stamp = (NOW.astimezone(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": ident, "filename": f"{ident}.webm", "kind": kind, "status": "DONE", "created_at": stamp, "event_ids": [], "media_url": f"/api/v1/sources/{ident}/media", **extra}


def test_only_videos_inside_the_window_come_back_newest_first(monkeypatch):
    monkeypatch.setattr(vd.db, "all_objects", lambda kind: [source("old", 300), source("a", 50), source("img", 10, kind="image"), source("b", 5)])
    window = vd.parse_window("videos uploaded in the past hour", NOW)
    assert [s["id"] for _, s in vd.uploaded_videos(window)] == ["b", "a"]
    assert [s["id"] for _, s in vd.uploaded_videos(vd.parse_window("the last 1 video", NOW))] == ["b"]


def make_video(path: Path, scenes=((30, 30, 200), (30, 200, 30), (200, 30, 30)), seconds_each=2, fps=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (160, 90))
    rng = np.random.default_rng(1)
    for colour in scenes:
        for _ in range(seconds_each * fps):
            frame = np.full((90, 160, 3), colour, dtype=np.uint8)
            frame[rng.integers(0, 60):, rng.integers(0, 100):] = rng.integers(0, 255, 3, dtype=np.uint8)   # texture so frames are sharp
            writer.write(frame)
    writer.release()


def test_key_frames_cover_every_scene_and_start_with_the_alert_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(vd, "STORAGE", tmp_path)
    monkeypatch.setattr(vd, "count_objects", lambda frames: {"person": 1})
    folder = tmp_path / "uploads" / "vid1"
    folder.mkdir(parents=True)
    make_video(folder / "playback.mp4")
    meta = vd.prepare_frames("vid1", [5000])                               # an alert 5 s in, the middle scene
    assert meta["duration_s"] == pytest.approx(6.0, abs=.3) and meta["objects"] == {"person": 1}
    assert 3 <= len(meta["frames"]) <= vd.KEYFRAMES
    assert [f["t_ms"] for f in meta["frames"]] == sorted(f["t_ms"] for f in meta["frames"])
    assert any(f["alert"] and 4000 <= f["t_ms"] <= 6000 for f in meta["frames"])
    colours = {tuple(int(v) // 100 for v in cv2.imread(str(folder / "keyframes" / f"{f['n']}.jpg"))[2, 2]) for f in meta["frames"]}
    assert len(colours) == 3                                               # all three scenes are represented
    assert vd.prepare_frames("vid1", [5000]) == meta                       # second call reads the cache


def test_a_still_scene_still_gets_frames_spread_over_the_video(tmp_path, monkeypatch):
    monkeypatch.setattr(vd, "STORAGE", tmp_path)
    monkeypatch.setattr(vd, "count_objects", lambda frames: {})
    folder = tmp_path / "uploads" / "still"
    folder.mkdir(parents=True)
    make_video(folder / "playback.mp4", scenes=((120, 120, 120),), seconds_each=8)
    meta = vd.prepare_frames("still", [])
    assert len(meta["frames"]) >= 3 and meta["frames"][-1]["t_ms"] - meta["frames"][0]["t_ms"] > 3000


def test_an_unreadable_upload_gives_no_frames_instead_of_failing(tmp_path, monkeypatch):
    monkeypatch.setattr(vd, "STORAGE", tmp_path)
    (tmp_path / "uploads" / "bad").mkdir(parents=True)
    (tmp_path / "uploads" / "bad" / "playback.mp4").write_bytes(b"not a video")
    assert vd.prepare_frames("bad", [])["frames"] == []
    assert vd.prepare_frames("missing", [])["frames"] == []


class FakeDb:
    def __init__(self, sources, events=()):
        self.sources, self.events = sources, {e["id"]: e for e in events}
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.execute("CREATE TABLE conversations(id TEXT PRIMARY KEY, user_id TEXT, body TEXT)")

    def all_objects(self, kind):
        return self.sources if kind == "source" else []

    def get(self, kind, ident):
        return self.events.get(ident)

    @contextmanager
    def connection(self):
        yield self.con


def run_stream(message, fake, monkeypatch, tmp_path, caption="A person sits at a desk and waves."):
    async def describe(source_id, meta, alerts, model_name):
        return caption
    monkeypatch.setattr(vd, "db", fake)
    monkeypatch.setattr(vd, "STORAGE", tmp_path)
    monkeypatch.setattr(vd, "describe", describe)
    monkeypatch.setattr(vd, "count_objects", lambda frames: {"person": 1})
    monkeypatch.setattr(chat, "settings", lambda: {"ollama_model": "test-model"})

    async def collect():
        return [item async for item in vd.stream(ChatRequest(message=message), {"user_id": "u1"})]
    return asyncio.run(collect())


def test_the_stream_lists_every_video_with_key_frames_and_a_summary(tmp_path, monkeypatch):
    for ident in ("a", "b"):
        (tmp_path / "uploads" / ident).mkdir(parents=True)
        make_video(tmp_path / "uploads" / ident / "playback.mp4")
    event = {"id": "evt_1", "category": {"label": "Fight"}, "status": "NEEDS_REVIEW", "severity": "HIGH", "peak_confidence": .91, "media_offset_ms": 3000}
    fake = FakeDb([source("a", 40, event_ids=["evt_1"]), source("b", 10), source("old", 500)], [event])
    items = run_stream("summarize all the videos uploaded in the past hour", fake, monkeypatch, tmp_path)
    kinds = [i["type"] for i in items]
    assert kinds[:4] == ["plan", "evidence", "context", "delta"] and kinds[-1] == "done"
    digest = next(i for i in items if i["type"] == "digest")
    assert digest["total"] == 2 and [x["source_id"] for x in digest["items"]] == ["b", "a"] and digest["items"][0]["summary_kind"] == "pending"
    done = items[-1]
    assert [x["source_id"] for x in done["digest"]["items"]] == ["b", "a"]
    newest, alerted = done["digest"]["items"]
    assert newest["summary"] == "A person sits at a desk and waves." and newest["summary_kind"] == "ai" and len(newest["frames"]) >= 3
    assert newest["frames"][0]["url"] == "/api/v1/sources/b/keyframes/1.jpg"
    assert alerted["alerts"][0]["label"] == "Fight" and any(f["alert"] for f in alerted["frames"])
    assert "old" not in done["answer"] and "the past hour" in done["answer"] and "a.webm" in done["answer"]
    assert len(done["cited"]) == 2 and done["cited"][0]["poster_url"] and done["cited"][0]["clip_url"].endswith("/media")
    saved = fake.con.execute("SELECT body FROM conversations").fetchone()[0]
    assert "keyframes/1.jpg" in saved                                      # reopening the chat still shows the cards


def test_no_uploads_in_the_window_says_so_and_names_the_latest(tmp_path, monkeypatch):
    items = run_stream("summarize the videos uploaded in the past 5 minutes", FakeDb([source("a", 300)]), monkeypatch, tmp_path)
    done = items[-1]
    assert done["type"] == "done" and done["digest"] is None and done["cited"] == []
    assert "No videos were uploaded in the past 5 minutes" in done["answer"] and "a.webm" in done["answer"]


def test_without_the_model_the_digest_still_answers_from_detector_facts(tmp_path, monkeypatch):
    (tmp_path / "uploads" / "a").mkdir(parents=True)
    make_video(tmp_path / "uploads" / "a" / "playback.mp4")
    items = run_stream("summarize the last video", FakeDb([source("a", 3)]), monkeypatch, tmp_path, caption=None)
    card = items[-1]["digest"]["items"][0]
    assert card["summary_kind"] == "facts" and "person x1" in card["summary"] and "unavailable" in card["summary"]


def test_a_failed_upload_is_listed_with_its_reason(tmp_path, monkeypatch):
    fake = FakeDb([source("bad", 3, status="FAILED", error="Video could not be decoded.", media_url=None)])
    card = run_stream("summarize the last video", fake, monkeypatch, tmp_path)[-1]["digest"]["items"][0]
    assert card["summary_kind"] == "unavailable" and "could not be decoded" in card["summary"] and card["frames"] == []
