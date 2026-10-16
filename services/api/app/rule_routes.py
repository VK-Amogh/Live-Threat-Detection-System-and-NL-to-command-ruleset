"""Authenticated rule management and idempotent worker event ingestion."""

import asyncio
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import secrets
import time
import uuid

import yaml
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from PIL import Image
from ultralytics import YOLO

from td_contracts import (CameraGeometry, CameraHealthEvent, EventOut, RuleActivationRequest, RuleCompileRequest,
                          RuleCompileResult, RuleEvent, RuleSpec, RuleStatusRequest, ReviewFailure, ReviewCompletion)
from services.rules.compiler import RuleCompiler
from services.rules.registry import CapabilityRegistry
from . import database as db, pipeline
from .security import authenticated, now
from .settings import ROOT, STORAGE, INTERNAL_TOKEN


router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticated)])
worker_router = APIRouter(prefix="/api/v1/internal")
BROADCAST = None
_class_cache = None


def detector_classes():
    global _class_cache
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
    path = ROOT / config["detector"]["weights"]
    signature = (str(path), path.stat().st_mtime_ns)
    if _class_cache is None or _class_cache[0] != signature:
        _class_cache = (signature, set(YOLO(str(path)).names.values()))
    return _class_cache[1]


def worker_auth(authorization: str = Header(default="")):
    if not INTERNAL_TOKEN or not secrets.compare_digest(authorization, f"Bearer {INTERNAL_TOKEN}"):
        raise HTTPException(401, "Internal authentication required")


def rule_record(row):
    return {"id": row["id"], "camera_id": row["camera_id"], "text": row["text"],
            "spec": json.loads(row["spec_json"]), "readback": row["readback"],
            "readback_hash": row["readback_hash"], "can_activate": bool(row["can_activate"]),
            "status": row["status"], "version": row["version"], "updated_at": row["updated_at"]}


@router.post("/rules/compile", response_model=RuleCompileResult)
async def compile_rule(req: RuleCompileRequest):
    if db.get("camera", req.camera_id) is None:
        raise HTTPException(404, "Camera not found")
    geometry, _ = db.get_geometry(req.camera_id)
    geometry = geometry or {"zones": {}, "lines": {}, "homography": None}
    try:
        classes = await asyncio.to_thread(detector_classes)
        compiler = RuleCompiler.from_config(classes, set(geometry["zones"]), set(geometry["lines"]), geometry["homography"] is not None)
        result = await asyncio.to_thread(compiler.compile, req.text, req.camera_id)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"Rule compiler unavailable: {str(exc)[:180]}") from exc
    if req.needs_visual_review and result.readback:
        result.spec.needs_visual_review = True
        result.readback += " A visual summary will follow the alert and will not decide whether it fires."
    digest = hashlib.sha256(result.readback.encode("utf-8")).hexdigest() if result.readback else None
    result.readback_hash = digest
    spec = result.spec
    db.put_rule({"id": spec.rule_id, "camera_id": req.camera_id, "text": req.text,
                 "spec_json": spec.model_dump_json(by_alias=True), "readback": result.readback,
                 "readback_hash": digest, "can_activate": int(result.can_activate),
                 "status": spec.status, "version": spec.version, "updated_at": now()})
    return result


@router.get("/rules")
async def list_rules(camera_id: str | None = None):
    return [rule_record(row) for row in db.list_rules(camera_id)]


