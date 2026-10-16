"""API persistence, activation and event idempotency checks."""

import sys
import uuid
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src"), str(ROOT)]
from app import database, main, pipeline, rule_routes
from td_contracts import RuleCompileResult, RuleSpec, RuleWhen


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setattr(pipeline, "STORAGE", tmp_path)
    monkeypatch.setattr(rule_routes, "STORAGE", tmp_path)
    monkeypatch.setattr(rule_routes, "INTERNAL_TOKEN", "worker-secret")
    monkeypatch.setattr(rule_routes, "detector_classes", lambda: {"person", "car"})
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "admin@gmail.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin123")
    (tmp_path / "media").mkdir()
    (tmp_path / "uploads").mkdir()
    main.ATTEMPTS.clear()
    main.TICKETS.clear()
    with TestClient(main.app) as api:
        assert api.post("/api/v1/auth/login", json={"username": "admin@gmail.com", "password": "admin123", "device_name": "test", "client_type": "web"}).status_code == 200
        yield api


def test_rule_activation_and_idempotent_event(client, monkeypatch, tmp_path):
    camera = client.post("/api/v1/cameras", json={"name": "Driveway", "source_type": "WEBCAM", "connection_uri": "0"}).json()
    camera_id = camera["id"]
    geometry = {"snapshot_width": 640, "snapshot_height": 480,
                "zones": {"driveway": [[10, 10], [200, 10], [200, 200], [10, 200]]},
                "lines": {}, "homography": None}
    assert client.put(f"/api/v1/cameras/{camera_id}/geometry", json={
        **geometry, "homography": [[0, 0, 0], [0, 0, 0], [0, 0, 0]]}).status_code == 422
    assert client.put(f"/api/v1/cameras/{camera_id}/geometry", json=geometry).status_code == 200

    class FakeCompiler:
        def compile(self, text, selected_camera):
            rule = RuleSpec(rule_id="r_test", camera_id=selected_camera, version=1, name="Driveway person",
                            entity="person", when=RuleWhen(type="in_zone", zone="driveway"), support_level="SUPPORTED")
            return RuleCompileResult(spec=rule, readback="Alert when a tracked person is inside driveway.",
                                     support_level="SUPPORTED", problems=[], can_activate=True)

    monkeypatch.setattr(rule_routes.RuleCompiler, "from_config", lambda *args: FakeCompiler())
    draft = client.post("/api/v1/rules/compile", json={"camera_id": camera_id, "text": "person in driveway",
                                                        "needs_visual_review": True})
    assert draft.status_code == 200, draft.text
    assert draft.json()["spec"]["needs_visual_review"] is True
    assert "visual summary" in draft.json()["readback"]
    digest = draft.json()["readback_hash"]
    assert len(digest) == 64
    wrong = client.post("/api/v1/rules/r_test/activate", json={"expected_version": 1, "confirmed_readback_hash": "0" * 64})
    assert wrong.status_code == 409
    active = client.post("/api/v1/rules/r_test/activate", json={"expected_version": 1, "confirmed_readback_hash": digest})
    assert active.status_code == 200, active.text
    assert active.json()["status"] == "active" and active.json()["version"] == 2

    event_id = str(uuid.uuid4())
    folder = tmp_path / "media" / event_id
    folder.mkdir()
    pixels = io.BytesIO()
    Image.new("RGB", (64, 48), "grey").save(pixels, format="JPEG")
    (folder / "frame.jpg").write_bytes(pixels.getvalue())
    body = {"event_id": event_id, "camera_id": camera_id, "rule_id": "r_test", "rule_version": 2,
            "ts": 1792121403.0, "episode_start": 1792121400.0, "status": "DETECTED",
            "tracks": [12], "model_versions": {"detector": "fixture", "tracker": "bytetrack"},
            "confidence": .87, "uncertainty": "Single camera angle", "needs_visual_review": True}
    headers = {"Authorization": "Bearer worker-secret", "Idempotency-Key": event_id}
    path = "/api/v1/internal/rule-events"
    first = client.post(path, json=body, headers=headers)
    second = client.post(path, json=body, headers=headers)
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["created"] is True and second.json()["created"] is False
    changes = client.get("/api/v1/changes?after=0").json()["items"]
    assert len(changes) == 1 and changes[0]["rule_id"] == "r_test"
    assert changes[0]["change_seq"] == 1
    assert changes[0]["media"][0]["width"] == 64

    # Reinitializing the API against the same SQLite file keeps the first commit.
    with TestClient(main.app) as restarted:
        assert restarted.post("/api/v1/auth/login", json={"username": "admin@gmail.com", "password": "admin123", "device_name": "restart", "client_type": "web"}).status_code == 200
        repeated = restarted.post(path, json=body, headers=headers)
        assert repeated.status_code == 200 and repeated.json()["created"] is False
        assert restarted.get("/api/v1/changes?after=0").json()["head_seq"] == 1

    (folder / "clip.mp4").write_bytes(b"recorded clip fixture")
    clip = client.post(f"/api/v1/internal/events/{event_id}/clip", headers={"Authorization": "Bearer worker-secret"})
    assert clip.status_code == 200 and clip.json()["created"] is True
    assert client.post(f"/api/v1/internal/events/{event_id}/clip", headers={"Authorization": "Bearer worker-secret"}).json()["created"] is False
    updates = client.get("/api/v1/changes?after=1").json()["items"]
    assert len(updates) == 1 and updates[0]["change_seq"] == 2
    assert [media["kind"] for media in updates[0]["media"]] == ["KEYFRAME", "CLIP"]


