"""Multi-camera Rulesets, Templates T1-T8, Security Modes (HOME/AWAY/NIGHT), Readback Gate, and Dry-Run Tester."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
import cv2
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request

from td_contracts import (
    CameraGeometry,
    Observation,
    ObservedTrack,
    RuleSpec,
    RuleTemplateOut,
    RuleWhen,
    RulesetArmRequest,
    RulesetCreateRequest,
    RulesetDryRunRequest,
    RulesetModeActivateRequest,
    RulesetOut,
    RulesetUpdateRequest,
)
from services.rules.compiler import RuleCompiler
from services.rules.engine import RuleEngine
from services.rules.readback import render_readback
from services.rules.registry import CapabilityRegistry
from services.rules.state import Fire, RuleState
from .. import database as db
from .. import rule_routes
from .. import settings
from ..llm_gateway import GATEWAY, P1_INTERACTIVE
from ..security import authenticated, now

router = APIRouter(prefix="/api/v1")


def load_templates() -> list[dict]:
    path = settings.ROOT / "config" / "rule_templates.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("templates", [])


def get_active_mode() -> str:
    mode_obj = db.get("setting", "security_mode")
    return (mode_obj or {}).get("mode", "HOME")


def _set_active_mode(mode: str) -> None:
    db.put("setting", {"id": "security_mode", "mode": mode, "updated_at": now()})


def _build_when_from_structured(
    rule_type: str,
    zone_id: str | None,
    line_id: str | None,
    dwell_seconds: float,
    min_count: int,
    geometry: dict,
    direction: str | None = None,
) -> tuple[RuleWhen | None, str, list[str], list[str]]:
    """(condition, chosen name, setup needed, caveats). A zone or line the rule needs that is neither chosen nor the only
    one drawn is a setup request, never a guess: the old builder picked the first zone, or fell back to "a person is visible"."""
    zones = list((geometry or {}).get("zones", {}).keys())
    lines = list((geometry or {}).get("lines", {}).keys())
    setup: list[str] = []

    def pick(kind: str, explicit: str | None, names: list[str]) -> str | None:
        if explicit:
            if explicit in names:
                return explicit
            setup.append(f"The {kind} '{explicit}' is not drawn on this camera")
        elif len(names) == 1:
            return names[0]
        elif names:
            setup.append(f"Choose which {kind} to use: {', '.join(sorted(names))}")
        else:
            setup.append(f"Draw a {kind} on this camera first")
        return None

    if rule_type == "absence":
        return RuleWhen(not_=RuleWhen(type="entity_present")), "", [], []
    if rule_type == "line_cross":
        line = pick("line", line_id, lines)
        if line is None:
            return None, "", setup, []
        node = {"type": "line_cross", "line": line, **({"direction": direction} if direction in ("a_to_b", "b_to_a") else {})}
        return RuleWhen(**node), line, [], []
    if rule_type == "count_threshold":
        if line_id:                                   # people crossing a line within a window
            line = pick("line", line_id, lines)
            if line is None:
                return None, "", setup, []
            return RuleWhen(type="unique_count_at_least", line=line, count=max(1, int(min_count)),
                            window_s=max(5.0, float(dwell_seconds or 30.0))), line, [], []
        zone = zone_id if zone_id in zones else None  # people gathered at the same time, in a zone if one was chosen
        if zone_id and zone is None:
            return None, "", [f"The zone '{zone_id}' is not drawn on this camera"], []
        return RuleWhen(type="count_in_zone_at_least", count=max(1, int(min_count)), **({"zone": zone} if zone else {})), zone or "", [], []
    if rule_type in ("dwell_in_zone", "stationary_object", "presence_in_zone"):
        zone = pick("zone", zone_id, zones)
        if zone is None:
            return None, "", setup, []
        hold = max(1.0, float(dwell_seconds or 10.0))
        caveats = []
        if rule_type == "stationary_object":
            caveats.append("Approximation: the object is tracked inside the zone for this long, but it is not checked to be stationary or unattended")
        if rule_type == "presence_in_zone" and not (dwell_seconds and dwell_seconds >= 2.0):
            return RuleWhen(type="in_zone", zone=zone), zone, [], caveats
        return RuleWhen(all=[RuleWhen(type="in_zone", zone=zone), RuleWhen(type="dwell_at_least", seconds=hold if rule_type != "presence_in_zone" else float(dwell_seconds))]), zone, [], caveats
    return None, "", [f"Unknown rule type '{rule_type}'"], []


def _format_schedule_readback(schedule: dict | None) -> str:
    if not schedule:
        return "24/7 on all days"
    days = ", ".join(d.title() for d in schedule.get("days", []))
    return f"{schedule.get('start_time', '00:00')}–{schedule.get('end_time', '23:59')} ({days})"


@router.get("/rulesets/templates", response_model=list[RuleTemplateOut])
async def list_rule_templates(session=Depends(authenticated)):
    return [RuleTemplateOut(**t) for t in load_templates()]


@router.get("/rulesets")
async def list_all_rulesets(session=Depends(authenticated)):
    return {
        "active_mode": get_active_mode(),
        "items": db.list_rulesets(),
    }


@router.get("/rulesets/{ruleset_id}", response_model=RulesetOut)
async def get_single_ruleset(ruleset_id: str, session=Depends(authenticated)):
    rs = db.get_ruleset(ruleset_id)
    if not rs:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    return RulesetOut(**rs)


@router.post("/rulesets", response_model=RulesetOut)
async def create_ruleset(
    body: RulesetCreateRequest,
    request: Request,
    session=Depends(authenticated),
):
    for cid in body.camera_ids:
        if db.get("camera", cid) is None:
            raise HTTPException(status_code=404, detail=f"Camera '{cid}' not found")

    templates_by_id = {t["id"]: t for t in load_templates()}
    known_template = templates_by_id.get(body.template_id or "")
    if body.source_type == "template" and not known_template:
        raise HTTPException(status_code=404, detail=f"Rule template '{body.template_id}' not found")
    # A template whose text the person did not edit is deterministic: no language model, no guessing.
    untouched = known_template is not None and (body.text or "").strip() in ("", known_template.get("description", ""), known_template.get("name", ""))
    use_template = known_template is not None and (body.source_type == "template" or (body.source_type == "nl" and untouched))
    tpl = known_template if use_template else None
    if use_template:
        body = body.model_copy(update={"source_type": "template"})

    sent = body.model_fields_set      # a template supplies the defaults; only what the client explicitly sent overrides them

    def pick(field: str, template_key: str, fallback):
        if field in sent or tpl is None:
            return getattr(body, field) if getattr(body, field) is not None else fallback
        return tpl.get(template_key, fallback)

    rule_type = (tpl["rule_type"] if tpl else body.rule_type) or "presence_in_zone"
    target_classes = pick("target_classes", "target_classes", ["person"]) or ["person"]
    entity = target_classes[0] if target_classes else "person"
    dwell_s = float(pick("dwell_seconds", "dwell_seconds", 1.5))
    min_count = int(pick("min_count", "min_count", 1))
    cooldown_s = float(pick("cooldown_seconds", "cooldown_seconds", 120.0))
    severity = pick("severity", "severity", "medium")
    schedule_dict = (
        body.schedule.model_dump()
        if body.schedule
        else ((tpl or {}).get("schedule_default") if tpl else None)
    )
    if "modes" in sent:
        modes = body.modes
    elif body.mode:
        modes = [body.mode]
    else:
        modes = (tpl or {}).get("modes") or body.modes

    direction = str((tpl or {}).get("direction") or "").lower() or None
    ruleset_id = f"ruleset_{uuid.uuid4().hex[:12]}"
    created_rule_ids: list[str] = []
    cam_readbacks: list[str] = []
    problems_all: list[str] = []
    support_levels: list[str] = []
    can_activate_all = True
    per_cam_specs: list[dict] = []

    try:
        classes = await asyncio.to_thread(rule_routes.detector_classes)
    except Exception:
        classes = {"person", "car", "motorcycle", "bus", "truck", "dog", "cat", "backpack", "handbag", "suitcase", "Knife", "gun"}

    for cid in body.camera_ids:
        geometry, _ = db.get_geometry(cid)
        geometry = geometry or {"zones": {}, "lines": {}, "homography": None}
        spec: RuleSpec | None = None
        readback_cam: str | None = None

        if body.source_type == "nl" and body.text:
            try:
                async with GATEWAY.slot(priority=P1_INTERACTIVE):
                    compiler = RuleCompiler.from_config(
                        classes,
                        set(geometry["zones"]),
                        set(geometry["lines"]),
                        geometry["homography"] is not None,
                        geometry,
                    )
                    res = await asyncio.to_thread(compiler.compile, body.text, cid)
                spec = res.spec
                spec.schedule = schedule_dict
                spec.ruleset_id = ruleset_id
                spec.severity = severity  # type: ignore[assignment]
                spec.modes = modes
                spec.needs_visual_review = body.needs_visual_review
                readback_cam = res.readback
                if res.problems:
                    problems_all.extend(res.problems)
                support_levels.append(res.support_level)
                if not res.can_activate:
                    can_activate_all = False
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"Rule compiler unavailable: {str(exc)[:160]}") from exc
        else:
            when_node, _, setup, caveats = _build_when_from_structured(
                rule_type, body.zone_id, body.line_id, dwell_s, min_count, geometry, direction
            )
            registry = CapabilityRegistry(
                settings.ROOT, classes, set(geometry["zones"]), set(geometry["lines"]), geometry["homography"] is not None,
                anchors=geometry.get("anchors"),
            )
            lvl, probs, exec_ok = registry.assess(entity, when_node)
            probs = [*probs, *[f"Needs setup: {item}" for item in setup],
                     *[f"Detector weights do not support '{cls}'" for cls in target_classes if cls not in classes]]
            if setup or any(cls not in classes for cls in target_classes):
                lvl, exec_ok = "UNSUPPORTED", False
            elif caveats:
                probs = [*probs, *caveats]
                lvl = "EXPERIMENTAL" if lvl == "SUPPORTED" else lvl
            spec = RuleSpec(
                rule_id=f"rule_{uuid.uuid4().hex[:12]}",
                camera_id=cid,
                version=1,
                name=body.name,
                entity=entity,
                entities=list(target_classes),
                when=when_node if exec_ok else None,
                min_hold_s=max(0.0, min(60.0, float(dwell_s if dwell_s <= 60 else 1.5))),
                cooldown_s=float(cooldown_s),
                needs_visual_review=body.needs_visual_review,
                support_level=lvl,
                status="draft",
                ruleset_id=ruleset_id,
                schedule=schedule_dict,
                severity=severity,  # type: ignore[arg-type]
                modes=modes,
            )
            readback_cam = render_readback(spec) if spec.when else body.name
            problems_all.extend(probs)
            support_levels.append(lvl)
            if not exec_ok:
                can_activate_all = False

        cam_readbacks.append(readback_cam or f"{body.name} (cannot activate: {'; '.join(problems_all[-3:]) or 'see problems'})")
        cam_readback_hash = hashlib.sha256((readback_cam or body.name).encode("utf-8")).hexdigest()
        db.put_rule(
            {
                "id": spec.rule_id,
                "camera_id": cid,
                "text": body.text or body.name,
                "spec_json": spec.model_dump_json(by_alias=True),
                "readback": readback_cam or body.name,
                "readback_hash": cam_readback_hash,
                "can_activate": int(can_activate_all),
                "status": "draft",
                "version": 1,
                "updated_at": now(),
                "ruleset_id": ruleset_id,
            }
        )
        created_rule_ids.append(spec.rule_id)
        per_cam_specs.append(spec.model_dump(mode="json", by_alias=True))

    cam_names = [
        (db.get("camera", cid) or {}).get("name", cid)
        for cid in body.camera_ids
    ]
    overall_level = (
        "UNSUPPORTED"
        if "UNSUPPORTED" in support_levels
        else ("EXPERIMENTAL" if "EXPERIMENTAL" in support_levels else "SUPPORTED")
    )
    schedule_summary = _format_schedule_readback(schedule_dict)
    combined_readback = (
        f"Alert ({severity.upper()}) on {', '.join(cam_names)} when '{entity}' matches "
        f"({rule_type.replace('_', ' ')}), schedule: {schedule_summary}, "
        f"cooldown: {int(cooldown_s)}s, modes: {', '.join(modes)}."
    )
    combined_readback += " What is evaluated: " + " | ".join(dict.fromkeys(cam_readbacks))
    if body.needs_visual_review:
        combined_readback += " A visual summary will follow the alert and will not decide whether it fires."
    readback_hash = hashlib.sha256(combined_readback.encode("utf-8")).hexdigest()

    now_ts = time.time()
    saved = db.put_ruleset(
        {
            "ruleset_id": ruleset_id,
            "name": body.name,
            "source_type": body.source_type,
            "spec_json": json.dumps(
                {
                    "rule_type": rule_type,
                    "target_classes": target_classes,
                    "zone_id": body.zone_id,
                    "line_id": body.line_id,
                    "dwell_seconds": dwell_s,
                    "min_count": min_count,
                    "cooldown_seconds": cooldown_s,
                    "severity": severity,
                    "needs_visual_review": body.needs_visual_review,
                    "template_id": body.template_id,
                    "description": body.description or body.text,
                    "per_camera_specs": per_cam_specs,
                }
            ),
            "readback": combined_readback,
            "readback_hash": readback_hash,
            "support_level": overall_level,
            "camera_ids": json.dumps(body.camera_ids),
            "rule_ids": json.dumps(created_rule_ids),
            "schedule_json": json.dumps(schedule_dict) if schedule_dict else None,
            "modes_json": json.dumps(modes),
            "status": "draft",
            "version": 1,
            "problems_json": json.dumps(list(dict.fromkeys(problems_all))),
            "can_activate": 1 if can_activate_all else 0,
            "created_at": now_ts,
            "updated_at": now_ts,
        }
    )
    db.log_audit(
        action="ruleset.create",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="ruleset",
        target_id=ruleset_id,
        detail={"name": body.name, "camera_ids": body.camera_ids, "source_type": body.source_type},
    )
    return RulesetOut(**saved)


@router.patch("/rulesets/{ruleset_id}", response_model=RulesetOut)
async def update_ruleset(
    ruleset_id: str,
    body: RulesetUpdateRequest,
    request: Request,
    session=Depends(authenticated),
):
    rs = db.get_ruleset(ruleset_id)
    if not rs:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    name = body.name or rs["name"]
    camera_ids = body.camera_ids if body.camera_ids is not None else rs["camera_ids"]
    schedule = body.schedule.model_dump() if body.schedule is not None else rs["schedule"]
    modes = body.modes if body.modes is not None else rs["modes"]
    spec_data = dict(rs["spec"])
    if body.cooldown_seconds is not None:
        spec_data["cooldown_seconds"] = body.cooldown_seconds
    if body.severity is not None:
        spec_data["severity"] = body.severity
    if body.needs_visual_review is not None:
        spec_data["needs_visual_review"] = body.needs_visual_review

    cam_names = [(db.get("camera", cid) or {}).get("name", cid) for cid in camera_ids]
    entity = (spec_data.get("target_classes") or ["person"])[0]
    rule_type = spec_data.get("rule_type", "presence_in_zone")
    severity = spec_data.get("severity", "medium")
    cooldown_s = spec_data.get("cooldown_seconds", 120)
    combined_readback = (
        f"Alert ({severity.upper()}) on {', '.join(cam_names)} when '{entity}' matches "
        f"({rule_type.replace('_', ' ')}), schedule: {_format_schedule_readback(schedule)}, "
        f"cooldown: {int(cooldown_s)}s, modes: {', '.join(modes)}."
    )
    readback_hash = hashlib.sha256(combined_readback.encode("utf-8")).hexdigest()

    updated = db.put_ruleset(
        {
            "ruleset_id": ruleset_id,
            "name": name,
            "source_type": rs["source_type"],
            "spec_json": json.dumps(spec_data),
            "readback": combined_readback,
            "readback_hash": readback_hash,
            "support_level": rs["support_level"],
            "camera_ids": json.dumps(camera_ids),
            "rule_ids": json.dumps(rs["rule_ids"]),
            "schedule_json": json.dumps(schedule) if schedule else None,
            "modes_json": json.dumps(modes),
            "status": rs["status"],
            "version": rs["version"] + 1,
            "problems_json": json.dumps(rs["problems"]),
            "can_activate": 1 if rs["can_activate"] else 0,
            "created_at": rs["created_at"],
            "updated_at": time.time(),
        }
    )
    return RulesetOut(**updated)


@router.post("/rulesets/{ruleset_id}/arm", response_model=RulesetOut)
async def arm_ruleset(
    ruleset_id: str,
    body: RulesetArmRequest,
    request: Request,
    session=Depends(authenticated),
):
    rs = db.get_ruleset(ruleset_id)
    if not rs:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    if body.confirmed_readback_hash != rs["readback_hash"]:
        raise HTTPException(status_code=409, detail="Readback hash mismatch; review and confirm the current readback")
    if not rs["can_activate"] or rs["support_level"] == "UNSUPPORTED":
        raise HTTPException(status_code=409, detail="Ruleset cannot be armed: " + "; ".join(rs["problems"]))
    if rs["support_level"] == "EXPERIMENTAL" and not body.acknowledge_experimental:
        raise HTTPException(status_code=409, detail="Experimental ruleset requires explicit acknowledgement")

    for rid in rs.get("rule_ids", []):
        row = db.get_rule(rid)
        if not row:
            continue
        spec = RuleSpec.model_validate_json(row["spec_json"])
        spec.status = "active"
        spec.schedule = rs["schedule"]
        spec.version += 1
        row.update(
            spec_json=spec.model_dump_json(by_alias=True),
            status="active",
            version=spec.version,
            updated_at=now(),
        )
        db.put_rule(row)

    updated = db.put_ruleset(
        {
            "ruleset_id": ruleset_id,
            "name": rs["name"],
            "source_type": rs["source_type"],
            "spec_json": json.dumps(rs["spec"]),
            "readback": rs["readback"],
            "readback_hash": rs["readback_hash"],
            "support_level": rs["support_level"],
            "camera_ids": json.dumps(rs["camera_ids"]),
            "rule_ids": json.dumps(rs["rule_ids"]),
            "schedule_json": json.dumps(rs["schedule"]) if rs["schedule"] else None,
            "modes_json": json.dumps(rs["modes"]),
            "status": "active",
            "version": rs["version"] + 1,
            "problems_json": json.dumps(rs["problems"]),
            "can_activate": 1,
            "created_at": rs["created_at"],
            "updated_at": time.time(),
        }
    )
    db.log_audit(
        action="ruleset.arm",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="ruleset",
        target_id=ruleset_id,
    )
    return RulesetOut(**updated)


@router.post("/rulesets/{ruleset_id}/disarm", response_model=RulesetOut)
async def disarm_ruleset(ruleset_id: str, request: Request, session=Depends(authenticated)):
    rs = db.get_ruleset(ruleset_id)
    if not rs:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    for rid in rs.get("rule_ids", []):
        row = db.get_rule(rid)
        if not row:
            continue
        spec = RuleSpec.model_validate_json(row["spec_json"])
        spec.status = "disabled"
        spec.version += 1
        row.update(
            spec_json=spec.model_dump_json(by_alias=True),
            status="disabled",
            version=spec.version,
            updated_at=now(),
        )
        db.put_rule(row)

    updated = db.put_ruleset(
        {
            "ruleset_id": ruleset_id,
            "name": rs["name"],
            "source_type": rs["source_type"],
            "spec_json": json.dumps(rs["spec"]),
            "readback": rs["readback"],
            "readback_hash": rs["readback_hash"],
            "support_level": rs["support_level"],
            "camera_ids": json.dumps(rs["camera_ids"]),
            "rule_ids": json.dumps(rs["rule_ids"]),
            "schedule_json": json.dumps(rs["schedule"]) if rs["schedule"] else None,
            "modes_json": json.dumps(rs["modes"]),
            "status": "disabled",
            "version": rs["version"] + 1,
            "problems_json": json.dumps(rs["problems"]),
            "can_activate": 1 if rs["can_activate"] else 0,
            "created_at": rs["created_at"],
            "updated_at": time.time(),
        }
    )
    db.log_audit(
        action="ruleset.disarm",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="ruleset",
        target_id=ruleset_id,
    )
    return RulesetOut(**updated)


@router.delete("/rulesets/{ruleset_id}")
async def delete_ruleset_endpoint(ruleset_id: str, request: Request, session=Depends(authenticated)):
    if not db.delete_ruleset(ruleset_id):
        raise HTTPException(status_code=404, detail="Ruleset not found")
    db.log_audit(
        action="ruleset.delete",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="ruleset",
        target_id=ruleset_id,
    )
    return {"ok": True}


@router.post("/rulesets/modes/activate")
async def activate_security_mode(
    body: RulesetModeActivateRequest,
    request: Request,
    session=Depends(authenticated),
):
    mode = body.mode
    _set_active_mode(mode)
    armed_ids: list[str] = []
    disarmed_ids: list[str] = []

    for rs in db.list_rulesets():
        if not rs.get("can_activate"):
            continue
        should_arm = mode != "DISARMED" and (mode in (rs.get("modes") or []))
        new_status = "active" if should_arm else "disabled"
        for rid in rs.get("rule_ids", []):
            row = db.get_rule(rid)
            if not row:
                continue
            spec = RuleSpec.model_validate_json(row["spec_json"])
            if spec.when is None:
                continue
            spec.status = new_status  # type: ignore[assignment]
            spec.version += 1
            row.update(
                spec_json=spec.model_dump_json(by_alias=True),
                status=new_status,
                version=spec.version,
                updated_at=now(),
            )
            db.put_rule(row)
        db.put_ruleset(
            {
                "ruleset_id": rs["ruleset_id"],
                "name": rs["name"],
                "source_type": rs["source_type"],
                "spec_json": json.dumps(rs["spec"]),
                "readback": rs["readback"],
                "readback_hash": rs["readback_hash"],
                "support_level": rs["support_level"],
                "camera_ids": json.dumps(rs["camera_ids"]),
                "rule_ids": json.dumps(rs["rule_ids"]),
                "schedule_json": json.dumps(rs["schedule"]) if rs["schedule"] else None,
                "modes_json": json.dumps(rs["modes"]),
                "status": new_status,
                "version": rs["version"] + 1,
                "problems_json": json.dumps(rs["problems"]),
                "can_activate": 1 if rs["can_activate"] else 0,
                "created_at": rs["created_at"],
                "updated_at": time.time(),
            }
        )
        if should_arm:
            armed_ids.append(rs["ruleset_id"])
        else:
            disarmed_ids.append(rs["ruleset_id"])

    db.log_audit(
        action=f"mode.activate.{mode}",
        actor_user=session.get("email"),
        ip=request.client.host if request.client else None,
        target_type="mode",
        target_id=mode,
        detail={"armed": armed_ids, "disarmed": disarmed_ids},
    )
    return {
        "mode": mode,
        "armed_ruleset_ids": armed_ids,
        "disarmed_ruleset_ids": disarmed_ids,
        "items": db.list_rulesets(),
    }


@router.post("/rulesets/{ruleset_id}/dry-run")
async def dry_run_ruleset(
    ruleset_id: str,
    body: RulesetDryRunRequest,
    session=Depends(authenticated),
):
    rs = db.get_ruleset(ruleset_id)
    if not rs:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    target_cam = body.camera_id or (rs["camera_ids"][0] if rs["camera_ids"] else None)
    if not target_cam:
        raise HTTPException(status_code=422, detail="No camera specified for dry-run")

    rule_row = None
    for rid in rs.get("rule_ids", []):
        r = db.get_rule(rid)
        if r and r["camera_id"] == target_cam:
            rule_row = r
            break
    if not rule_row and rs.get("rule_ids"):
        rule_row = db.get_rule(rs["rule_ids"][0])
    if not rule_row:
        raise HTTPException(status_code=404, detail="No compiled rule found in ruleset")

    spec = RuleSpec.model_validate_json(rule_row["spec_json"])
    spec.status = "active"
    spec.schedule = None
    geometry, _ = db.get_geometry(target_cam)
    configured = CameraGeometry.model_validate(geometry) if geometry else None
    engine = RuleEngine(
        configured.zones if configured else {},
        configured.lines if configured else {},
        configured.homography if configured else None,
    )
    state = RuleState()
    matches: list[dict] = []
    frames_evaluated = 0

    base = settings.active_storage()
    video_files = []
    if body.source_id:
        src_vid = base / "uploads" / body.source_id / "playback.mp4"
        if src_vid.exists():
            video_files.append((0.0, src_vid))
    if not video_files:
        segs = db.list_recording_segments(
            camera_id=target_cam,
            from_ts=body.from_ts,
            to_ts=body.to_ts,
            limit=5,
        )
        for s in segs:
            p = base / s["path"]
            if p.exists():
                video_files.append((float(s["start_ts"]), p))

    if video_files:
        try:
            from services.rules.detect import CameraDetector

            conf = yaml.safe_load((settings.ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["detector"]
            detector = await asyncio.to_thread(
                CameraDetector,
                target_cam,
                settings.ROOT / conf["weights"],
                conf["tracker"],
                float(conf["confidence"]),
                int(conf["image_size"]),
            )
        except Exception:
            detector = None

        for base_ts, vpath in video_files:
            cap = cv2.VideoCapture(str(vpath))
            fps = cap.get(cv2.CAP_PROP_FPS) or 5.0
            idx = 0
            while cap.isOpened() and frames_evaluated < 120:
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                idx += 1
                if idx % max(1, body.stride) != 0:
                    continue
                frames_evaluated += 1
                ts = base_ts + (idx / max(1.0, fps))
                if detector is not None:
                    obs = await asyncio.to_thread(detector.observe, frame, frames_evaluated, ts)
                else:
                    obs = Observation(
                        camera_id=target_cam,
                        frame_id=frames_evaluated,
                        ts=ts,
                        tracks=[],
                        model_versions={"detector": "dry_run"},
                    )
                for out in engine.evaluate(spec, obs, state):
                    if isinstance(out, Fire):
                        matches.append(
                            {
                                "ts": round(ts, 2),
                                "frame_id": frames_evaluated,
                                "tracks": list(out.tracks),
                                "confidence": round(out.confidence, 3),
                            }
                        )
            cap.release()
    else:
        zones = configured.zones if configured else {}
        lines = configured.lines if configured else {}
        foot = (320.0, 240.0)
        if zones:
            first_poly = next(iter(zones.values()))
            foot = (
                sum(pt[0] for pt in first_poly) / len(first_poly),
                sum(pt[1] for pt in first_poly) / len(first_poly),
            )
        base_ts = time.time() - 30.0
        for step in range(50):
            frames_evaluated += 1
            ts = base_ts + step * 0.5
            cur_foot = foot
            if lines:
                (ax, ay), (bx, by) = next(iter(lines.values()))
                mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
                dx, dy = -(by - ay), (bx - ax)
                cur_foot = (mx - dx * 0.2, my - dy * 0.2) if step < 6 else (mx + dx * 0.2, my + dy * 0.2)
            obs = Observation(
                camera_id=target_cam,
                frame_id=frames_evaluated,
                ts=ts,
                tracks=[
                    ObservedTrack(
                        track_id=1,
                        cls=spec.entity,
                        conf=0.91,
                        bbox=(max(0.0, cur_foot[0] - 20), max(0.0, cur_foot[1] - 60), cur_foot[0] + 20, cur_foot[1]),
                        foot=cur_foot,
                        velocity=(2.0, 0.0),
                        first_seen=base_ts,
                        last_seen=ts,
                    )
                ],
                model_versions={"detector": "dry_run_sim"},
            )
            for out in engine.evaluate(spec, obs, state):
                if isinstance(out, Fire):
                    matches.append(
                        {
                            "ts": round(ts, 2),
                            "frame_id": frames_evaluated,
                            "tracks": list(out.tracks),
                            "confidence": round(out.confidence, 3),
                        }
                    )

    return {
        "ruleset_id": ruleset_id,
        "camera_id": target_cam,
        "frames_evaluated": frames_evaluated,
        "match_count": len(matches),
        "matches": matches,
        "persisted_alerts": 0,
    }