@router.post("/rules/{ident}/activate")
async def activate_rule(ident: str, req: RuleActivationRequest):
    row = db.get_rule(ident)
    if row is None:
        raise HTTPException(404, "Rule not found")
    if row["version"] != req.expected_version or row["readback_hash"] != req.confirmed_readback_hash:
        raise HTTPException(409, "Rule or readback changed; review it again")
    spec = RuleSpec.model_validate_json(row["spec_json"])
    geometry, _ = db.get_geometry(spec.camera_id)
    geometry = geometry or {"zones": {}, "lines": {}, "homography": None}
    registry = CapabilityRegistry(ROOT, detector_classes(), set(geometry["zones"]), set(geometry["lines"]), geometry["homography"] is not None)
    level, problems, executable = registry.assess(spec.entity, spec.when)
    if not executable or level == "UNSUPPORTED" or not row["can_activate"]:
        raise HTTPException(409, "Rule cannot activate: " + "; ".join(problems))
    if level == "EXPERIMENTAL" and not req.acknowledge_experimental:
        raise HTTPException(409, "Experimental capability requires acknowledgement")
    spec.status = "active"
    spec.support_level = level
    spec.version += 1
    row.update(spec_json=spec.model_dump_json(by_alias=True), status="active", version=spec.version, updated_at=now())
    db.put_rule(row)
    return rule_record(row)


@router.patch("/rules/{ident}")
async def change_rule_status(ident: str, req: RuleStatusRequest):
    row = db.get_rule(ident)
    if row is None:
        raise HTTPException(404, "Rule not found")
    if row["version"] != req.expected_version:
        raise HTTPException(409, "Rule version changed")
    if req.status != "disabled":
        raise HTTPException(422, "Use the activation endpoint to confirm the readback")
    spec = RuleSpec.model_validate_json(row["spec_json"])
    spec.status = "disabled"
    spec.version += 1
    row.update(spec_json=spec.model_dump_json(by_alias=True), status="disabled", version=spec.version, updated_at=now())
    db.put_rule(row)
    return rule_record(row)


@router.get("/cameras/{camera_id}/geometry", response_model=CameraGeometry | None)
async def get_geometry(camera_id: str):
    if db.get("camera", camera_id) is None:
        raise HTTPException(404, "Camera not found")
    geometry, _ = db.get_geometry(camera_id)
    return geometry


@router.put("/cameras/{camera_id}/geometry")
async def put_geometry(camera_id: str, geometry: CameraGeometry):
    if db.get("camera", camera_id) is None:
        raise HTTPException(404, "Camera not found")
    version = db.put_geometry(camera_id, geometry.model_dump(mode="json"), now())
    return {"camera_id": camera_id, "version": version, "geometry": geometry}


@worker_router.get("/rules", dependencies=[Depends(worker_auth)])
async def worker_rules(camera_id: str):
    geometry, version = db.get_geometry(camera_id)
    return {"rules": [rule_record(row) for row in db.list_rules(camera_id) if row["status"] == "active"],
            "geometry": geometry, "geometry_version": version}


@worker_router.get("/cameras", dependencies=[Depends(worker_auth)])
async def worker_cameras():
    active = []
    for camera in db.all_objects("camera"):
        if not camera.get("desired_active") or not camera.get("enabled", True):
            continue
        source = db.get("source", camera.get("_active_source_id"))
        if source is None or source["status"] != "RUNNING":
            from td_contracts import SourceRecord
            source = SourceRecord(id=uuid.uuid4().hex, filename=camera["name"], kind="live",
                                  camera_id=camera["id"], status="RUNNING", created_at=now()).model_dump()
            source["_started_epoch"] = time.time()
            db.put("source", source)
            camera["_active_source_id"] = source["id"]
            db.put("camera", camera)
        active.append({"id": camera["id"], "name": camera["name"],
                       "source": camera["connection_uri"], "source_id": source["id"]})
    return active


