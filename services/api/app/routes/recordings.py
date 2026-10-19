"""Recordings timeline, HTTP Range MP4 streaming, clip export, and storage retention endpoints."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from td_contracts import (
    ClipExportRequest,
    ClipExportOut,
    RecordingSegmentOut,
    StorageSummaryOut,
    TimelineGapOut,
    TimelineOut,
)
from .. import database as db
from .. import settings
from ..media.hub import HUB
from ..media.recorder import RECORDER_MANAGER, export_camera_clip
from ..media.sweeper import get_storage_summary, run_retention_sweep
from ..network_guard import check_request_allowed
from ..security import authenticated, session_for

router = APIRouter()


def _serve_file_with_range(path: Path, request: Request, media_type: str = "video/mp4") -> Response:
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        )

    m = re.match(r"bytes=(\d*)-(\d*)", range_header.strip())
    if not m:
        raise HTTPException(status_code=416, detail="Invalid Range header")
    start_str, end_str = m.groups()
    if start_str == "" and end_str == "":
        raise HTTPException(status_code=416, detail="Empty byte range")

    if start_str == "":
        suffix_len = int(end_str)
        start = max(0, file_size - suffix_len)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str != "" else file_size - 1

    if start >= file_size or start < 0 or end < start:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}", "Accept-Ranges": "bytes"},
        )
    end = min(end, file_size - 1)
    chunk_size = (end - start) + 1

    def file_iterator(file_path: Path, offset: int, length: int):
        with open(file_path, "rb") as f:
            f.seek(offset)
            remaining = length
            while remaining > 0:
                data = f.read(min(65536, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(
        file_iterator(path, start, chunk_size),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


def _check_media_auth(request: Request) -> dict:
    token = request.query_params.get("token", "")
    if not token:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else request.cookies.get("safespace_session", "")
    sess = session_for(token) if token else None
    if not sess or (sess.get("scope") or "admin") != "admin":
        raise HTTPException(status_code=401, detail="Sign in to continue")
    return sess


def _iso_to_ts(val: str | None) -> float | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


@router.get("/api/v1/cameras/{camera_id}/timeline", response_model=TimelineOut)
async def get_camera_timeline(
    camera_id: str,
    from_ts: float | None = None,
    to_ts: float | None = None,
    flush: bool = True,
    session=Depends(authenticated),
):
    if flush:
        RECORDER_MANAGER.flush(camera_id)

    now_ts = time.time()
    start_bound = float(from_ts) if from_ts is not None else (now_ts - 86400.0)
    end_bound = float(to_ts) if to_ts is not None else (now_ts + 60.0)

    raw_segments = db.list_recording_segments(
        camera_id=camera_id,
        from_ts=start_bound,
        to_ts=end_bound,
        limit=1000,
    )
    segments_out: list[RecordingSegmentOut] = []
    gaps_out: list[TimelineGapOut] = []
    prev_end: float | None = None

    for seg in raw_segments:
        if prev_end is not None and (float(seg["start_ts"]) - prev_end) > 5.0:
            gaps_out.append(
                TimelineGapOut(
                    start_ts=round(prev_end, 3),
                    end_ts=round(float(seg["start_ts"]), 3),
                    duration_s=round(float(seg["start_ts"]) - prev_end, 3),
                )
            )
        prev_end = float(seg["end_ts"])
        segments_out.append(
            RecordingSegmentOut(
                segment_id=seg["segment_id"],
                camera_id=seg["camera_id"],
                start_ts=seg["start_ts"],
                end_ts=seg["end_ts"],
                duration_s=seg["duration_s"],
                url=f"/api/v1/recordings/{seg['segment_id']}.mp4",
                size_bytes=seg["size_bytes"],
                width=seg["width"],
                height=seg["height"],
                fps=seg["fps"],
                codec=seg.get("codec", "h264"),
                has_events=bool(seg.get("has_events")),
                event_count=int(seg.get("event_count", 0)),
            )
        )

    events_out = []
    for ev in db.all_objects("event"):
        if ev.get("camera", {}).get("id") != camera_id:
            continue
        ev_ts = _iso_to_ts(ev.get("first_seen_at") or ev.get("created_at"))
        if ev_ts is None or (start_bound <= ev_ts <= end_bound):
            events_out.append(
                {
                    "id": ev["id"],
                    "ts": ev_ts or now_ts,
                    "category": ev.get("category", {}).get("label", "Incident"),
                    "severity": ev.get("severity", "MEDIUM"),
                    "status": ev.get("status", "DETECTED"),
                    "summary": ev.get("summary"),
                    "media": ev.get("media", []),
                }
            )

    snapshots = db.list_snapshots(camera_id=camera_id, from_ts=start_bound, to_ts=end_bound, limit=200)
    for s in snapshots:
        s["url"] = f"/api/v1/snapshots/{s['snapshot_id']}.jpg"

    return TimelineOut(
        camera_id=camera_id,
        from_ts=start_bound,
        to_ts=end_bound,
        segments=segments_out,
        events=events_out,
        snapshots=snapshots,
        gaps=gaps_out,
    )


@router.get("/api/v1/recordings")
async def list_recordings_endpoint(
    camera_id: str | None = None,
    from_ts: float | None = None,
    to_ts: float | None = None,
    limit: int = 200,
    flush: bool = True,
    session=Depends(authenticated),
):
    if flush:
        if camera_id:
            RECORDER_MANAGER.flush(camera_id)
        else:
            RECORDER_MANAGER.flush_all()
    segs = db.list_recording_segments(camera_id=camera_id, from_ts=from_ts, to_ts=to_ts, limit=max(1, min(1000, limit)))
    for s in segs:
        s["url"] = f"/api/v1/recordings/{s['segment_id']}.mp4"
        s["has_events"] = bool(s.get("has_events"))
    return {"items": segs}


@router.get("/api/v1/recordings/{segment_id}.mp4")
async def stream_recording_segment(segment_id: str, request: Request):
    check_request_allowed(request)
    _check_media_auth(request)
    seg = db.get_recording_segment(segment_id)
    if seg:
        p = settings.active_storage() / seg["path"]
        if not p.exists():
            p = settings.STORAGE / seg["path"]
        return _serve_file_with_range(p, request, media_type="video/mp4")

    # Fallback to legacy phone_camera recording object if requested by id
    legacy = db.get("recording", segment_id)
    if legacy:
        p = settings.active_storage() / "recordings" / legacy["camera_id"] / legacy["filename"]
        if not p.exists():
            p = settings.STORAGE / "recordings" / legacy["camera_id"] / legacy["filename"]
        return _serve_file_with_range(p, request, media_type="video/mp4")

    raise HTTPException(status_code=404, detail="Recording segment not found")


@router.delete("/api/v1/recordings/{segment_id}")
async def delete_recording_segment_endpoint(segment_id: str, request: Request, session=Depends(authenticated)):
    seg = db.delete_recording_segment(segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Recording segment not found")
    p = settings.active_storage() / seg["path"]
    p.unlink(missing_ok=True)
    db.log_audit(
        action="recording.delete",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="recording",
        target_id=segment_id,
    )
    return {"ok": True}


@router.post("/api/v1/cameras/{camera_id}/exports", response_model=ClipExportOut)
async def create_clip_export(
    camera_id: str,
    body: ClipExportRequest,
    request: Request,
    session=Depends(authenticated),
):
    check_request_allowed(request)
    if body.to_ts <= body.from_ts:
        raise HTTPException(status_code=422, detail="to_ts must be greater than from_ts")
    ch = HUB.channel(camera_id)
    exp = export_camera_clip(
        camera_id=camera_id,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        recent_frames=list(ch.recent_frames),
    )
    db.log_audit(
        action="recording.export",
        actor_user=session.get("email"),
        actor_device=session.get("device_id"),
        ip=request.client.host if request.client else None,
        target_type="export",
        target_id=exp["export_id"],
        detail={"camera_id": camera_id, "from_ts": body.from_ts, "to_ts": body.to_ts},
    )
    return ClipExportOut(**exp)


@router.get("/api/v1/exports")
async def list_exports_endpoint(camera_id: str | None = None, session=Depends(authenticated)):
    items = db.list_exports(camera_id=camera_id)
    for item in items:
        item["url"] = f"/api/v1/exports/{item['export_id']}.mp4"
    return {"items": items}


@router.get("/api/v1/exports/{export_id}.mp4")
async def download_exported_clip(export_id: str, request: Request):
    check_request_allowed(request)
    _check_media_auth(request)
    exp = db.get_export(export_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Export not found")
    p = settings.active_storage() / exp["path"]
    if not p.exists():
        p = settings.STORAGE / exp["path"]
    return _serve_file_with_range(p, request, media_type="video/mp4")


@router.get("/api/v1/storage/summary", response_model=StorageSummaryOut)
async def storage_summary_endpoint(session=Depends(authenticated)):
    return StorageSummaryOut(**get_storage_summary())


@router.post("/api/v1/storage/sweep")
async def storage_sweep_endpoint(body: dict | None = None, request: Request = None, session=Depends(authenticated)):
    res = run_retention_sweep(override_policy=body or None)
    db.log_audit(
        action="storage.sweep",
        actor_user=session.get("email"),
        ip=request.client.host if request and request.client else None,
        target_type="storage",
        detail={"deleted_segments": res["deleted_segments"], "deleted_snapshots": res["deleted_snapshots"]},
    )
    return res
