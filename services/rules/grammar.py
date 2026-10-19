"""Deterministic phrase parser and coverage invariant for rule text.

Two jobs:

* `parse` compiles the person-object and door phrasings the local language model handled worst (sits on, touches, picks up,
  next to, goes missing, enters/leaves a door) directly into conditions, with no model call. It resolves "the chair" to a
  specific object confirmed on the camera snapshot, or says exactly what must be set up first. Anything it does not
  recognise falls through (status "fallthrough") to the model path.
* `uncovered` is the invariant for every compiled rule, from either path: each action word, object noun and name in the
  text must be honoured by a condition, a known class, or a configured name. Otherwise the rule is refused with the word
  named. A clause is never dropped silently (an active rule once compiled "sits on the chair" into "a person is visible").
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from td_contracts import ObjectRef, RuleWhen

ROOT = Path(__file__).resolve().parents[2]
_LEXICON = None
CLAUSE_SPLIT = re.compile(r"\b(?:and then|then|and)\b")
TIME_WORD = re.compile(r"^\d{1,2}(?::\d{2})?$")
DEFINITE = {"the", "that", "this", "my", "our", "its"}
INDEFINITE = {"a", "an", "any"}


def lexicon() -> dict:
    global _LEXICON
    if _LEXICON is None:
        data = yaml.safe_load((ROOT / "config/rule_lexicon.yaml").read_text(encoding="utf-8"))
        data["verbs"] = [{**verb, "regex": re.compile(verb["pattern"])} for verb in data["verbs"]]
        data["known"] = set(data["ignorable"]) | set(data["units"]) | set(data["numbers"])
        data["verb_words"] = {word for verb in data["verbs"] for word in re.findall(r"[a-z]{3,}", verb["pattern"])}
        _LEXICON = data
    return _LEXICON


def normalize(text: str) -> str:
    text = text.lower().replace("a.m.", "am").replace("p.m.", "pm")
    return " ".join(re.sub(r"[^a-z0-9:_\s]", " ", text).split())


def singular(word: str) -> str:
    for suffix, replacement in (("ies", "y"), ("ses", "s"), ("es", "e"), ("s", "")):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)] + replacement
    return word


@dataclass
class Context:
    classes: set[str]
    zones: set[str]
    lines: set[str]
    anchors: dict[str, dict] = field(default_factory=dict)       # name -> {"cls": ..., "label": ...}
    synonyms: dict[str, str] = field(default_factory=dict)
    zone_roles: dict[str, str] = field(default_factory=dict)

    def class_of(self, word: str) -> str | None:
        for candidate in (word, singular(word), word.rstrip("s")):
            resolved = self.synonyms.get(candidate, candidate)
            if resolved in self.classes:
                return resolved
        return None

    def name_words(self) -> set[str]:
        words = set()
        for name in [*self.zones, *self.lines, *self.anchors]:
            words |= set(name.lower().replace("_", " ").split())
        for info in self.anchors.values():
            words |= set(normalize(info.get("label") or "").split())
        return words


@dataclass
class Parsed:
    status: str                                    # ok | needs_setup | unsupported | fallthrough
    entity: str | None = None
    when: RuleWhen | None = None
    hold_s: float | None = None
    needs_setup: list[str] = field(default_factory=list)
    reason: str | None = None


def _has_not(node) -> bool:
    return node.not_ is not None or any(_has_not(child) for child in (node.all or node.any or node.sequence or []))


def _mentioned(name: str, normalized: str) -> bool:
    return re.search(rf"\b{re.escape(name.lower().replace('_', ' '))}\b", normalized) is not None


def uncovered(text: str, when, ctx: Context) -> list[str]:
    """What the rule text asks for that its conditions do not check.

    `when` is the compiled condition tree (a plain set of condition types is accepted for the word checks only). Words are
    checked against the lexicon, classes and configured names; then the structure: a zone or line named in the text must be
    used by a condition, a negation needs a `not`, a clock time needs a time window, "at least N" needs a count."""
    lex = lexicon()
    tree = when if hasattr(when, "leaves") else None
    leaf_types = {leaf.type for leaf in when.leaves()} if tree is not None else set(when)
    normalized = normalize(text)
    problems, remaining = [], normalized
    for verb in lex["verbs"]:
        matches = list(verb["regex"].finditer(normalized))
        if matches and "any" not in verb["types"] and not (set(verb["types"]) & leaf_types):
            problems.append(f"'{matches[0].group(0)}' (needs {' or '.join(verb['types'])})")
        remaining = verb["regex"].sub(" ", remaining)
    known_names = ctx.name_words()
    negated = tree is not None and _has_not(tree)
    for word in remaining.split():
        if word in lex["negations"]:
            if tree is not None and not negated:
                problems.append(f"'{word}' (a negation needs a 'not' condition)")
            continue
        if word in lex.get("crossing_context", ()) and leaf_types & {"line_cross", "enters_zone", "exits_zone"}:
            continue
        if word in lex["known"] or TIME_WORD.match(word) or word in known_names or word in lex["door_words"] or word in lex["intent"]:
            continue
        if ctx.class_of(word) or singular(word) in known_names:
            continue
        problems.append(f"'{word}'")
    if tree is not None:
        leaves = list(tree.leaves())
        for name in sorted(ctx.zones):
            if _mentioned(name, normalized) and name not in {leaf.zone for leaf in leaves}:
                problems.append(f"'{name}' (the zone is mentioned but no condition uses it)")
        for name in sorted(ctx.lines):
            if _mentioned(name, normalized) and name not in {leaf.line for leaf in leaves}:
                problems.append(f"'{name}' (the line is mentioned but no condition uses it)")
        if re.search(r"\b\d{1,2}:\d{2}\b|\b(?:am|pm|midnight)\b", normalized) and "time_window" not in leaf_types:
            problems.append("a clock time (needs a time window condition)")
        if re.search(r"\bat least\b|\bor more\b", normalized) and not (leaf_types & {"unique_count_at_least", "count_in_zone_at_least"}):
            problems.append("'at least' (needs a count condition)")
    return list(dict.fromkeys(problems))


# --- phrase parser ------------------------------------------------------------------------------------------------

def _hold(clause: str) -> float | None:
    found = re.search(r"\bfor\s+(?:at least\s+)?(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", clause)
    return float(found.group(1)) if found else None


def _resolve_object(rest: str, ctx: Context, need_anchor: bool = False) -> tuple[ObjectRef | None, list[str], str | None]:
    """The object a person-object phrase names: a confirmed anchor ("the chair"), or any instance ("a chair")."""
    words = rest.split()
    for index, word in enumerate(words):
        noun = ctx.class_of(word)
        if noun is None or noun == "person":
            continue
        article = words[index - 1] if index else ""
        qualifiers = {w for w in words if w != word and w not in lexicon()["ignorable"]}
        candidates = {name: info for name, info in ctx.anchors.items() if info["cls"] == noun}
        if article in INDEFINITE and not need_anchor:
            return ObjectRef(cls=noun), [], noun
        if article in INDEFINITE and need_anchor:
            return None, [f"This rule needs one specific {noun}: confirm it on the camera snapshot and say 'the {noun}' instead of '{article} {noun}'"], noun
        if not candidates:
            return None, [f"Click the {noun} you mean on this camera's snapshot to confirm which one it is"], noun
        if len(candidates) == 1:
            return ObjectRef(anchor=next(iter(candidates))), [], noun
        scored = {name: len(qualifiers & (set(name.lower().replace("_", " ").split()) | set(normalize(info.get("label") or "").split())))
                  for name, info in candidates.items()}
        best = max(scored.values())
        winners = [name for name, score in scored.items() if score == best]
        if best > 0 and len(winners) == 1:
            return ObjectRef(anchor=winners[0]), [], noun
        names = ", ".join(sorted(candidates))
        return None, [f"Which {noun} do you mean? Confirmed on this camera: {names}. Name it (for example '{noun} by the window') or say 'any {noun}'"], noun
    return None, [], None


def _find_door(clause: str, ctx: Context) -> tuple[tuple[str, str] | None, list[str]]:
    lex = lexicon()
    words = set(clause.split())
    if not words & set(lex["door_words"]):
        return None, []
    named = [("line", name) for name in sorted(ctx.lines) if set(name.lower().split("_")) & set(lex["door_words"])]
    named += [("zone", name) for name in sorted(ctx.zones) if ctx.zone_roles.get(name) == "door" or set(name.lower().split("_")) & set(lex["door_words"])]
    # Only a drawn door whose name shares a word with the text can be meant: "the door" is never bound to a line named "gate".
    sharing = [item for item in named if set(item[1].lower().split("_")) & words]
    qualified = lambda item: len((set(item[1].lower().split("_")) - set(lex["door_words"])) & words)   # "back" in "back door"
    best = max((qualified(item) for item in sharing), default=0)
    if best > 0:
        sharing = [item for item in sharing if qualified(item) == best]
    if len(sharing) == 1:
        return sharing[0], []
    if len(sharing) > 1:
        return None, [f"Which door do you mean? Drawn on this camera: {', '.join(name for _, name in sharing)}. Name it, for example 'front door'"]
    if named:
        return None, [f"None of the drawn door-like shapes ({', '.join(name for _, name in named)}) matches the word you used; use its name, or draw the door and name it with 'door' in it"]
    return None, ["Draw the door on this camera: in Zones, lines and objects choose 'Crossing line or door', name it with 'door' in it (for example 'front_door'), "
                  "click two points across the doorway, check the arrow points into the room (Flip if not) and save"]


def _clause(clause: str, ctx: Context) -> tuple[str, RuleWhen | None, list[str], str | None, float | None]:
    """(status, condition, needs_setup, entity, hold). status: handled | fallthrough."""
    lex = lexicon()
    verbs = {verb["id"]: verb["regex"].search(clause) for verb in lex["verbs"]}
    first = min((m for m in verbs.values() if m), key=lambda m: m.start(), default=None)
    if first is None:
        return "fallthrough", None, [], None, None
    kind = next(vid for vid, m in verbs.items() if m is first)
    rest = clause[first.end():]
    hold = _hold(clause)
    if kind in ("sit", "touch", "near"):
        ref, setup, noun = _resolve_object(rest, ctx)
        if ref is None and not setup:
            return "fallthrough", None, [], None, None
        if ref is None:
            return "handled", None, setup, None, None
        node = {"sit": "sits_on", "touch": "touches_object", "near": "near_object"}[kind]
        if kind == "sit" and hold is None:
            hold = 1.0                           # sitting is a settled posture: one second of it is enough to alert
        return "handled", RuleWhen(type=node, object=ref), [], None, hold
    if kind == "pickup":
        ref, setup, noun = _resolve_object(rest, ctx, need_anchor=True)
        if ref is None and not setup:
            return "fallthrough", None, [], None, None
        return "handled", (RuleWhen(type="picks_up", object=ref) if ref else None), setup, None, hold
    if kind == "missing":
        subject = clause[:first.start()]
        ref, setup, noun = _resolve_object(subject + " " + rest, ctx, need_anchor=True)
        if ref is None and not setup:
            return "fallthrough", None, [], None, None
        seconds = hold or 5.0
        return "handled", (RuleWhen(type="object_absent", object=ref, seconds=seconds) if ref else None), setup, noun, 0.0
    if kind == "open":
        door, setup = _find_door(clause, ctx)
        if door is None and not setup:
            return "fallthrough", None, [], None, None
        if door is None:
            return "handled", None, setup, None, None
        if door[0] == "line":
            return "handled", None, ["To notice a door opening, draw the door itself as a zone (Zone polygon, role Door) around the door; a line across the doorway cannot see the door move"], None, None
        return "handled", RuleWhen(type="zone_changes", zone=door[1]), [], None, 0.4
    if kind in ("enter", "leave"):
        door, setup = _find_door(rest, ctx)
        if door is None and not setup:
            return "fallthrough", None, [], None, None       # "enters the driveway": the model path's in_zone handles zones
        if door is None:
            return "handled", None, setup, None, None
        what, name = door
        if what == "line":
            return "handled", RuleWhen(type="line_cross", line=name, direction="a_to_b" if kind == "enter" else "b_to_a"), [], None, None
        return "handled", RuleWhen(type="enters_zone" if kind == "enter" else "exits_zone", zone=name), [], None, None
    return "fallthrough", None, [], None, None


def parse(text: str, ctx: Context) -> Parsed:
    lex = lexicon()
    normalized = normalize(text)
    words = set(normalized.split())
    for word, reason in lex["intent"].items():
        if word in words:
            return Parsed("unsupported", reason=reason)
    if re.search(r"\b(between|at least|metre|metres|meter|meters|distinct)\b|\d{1,2}:\d{2}|\b(am|pm|midnight)\b", normalized):
        return Parsed("fallthrough")
    actor = None
    for word in normalized.split():
        found = ctx.class_of(word)
        if found == "person" or word in ("someone", "anyone", "somebody"):
            actor = "person"
            break
        if found is not None and actor is None and found in ("dog", "cat", "car", "truck", "bus", "motorcycle", "bicycle"):
            actor = found
    clauses = [c.strip() for c in CLAUSE_SPLIT.split(normalized) if c.strip()]
    handled = []
    for clause in clauses:
        status, node, setup, entity, hold = _clause(clause, ctx)
        if status == "handled":
            handled.append((node, setup, entity, hold))
        elif len(clauses) > 1:
            handled.append(None)
    if not any(item for item in handled):
        return Parsed("fallthrough")
    if any(item is None for item in handled):
        return Parsed("fallthrough")                    # a second clause the parser cannot read: let the coverage check judge it
    setup = [message for _, messages, _, _ in handled for message in messages]
    if setup:
        return Parsed("needs_setup", needs_setup=list(dict.fromkeys(setup)))
    nodes = [node for node, _, _, _ in handled]
    entity = next((e for _, _, e, _ in handled if e), None) or actor
    if entity is None and all(node.type == "zone_changes" for node in nodes):
        entity = "person"                       # "the door opens" has no actor; the rule watches the zone itself
    if entity is None:
        return Parsed("fallthrough")
    if len(nodes) == 1:
        when = nodes[0]
    else:
        within = re.search(r"\bwithin\s+(\d+(?:\.\d+)?)\s*(?:seconds?|secs?)\b", normalized)
        when = RuleWhen(sequence=nodes, **({"within_s": float(within.group(1))} if within else {}))
    holds = [h for _, _, _, h in handled if h is not None]
    return Parsed("ok", entity=entity, when=when, hold_s=max(holds) if holds else None)


# --- typo tolerance ----------------------------------------------------------------------------------------------

def _distance(a: str, b: str) -> int:
    """Optimal string alignment distance: an insertion, deletion, substitution or swap of neighbours is one edit."""
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            rows[i][j] = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                rows[i][j] = min(rows[i][j], rows[i - 2][j - 2] + 1)
    return rows[-1][-1]


def correct_typos(text: str, ctx: Context) -> tuple[str, list[tuple[str, str]]]:
    """Fix obvious misspellings ("entres", "throught") so a good rule is not refused over a slip of the keyboard.

    Only words of five or more letters that are not already known are touched, only when exactly one known word is one edit
    away (two for words of eight or more letters), so real unknown words ("dances", "drone") are left for the invariant to
    refuse. Every correction is reported back in the readback."""
    lex = lexicon()
    # A misspelling is never repaired into a negation or an intent word: that would change what the rule means.
    vocab = (set(lex["known"]) | set(lex["door_words"]) | lex["verb_words"] | ctx.name_words() | set(ctx.synonyms))
    for name in ctx.classes:
        vocab |= set(name.split())
    vocab = {word for word in vocab if len(word) >= 4}
    protected = set(lex["negations"]) | set(lex["intent"])
    fixes, pieces, position = [], [], 0
    for found in re.finditer(r"[A-Za-z]{5,}", text):
        word = found.group().lower()
        if word in vocab or word in protected or singular(word) in vocab:
            continue
        limit = 2 if len(word) >= 8 else 1
        candidates = {known for known in vocab if abs(len(known) - len(word)) <= limit and _distance(word, known) <= limit}
        if len(candidates) == 1:
            replacement = next(iter(candidates))
            pieces += [text[position:found.start()], replacement]
            position = found.end()
            fixes.append((found.group(), replacement))
    pieces.append(text[position:])
    return "".join(pieces), fixes
