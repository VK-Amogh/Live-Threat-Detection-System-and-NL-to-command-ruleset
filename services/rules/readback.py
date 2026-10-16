"""Deterministic explanation of exactly what a rule will evaluate."""

from td_contracts import RuleSpec, RuleWhen


def describe_when(node: RuleWhen) -> str:
    if node.all is not None:
        phrases = [describe_when(child) for child in node.all]
        result = phrases[0]
        for phrase in phrases[1:]:
            result += (" " if phrase.startswith("between ") else " and ") + phrase
        return result
    if node.any is not None:
        return "(" + " or ".join(describe_when(child) for child in node.any) + ")"
    if node.not_ is not None:
        return "not (" + describe_when(node.not_) + ")"
    if node.type == "entity_present":
        return "is visible"
    if node.type == "in_zone":
        return f"is inside {node.zone}"
    if node.type == "line_cross":
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
    raise ValueError(f"Unknown condition: {node.type}")


def readback(spec: RuleSpec) -> str:
    return f"Alert when a tracked {spec.entity} {describe_when(spec.when)}."
