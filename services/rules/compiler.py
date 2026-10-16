"""Gemma candidate -> strict RuleSpec -> capability check -> readback."""

import re
import uuid
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from td_contracts import RuleCompileResult, RuleSpec, RuleWhen
from .llm import LocalLLM
from .readback import readback
from .registry import CapabilityRegistry


ROOT = Path(__file__).resolve().parents[2]


class FlatCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    zone: str | None = None
    line: str | None = None
    seconds: float | None = None
    count: int | None = None
    window_s: float | None = None
    meters: float | None = None
    start: str | None = None
    end: str | None = None
    tz: str | None = None
    negated: bool = False


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    entity: str
    conditions: list[FlatCondition]
    join: str
    unsupported_reason: str | None


FORBIDDEN_ACTION = re.compile(r"\b(scratch(?:es|ing|ed)?|steal(?:s|ing)?|fight(?:s|ing)?|attack(?:s|ing|ed)?)\b", re.I)
COLOR_ATTRIBUTE = re.compile(r"\b(red|blue|green|yellow|black|white|orange|purple)\s+\w+", re.I)


class RuleCompiler:
    def __init__(self, registry: CapabilityRegistry, llm: LocalLLM):
        self.registry = registry
        self.llm = llm

    @classmethod
    def from_config(cls, classes: set[str], zones: set[str], lines: set[str], calibrated: bool):
        config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
        llm = LocalLLM(**config["llm"])
        registry = CapabilityRegistry(ROOT, classes, zones, lines, calibrated)
        return cls(registry, llm)

    def _unsupported(self, text: str, camera_id: str, reason: str) -> RuleCompileResult:
        spec = RuleSpec(rule_id="r_" + uuid.uuid4().hex, camera_id=camera_id, version=1, name=text[:120],
                        entity="unknown", when=None, support_level="UNSUPPORTED", unsupported_reason=reason)
        return RuleCompileResult(spec=spec, readback=None, support_level="UNSUPPORTED", problems=[reason], can_activate=False)

    def compile(self, text: str, camera_id: str) -> RuleCompileResult:
        text = text.strip()
        if not text or len(text) > 1000:
            return self._unsupported(text or "Empty request", camera_id, "Rule text must be 1–1000 characters")
        if FORBIDDEN_ACTION.search(text):
            return self._unsupported(text, camera_id, "Requested action or intent has no supported detector")
        if COLOR_ATTRIBUTE.search(text):
            return self._unsupported(text, camera_id, "Color attributes are not supported by object detection")
        if re.search(r"\bnight\b", text, re.I) and not re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b|midnight", text, re.I):
            return self._unsupported(text, camera_id, "Specify exact night hours")
        system = (
            "Compile a monitoring request into JSON only. Never generate code, SQL or unrequested conditions. "
            "Allowed condition types: entity_present, in_zone, line_cross, unique_count_at_least, "
            "dwell_at_least, moving_toward, distance_below, time_window. "
            "Return a flat conditions array, joined with 'all' unless the user explicitly says OR. "
            "If any requested part cannot be expressed, return conditions=[] and a specific unsupported_reason. "
            "Use supplied zone and line names exactly. A count rule needs line, count and window_s. "
            "For a three-second dwell use seconds=3. Do not add an extra hold. "
            "For midnight to 5 a.m. use start=00:00 and end=05:00. "
            "Time zone defaults to the camera's configured zone if omitted. "
            f"Available detector classes: {sorted(self.registry.classes)}. "
            f"Zones: {sorted(self.registry.zones)}. Lines: {sorted(self.registry.lines)}. "
            "Output name, entity, conditions, join, unsupported_reason (null when supported)."
        )
        last_error = None
        for attempt in range(2):
            try:
                data = self.llm.generate_json(system, text if attempt == 0 else text + f"\nCorrect this validation error: {last_error}", Candidate.model_json_schema())
                candidate = Candidate.model_validate(data)
                break
            except (ValidationError, RuntimeError, ValueError) as exc:
                last_error = str(exc)[:300]
        else:
            return self._unsupported(text, camera_id, f"Compiler could not produce a valid rule: {last_error}")
        if candidate.unsupported_reason:
            return self._unsupported(text, camera_id, candidate.unsupported_reason)
        try:
            conditions = []
            timezone_name = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["timezone"]
            mentioned_zones = [zone for zone in sorted(self.registry.zones) if re.search(rf"\b{re.escape(zone)}\b", text, re.I)]
            explicit_seconds = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", text, re.I)
            requested_dwell = bool(re.search(r"\b(stays?|remains?|dwells?|lingers?)\b", text, re.I))
            requested_count = bool(re.search(r"\b(at least|or more)\b", text, re.I))
            for item in candidate.conditions:
                data = item.model_dump(exclude_none=True, exclude={"negated"})
                condition_type = data["type"]
                if condition_type != "time_window" and data.get("start") and data.get("end") and "between" in text.lower():
                    conditions.append(RuleWhen.model_validate({"type": "time_window", "start": data["start"],
                                                               "end": data["end"], "tz": data.get("tz") or timezone_name}))
                if condition_type == "dwell_at_least" and requested_dwell and explicit_seconds:
                    data["seconds"] = float(explicit_seconds.group(1))
                    zone = data.get("zone")
                    if zone in mentioned_zones:
                        conditions.append(RuleWhen(type="in_zone", zone=zone))
                if condition_type == "distance_below" and re.search(r"\bwithin\s+\d+(?:\.\d+)?\s+met(?:re|er)s?\b", text, re.I):
                    found = re.search(r"\bwithin\s+(\d+(?:\.\d+)?)\s+met(?:re|er)s?\b", text, re.I)
                    data["meters"] = float(found.group(1))
                    if not data.get("zone") and len(mentioned_zones) == 1:
                        data["zone"] = mentioned_zones[0]
                if data["type"] == "time_window":
                    data.setdefault("tz", timezone_name)
                if data["type"] == "unique_count_at_least":
                    data.setdefault("window_s", 60)
                allowed = {
                    "entity_present": set(), "in_zone": {"zone"}, "line_cross": {"line"},
                    "unique_count_at_least": {"line", "count", "window_s"},
                    "dwell_at_least": {"seconds"}, "moving_toward": {"zone"},
                    "distance_below": {"zone", "meters"}, "time_window": {"start", "end", "tz"},
                }
                data = {key: value for key, value in data.items() if key == "type" or key in allowed.get(condition_type, set())}
                node = RuleWhen.model_validate(data)
                conditions.append(RuleWhen.model_validate({"not": node.model_dump(by_alias=True, exclude_none=True)}) if item.negated else node)
            if not conditions:
                return self._unsupported(text, camera_id, "No executable conditions were produced")
            join = "any" if re.search(r"\bor\b", text, re.I) else "all"
            if join == "any" and len(mentioned_zones) == 2 and re.search(r"\b(?:in|inside|enters?)\s+\w+\s+or\s+\w+", text, re.I):
                conditions = [RuleWhen(type="in_zone", zone=zone) for zone in mentioned_zones]
            if requested_dwell and explicit_seconds and len(mentioned_zones) == 1:
                if not any(node.type == "in_zone" for node in conditions):
                    conditions.append(RuleWhen(type="in_zone", zone=mentioned_zones[0]))
            if requested_count and any(node.type == "unique_count_at_least" for node in conditions):
                counted_lines = {node.line for node in conditions if node.type == "unique_count_at_least"}
                conditions = [node for node in conditions if node.type != "line_cross" or node.line not in counted_lines]
            unique = []
            for node in conditions:
                if node not in unique:
                    unique.append(node)
            conditions = unique
            if join == "all" and any(node.type in {"in_zone", "line_cross", "unique_count_at_least", "dwell_at_least", "moving_toward", "distance_below"} for node in conditions):
                # A positive tracked-object condition already entails presence.
                conditions = [node for node in conditions if node.type != "entity_present"]
            when = RuleWhen.model_validate({join: [node.model_dump(by_alias=True, exclude_none=True) for node in conditions]})
        except (ValidationError, ValueError, KeyError) as exc:
            return self._unsupported(text, camera_id, f"Compiler conditions are invalid: {str(exc)[:240]}")
        entity = self.registry.resolve_entity(candidate.entity)
        level, problems, can_activate = self.registry.assess(entity, when)
        spec = RuleSpec(rule_id="r_" + uuid.uuid4().hex, camera_id=camera_id, version=1,
                        name=candidate.name[:120] or text[:120], entity=entity, when=when,
                        support_level=level, unsupported_reason="; ".join(problems) or None)
        return RuleCompileResult(spec=spec, readback=readback(spec) if level != "UNSUPPORTED" else None,
                                 support_level=level, problems=problems, can_activate=can_activate)
