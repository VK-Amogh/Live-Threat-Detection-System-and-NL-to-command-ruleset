"""Gemma candidate -> strict RuleSpec -> capability check -> readback."""

import re
import uuid
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from td_contracts import RuleCompileResult, RuleSpec, RuleWhen
from . import grammar
from .llm import LocalLLM
from .readback import limits, readback
from .registry import CapabilityRegistry


ROOT = Path(__file__).resolve().parents[2]
V2_TYPES = {"enters_zone", "exits_zone", "near_object", "touches_object", "sits_on", "picks_up", "object_absent", "zone_changes"}


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


FORBIDDEN_ACTION = re.compile(r"\b(scratch(?:es|ing|ed)?|fight(?:s|ing)?|attack(?:s|ing|ed)?)\b", re.I)
COLOR_ATTRIBUTE = re.compile(r"\b(red|blue|green|yellow|black|white|orange|purple)\s+\w+", re.I)


class RuleCompiler:
    def __init__(self, registry: CapabilityRegistry, llm: LocalLLM, geometry: dict | None = None):
        self.registry = registry
        self.llm = llm
        geometry = geometry or {}
        self.sides = {name: {"a": value["a"], "b": value["b"]} for name, value in (geometry.get("line_sides") or {}).items()}
        self.zone_roles = dict(geometry.get("zone_roles") or {})

    @classmethod
    def from_config(cls, classes: set[str], zones: set[str], lines: set[str], calibrated: bool, geometry: dict | None = None):
        config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))
        llm = LocalLLM(**config["llm"])
        registry = CapabilityRegistry(ROOT, classes, zones, lines, calibrated, anchors=(geometry or {}).get("anchors"))
        return cls(registry, llm, geometry)

    def _context(self) -> grammar.Context:
        return grammar.Context(self.registry.classes, self.registry.zones, self.registry.lines, self.registry.anchors,
                               self.registry.synonyms, self.zone_roles)

    def _needs_setup(self, text: str, camera_id: str, messages: list[str]) -> RuleCompileResult:
        spec = RuleSpec(rule_id="r_" + uuid.uuid4().hex, camera_id=camera_id, version=1, name=text[:120],
                        entity="unknown", when=None, support_level="UNSUPPORTED", feasibility="NEEDS_SETUP",
                        unsupported_reason="Needs setup: " + "; ".join(messages))
        return RuleCompileResult(spec=spec, readback=None, support_level="UNSUPPORTED", problems=messages,
                                 can_activate=False, needs_setup=messages)

    def _finish(self, text: str, camera_id: str, name: str, entity: str, when: RuleWhen, hold_s: float | None = None) -> RuleCompileResult:
        """One construction path for every compiled rule: capability check, feasibility, verification policy, cost, readback."""
        entity = self.registry.resolve_entity(entity)
        level, problems, can_activate = self.registry.assess(entity, when)
        if level != "UNSUPPORTED":
            # Coverage invariant, for every path: the text must not ask for more than the conditions check.
            missing = grammar.uncovered(text, when, self._context())
            if missing:
                return self._unsupported(text, camera_id, "Not covered by any available condition: " + ", ".join(missing))
        v2 = any(leaf.type in V2_TYPES or leaf.direction for leaf in when.leaves()) or when.sequence is not None
        extra = {}
        if v2:
            plan = self.registry.plan(when, hold_s if hold_s is not None else 1.5)
            extra = {"schema_version": 2, "verification": plan["verification"], "feasibility": plan["feasibility"],
                     "reliability": plan["reliability"], "cost": plan["cost"]}
        spec = RuleSpec(rule_id="r_" + uuid.uuid4().hex, camera_id=camera_id, version=1,
                        name=(name or text)[:120], entity=entity, when=when, support_level=level,
                        unsupported_reason="; ".join(problems) or None,
                        **({"min_hold_s": hold_s} if hold_s is not None else {}), **extra)
        setup = self.registry.needs_setup(entity, when) if level == "UNSUPPORTED" else []
        text_readback = readback(spec, self.sides, self.zone_roles) if level != "UNSUPPORTED" else None
        if text_readback and v2 and limits(spec, self.zone_roles):
            text_readback += " " + limits(spec, self.zone_roles)
        if text_readback and getattr(self, "_fixes", None):
            text_readback += " Read " + ", ".join(f"'{wrong}' as '{right}'" for wrong, right in self._fixes) + "."
        return RuleCompileResult(spec=spec, readback=text_readback, support_level=level, problems=problems,
                                 can_activate=can_activate, needs_setup=setup)

    def _unsupported(self, text: str, camera_id: str, reason: str) -> RuleCompileResult:
        spec = RuleSpec(rule_id="r_" + uuid.uuid4().hex, camera_id=camera_id, version=1, name=text[:120],
                        entity="unknown", when=None, support_level="UNSUPPORTED", unsupported_reason=reason)
        return RuleCompileResult(spec=spec, readback=None, support_level="UNSUPPORTED", problems=[reason], can_activate=False)

    def compile(self, text: str, camera_id: str) -> RuleCompileResult:
        """Compile once; if the model's answer was refused for missing something the text asked for (or was malformed),
        ask it once more with that exact reason. A second failure is returned as the refusal it is."""
        self._model_used = False
        text, self._fixes = grammar.correct_typos(text.strip(), self._context())
        result = self._compile_once(text, camera_id)
        retryable = ("Not covered by any available condition", "Compiler conditions are invalid")
        if self._model_used and result.support_level == "UNSUPPORTED" and result.problems and result.problems[0].startswith(retryable):
            retry = self._compile_once(text, camera_id, feedback=result.problems[0][:300])
            if retry.support_level != "UNSUPPORTED":
                return retry
        return result

    def _compile_once(self, text: str, camera_id: str, feedback: str | None = None) -> RuleCompileResult:
        text = text.strip()
        if not text or len(text) > 1000:
            return self._unsupported(text or "Empty request", camera_id, "Rule text must be 1–1000 characters")
        if FORBIDDEN_ACTION.search(text):
            return self._unsupported(text, camera_id, "Requested action or intent has no supported detector")
        if COLOR_ATTRIBUTE.search(text):
            return self._unsupported(text, camera_id, "Color attributes are not supported by object detection")
        if re.search(r"\bnight\b", text, re.I) and not re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b|midnight", text, re.I):
            return self._unsupported(text, camera_id, "Specify exact night hours")
        parsed = grammar.parse(text, self._context())
        if parsed.status == "unsupported":
            return self._unsupported(text, camera_id, parsed.reason)
        if parsed.status == "needs_setup":
            return self._needs_setup(text, camera_id, parsed.needs_setup)
        if parsed.status == "ok":
            return self._finish(text, camera_id, text.rstrip(". ")[:120], parsed.entity, parsed.when, parsed.hold_s)
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
        prompt = text if not feedback else (text + f"\nA previous answer was refused because: {feedback}. "
                                                   "Answer again and include every condition the request asks for.")
        self._model_used = True
        for attempt in range(2):
            try:
                data = self.llm.generate_json(system, prompt if attempt == 0 else prompt + f"\nCorrect this validation error: {last_error}", Candidate.model_json_schema())
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
            mentioned_lines = [line for line in sorted(self.registry.lines) if re.search(rf"\b{re.escape(line)}\b", text, re.I)]
            explicit_seconds = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", text, re.I)
            requested_dwell = bool(re.search(r"\b(stays?|remains?|dwells?|lingers?)\b", text, re.I))
            requested_count = bool(re.search(r"\b(at least|or more)\b", text, re.I))
            for item in candidate.conditions:
                data = item.model_dump(exclude_none=True, exclude={"negated"})
                condition_type = data["type"]
                if condition_type == "time_window" and not (data.get("start") and data.get("end")):
                    continue                    # the model emitted an empty window: no time was asked for
                if condition_type in ("unique_count_at_least", "line_cross") and not data.get("line") and len(mentioned_lines) == 1:
                    data["line"] = mentioned_lines[0]      # "cross gate": the line is named in the text and the model left it out
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
            if len(conditions) == 1 and conditions[0].type == "entity_present" and re.search(r"\b(?:no|nobody|no one)\b", text, re.I):
                # "no person is visible" is an absence rule; the model often returns plain presence without the negation.
                conditions = [RuleWhen.model_validate({"not": conditions[0].model_dump(by_alias=True, exclude_none=True)})]
            if join == "all" and any(node.type in {"in_zone", "line_cross", "unique_count_at_least", "dwell_at_least", "moving_toward", "distance_below"} for node in conditions):
                # A positive tracked-object condition already entails presence.
                conditions = [node for node in conditions if node.type != "entity_present"]
            when = RuleWhen.model_validate({join: [node.model_dump(by_alias=True, exclude_none=True) for node in conditions]})
        except (ValidationError, ValueError, KeyError) as exc:
            return self._unsupported(text, camera_id, f"Compiler conditions are invalid: {str(exc)[:240]}")
        entity = self.registry.resolve_entity(candidate.entity)
        return self._finish(text, camera_id, candidate.name, entity, when)