@worker_router.post("/live-frame", dependencies=[Depends(worker_auth)])
async def ingest_live_frame(camera_id: str = Form(...), frame_ts: float = Form(...),
                            file: UploadFile = File(...)):
    camera = db.get("camera", camera_id)
    if camera is None or not camera.get("desired_active"):
        raise HTTPException(409, "Camera is not active")
    source = db.get("source", camera.get("_active_source_id"))
    if source is None or source["status"] != "RUNNING":
        raise HTTPException(409, "Live source is unavailable")
    data = await file.read(5 * 1024 * 1024 + 1)
    if not data or len(data) > 5 * 1024 * 1024:
        raise HTTPException(413, "Live frame is empty or oversized")
    preview_dir = STORAGE / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / f"{camera_id}.jpg").write_bytes(data)
    camera["is_online"] = True
    db.put("camera", camera)
    with db.connection() as con:
        con.execute("""INSERT INTO camera_health(camera_id,last_frame_ts,updated_at) VALUES(?,?,?)
            ON CONFLICT(camera_id) DO UPDATE SET last_frame_ts=excluded.last_frame_ts,updated_at=excluded.updated_at""",
                    (camera_id, frame_ts, now()))
    offset_ms = max(0, round((frame_ts - source.get("_started_epoch", frame_ts)) * 1000))
    result = await pipeline.process_frame(data, source, offset_ms)
    return {"created_event_ids": result.created_event_ids, "result": result.model_dump(mode="json")}


@worker_router.post("/rule-events", dependencies=[Depends(worker_auth)])
async def ingest_rule_event(event: RuleEvent, idempotency_key: str = Header(alias="Idempotency-Key")):
    if idempotency_key != event.event_id:
        raise HTTPException(400, "Idempotency-Key must equal event_id")
    rule = db.get_rule(event.rule_id)
    if rule is None or rule["camera_id"] != event.camera_id or event.rule_version > rule["version"]:
        raise HTTPException(422, "Unknown rule version or camera")
    spec = RuleSpec.model_validate_json(rule["spec_json"])
    if event.needs_visual_review != spec.needs_visual_review:
        raise HTTPException(422, "Visual-review setting does not match the confirmed rule")
    frame = STORAGE / "media" / event.event_id / "frame.jpg"
    if not frame.is_file():
        raise HTTPException(422, "Rule keyframe is missing")
    try:
        with Image.open(io.BytesIO(frame.read_bytes())) as image:
            width, height = image.size
    except (OSError, ValueError) as exc:
        raise HTTPException(422, "Rule keyframe cannot be decoded") from exc
    stamp = datetime.fromtimestamp(event.ts, timezone.utc).isoformat()
    first = datetime.fromtimestamp(event.episode_start, timezone.utc).isoformat()
    camera = db.get("camera", event.camera_id)
    media = [{"id": "keyframe", "kind": "KEYFRAME", "role": "peak",
              "url": f"/api/v1/events/{event.event_id}/media/frame.jpg",
              "width": width, "height": height}]
    output = EventOut(id=event.event_id, rule_id=event.rule_id, rule_version=event.rule_version,
                      uncertainty=event.uncertainty, needs_visual_review=event.needs_visual_review,
                      evidence_bbox=event.evidence_bbox,
                      camera={"id": event.camera_id, "name": camera["name"] if camera else event.camera_id},
                      category={"key": "RULE_ALERT", "label": spec.name}, status="DETECTED",
                      status_reason="Programmable rule matched; inspect evidence",
                      verified_by="NONE", severity="MEDIUM", yolo_confidence=event.confidence,
                      peak_confidence=event.confidence, summary=None, first_seen_at=first,
                      last_seen_at=stamp, track_refs=[{"track_id": ident, "class": spec.entity} for ident in event.tracks],
                      media=media, models={"yolo": {"name": event.model_versions.get("detector", "unknown"),
                                                    "tracker": event.model_versions.get("tracker")}},
                      change_seq=0, created_at=stamp, updated_at=stamp).model_dump(mode="json", by_alias=True)
    saved, created = db.insert_event_once(output)
    if created and BROADCAST is not None:
        await BROADCAST({"v": 1, "type": "event.created", "sent_at": now(),
                         "data": {"event": EventOut.model_validate(saved).model_dump(mode="json", by_alias=True)}})
    return {"event": saved, "created": created}


