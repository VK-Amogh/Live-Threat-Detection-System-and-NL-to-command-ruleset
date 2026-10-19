"""Live camera WebSocket publish/view endpoints, MJPEG stream, latest frame, and snapshots."""
from __future__ import annotations

import asyncio
import json
import time
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

from td_contracts import SnapshotCreateRequest, SnapshotOut
from .. import database as db
from .. import settings
from ..media.hub import HUB, FramePacket
from ..media.recorder import RECORDER_MANAGER
from ..network_guard import check_request_allowed, check_websocket_allowed
from .. import tickets
from ..security import authenticated, now, session_for

router = APIRouter()


def _authenticate_ws(ws: WebSocket, allow_camera_scope: bool = False) -> dict | None:
    """Session behind a media socket. Order: Authorization header (the apps; nothing secret in a URL or a log),
    then a single-use ticket, then the dashboard's session cookie (with an Origin check against cross-site hijacking)."""
    token = ""
    auth_header = ws.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        ticket = ws.query_params.get("ticket")
        if ticket:
            token = tickets.redeem(ticket) or ""
    if not token:
        cookie = ws.cookies.get("safespace_session", "")
        if cookie:
            origin = ws.headers.get("origin")
            same = f"{'https' if ws.url.scheme == 'wss' else 'http'}://{ws.headers.get('host', '')}"
            if origin and origin != same and origin not in settings.ALLOWED_ORIGINS:
                return None
            token = cookie
    sess = session_for(token) if token else None
    if not sess:
        return None
    if not allow_camera_scope and (sess.get("scope") or "admin") != "admin":
        return None
    return sess


