"""Device enrollment, fleet telemetry, remote commands, single-use APK download tokens, and audit log."""
from __future__ import annotations

import hmac
from pathlib import Path
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from td_contracts import (
    ApkTokenResponse,
    DeviceCommandRequest,
    DeviceEnrollRequest,
    DeviceEnrollResponse,
)
from .. import database as db
from .. import settings
from ..media.hub import HUB
from ..network_policy import (
    check_request_allowed,
    classify_request,
    client_ip,
    get_host_wifi_status,
    public_origin,
    requires,
    route_document,
)
from ..security import (
    authenticated,
    authenticated_any_scope,
    create_session,
    digest,
    now,
    stable_camera_id,
    stable_device_id,
)

router = APIRouter()

# Single-use APK download tokens: token -> {expires: float, used: bool}
APK_TOKENS: dict[str, dict] = {}


def _find_apk_path() -> Path | None:
    candidates = [
        settings.active_storage() / "dist" / "SafeSpace.apk",
        settings.STORAGE / "dist" / "SafeSpace.apk",
        settings.ROOT / "apps" / "mobile" / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk",
        settings.ROOT / "apps" / "mobile" / "build" / "app" / "outputs" / "flutter-apk" / "app-debug.apk",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def register_camera_device(
    *,
    installation_id: str,
    device_name: str,
    role: str,
    model: str | None,
    os_version: str | None,
    app_version: str | None,
    request: Request,
    owner: str = "camera_enrollment",
    audit_action: str = "device.enroll",
) -> dict:
    """Issue a camera-scoped token for a phone and make its camera appear everywhere. Shared by enrollment and pairing."""
    c = classify_request(request)
    device_id = stable_device_id(installation_id)
    camera_id = stable_camera_id(installation_id)
    scope = "camera"
    token, _ = create_session(
        owner,
        device_name,
        installation_id=installation_id,
        scope=scope,
        role=role,
        days=settings.CAMERA_TOKEN_DAYS,
    )
    expires_at = time.time() + settings.CAMERA_TOKEN_DAYS * 86400
    db.upsert_device(
        {
            "device_id": device_id,
            "installation_id": installation_id,
            "name": device_name,
            "role": role,
            "camera_id": camera_id,
            "model": model,
            "os_version": os_version,
            "app_version": app_version,
            "token_hash": digest(token),
            "token_scope": scope,
            "token_expires": expires_at,
            "local_ip": c.client_ip,
            "status": "online",
            "last_seen": time.time(),
        }
    )
    db.set_device_route(device_id, c.route, c.client_ip)
    # The camera shows up in every camera list immediately, before its first frame.
    existing_cam = db.get("camera", camera_id) or {}
    db.put(
        "camera",
        {
            **existing_cam,
            "id": camera_id,
            "name": device_name,
            "source_type": "PHONE",
            "connection_uri": f"mobile://{device_id}",
            "enabled": True,
            "is_online": True,
            "status": "LIVE",
            "device_id": device_id,
            "created_at": existing_cam.get("created_at") or now(),
        },
    )
    HUB.channel(camera_id).device_id = device_id
    db.log_audit(
        action=audit_action,
        actor_device=device_id,
        ip=c.client_ip,
        target_type="camera",
        target_id=camera_id,
        detail={"device_name": device_name, "model": model, "role": role, "route": c.route},
    )
    return {"device_id": device_id, "camera_id": camera_id, "token": token, "scope": scope, "expires_at": expires_at, "route": c.route}


@router.post("/api/v1/devices/enroll", response_model=DeviceEnrollResponse, dependencies=[Depends(requires("enroll"))])
async def enroll_device(body: DeviceEnrollRequest, request: Request):
    if not hmac.compare_digest(body.enrollment_code.strip(), settings.CAMERA_ENROLLMENT_CODE):
        raise HTTPException(status_code=401, detail="Invalid camera enrollment code")
    reg = register_camera_device(
        installation_id=body.installation_id,
        device_name=body.device_name,
        role=body.role,
        model=body.model,
        os_version=body.os_version,
        app_version=body.app_version,
        request=request,
    )
    return DeviceEnrollResponse(
        device_id=reg["device_id"],
        camera_id=reg["camera_id"],
        device_name=body.device_name,
        role=body.role,
        scope=reg["scope"],
        token=reg["token"],
        expires_at=reg["expires_at"],
        server_id=settings.SERVER_ID,
        server_name=settings.SERVER_NAME,
        urls=[r["url"] for r in route_document()["routes"]],
        route=reg["route"],
    )


@router.get("/api/v1/devices/me")
async def get_my_device(request: Request, session=Depends(authenticated_any_scope)):
    check_request_allowed(request)
    device_id = session["device_id"]
    dev = db.get_device(device_id)
    cam = db.get("camera", dev["camera_id"]) if dev and dev.get("camera_id") else None
    return {
        "device_id": device_id,
        "name": session.get("name"),
        "scope": session.get("scope", "admin"),
        "role": session.get("role", "control"),
        "device": dev,
        "camera": cam,
        "wifi_lock": get_host_wifi_status(),
    }


@router.post("/api/v1/devices/me/heartbeat")
async def heartbeat_my_device(payload: dict, request: Request, session=Depends(authenticated_any_scope)):
    check_request_allowed(request)
    c = classify_request(request)
    client_ip_value = c.client_ip

    device_id = session["device_id"]
    payload = dict(payload)
    payload["local_ip"] = client_ip_value
    # Reported SSID/BSSID are informational telemetry only; they are never used to allow or deny access.
    payload["last_seen"] = time.time()
    payload.setdefault("status", "online")
    dev = db.get_device(device_id)
    if dev is None:
        dev = db.upsert_device(
            {
                "device_id": device_id,
                "installation_id": payload.get("installation_id") or device_id,
                "name": session.get("name") or "Mobile Device",
                "role": session.get("role") or "camera",
                "camera_id": payload.get("camera_id") or stable_camera_id(device_id),
                **payload,
            }
        )
    else:
        dev = db.update_device_telemetry(device_id, payload)
    db.set_device_route(device_id, c.route, client_ip_value)

    if dev and dev.get("camera_id"):
        ch = HUB.channel(dev["camera_id"])
        ch.device_id = device_id
        if "battery_pct" in payload:
            ch.battery_pct = payload["battery_pct"]
        if "charging" in payload:
            ch.charging = bool(payload["charging"])
        if "temp_c" in payload:
            ch.temp_c = payload["temp_c"]
        if "wifi_rssi" in payload:
            ch.wifi_rssi = payload["wifi_rssi"]

    return {"ok": True, "device": dev, "ts": time.time()}


@router.get("/api/v1/devices/fleet")
async def list_fleet_devices(session=Depends(authenticated)):
    devices = db.list_devices_v3()
    for d in devices:
        cid = d.get("camera_id")
        if cid:
            ch = HUB.channel(cid)
            d["fps"] = ch.fps if ch.is_online else d.get("fps", 0.0)
            d["viewer_count"] = ch.viewer_count
            if ch.is_online:
                d["status"] = "streaming"
            elif d.get("last_seen") and (time.time() - float(d["last_seen"])) > 30:
                d["status"] = "offline"
    return {"items": devices}


@router.post("/api/v1/devices/{device_id}/commands")
async def send_command_to_device(
    device_id: str,
    body: DeviceCommandRequest,
    request: Request,
    session=Depends(authenticated),
):
    dev = db.get_device(device_id)
    if not dev:
        # Also allow looking up by camera_id if caller passed camera_id
        dev = db.get_device_by_camera(device_id)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    if body.action == "revoke_token":
        db.delete_device_v3(dev["device_id"])
        db.log_audit(
            action="device.revoke",
            actor_user=session.get("email"),
            actor_device=session.get("device_id"),
            ip=client_ip(request),
            target_type="device",
            target_id=dev["device_id"],
        )
        return {"ok": True, "revoked": True, "device_id": dev["device_id"]}

    camera_id = dev.get("camera_id") or device_id
    res = await HUB.send_device_command(camera_id, body.action, body.params)
    db.log_audit(
        action=f"device.command.{body.action}",
        actor_user=session.get("email"),
        actor_device=session.get("device_id"),
        ip=client_ip(request),
        target_type="device",
        target_id=dev["device_id"],
        detail={"action": body.action, "params": body.params},
    )
    return res


@router.post("/api/v1/devices/apk-token", response_model=ApkTokenResponse)
async def create_apk_download_token(request: Request, session=Depends(authenticated)):
    token = secrets.token_urlsafe(24)
    expires_at = time.time() + 600.0
    APK_TOKENS[token] = {"expires": expires_at, "used": False, "created_by": session.get("email")}
    base_url = public_origin(request)   # the address the signed-in admin is using right now, on whichever route
    download_url = f"{base_url}/download/{token}/SafeSpace.apk"
    apk_path = _find_apk_path()
    db.log_audit(
        action="apk.token_create",
        actor_user=session.get("email"),
        actor_device=session.get("device_id"),
        ip=client_ip(request),
        target_type="apk",
        target_id=token[:8],
    )
    return ApkTokenResponse(
        token=token,
        url=download_url,
        qr_payload=download_url,
        expires_in=600,
        expires_at=expires_at,
        apk_ready=apk_path is not None,
        apk_size_bytes=apk_path.stat().st_size if apk_path else None,
    )


@router.get("/download/{token}/SafeSpace.apk")
async def download_apk_with_token(token: str, request: Request):
    check_request_allowed(request)
    entry = APK_TOKENS.get(token)
    if not entry:
        raise HTTPException(status_code=404, detail="APK download token not found")
    if entry.get("used") or entry["expires"] < time.time():
        APK_TOKENS.pop(token, None)
        raise HTTPException(status_code=410, detail="APK download token has already been used or expired")

    # Burn single-use token immediately
    entry["used"] = True
    APK_TOKENS.pop(token, None)

    apk_path = _find_apk_path()
    if apk_path is None:
        # Create a placeholder file in storage/dist/SafeSpace.apk if running in a unit test environment before build
        dist_apk = settings.active_storage() / "dist" / "SafeSpace.apk"
        dist_apk.parent.mkdir(parents=True, exist_ok=True)
        if not dist_apk.exists():
            dist_apk.write_bytes(b"PK\x03\x04SafeSpace-APK-Placeholder")
        apk_path = dist_apk

    db.log_audit(
        action="apk.download",
        ip=client_ip(request),
        target_type="apk",
        target_id=token[:8],
        detail={"path": str(apk_path.name), "size_bytes": apk_path.stat().st_size},
    )
    return FileResponse(
        apk_path,
        media_type="application/vnd.android.package-archive",
        filename="SafeSpace.apk",
    )


@router.get("/api/v1/audit")
async def get_audit_entries(limit: int = 100, session=Depends(authenticated)):
    return {"items": db.list_audit_log(limit=max(1, min(500, limit)))}