@worker_router.post("/health-events", dependencies=[Depends(worker_auth)])
async def ingest_health_event(event: CameraHealthEvent, idempotency_key: str = Header(alias="Idempotency-Key")):
    if idempotency_key != event.event_id:
        raise HTTPException(400, "Idempotency-Key must equal event_id")
    camera = db.get("camera", event.camera_id)
    if camera is None:
        raise HTTPException(404, "Camera not found")
    stamp = datetime.fromtimestamp(event.ts, timezone.utc).isoformat()
    output = EventOut(id=event.event_id, camera={"id": event.camera_id, "name": camera["name"]},
                      category={"key": "CAMERA_OFFLINE", "label": "Camera signal lost"},
                      status="DETECTED", status_reason=event.reason, verified_by="NONE", severity="MEDIUM",
                      yolo_confidence=0, peak_confidence=0, summary=event.reason,
                      uncertainty="Camera feed unavailable", first_seen_at=stamp, last_seen_at=stamp,
                      media=[], models={"yolo": {"name": "camera health"}},
                      change_seq=0, created_at=stamp, updated_at=stamp).model_dump(mode="json", by_alias=True)
    saved, created = db.insert_event_once(output)
    if created and BROADCAST is not None:
        await BROADCAST({"v": 1, "type": "event.created", "sent_at": now(),
                         "data": {"event": EventOut.model_validate(saved).model_dump(mode="json", by_alias=True)}})
    return {"event": saved, "created": created}


@worker_router.post("/events/{ident}/clip", dependencies=[Depends(worker_auth)])
async def attach_clip(ident: str):
    clip = STORAGE / "media" / ident / "clip.mp4"
    if not clip.is_file():
        raise HTTPException(422, "Evidence clip is missing")
    event = db.get("event", ident)
    if event is None:
        raise HTTPException(404, "Event not found yet")
    if any(item["kind"] == "CLIP" for item in event["media"]):
        return {"event": event, "created": False}
    first = event["media"][0] if event["media"] else {}
    event["media"].append({"id": "clip", "kind": "CLIP", "role": "context",
                           "url": f"/api/v1/events/{ident}/media/clip.mp4",
                           "width": first.get("width", 0), "height": first.get("height", 0)})
    event["updated_at"] = now()
    saved = db.save_event(event)
    if BROADCAST is not None:
        await BROADCAST({"v": 1, "type": "event.updated", "sent_at": now(),
                         "data": {"event": EventOut.model_validate(saved).model_dump(mode="json", by_alias=True)}})
    return {"event": saved, "created": True}


async def _broadcast_review(event):
    if event is not None and BROADCAST is not None:
        await BROADCAST({"v": 1, "type": "event.updated", "sent_at": now(),
                         "data": {"event": EventOut.model_validate(event).model_dump(mode="json", by_alias=True)}})


@worker_router.post("/review-jobs/claim", dependencies=[Depends(worker_auth)])
async def claim_review():
    claimed = db.claim_review_job(now())
    if claimed is None:
        return {"job": None}
    event, token = claimed
    await _broadcast_review(event)
    return {"job": {"event": EventOut.model_validate(event).model_dump(mode="json", by_alias=True),
                    "claim_token": token}}


@worker_router.post("/review-jobs/{ident}/complete", dependencies=[Depends(worker_auth)])
async def complete_review(ident: str, request: ReviewCompletion):
    event = db.finish_review_job(ident, request.claim_token, request.result.model_dump(), now())
    if event is None:
        raise HTTPException(409, "Review claim expired or was replaced")
    await _broadcast_review(event)
    return {"event": event}


@worker_router.post("/review-jobs/{ident}/retry", dependencies=[Depends(worker_auth)])
async def retry_review(ident: str, request: ReviewFailure):
    event = db.retry_review_job(ident, request.claim_token, request.reason, now())
    if event is None:
        raise HTTPException(409, "Review claim expired or was replaced")
    await _broadcast_review(event)
    return {"event": event}
