"""Deterministic explanation of exactly what a rule will evaluate."""

from td_contracts import RuleSpec, RuleWhen


def describe_object(node: RuleWhen) -> str:
    ref = node.object
    return f"'{ref.anchor}'" if ref.anchor else f"a {ref.cls}"


def describe_when(node: RuleWhen, sides: dict | None = None, roles: dict | None = None) -> str:
    if node.all is not None:
        phrases = [describe_when(child, sides, roles) for child in node.all]
        result = phrases[0]
        for phrase in phrases[1:]:
            result += (" " if phrase.startswith("between ") else " and ") + phrase
        return result
    if node.any is not None:
        return "(" + " or ".join(describe_when(child, sides, roles) for child in node.any) + ")"
    if node.not_ is not None:
        return "not (" + describe_when(node.not_, sides, roles) + ")"
    if node.sequence is not None:
        within = f" within {node.within_s:g} seconds" if node.within_s else ""
        return "first " + ", then ".join(describe_when(child, sides, roles) for child in node.sequence) + within
    if node.type == "entity_present":
        return "is visible"
    if node.type == "in_zone":
        return f"is inside {node.zone}"
    if node.type == "line_cross":
        if node.direction in ("a_to_b", "b_to_a"):
            labels = (sides or {}).get(node.line)
            first, second = ("a", "b") if node.direction == "a_to_b" else ("b", "a")
            if labels:
                return f"crosses {node.line} from {labels[first]} to {labels[second]}"
            return f"crosses {node.line} from side {first.upper()} to side {second.upper()}"
        return f"crosses {node.line}"
    if node.type == "unique_count_at_least":
        return f"at least {node.count} distinct tracks cross {node.line} within {node.window_s:g} seconds"
    if node.type == "dwell_at_least":
        return f"remains there for at least {node.seconds:g} seconds"
    if node.type == "moving_toward":
        return f"moves toward {node.zone}"
    if node.type == "distance_below":
        return f"is within {node.meters:g} calibrated metres of {node.zone}"
    if node.type == "time_window":
        return f"between {node.start} and {node.end} {node.tz}"
    if node.type == "zone_changes":
        return f"the picture inside {node.zone} changes (a door opening; people in front of it are ignored)"
    if node.type == "count_in_zone_at_least":
        return f"at least {node.count} are {'inside ' + node.zone if node.zone else 'in view'} at the same time"
    if node.type == "enters_zone":
        if (roles or {}).get(node.zone) == "door":
            return f"comes in through {node.zone} (appears in the doorway)"
        return f"enters {node.zone} (was seen outside it first)"
    if node.type == "exits_zone":
        if (roles or {}).get(node.zone) == "door":
            return f"goes out through {node.zone} (is last seen in the doorway, then gone)"
        return f"leaves {node.zone} (was seen inside it first)"
    if node.type == "near_object":
        return f"is next to {describe_object(node)}"
    if node.type == "touches_object":
        return f"touches {describe_object(node)} with a visible hand"
    if node.type == "sits_on":
        return f"sits on {describe_object(node)} (hips and torso must be visible)"
    if node.type == "picks_up":
        return f"is at {describe_object(node)} and its place is then left empty"
    if node.type == "object_absent":
        return f"{describe_object(node)} is missing from its place for at least {node.seconds:g} seconds (not while someone stands in front of it)"
    raise ValueError(f"Unknown condition: {node.type}")


def limits(spec: RuleSpec, roles: dict | None = None) -> str:
    """What the rule will NOT do, so the person confirming it knows the blind spots."""
    types = {leaf.type for leaf in spec.when.leaves()} if spec.when else set()
    notes = []
    if types & {"touches_object", "sits_on"}:
        notes.append("It needs the body part to be visible: a hidden hand or hips means no alert, never a guess.")
    door_zones = {leaf.zone for leaf in spec.when.leaves() if leaf.type in ("enters_zone", "exits_zone")} if spec.when else set()
    if door_zones and all((roles or {}).get(zone) == "door" for zone in door_zones):
        notes.append("In a door zone, a person who appears in the doorway counts as coming in and one who disappears there counts as going out; someone walking past the door does neither.")
    elif door_zones:
        notes.append("A zone cannot tell which way someone is going; to detect going through a door, draw the door as a Door zone or a line across the doorway.")
    if "zone_changes" in types:
        notes.append("It watches the picture inside the zone with people masked out, so it sees the door itself move; a door opened while a person hides most of it cannot be judged.")
    if types & {"picks_up", "object_absent"}:
        notes.append("It does not alert while a person stands in front of the object, or if the camera has moved.")
    if types & {"in_zone", "line_cross", "enters_zone", "exits_zone", "near_object", "touches_object", "sits_on", "picks_up", "object_absent", "zone_changes"}:
        notes.append("Zones, lines and objects are paused while the camera view is moving.")
    if spec.verification and spec.verification.method == "vlm":
        policy = {"hold_for_review": "held for review", "send_unverified": "sent marked unverified", "drop": "dropped"}[spec.verification.on_unverifiable]
        notes.append(f"A visual check confirms each alert; if it cannot decide or is unavailable the alert is {policy}.")
    if types and not types <= {"time_window"} and spec.when is not None:
        notes.append("It reports a visible pattern, not intent.")
    return " ".join(notes)


def readback(spec: RuleSpec, sides: dict | None = None, roles: dict | None = None) -> str:
    if spec.when is not None and spec.when.type == "zone_changes":
        return f"Alert when {describe_when(spec.when, sides, roles)}."          # about the area, not about a tracked person
    return f"Alert when a tracked {spec.entity} {describe_when(spec.when, sides, roles)}."


render_readback = readback
