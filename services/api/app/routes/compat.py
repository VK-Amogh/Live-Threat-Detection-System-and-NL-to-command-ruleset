"""Endpoints the apps and dashboard call under names the server did not originally expose.

The mobile app and the dashboard were built against one shared draft of the rules/system API; the server grew a
different one. Rather than let every screen fail, these routes translate the draft names onto the real handlers
(`/rulesets/modes/activate`, `/rulesets/{id}/arm`, `/devices/{id}/commands`, `/audit`) and add the one piece that had no
equivalent: a deterministic, explainable rule test. Nothing here has logic of its own beyond reshaping.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from services.rules.simulate import simulate
from td_contracts import DeviceCommandRequest, RulesetArmRequest, RulesetModeActivateRequest, RuleSpec
from .. import database as db
from ..security import authenticated
from . import devices as devices_routes
from . import rulesets as rulesets_routes

router = APIRouter(prefix="/api/v1")


@router.get("/rules/templates")
async def rule_templates(session=Depends(authenticated)):
    """Templates in the shape the apps render (`default_text`, `requires_zone`, ...)."""
    out = []
    for t in rulesets_routes.load_templates():
        schedule = t.get("schedule_default")
        out.append({
            "id": t["id"],
            "name": t["name"],
            "category": t.get("rule_type", "").replace("_", " "),
            "description": t.get("description", ""),
            # Unedited, this text makes the server build the rule deterministically from the template (no model).
            "default_text": t.get("description", t["name"]),
            "default_severity": t.get("severity", "medium"),
            "requires_zone": bool(t.get("zone_required")),
            "requires_line": t.get("rule_type") in ("line_cross", "count_threshold"),
            "target_classes": t.get("target_classes", []),
            "modes": t.get("modes", []),
            "default_schedule": schedule,
        })
    return out


@router.get("/system/mode")
async def get_system_mode(session=Depends(authenticated)):
    return {"mode": rulesets_routes.get_active_mode()}


@router.put("/system/mode")
async def set_system_mode(body: RulesetModeActivateRequest, request: Request, session=Depends(authenticated)):
    result = await rulesets_routes.activate_security_mode(body, request, session)
    return {"mode": result["mode"], "armed_ruleset_ids": result["armed_ruleset_ids"], "disarmed_ruleset_ids": result["disarmed_ruleset_ids"]}


@router.post("/rulesets/{ruleset_id}/activate")
async def activate_ruleset(ruleset_id: str, body: RulesetArmRequest, request: Request, session=Depends(authenticated)):
    return await rulesets_routes.arm_ruleset(ruleset_id, body, request, session)


@router.post("/rules/{rule_id}/dry-run")
async def dry_run_rule(rule_id: str, body: dict | None = None, session=Depends(authenticated)):
    """Would this rule alert? Runs a synthetic object through the real rule engine and explains the answer."""
    row = db.get_rule(rule_id)
    if row is None:
        raise HTTPException(404, "Rule not found")
    spec = RuleSpec.model_validate_json(row["spec_json"])
    geometry, _ = db.get_geometry(spec.camera_id)
    geometry = geometry or {}
    tracks = (body or {}).get("synthetic_tracks") or [{}]
    return simulate(spec, geometry.get("zones", {}), geometry.get("lines", {}), geometry.get("homography"), tracks[0])


@router.get("/system/audit")
async def system_audit(limit: int = 15, session=Depends(authenticated)):
    out = []
    for entry in db.list_audit_log(limit=max(1, min(200, limit))):
        out.append({
            "id": entry["id"],
            "actor": entry.get("actor_user") or entry.get("actor_device") or "system",
            "action": entry["action"],
            "target_id": entry.get("target_id"),
            "created_at": datetime.fromtimestamp(entry["ts"], timezone.utc).isoformat(),
        })
    return out


COMMAND_NAMES = {"take_snapshot": "take_full_snapshot", "flip_lens": "switch_lens", "toggle_stealth": "enter_stealth"}


@router.post("/devices/{device_id}/command")
async def device_command(device_id: str, body: dict, request: Request, session=Depends(authenticated)):
    action = body.get("command") or body.get("action")
    action = COMMAND_NAMES.get(action, action)
    if not action:
        raise HTTPException(422, "A command is required")
    return await devices_routes.send_command_to_device(
        device_id, DeviceCommandRequest(action=action, params=body.get("params") or {}), request, session)
