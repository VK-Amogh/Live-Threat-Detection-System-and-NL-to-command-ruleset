"""The rules API as the apps use it: templates, modes, ruleset create/activate, and the explainable rule test."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services/api"), str(ROOT / "contracts/src"), str(ROOT)]

from app import database as db, main, network_policy as net, settings, tickets  # noqa: E402
from services.rules.simulate import simulate  # noqa: E402
from td_contracts import RuleSpec, RuleWhen  # noqa: E402

ZONE = [(100, 100), (500, 100), (500, 400), (100, 400)]
LINE = ((300, 100), (300, 400))


@pytest.fixture
def api(tmp_path, monkeypatch):
    for folder in ("media", "uploads", "logs", "recordings", "snapshots", "exports", "backups", "dist", "previews"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "safespace.db")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "safespace.db")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    monkeypatch.setenv("SEED_ACCOUNTS", "admin1@safespace.com:admin123:Admin 1")
    monkeypatch.setenv("NETWORK_MODE", "hotspot_only")
    net._POLICY.update(sig=None, policy=None, checked=0.0)
    main.ATTEMPTS.clear()
    tickets.TICKETS.clear()
    with TestClient(main.app) as client:
        login = {"username": "admin1@safespace.com", "password": "admin123", "device_name": "t", "client_type": "mobile"}
        token = client.post("/api/v1/auth/login", json=login).json()["device_token"]
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


def make_camera(api, name="Driveway"):
    cam = api.post("/api/v1/cameras", json={"name": name, "source_type": "WEBCAM", "connection_uri": "0"}).json()
    api.put(f"/api/v1/cameras/{cam['id']}/geometry", json={
        "snapshot_width": 640, "snapshot_height": 480, "zones": {"driveway": ZONE}, "lines": {"gate": LINE}, "homography": None})
    return cam["id"]


def spec(when, entity="person", **kw):
    return RuleSpec(rule_id="r_t", camera_id="cam", version=1, name="t", entity=entity, when=RuleWhen.model_validate(when),
                    support_level="SUPPORTED", status="active", **kw)


# ---- endpoints the apps call -----------------------------------------------------------------------------------------------

def test_templates_come_in_the_shape_the_apps_render(api):
    templates = api.get("/api/v1/rules/templates").json()
    assert [t["id"] for t in templates] == [f"T{i}" for i in range(1, 9)]
    t2 = next(t for t in templates if t["id"] == "T2")
    assert t2["requires_zone"] is True and t2["default_text"] and t2["default_severity"] == "medium"
    assert next(t for t in templates if t["id"] == "T3")["requires_line"] is True


def test_system_mode_round_trip(api):
    assert api.get("/api/v1/system/mode").json() == {"mode": "HOME"}
    assert api.put("/api/v1/system/mode", json={"mode": "AWAY"}).json()["mode"] == "AWAY"
    assert api.get("/api/v1/system/mode").json() == {"mode": "AWAY"}
    assert api.put("/api/v1/system/mode", json={"mode": "NOPE"}).status_code == 422


def test_ruleset_from_an_unedited_template_is_deterministic_and_keeps_template_values(api):
    cam = make_camera(api)
    text = "Alert when a suitcase, backpack, or box is left near the doorway for 15 seconds."
    # exactly what the apps post: free-text fields plus the template id
    body = {"name": "Package at door", "description": text, "camera_ids": [cam], "template_id": "T7", "text": text,
            "mode": "HOME", "schedule": None, "needs_visual_review": False}
    made = api.post("/api/v1/rulesets", json=body)
    assert made.status_code == 200, made.text
    rs = made.json()
    assert rs["id"] == rs["ruleset_id"] and rs["readback_text"] == rs["readback"] and rs["template_id"] == "T7"
    assert rs["mode"] == "HOME" and rs["status"] == "draft"
    rule = api.get("/api/v1/rules", params={"camera_id": cam}).json()[0]
    assert rule["spec"]["entity"] == "suitcase"          # the template's class, not the request default ("person")
    assert rule["spec"]["severity"] == "low"             # the template's severity, not the request default


def test_ruleset_can_be_activated_with_the_apps_activate_path_and_listed(api):
    cam = make_camera(api)
    t2_text = api.get("/api/v1/rules/templates").json()[1]["default_text"]
    rs = api.post("/api/v1/rulesets", json={"name": "Loitering", "description": "x", "camera_ids": [cam], "template_id": "T2", "text": t2_text, "mode": None}).json()
    assert rs["support_level"] == "SUPPORTED", rs["problems"]
    wrong = api.post(f"/api/v1/rulesets/{rs['id']}/activate", json={"confirmed_readback_hash": "0" * 64})
    assert wrong.status_code == 409                       # must confirm the exact readback
    ok = api.post(f"/api/v1/rulesets/{rs['id']}/activate", json={"expected_version": rs["version"], "confirmed_readback_hash": rs["readback_hash"], "acknowledge_experimental": True})
    assert ok.status_code == 200 and ok.json()["status"] == "active"
    items = api.get("/api/v1/rulesets").json()["items"]
    assert items[0]["id"] == rs["id"] and items[0]["status"] == "active"
    active_rules = [r for r in api.get("/api/v1/rules", params={"camera_id": cam}).json() if r["status"] == "active"]
    assert len(active_rules) == 1


def test_system_audit_and_device_command_aliases(api):
    cam = make_camera(api)
    api.post("/api/v1/rulesets", json={"name": "x", "camera_ids": [cam], "template_id": "T1",
                                       "text": "Alert when a person is seen in a watched zone during night hours."})
    audit = api.get("/api/v1/system/audit", params={"limit": 5}).json()
    assert audit and {"id", "actor", "action", "created_at"} <= set(audit[0])
    assert api.post("/api/v1/devices/nope/command", json={"command": "toggle_torch"}).status_code == 404


def test_dry_run_endpoint_explains_a_dwell_rule(api):
    cam = make_camera(api)
    api.post("/api/v1/rulesets", json={"name": "Loiter", "camera_ids": [cam], "template_id": "T2",
                                       "text": "Alert when a person stays inside a restricted zone for at least 20 seconds."})
    rule_id = api.get("/api/v1/rules", params={"camera_id": cam}).json()[0]["id"]
    track = {"track_id": 1, "class_name": "person", "confidence": 0.92, "bbox": [120, 120, 260, 380], "dwell_seconds": 12.0}
    result = api.post(f"/api/v1/rules/{rule_id}/dry-run", json={"synthetic_tracks": [track]}).json()
    assert result["matched"] is True and result["sub_results"] and all(s["matched"] for s in result["sub_results"])
    assert any("alert" in r.lower() for r in result["reasons"])
    assert api.post("/api/v1/rules/missing/dry-run", json={}).status_code == 404


# ---- the simulator itself ---------------------------------------------------------------------------------------------------

def test_simulator_zone_presence_fires():
    out = simulate(spec({"type": "in_zone", "zone": "z"}), {"z": ZONE}, {})
    assert out["matched"] and out["sub_results"][0]["matched"]


def test_simulator_dwell_and_missing_zone():
    rule = spec({"all": [{"type": "in_zone", "zone": "z"}, {"type": "dwell_at_least", "seconds": 30}]})
    assert simulate(rule, {"z": ZONE}, {})["matched"]            # the test lasts long enough by design
    missing = simulate(spec({"type": "in_zone", "zone": "gone"}), {"z": ZONE}, {})
    assert not missing["matched"]
    assert "not drawn" in " ".join(s["reason"] for s in missing["sub_results"])


def test_simulator_line_crossing_and_crowd():
    assert simulate(spec({"type": "line_cross", "line": "gate"}), {}, {"gate": LINE})["matched"]
    crowd = spec({"type": "unique_count_at_least", "line": "gate", "count": 3, "window_s": 30})
    assert simulate(crowd, {}, {"gate": LINE})["matched"]


def test_simulator_reports_unexecutable_rules_and_schedules():
    empty = RuleSpec(rule_id="r", camera_id="c", version=1, name="n", entity="person", when=None,
                     support_level="UNSUPPORTED", unsupported_reason="Color attributes are not supported")
    out = simulate(empty, {}, {})
    assert not out["matched"] and "Color attributes" in out["reasons"][0]
    scheduled = simulate(spec({"type": "entity_present"}, schedule={"days": ["mon"], "start_time": "22:00", "end_time": "06:00"}), {}, {})
    assert scheduled["matched"] and any("schedule" in r for r in scheduled["reasons"])
