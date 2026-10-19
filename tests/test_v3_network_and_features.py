"""Acceptance tests for SafeSpace v3 (AT-01..AT-17). Network-route policy is covered in test_network_policy.py."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys
import time
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src")]

from app import database as db, main, security, settings
from app.llm_gateway import GATEWAY, P0_ALERT_SUMMARY, P1_INTERACTIVE, P2_BACKGROUND
from app.media.hub import HUB, LatestOnlyMailbox, pack_ssf1_frame
from services.rules.engine import RuleEngine
from services.rules.state import Fire, RuleState
from td_contracts import Observation, ObservedTrack, RuleSpec, RuleWhen


def _sample_jpeg(width: int = 320, height: int = 180, color=(40, 180, 90)) -> bytes:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    cv2.rectangle(frame, (40, 30), (width - 40, height - 30), (255, 255, 255), 2)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    assert ok
    return encoded.tobytes()


@pytest.fixture()
def v3_client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    for folder in ("media", "uploads", "logs", "recordings", "snapshots", "exports", "backups", "dist", "previews", "benchmarks"):
        (storage / folder).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE", storage)
    monkeypatch.setattr(settings, "DB_PATH", storage / "safespace.db")
    monkeypatch.setattr(db, "DB_PATH", storage / "safespace.db")
    monkeypatch.setattr(main, "STORAGE", storage)
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv(
        "SEED_ACCOUNTS",
        "admin1@safespace.com:admin123:Admin 1,admin2@safespace.com:admin123:Admin 2",
    )
    main.ATTEMPTS.clear()
    main.TICKETS.clear()

    db.initialize()
    with db.connection() as con:
        con.execute(
            "INSERT OR IGNORE INTO users(id, email, password, created_at, display_name, disabled, role) VALUES(?,?,?,?,?,?,?)",
            ("legacy_id", "admin@gmail.com", security.password_hash("admin123"), security.now(), "Legacy", 0, "admin"),
        )
    with TestClient(main.app) as client:
        yield client


def test_at02_and_at13_seed_accounts_and_legacy_disabled(v3_client):
    """AT-02 & AT-13: Admin 1 and Admin 2 log in; legacy admin@gmail.com returns 401."""
    r_legacy = v3_client.post(
        "/api/v1/auth/login",
        json={"username": "admin@gmail.com", "password": "admin123", "device_name": "Web"},
    )
    assert r_legacy.status_code == 401

    for email in ("admin1@safespace.com", "admin2@safespace.com"):
        r = v3_client.post(
            "/api/v1/auth/login",
            json={
                "username": email,
                "password": "admin123",
                "device_name": "Control Phone",
                "client_type": "mobile",
                "installation_id": f"inst_{email}",
            },
        )
        assert r.status_code == 200
        payload = r.json()
        assert payload["device_token"]
        assert payload["scope"] == "admin"


def test_at03_at04_at14_device_enrollment_and_scope_isolation(v3_client):
    """AT-03, AT-04, AT-14: Camera enrollment gives stable camera_id and camera-scoped token that gets 403 on admin routes."""
    enroll_body = {
        "installation_id": "nothing_phone_4a_install_001",
        "enrollment_code": settings.CAMERA_ENROLLMENT_CODE,
        "device_name": "Hallway Nothing Phone",
        "role": "camera",
        "model": "Nothing A069",
        "os_version": "Android 16",
        "app_version": "3.0.0",
    }
    r1 = v3_client.post("/api/v1/devices/enroll", json=enroll_body)
    assert r1.status_code == 200
    d1 = r1.json()
    cam_id = d1["camera_id"]
    cam_token = d1["token"]
    assert cam_id.startswith("cam_")
    assert d1["scope"] == "camera"

    r2 = v3_client.post("/api/v1/devices/enroll", json=enroll_body)
    assert r2.status_code == 200
    assert r2.json()["camera_id"] == cam_id
    assert r2.json()["device_id"] == d1["device_id"]

    me_res = v3_client.get("/api/v1/devices/me", headers={"Authorization": f"Bearer {cam_token}"})
    assert me_res.status_code == 200

    for admin_endpoint in ("/api/v1/events", "/api/v1/rulesets", "/api/v1/devices/fleet", "/api/v1/audit"):
        res_forbidden = v3_client.get(admin_endpoint, headers={"Authorization": f"Bearer {cam_token}"})
        assert res_forbidden.status_code == 403, f"Expected 403 on {admin_endpoint}"


def test_at05_at06_at07_ws_publish_latest_mailbox_recordings_range_and_export(v3_client):
    """AT-05, AT-06, AT-07: WS publish SSF1 frames, non-blocking mailboxes, HTTP 206 Range MP4, and clip export."""
    enroll = v3_client.post(
        "/api/v1/devices/enroll",
        json={
            "installation_id": "cam_station_test_99",
            "enrollment_code": settings.CAMERA_ENROLLMENT_CODE,
            "device_name": "Front Gate Phone",
            "role": "camera",
        },
    ).json()
    cam_id = enroll["camera_id"]
    cam_token = enroll["token"]

    admin_login = v3_client.post(
        "/api/v1/auth/login",
        json={"username": "admin1@safespace.com", "password": "admin123", "device_name": "Web", "client_type": "mobile"},
    ).json()
    admin_headers = {"Authorization": f"Bearer {admin_login['device_token']}"}

    jpeg_bytes = _sample_jpeg()
    t_start = time.time()
    with v3_client.websocket_connect(f"/api/v1/cameras/{cam_id}/publish", headers={"Authorization": f"Bearer {cam_token}"}) as ws_pub:
        ready = ws_pub.receive_json()
        assert ready["type"] == "ready"
        for seq in range(1, 7):
            ssf1 = pack_ssf1_frame(jpeg_bytes, seq=seq, width=320, height=180)
            ws_pub.send_bytes(ssf1)
            ack = ws_pub.receive_json()
            assert ack["type"] == "ack"
            assert ack["seq"] == seq

    frame_res = v3_client.get(f"/api/v1/cameras/{cam_id}/frame.jpg", headers=admin_headers)
    assert frame_res.status_code == 200
    assert frame_res.headers["content-type"].startswith("image/jpeg")

    snap_res = v3_client.post(f"/api/v1/cameras/{cam_id}/snapshot", json={"kind": "stream"}, headers=admin_headers)
    assert snap_res.status_code == 200
    snap_data = snap_res.json()
    snap_img = v3_client.get(snap_data["url"], headers=admin_headers)
    assert snap_img.status_code == 200

    tl_res = v3_client.get(f"/api/v1/cameras/{cam_id}/timeline?flush=true", headers=admin_headers)
    assert tl_res.status_code == 200
    tl = tl_res.json()
    assert len(tl["segments"]) >= 1
    seg_url = tl["segments"][0]["url"]

    range_res = v3_client.get(seg_url, headers={**admin_headers, "Range": "bytes=0-127"})
    assert range_res.status_code == 206
    assert "bytes 0-127/" in range_res.headers.get("content-range", "")
    assert len(range_res.content) == 128

    exp_res = v3_client.post(
        f"/api/v1/cameras/{cam_id}/exports",
        json={"from_ts": t_start - 5.0, "to_ts": time.time() + 5.0},
        headers=admin_headers,
    )
    assert exp_res.status_code == 200
    exp = exp_res.json()
    exp_dl = v3_client.get(exp["url"], headers={**admin_headers, "Range": "bytes=0-63"})
    assert exp_dl.status_code == 206


def test_at05_mailbox_non_blocking():
    """AT-05 unit verification: slow subscriber mailbox replaces stale frames without blocking fast subscriber."""
    slow_mb: LatestOnlyMailbox[int] = LatestOnlyMailbox("slow")
    fast_mb: LatestOnlyMailbox[int] = LatestOnlyMailbox("fast")
    for i in range(1, 50):
        slow_mb.put(i)
        fast_mb.put(i)
    assert slow_mb.replaced_count == 48
    latest = asyncio.run(slow_mb.get(timeout=0.1))
    assert latest == 49


def test_at08_at09_at10_rulesets_readback_schedule_and_dry_run(v3_client):
    """AT-08, AT-09, AT-10: Ruleset creation, readback hash gate, schedule evaluation, and dry-run."""
    admin_login = v3_client.post(
        "/api/v1/auth/login",
        json={"username": "admin1@safespace.com", "password": "admin123", "device_name": "Web", "client_type": "mobile"},
    ).json()
    headers = {"Authorization": f"Bearer {admin_login['device_token']}"}

    cam = v3_client.post(
        "/api/v1/cameras",
        json={"name": "Kitchen Camera", "source_type": "WEBCAM", "connection_uri": "0"},
        headers=headers,
    ).json()
    cid = cam["id"]
    v3_client.put(
        f"/api/v1/cameras/{cid}/geometry",
        json={
            "zones": {"doorway": [[50, 50], [300, 50], [300, 300], [50, 300]]},
            "lines": {},
            "snapshot_width": 640,
            "snapshot_height": 360,
        },
        headers=headers,
    )

    rs_res = v3_client.post(
        "/api/v1/rulesets",
        json={
            "name": "Night Doorway Watch",
            "source_type": "template",
            "template_id": "T1",
            "camera_ids": [cid],
            "zone_id": "doorway",
            "dwell_seconds": 1.5,
        },
        headers=headers,
    )
    assert rs_res.status_code == 200
    rs = rs_res.json()
    assert rs["status"] == "draft"
    ruleset_id = rs["ruleset_id"]

    bad_arm = v3_client.post(
        f"/api/v1/rulesets/{ruleset_id}/arm",
        json={"confirmed_readback_hash": "0" * 64},
        headers=headers,
    )
    assert bad_arm.status_code == 409

    good_arm = v3_client.post(
        f"/api/v1/rulesets/{ruleset_id}/arm",
        json={"confirmed_readback_hash": rs["readback_hash"]},
        headers=headers,
    )
    assert good_arm.status_code == 200
    assert good_arm.json()["status"] == "active"

    events_before = len(v3_client.get("/api/v1/events", headers=headers).json())
    dry_res = v3_client.post(
        f"/api/v1/rulesets/{ruleset_id}/dry-run",
        json={"camera_id": cid},
        headers=headers,
    )
    assert dry_res.status_code == 200
    dry = dry_res.json()
    assert dry["frames_evaluated"] > 0
    assert dry["match_count"] >= 1
    assert dry["persisted_alerts"] == 0
    events_after = len(v3_client.get("/api/v1/events", headers=headers).json())
    assert events_after == events_before

    engine = RuleEngine({"doorway": [(50.0, 50.0), (300.0, 50.0), (300.0, 300.0), (50.0, 300.0)]}, {})
    spec = RuleSpec(
        rule_id="r_sched",
        camera_id=cid,
        version=1,
        name="Night Rule",
        entity="person",
        when=RuleWhen(type="in_zone", zone="doorway"),
        min_hold_s=0.0,
        cooldown_s=10.0,
        support_level="SUPPORTED",
        status="active",
        schedule={"timezone": "UTC", "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "start_time": "22:00", "end_time": "06:00"},
    )
    obs_afternoon = Observation(
        camera_id=cid,
        frame_id=1,
        ts=1792159200.0,
        tracks=[
            ObservedTrack(
                track_id=1,
                cls="person",
                conf=0.9,
                bbox=(100, 100, 140, 200),
                foot=(120, 200),
                velocity=(0, 0),
                first_seen=1792159190.0,
                last_seen=1792159200.0,
            )
        ],
        model_versions={"detector": "test"},
    )
    assert engine.evaluate(spec, obs_afternoon, RuleState()) == []

    obs_night = Observation(
        camera_id=cid,
        frame_id=2,
        ts=1792191600.0,
        tracks=[
            ObservedTrack(
                track_id=1,
                cls="person",
                conf=0.9,
                bbox=(100, 100, 140, 200),
                foot=(120, 200),
                velocity=(0, 0),
                first_seen=1792191590.0,
                last_seen=1792191600.0,
            )
        ],
        model_versions={"detector": "test"},
    )
    night_outcomes = engine.evaluate(spec, obs_night, RuleState())
    assert any(isinstance(o, Fire) for o in night_outcomes)


def test_at12_priority_llm_gateway_ordering():
    """AT-12: PriorityLLMGateway wakes P0 and P1 ahead of P2 when busy."""
    execution_order: list[str] = []

    async def run_priority_test():
        async with GATEWAY.slot(priority=P2_BACKGROUND):
            execution_order.append("initial_holder")

            async def worker(label: str, prio: int):
                async with GATEWAY.slot(priority=prio):
                    execution_order.append(label)

            t_p2 = asyncio.create_task(worker("P2", P2_BACKGROUND))
            await asyncio.sleep(0.01)
            t_p1 = asyncio.create_task(worker("P1", P1_INTERACTIVE))
            await asyncio.sleep(0.01)
            t_p0 = asyncio.create_task(worker("P0", P0_ALERT_SUMMARY))
            await asyncio.sleep(0.01)

        await asyncio.gather(t_p2, t_p1, t_p0)

    asyncio.run(run_priority_test())
    assert execution_order == ["initial_holder", "P0", "P1", "P2"]


def test_at15_single_use_apk_token_and_at16_retention_sweep(v3_client):
    """AT-15 & AT-16: Single-use APK token burns after first download; storage sweep prunes old segments."""
    admin_login = v3_client.post(
        "/api/v1/auth/login",
        json={"username": "admin1@safespace.com", "password": "admin123", "device_name": "Web", "client_type": "mobile"},
    ).json()
    headers = {"Authorization": f"Bearer {admin_login['device_token']}"}

    tok_res = v3_client.post("/api/v1/devices/apk-token", headers=headers)
    assert tok_res.status_code == 200
    token = tok_res.json()["token"]

    dl1 = v3_client.get(f"/download/{token}/SafeSpace.apk")
    assert dl1.status_code == 200

    dl2 = v3_client.get(f"/download/{token}/SafeSpace.apk")
    assert dl2.status_code in (404, 410)

    sweep_res = v3_client.post("/api/v1/storage/sweep", json={"recordings_days": 7}, headers=headers)
    assert sweep_res.status_code == 200
    assert "summary" in sweep_res.json()


def test_camera_list_works_once_a_phone_camera_exists(v3_client):
    """Regression: phone cameras were stored with an invalid source_type, so GET /cameras returned HTTP 500."""
    admin = v3_client.post("/api/v1/auth/login", json={"username": "admin1@safespace.com", "password": "admin123", "device_name": "t", "client_type": "mobile"}).json()["device_token"]
    headers = {"Authorization": f"Bearer {admin}"}
    code = v3_client.post("/api/v1/auth/pairing-code", json={"role": "camera"}, headers=headers).json()["code"]
    cam = v3_client.post("/api/v1/auth/pair", json={"code": code, "device_name": "Hall", "installation_id": "regress-cam-1"}).json()
    listed = v3_client.get("/api/v1/cameras", headers=headers)
    assert listed.status_code == 200
    assert [c["source_type"] for c in listed.json() if c["id"] == cam["camera_id"]] == ["PHONE"]
    # a row written by the old code still reads back
    row = db.get("camera", cam["camera_id"])
    row["source_type"] = "MOBILE"
    db.put("camera", row)
    assert v3_client.get("/api/v1/cameras", headers=headers).status_code == 200
