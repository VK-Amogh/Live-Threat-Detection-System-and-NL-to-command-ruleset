"""Capability availability comes from config, loaded classes and camera geometry."""

from pathlib import Path

import yaml

from td_contracts import RuleWhen


class CapabilityRegistry:
    def __init__(self, root: Path, classes: set[str], zones: set[str], lines: set[str], calibrated: bool):
        self.entries = yaml.safe_load((root / "config/rule_capabilities.yaml").read_text(encoding="utf-8"))["capabilities"]
        self.synonyms = yaml.safe_load((root / "config/rule_synonyms.yaml").read_text(encoding="utf-8"))["entities"]
        self.classes = classes
        self.zones = zones
        self.lines = lines
        self.calibrated = calibrated

    def resolve_entity(self, word: str) -> str:
        name = word.lower().strip()
        return self.synonyms.get(name, name)

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
            if condition.type in ("in_zone", "moving_toward", "distance_below") and condition.zone not in self.zones:
                problems.append(f"Zone '{condition.zone}' is not configured")
            if condition.type in ("line_cross", "unique_count_at_least") and condition.line not in self.lines:
                problems.append(f"Line '{condition.line}' is not configured")
            if condition.type == "distance_below" and not self.calibrated:
                problems.append("Metre distance needs camera homography calibration")
                can_activate = False
        level = "UNSUPPORTED" if any(not item.startswith("Metre distance") for item in problems) else "EXPERIMENTAL" if experimental else "SUPPORTED"
        return level, problems, can_activate and level != "UNSUPPORTED"
