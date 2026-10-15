"""
SafeSpace API Endpoint Tests
Validates core REST endpoints, auth validation, and contract integrity.
"""
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure services/api is on sys.path
api_path = Path(__file__).resolve().parents[2] / "services" / "api"
if str(api_path) not in sys.path:
    sys.path.insert(0, str(api_path))

from app.main import app

client = TestClient(app)


def test_health_endpoints():
    """Verify system health and liveness checks."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "components" in data
    assert "timestamp" in data

    live_resp = client.get("/health/live")
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["status"] == "ok"


def test_pair_device():
    """Verify device pairing endpoint accepts code and registers device."""
    payload = {
        "code": "SAFE-1234",
        "device_name": "Test Android Mobile"
    }
    resp = client.post("/api/v1/auth/pair", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "device_id" in data
    assert "device_token" in data
    assert len(data["device_token"]) > 10


def test_ws_ticket_generation():
    """Verify short-lived WebSocket ticket generation."""
    resp = client.post("/api/v1/ws-tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert "ticket" in data
    assert "expires_in" in data


def test_events_list_and_retrieval():
    """Verify events querying."""
    resp = client.get("/api/v1/events")
    assert resp.status_code == 200
    events = resp.json()
    assert isinstance(events, list)


def test_chat_query():
    """Verify natural language incident assistant query endpoint."""
    payload = {
        "message": "Show weapons detected today",
        "conversation_id": "test-conv-1"
    }
    resp = client.post("/api/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "event_ids" in data
