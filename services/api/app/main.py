"""
SafeSpace FastAPI Backend Application
Entrypoint and contract router registry.
"""
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from td_contracts import (
    CameraCreate,
    CameraOut,
    CameraStatusOut,
    CameraUpdate,
    CategoryRef,
    ChangesResponse,
    ChatRequest,
    ChatResponse,
    DeviceOut,
    DeviceUpdateRequest,
    ErrorEnvelope,
    EventExtendRequest,
    EventIngest,
    EventIngestResponse,
    EventOut,
    HealthResponse,
    HumanVerificationRequest,
    InternalConfigOut,
    JobClaimRequest,
    JobClaimResponse,
    JobCompleteRequest,
    JobProgressRequest,
    LiveHealthResponse,
    LoginRequest,
    LoginResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    PairingCodeCreateResponse,
    SourceOut,
    SourceUploadResponse,
    UserOut,
    VlmVerificationIngest,
    VlmVerificationResponse,
    WorkerHeartbeatRequest,
    WsTicketResponse,
)

app = FastAPI(
    title="SafeSpace Threat Detection API",
    version="1.0.0",
    description="Local-first AI surveillance and threat detection backend API",
    responses={
        400: {"model": ErrorEnvelope, "description": "Bad Request"},
        401: {"model": ErrorEnvelope, "description": "Unauthorized"},
        403: {"model": ErrorEnvelope, "description": "Forbidden"},
        404: {"model": ErrorEnvelope, "description": "Not Found"},
        409: {"model": ErrorEnvelope, "description": "Conflict"},
        422: {"model": ErrorEnvelope, "description": "Validation Error"},
        500: {"model": ErrorEnvelope, "description": "Internal Server Error"},
    },
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================
# Health & Status Endpoints
# ==============================================================================

@app.get("/health/live", response_model=LiveHealthResponse, tags=["Health"])
async def live_health() -> LiveHealthResponse:
    """Unauthenticated liveness probe."""
    return LiveHealthResponse(status="ok")


@app.get("/api/v1/health", response_model=HealthResponse, tags=["Health"])
async def detailed_health() -> HealthResponse:
    """Authenticated component health inspection."""
    return HealthResponse(
        status="ok",
        components={"database": "healthy", "worker": "connected", "ollama": "available"},
        timestamp="2026-10-15T10:00:00.000Z",
    )


# ==============================================================================
# Authentication & Device Pairing Endpoints
# ==============================================================================

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(req: LoginRequest) -> LoginResponse:
    """Admin login with device credential issuance."""
    return LoginResponse(
        device_id="d1e2f3a4-5d0a-4c3e-9d57-2d8a6c1f9a50",
        device_name=req.device_name,
        device_token="dev_opaque_token_example",
    )


@app.post("/api/v1/auth/pairing-codes", response_model=PairingCodeCreateResponse, tags=["Auth"])
async def create_pairing_code() -> PairingCodeCreateResponse:
    """Admin creates a 10-minute single-use pairing code and QR payload."""
    return PairingCodeCreateResponse(
        code="SAFE-9821",
        qr_payload="safespace://pair?code=SAFE-9821&host=192.168.1.100&port=8000",
        expires_in=600,
    )


@app.post("/api/v1/auth/pair", response_model=PairDeviceResponse, tags=["Auth"])
async def pair_device(req: PairDeviceRequest) -> PairDeviceResponse:
    """Mobile device exchanges 10-minute code for a permanent device token."""
    return PairDeviceResponse(
        device_id="d1e2f3a4-5d0a-4c3e-9d57-2d8a6c1f9a50",
        device_name=req.device_name,
        device_token="dev_mobile_opaque_token",
    )


@app.get("/api/v1/auth/me", response_model=UserOut, tags=["Auth"])
async def get_current_user() -> UserOut:
    return UserOut(
        id="u1a2b3c4-5d0a-4c3e-9d57-2d8a6c1f9a00",
        username="admin",
        role="admin",
        created_at="2026-10-15T00:00:00.000Z",
    )


@app.get("/api/v1/devices", response_model=List[DeviceOut], tags=["Devices"])
async def list_devices() -> List[DeviceOut]:
    return []


@app.patch("/api/v1/devices/me", response_model=DeviceOut, tags=["Devices"])
async def update_device_me(req: DeviceUpdateRequest) -> DeviceOut:
    return DeviceOut(
        id="d1e2f3a4-5d0a-4c3e-9d57-2d8a6c1f9a50",
        name="Security Phone",
        created_at="2026-10-15T00:00:00.000Z",
        last_seen_at="2026-10-15T10:00:00.000Z",
        notify_enabled=True,
    )


@app.post("/api/v1/ws-tickets", response_model=WsTicketResponse, tags=["Auth"])
async def create_ws_ticket() -> WsTicketResponse:
    """Issue a 30-second single-use ticket for WebSocket authentication."""
    return WsTicketResponse(ticket="wst_7f8a9b0c1d2e", expires_in=30)


# ==============================================================================
# Camera Management Endpoints
# ==============================================================================

@app.get("/api/v1/cameras", response_model=List[CameraOut], tags=["Cameras"])
async def list_cameras() -> List[CameraOut]:
    return []


@app.post("/api/v1/cameras", response_model=CameraOut, status_code=status.HTTP_201_CREATED, tags=["Cameras"])
async def create_camera(req: CameraCreate) -> CameraOut:
    return CameraOut(
        id="c2d1b0a4-7b1e-4f0e-8d21-5a0f4c3b9e11",
        name=req.name,
        source_type=req.source_type,
        connection_uri=req.connection_uri,
        enabled=True,
        is_online=True,
        created_at="2026-10-15T10:00:00.000Z",
    )


@app.patch("/api/v1/cameras/{camera_id}", response_model=CameraOut, tags=["Cameras"])
async def update_camera(camera_id: str, req: CameraUpdate) -> CameraOut:
    return CameraOut(
        id=camera_id,
        name=req.name or "Updated Camera",
        source_type="WEBCAM",
        enabled=True,
        is_online=True,
        created_at="2026-10-15T10:00:00.000Z",
    )


# ==============================================================================
# Events & Incidents Endpoints
# ==============================================================================

@app.get("/api/v1/events", response_model=List[EventOut], tags=["Events"])
async def list_events(
    camera_id: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
) -> List[EventOut]:
    return []


@app.get("/api/v1/events/{event_id}", response_model=EventOut, tags=["Events"])
async def get_event(event_id: str) -> EventOut:
    raise HTTPException(status_code=404, detail="Event not found")


@app.post("/api/v1/events/{event_id}/verification", response_model=EventOut, tags=["Events"])
async def human_verify_event(event_id: str, req: HumanVerificationRequest) -> EventOut:
    raise HTTPException(status_code=404, detail="Event not found")


@app.get("/api/v1/changes", response_model=ChangesResponse, tags=["Events"])
async def get_changes(after: int = Query(default=0), limit: int = Query(default=50, ge=1, le=200)) -> ChangesResponse:
    """Client recovery endpoint: fetch events updated after change_seq."""
    return ChangesResponse(items=[], next_after=after, has_more=False, head_seq=after)


@app.get("/api/v1/categories", response_model=List[CategoryRef], tags=["Categories"])
async def list_categories() -> List[CategoryRef]:
    return [
        CategoryRef(key="WEAPON_DETECTED", label="Weapon Detected"),
        CategoryRef(key="FIGHT", label="Physical Altercation / Fight"),
    ]


# ==============================================================================
# Chatbot Endpoints
# ==============================================================================

@app.post("/api/v1/chat", response_model=ChatResponse, tags=["Chat"])
async def query_chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(
        conversation_id="conv_12345",
        answer="No threat events recorded in the specified timeframe.",
        event_ids=[],
        filters_used={},
        counts={"matched": 0},
        coverage={"cameras_with_data": [], "cameras_without_data": [], "note": None},
    )


# ==============================================================================
# Internal Endpoints (Worker -> API, Loopback + Service Token)
# ==============================================================================

@app.post("/api/v1/internal/events", response_model=EventIngestResponse, status_code=status.HTTP_201_CREATED, tags=["Internal"])
async def internal_create_event(req: EventIngest) -> EventIngestResponse:
    """Ingest candidate threat incident from worker with idempotency."""
    return EventIngestResponse(
        event_id=req.event_id,
        result="created",
        status="VERIFYING",
        change_seq=1,
    )


@app.post("/api/v1/internal/events/{event_id}/extend", response_model=EventIngestResponse, tags=["Internal"])
async def internal_extend_event(event_id: str, req: EventExtendRequest) -> EventIngestResponse:
    """Extend ongoing active incident with new frames and updated confidence."""
    return EventIngestResponse(
        event_id=event_id,
        result="created",
        status="VERIFYING",
        change_seq=2,
    )


@app.post("/api/v1/internal/events/{event_id}/verification", response_model=VlmVerificationResponse, tags=["Internal"])
async def internal_verify_event(event_id: str, req: VlmVerificationIngest) -> VlmVerificationResponse:
    """Post raw VLM verification verdict from worker."""
    return VlmVerificationResponse(
        event_id=event_id,
        status="CONFIRMED" if req.status == "OK" and req.result and req.result.incident_visible == "yes" else "NEEDS_REVIEW",
        verified_by="AI",
        change_seq=3,
        applied=True,
    )


@app.get("/api/v1/internal/config", response_model=InternalConfigOut, tags=["Internal"])
async def internal_get_config() -> InternalConfigOut:
    return InternalConfigOut(config_version=1, cameras=[], enabled_categories=["WEAPON_DETECTED", "FIGHT"])


@app.post("/api/v1/internal/jobs/claim", response_model=JobClaimResponse, tags=["Internal"])
async def internal_claim_job(req: JobClaimRequest) -> JobClaimResponse:
    return JobClaimResponse(job_id=None, lease_token=None, payload=None)


@app.post("/api/v1/internal/jobs/{job_id}/progress", tags=["Internal"])
async def internal_job_progress(job_id: str, req: JobProgressRequest) -> dict:
    return {"status": "ok"}


@app.post("/api/v1/internal/jobs/{job_id}/complete", tags=["Internal"])
async def internal_job_complete(job_id: str, req: JobCompleteRequest) -> dict:
    return {"status": "ok"}


@app.post("/api/v1/internal/heartbeat", tags=["Internal"])
async def internal_heartbeat(req: WorkerHeartbeatRequest) -> dict:
    return {"status": "acknowledged"}
