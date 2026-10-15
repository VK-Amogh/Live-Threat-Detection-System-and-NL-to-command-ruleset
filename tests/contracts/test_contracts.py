import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from td_contracts.common import ErrorEnvelope
from td_contracts.events import EventIngest, EventOut, HumanVerificationRequest, ChangesResponse
from td_contracts.vlm import VlmVerificationIngest, VlmVerificationResponse
from td_contracts.internal import EventIngestResponse
from td_contracts.ws import WsEnvelope
from td_contracts.chat import ChatRequest, ChatResponse
from td_contracts.enums import EventStatus, Severity, VerifiedBy, ErrorCode

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "contracts" / "examples"

def load_example(filename: str) -> dict:
    filepath = EXAMPLES_DIR / filename
    assert filepath.exists(), f"Example file {filename} does not exist at {filepath}"
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def test_event_ingest_example():
    data = load_example("event_ingest.json")
    model = EventIngest.model_validate(data)
    assert model.event_id == "0b6f7c1e-5d0a-4c3e-9d57-2d8a6c1f9a10"
    assert model.severity == Severity.HIGH
    assert model.evidence.hits == 3
    assert len(model.track_refs) == 1
    assert model.track_refs[0].class_name == "knife"
    assert model.verify is True

    # Test extra='forbid'
    data_with_extra = dict(data)
    data_with_extra["unexpected_field"] = "malicious_payload"
    with pytest.raises(ValidationError):
        EventIngest.model_validate(data_with_extra)

def test_event_ingest_response_example():
    data = load_example("event_ingest_response.json")
    model = EventIngestResponse.model_validate(data)
    assert model.result == "created"
    assert model.status == EventStatus.VERIFYING
    assert model.change_seq == 1042

def test_vlm_verification_ingest_example():
    data = load_example("vlm_verification_ingest.json")
    model = VlmVerificationIngest.model_validate(data)
    assert model.status == "OK"
    assert model.result is not None
    assert model.result.incident_visible == "yes"
    assert model.result.confidence == 0.78

    # Test extra='forbid'
    data_with_extra = dict(data)
    data_with_extra["unknown_key"] = 123
    with pytest.raises(ValidationError):
        VlmVerificationIngest.model_validate(data_with_extra)

def test_vlm_verification_response_example():
    data = load_example("vlm_verification_response.json")
    model = VlmVerificationResponse.model_validate(data)
    assert model.status == EventStatus.NEEDS_REVIEW
    assert model.verified_by == VerifiedBy.NONE
    assert model.applied is True

def test_event_out_example():
    data = load_example("event_out.json")
    model = EventOut.model_validate(data)
    assert model.id == "0b6f7c1e-5d0a-4c3e-9d57-2d8a6c1f9a10"
    assert model.status == EventStatus.NEEDS_REVIEW
    assert model.category.key == "WEAPON_DETECTED"
    assert model.reasoning is not None
    assert model.reasoning.confidence == 0.78
    assert len(model.media) == 1
    assert model.media[0].kind == "KEYFRAME"

def test_human_verification_request_example():
    data = load_example("human_verification_request.json")
    model = HumanVerificationRequest.model_validate(data)
    assert model.action == "MARK_FALSE_POSITIVE"
    assert model.note == "Shadow on wall"

    # Test extra='forbid'
    data_with_extra = dict(data)
    data_with_extra["fake_admin_role"] = True
    with pytest.raises(ValidationError):
        HumanVerificationRequest.model_validate(data_with_extra)

def test_changes_response_example():
    data = load_example("changes_response.json")
    model = ChangesResponse.model_validate(data)
    assert len(model.items) == 1
    assert model.next_after == 1043
    assert model.has_more is False
    assert model.head_seq == 1043

def test_ws_hello_example():
    data = load_example("ws_hello.json")
    model = WsEnvelope.model_validate(data)
    assert model.v == 1
    assert model.type == "hello"
    assert model.data["head_seq"] == 1043

def test_ws_event_created_example():
    data = load_example("ws_event_created.json")
    model = WsEnvelope.model_validate(data)
    assert model.type == "event.created"
    assert "event" in model.data
    event_model = EventOut.model_validate(model.data["event"])
    assert event_model.status == EventStatus.DETECTED

def test_chat_request_example():
    data = load_example("chat_request.json")
    model = ChatRequest.model_validate(data)
    assert model.message == "Show weapon-related detections today"

    # Test extra='forbid'
    data_with_extra = dict(data)
    data_with_extra["injection"] = "true"
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(data_with_extra)

def test_chat_response_example():
    data = load_example("chat_response.json")
    model = ChatResponse.model_validate(data)
    assert model.counts["matched"] == 3
    assert "Webcam 1" in model.coverage.cameras_with_data

def test_error_envelope_example():
    data = load_example("error_envelope.json")
    model = ErrorEnvelope.model_validate(data)
    assert model.error.code == ErrorCode.EVENT_ID_CONFLICT
    assert model.error.request_id == "9f1c2e7a-5d0a-4c3e-9d57-2d8a6c1f9a70"

    # Test extra='forbid'
    data_with_extra = dict(data)
    data_with_extra["bypass"] = True
    with pytest.raises(ValidationError):
        ErrorEnvelope.model_validate(data_with_extra)
