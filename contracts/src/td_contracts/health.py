from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LiveHealthResponse(BaseModel):
    status: str = "ok"


class AdvertisedRoute(BaseModel):
    route: str = Field(..., description="loopback | trusted_lan | ibus_lan | tailnet | relay | configured")
    label: str
    url: str
    tls: bool = False
    interface: str = ""


class IdentityHealthResponse(BaseModel):
    server_id: str
    server_name: str
    version: str = "3.0.0"
    urls: List[str] = Field(default_factory=list, description="Advertised server URLs (flat list, kept for older clients)")
    discovery_port: int = 47800
    capabilities: List[str] = Field(default_factory=list)
    wifi_lock: Dict[str, Any] = Field(default_factory=dict, description="Truthful network status; kept under the old name for older clients")
    # How THIS request reached the server and what that route allows.
    route: Optional[str] = None
    route_label: Optional[str] = None
    mode: Optional[str] = None
    route_capabilities: Dict[str, Any] = Field(default_factory=dict)
    # Signed list of addresses a device can try (HMAC with the shared secret), plus the pinned TLS key(s).
    routes: List[AdvertisedRoute] = Field(default_factory=list)
    tls_pins: List[str] = Field(default_factory=list)
    routes_json: Optional[str] = Field(default=None, description="Exact JSON text that routes_sig signs: {server_id, routes, pins}")
    routes_sig: Optional[str] = Field(default=None, description="HMAC-SHA256 of 'routes|' + routes_json under the shared secret")
    # HMAC(secret, nonce) when the caller supplied ?nonce= : proves this is the genuine server.
    proof: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = Field(..., description="ok | degraded | down")
    components: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
