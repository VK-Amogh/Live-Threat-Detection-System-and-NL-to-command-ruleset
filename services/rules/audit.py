"""Find rules whose stored text asks for more than their conditions check.

Rules compiled before the coverage invariant existed could silently lose clauses ("if someone sits on the chair" was
stored, and ran, as "a person is visible"). The text of each natural-language rule is kept next to its spec, so the same
invariant can be applied to what is already stored: such a rule is not loaded by the workers and cannot be activated."""

from td_contracts import RuleSpec
from . import grammar
from .registry import CapabilityRegistry


def dropped_clauses(text: str | None, spec: RuleSpec, registry: CapabilityRegistry, zone_roles: dict | None = None) -> list[str]:
    """Words of a natural-language rule's text that no condition accounts for (empty for template and builder rules)."""
    if not text or not spec.rule_id.startswith("r_") or spec.when is None:
        return []
    context = grammar.Context(registry.classes, registry.zones, registry.lines, registry.anchors, registry.synonyms, zone_roles or {})
    return grammar.uncovered(text, spec.when, context)
