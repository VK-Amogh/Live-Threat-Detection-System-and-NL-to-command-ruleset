"""Capability availability comes from config, loaded classes and camera geometry."""

from pathlib import Path

import yaml

from td_contracts import CostEstimate, RuleWhen, Verification

ZONE_TYPES = ("in_zone", "moving_toward", "distance_below", "enters_zone", "exits_zone", "zone_changes")
LINE_TYPES = ("line_cross", "unique_count_at_least")
OBJECT_TYPES = ("near_object", "touches_object", "sits_on", "picks_up", "object_absent")
ANCHOR_ONLY_TYPES = ("picks_up", "object_absent")        # "any chair" is meaningful; "any bag that disappears" is not
RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


class CapabilityRegistry:
    def __init__(self, root: Path, classes: set[str], zones: set[str], lines: set[str], calibrated: bool, anchors=None):
        self.entries = yaml.safe_load((root / "config/rule_capabilities.yaml").read_text(encoding="utf-8"))
        self.defaults = self.entries.get("verification_defaults", {})
        self.entries = self.entries["capabilities"]
        self.synonyms = yaml.safe_load((root / "config/rule_synonyms.yaml").read_text(encoding="utf-8"))["entities"]
        self.classes = classes
        self.zones = zones
        self.lines = lines
        self.calibrated = calibrated
        self.anchors = {name: ({"cls": a.cls, "label": a.label} if hasattr(a, "cls") else {"cls": a["cls"], "label": a.get("label")})
                        for name, a in dict(anchors or {}).items()}
        pose = (yaml.safe_load((root / "config/rules.yaml").read_text(encoding="utf-8")).get("pose") or {}).get("weights", "weights/yolo26n-pose.pt")
        self.pose_available = (root / pose).is_file()

    def resolve_entity(self, word: str) -> str:
        name = word.lower().strip()
        return self.synonyms.get(name, name)

    def needs_setup(self, entity: str, when: RuleWhen | None) -> list[str]:
        """Things the user can fix: draw a zone or line, confirm an object, install pose weights."""
        missing = []
        for condition in when.leaves() if when else ():
            if (condition.type in ZONE_TYPES or condition.type == "count_in_zone_at_least" and condition.zone) and condition.zone not in self.zones:
                missing.append(f"Draw a zone named '{condition.zone}' on this camera")
            if condition.type in LINE_TYPES and condition.line not in self.lines:
                missing.append(f"Draw a line named '{condition.line}' on this camera")
            ref = condition.object
            if ref is not None and ref.anchor and ref.anchor not in self.anchors:
                missing.append(f"Click the object '{ref.anchor}' on this camera's snapshot to confirm which one you mean")
            if condition.type in ANCHOR_ONLY_TYPES and (ref is None or not ref.anchor):
                missing.append(f"{condition.type} needs one specific object confirmed on the snapshot")
            if "pose" in self.entries.get(condition.type, {}).get("requires", []) and not self.pose_available:
                missing.append("Install pose weights once with: python scripts/fetch_pose_weights.py")
        return list(dict.fromkeys(missing))

    def assess(self, entity: str, when: RuleWhen | None) -> tuple[str, list[str], bool]:
        problems = []
        if entity not in self.classes:
            problems.append(f"Detector weights do not support '{entity}'")
        if when is None:
            problems.append("No executable conditions were produced")
        experimental = False
        can_activate = True
        for condition in when.leaves() if when else ():
            entry = self.entries[condition.type]
            if entry["status"] == "UNSUPPORTED":
                problems.append(f"{condition.type} is unsupported")
            if entry["status"] == "EXPERIMENTAL":
                experimental = True
            if (condition.type in ZONE_TYPES or condition.type == "count_in_zone_at_least" and condition.zone) and condition.zone not in self.zones:
                problems.append(f"Zone '{condition.zone}' is not configured")
            if condition.type in LINE_TYPES and condition.line not in self.lines:
                problems.append(f"Line '{condition.line}' is not configured")
            if condition.object is not None and condition.object.cls and condition.object.cls not in self.classes:
                problems.append(f"Detector weights do not support '{condition.object.cls}'")
            if condition.object is not None and condition.object.anchor and condition.object.anchor not in self.anchors:
                problems.append(f"Object '{condition.object.anchor}' is not confirmed on this camera")
            if condition.type in ANCHOR_ONLY_TYPES and (condition.object is None or not condition.object.anchor):
                problems.append(f"{condition.type} needs one specific object confirmed on the snapshot")
            if "pose" in entry.get("requires", []) and not self.pose_available:
                problems.append("Pose weights are not installed (python scripts/fetch_pose_weights.py)")
            if condition.type == "distance_below" and not self.calibrated:
                problems.append("Metre distance needs camera homography calibration")
                can_activate = False
        level = "UNSUPPORTED" if any(not item.startswith("Metre distance") for item in problems) else "EXPERIMENTAL" if experimental else "SUPPORTED"
        return level, problems, can_activate and level != "UNSUPPORTED"

    def plan(self, when: RuleWhen | None, hold_s: float = 0.0) -> dict:
        """Feasibility class, reliability ceiling, default verification policy and cost for a compiled condition tree."""
        leaves = list(when.leaves()) if when else []
        entries = [self.entries[leaf.type] for leaf in leaves]
        if any(entry["status"] == "UNSUPPORTED" for entry in entries):
            return {"feasibility": "UNVERIFIABLE", "reliability": None, "verification": None, "cost": None}
        reliability = min((entry.get("reliability", "MEDIUM") for entry in entries), key=RANK.get, default="HIGH")
        pose = any("pose" in entry.get("requires", []) for entry in entries)
        question = next((self.defaults[leaf.type] for leaf in leaves if leaf.type in self.defaults), None)
        method = "vlm" if question else ("pose" if pose else "geometry")
        verification = Verification(method=method, vlm_question=question)
        stages = ["detect", "track"] + (["pose"] if pose else []) + (["vlm"] if question else [])
        extra = "pose+vlm" if pose and question else "pose" if pose else "vlm" if question else "none"
        dwell = max((leaf.seconds or 0 for leaf in leaves if leaf.type in ("dwell_at_least", "object_absent")), default=0)
        cost = CostEstimate(stages=stages, gpu_extra=extra, expected_latency_s=None if question else round(max(hold_s, dwell), 1),
                            basis=f"hold {max(hold_s, dwell):g} s" + (" + visual check (not yet measured)" if question else ""))
        return {"feasibility": "TEMPORAL_VLM" if question and not pose else "POSE" if pose else "GEOMETRIC",
                "reliability": reliability, "verification": verification, "cost": cost}