def test_unsupported_rule_cannot_activate(client, monkeypatch):
    camera = client.post("/api/v1/cameras", json={"name": "Driveway", "source_type": "WEBCAM", "connection_uri": "0"}).json()

    class FakeCompiler:
        def compile(self, text, selected_camera):
            rule = RuleSpec(rule_id="r_bad", camera_id=selected_camera, version=1, name=text,
                            entity="unknown", when=None, support_level="UNSUPPORTED",
                            unsupported_reason="Action recognition unsupported")
            return RuleCompileResult(spec=rule, readback=None, support_level="UNSUPPORTED",
                                     problems=["Action recognition unsupported"], can_activate=False)

    monkeypatch.setattr(rule_routes.RuleCompiler, "from_config", lambda *args: FakeCompiler())
    draft = client.post("/api/v1/rules/compile", json={"camera_id": camera["id"], "text": "scratch my car"})
    assert draft.status_code == 200 and draft.json()["support_level"] == "UNSUPPORTED"
    response = client.post("/api/v1/rules/r_bad/activate", json={"expected_version": 1, "confirmed_readback_hash": "0" * 64})
    assert response.status_code == 409


def test_visual_review_job_retries_and_updates_change_feed(client, tmp_path):
    camera = client.post("/api/v1/cameras", json={"name": "Patio", "source_type": "WEBCAM", "connection_uri": "0"}).json()
    spec = RuleSpec(rule_id="r_review", camera_id=camera["id"], version=2, name="Patio person",
                    entity="person", when=RuleWhen(type="entity_present"), support_level="SUPPORTED",
                    status="active", needs_visual_review=True)
    database.put_rule({"id": spec.rule_id, "camera_id": camera["id"], "text": "person on patio",
                       "spec_json": spec.model_dump_json(by_alias=True), "readback": "person on patio",
                       "readback_hash": "a" * 64, "can_activate": 1, "status": "active",
                       "version": 2, "updated_at": "2026-10-16T00:00:00Z"})
    ident = str(uuid.uuid4())
    folder = tmp_path / "media" / ident
    folder.mkdir()
    pixels = io.BytesIO()
    Image.new("RGB", (64, 48), "grey").save(pixels, format="JPEG")
    (folder / "frame.jpg").write_bytes(pixels.getvalue())
    headers = {"Authorization": "Bearer worker-secret", "Idempotency-Key": ident}
    body = {"event_id": ident, "camera_id": camera["id"], "rule_id": "r_review", "rule_version": 2,
            "ts": 1792121403.0, "episode_start": 1792121400.0, "tracks": [12],
            "model_versions": {"detector": "fixture"}, "confidence": .8,
            "uncertainty": "Single angle", "needs_visual_review": True}
    assert client.post("/api/v1/internal/rule-events", headers=headers, json=body).status_code == 200
    assert client.post("/api/v1/internal/review-jobs/claim", headers=headers).json()["job"] is None
    (folder / "clip.mp4").write_bytes(b"clip fixture")
    assert client.post(f"/api/v1/internal/events/{ident}/clip", headers=headers).status_code == 200
    job = client.post("/api/v1/internal/review-jobs/claim", headers=headers).json()["job"]
    assert job["event"]["status"] == "VERIFYING"
    failed = client.post(f"/api/v1/internal/review-jobs/{ident}/retry", headers=headers,
                         json={"claim_token": job["claim_token"], "reason": "LLM server stopped"})
    assert failed.status_code == 200 and failed.json()["event"]["status"] == "DETECTED"
    with database.connection() as con:
        con.execute("UPDATE review_jobs SET lease_until=0 WHERE event_id=?", (ident,))
    job = client.post("/api/v1/internal/review-jobs/claim", headers=headers).json()["job"]
    completed = client.post(f"/api/v1/internal/review-jobs/{ident}/complete", headers=headers,
                            json={"claim_token": job["claim_token"], "result": {
                                "visible_evidence": "One person is visible beside a parked car.",
                                "uncertainty": "The person's hands are obscured.",
                                "possible_false_positive": False}})
    assert completed.status_code == 200 and completed.json()["event"]["status"] == "NEEDS_REVIEW"
    assert client.post("/api/v1/internal/review-jobs/claim", headers=headers).json()["job"] is None
    updates = client.get("/api/v1/changes?after=0").json()["items"]
    assert [item["status"] for item in updates] == ["DETECTED", "DETECTED", "VERIFYING", "DETECTED", "VERIFYING", "NEEDS_REVIEW"]