def _placeholder_jpeg(camera_id: str, label: str = "AWAITING LIVE STREAM") -> bytes:
    canvas = np.zeros((360, 640, 3), dtype=np.uint8)
    canvas[:] = (16, 16, 16)
    cv2.rectangle(canvas, (16, 16), (624, 344), (42, 42, 42), 1)
    cv2.putText(canvas, "SafeSpace", (36, 64), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"CAMERA: {camera_id}", (36, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(canvas, label, (36, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    ok, enc = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return enc.tobytes() if ok else b""


@router.websocket("/api/v1/cameras/{camera_id}/publish")
async def camera_publish_ws(camera_id: str, ws: WebSocket):
    if not await check_websocket_allowed(ws):
        return
    sess = _authenticate_ws(ws, allow_camera_scope=True)
    if not sess:
        await ws.close(code=4401)
        return
    if (sess.get("scope") or "admin") == "camera":
        # A camera-scoped token may publish only the camera that belongs to its own device.
        owner = db.get_device(sess.get("device_id") or "")
        if not owner or owner.get("camera_id") != camera_id:
            await ws.close(code=4403)
            return

    await ws.accept()
    ch = HUB.channel(camera_id)
    ch.publisher_ws = ws
    if sess.get("device_id") and sess["device_id"] != "ticket":
        ch.device_id = sess["device_id"]

    # Ensure camera row exists and is marked online
    cam = db.get("camera", camera_id)
    if not cam:
        cam = {
            "id": camera_id,
            "name": sess.get("name") or f"Phone Camera ({camera_id[-4:]})",
            "source_type": "PHONE",
            "connection_uri": f"mobile://{camera_id}",
            "enabled": True,
            "is_online": True,
            "status": "LIVE",
            "device_id": ch.device_id,
            "created_at": now(),
        }
    else:
        cam["is_online"] = True
        cam["status"] = "LIVE"
    db.put("camera", cam)

    await ws.send_json(
        {
            "type": "ready",
            "camera_id": camera_id,
            "server_id": settings.SERVER_ID,
            **ch.select_adaptive_profile(),
        }
    )

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                raw_bytes = message["bytes"]
                try:
                    ack = await HUB.publish_frame(camera_id, raw_bytes)
                    await ws.send_json(ack)
                except ValueError as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
            elif message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except Exception:
                    continue
                msg_type = data.get("type")
                if msg_type in ("hello", "telemetry"):
                    if "battery_pct" in data:
                        ch.battery_pct = data["battery_pct"]
                    if "charging" in data:
                        ch.charging = bool(data["charging"])
                    if "temp_c" in data:
                        ch.temp_c = data["temp_c"]
                    if "wifi_rssi" in data:
                        ch.wifi_rssi = data["wifi_rssi"]
                    if "dropped_frames" in data:
                        ch.dropped_frames = int(data["dropped_frames"])
                    if "stealth_mode" in data:
                        ch.stealth_mode = bool(data["stealth_mode"])
                    if "torch_enabled" in data:
                        ch.torch_enabled = bool(data["torch_enabled"])
                    if "lens_facing" in data:
                        ch.lens_facing = str(data["lens_facing"])
                    if ch.device_id:
                        db.update_device_telemetry(ch.device_id, data)
                    await ws.send_json(
                        {
                            "type": "telemetry_ack",
                            "viewer_count": ch.viewer_count,
                            **ch.select_adaptive_profile(),
                        }
                    )
                elif msg_type == "ping":
                    await ws.send_json({"type": "pong", "ts": time.time(), "viewer_count": ch.viewer_count})
                elif msg_type == "snapshot":
                    # The camera phone asks for a screenshot of its own stream (a camera-scoped token cannot call the admin API).
                    snap = await HUB.request_snapshot(camera_id, kind="stream")
                    await ws.send_json({"type": "snapshot", "ok": snap is not None,
                                        "snapshot_id": (snap or {}).get("snapshot_id"),
                                        "url": f"/api/v1/snapshots/{snap['snapshot_id']}.jpg" if snap else None})
                    db.log_audit(action="camera.snapshot", actor_device=ch.device_id, ip=None, target_type="camera", target_id=camera_id,
                                 detail={"source": "camera phone"})
    except WebSocketDisconnect:
        pass
    finally:
        if ch.publisher_ws is ws:
            ch.publisher_ws = None
        RECORDER_MANAGER.flush(camera_id)
        if ch.publisher_ws is None:
            from .. import mobile_camera
            session = mobile_camera.SESSIONS.get(camera_id)
            if session is not None:
                session.end_source()
        cam_now = db.get("camera", camera_id)
        if cam_now and ch.publisher_ws is None:
            cam_now["is_online"] = False
            cam_now["status"] = "OFFLINE"
            db.put("camera", cam_now)
        if ch.device_id and ch.publisher_ws is None:
            db.update_device_telemetry(ch.device_id, {"status": "offline", "fps": 0.0})


@router.websocket("/api/v1/cameras/{camera_id}/view")
async def camera_view_ws(camera_id: str, ws: WebSocket):
    if not await check_websocket_allowed(ws):
        return
    sess = _authenticate_ws(ws, allow_camera_scope=False)
    if not sess:
        await ws.close(code=4401)
        return

    await ws.accept()
    ch = HUB.channel(camera_id)
    mb = HUB.subscribe(camera_id, name=f"ws_viewer_{id(ws)}")
    try:
        await ws.send_json(
            {
                "type": "hello",
                "camera_id": camera_id,
                "is_online": ch.is_online,
                "fps": ch.fps,
                "viewer_count": ch.viewer_count,
                "server_ts_ms": int(time.time() * 1000),
            }
        )
        if ch.latest_overlay:
            await ws.send_json(ch.latest_overlay)
        while True:
            item = await mb.get(timeout=5.0)
            if item is None:
                await ws.send_json(
                    {
                        "type": "heartbeat",
                        "camera_id": camera_id,
                        "is_online": ch.is_online,
                        "fps": ch.fps,
                        "viewer_count": ch.viewer_count,
                        "server_ts_ms": int(time.time() * 1000),
                    }
                )
                continue
            if isinstance(item, FramePacket):
                await ws.send_bytes(item.wire)   # SSF1 header (seq, capture time, size) + JPEG
            elif isinstance(item, dict):
                await ws.send_json(item)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        HUB.unsubscribe(camera_id, mb)


@router.get("/api/v1/cameras/{camera_id}/frame.jpg")
async def get_camera_latest_frame(camera_id: str, request: Request, session=Depends(authenticated)):
    check_request_allowed(request)
    ch = HUB.channel(camera_id)
    if ch.latest_frame is not None:
        return Response(
            content=ch.latest_frame.jpeg_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store, max-age=0"},
        )
    base = settings.active_storage()
    for candidate in (
        base / "previews" / f"{camera_id}.jpg",
        base / "media" / f"{camera_id}_live.jpg",
        settings.STORAGE / "previews" / f"{camera_id}.jpg",
    ):
        if candidate.exists():
            return FileResponse(candidate, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
    return Response(
        content=_placeholder_jpeg(camera_id),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


async def _mjpeg_generator(camera_id: str):
    mb = HUB.subscribe(camera_id, name="mjpeg_viewer")
    try:
        # Yield initial frame right away so `<img src="...">` renders immediately
        ch = HUB.channel(camera_id)
        first_jpeg = ch.latest_frame.jpeg_bytes if ch.latest_frame else None
        if not first_jpeg:
            p = settings.active_storage() / "previews" / f"{camera_id}.jpg"
            first_jpeg = p.read_bytes() if p.exists() else _placeholder_jpeg(camera_id)
        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(first_jpeg)).encode("ascii")
            + b"\r\n\r\n"
            + first_jpeg
            + b"\r\n"
        )
        while True:
            item = await mb.get(timeout=2.0)
            if isinstance(item, FramePacket):
                jb = item.jpeg_bytes
                yield (
                    b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jb)).encode("ascii")
                    + b"\r\n\r\n"
                    + jb
                    + b"\r\n"
                )
            elif item is None:
                # Keep stream alive
                await asyncio.sleep(0.05)
    finally:
        HUB.unsubscribe(camera_id, mb)


@router.get("/api/v1/cameras/{camera_id}/live.mjpg")
@router.get("/api/v1/cameras/{camera_id}/stream")
async def stream_camera_mjpeg(camera_id: str, request: Request):
    check_request_allowed(request)
    # Allow auth via cookie, Bearer header, or ?token= query param for <img> tags
    token = request.query_params.get("token", "")
    if not token:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else request.cookies.get("safespace_session", "")
    sess = session_for(token) if token else None
    if not sess or (sess.get("scope") or "admin") != "admin":
        raise HTTPException(status_code=401, detail="Sign in to view live stream")
    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/api/v1/cameras/{camera_id}/overlay")
async def get_camera_overlay(camera_id: str, session=Depends(authenticated)):
    ch = HUB.channel(camera_id)
    geometry, version = db.get_geometry(camera_id)
    return {
        **ch.latest_overlay,
        "camera_id": camera_id,
        "is_online": ch.is_online,
        "fps": ch.fps,
        "viewer_count": ch.viewer_count,
        "geometry": geometry,
        "geometry_version": version,
    }


@router.post("/api/v1/cameras/{camera_id}/snapshot", response_model=SnapshotOut)
async def create_camera_snapshot(
    camera_id: str,
    request: Request,
    body: SnapshotCreateRequest | None = None,
    session=Depends(authenticated),
):
    check_request_allowed(request)
    kind = body.kind if body else "stream"
    snap = await HUB.request_snapshot(camera_id, kind=kind)
    if not snap:
        # Create snapshot from placeholder if camera has never streamed yet
        from ..media.recorder import save_snapshot_bytes

        snap = save_snapshot_bytes(camera_id, _placeholder_jpeg(camera_id, "SNAPSHOT"), kind=kind)
    db.log_audit(
        action="camera.snapshot",
        actor_user=session.get("email"),
        actor_device=session.get("device_id"),
        ip=request.client.host if request.client else None,
        target_type="camera",
        target_id=camera_id,
        detail={"snapshot_id": snap["snapshot_id"], "kind": kind},
    )
    return SnapshotOut(**snap)


@router.get("/api/v1/snapshots")
async def list_all_snapshots(camera_id: str | None = None, limit: int = 100, session=Depends(authenticated)):
    snaps = db.list_snapshots(camera_id=camera_id, limit=max(1, min(500, limit)))
    for s in snaps:
        s["url"] = f"/api/v1/snapshots/{s['snapshot_id']}.jpg"
    return {"items": snaps}


@router.get("/api/v1/snapshots/{snapshot_id}.jpg")
async def get_snapshot_image(snapshot_id: str, request: Request):
    check_request_allowed(request)
    token = request.query_params.get("token", "")
    if not token:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else request.cookies.get("safespace_session", "")
    sess = session_for(token) if token else None
    if not sess or (sess.get("scope") or "admin") != "admin":
        raise HTTPException(status_code=401, detail="Sign in to view snapshot")

    snap = db.get_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    path = settings.active_storage() / snap["path"]
    if not path.exists():
        path = settings.STORAGE / snap["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file missing")
    return FileResponse(path, media_type="image/jpeg")


@router.delete("/api/v1/snapshots/{snapshot_id}")
async def delete_snapshot_endpoint(snapshot_id: str, request: Request, session=Depends(authenticated)):
    snap = db.delete_snapshot(snapshot_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    p = settings.active_storage() / snap["path"]
    p.unlink(missing_ok=True)
    db.log_audit(
        action="snapshot.delete",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="snapshot",
        target_id=snapshot_id,
    )
    return {"ok": True}
