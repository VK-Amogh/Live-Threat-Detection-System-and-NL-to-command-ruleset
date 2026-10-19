"""Compiler behaviour for person-object and door phrasings, and the coverage invariant. The language model is stubbed:
every case here must be decided by the deterministic parser or the invariant, never by a model."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "contracts/src"), str(ROOT / "services")]
from rules.compiler import RuleCompiler
from rules.registry import CapabilityRegistry

CLASSES = {"person", "chair", "backpack", "car", "laptop", "couch"}


class Llm:
    def __init__(self, conditions=None, entity="person", unsupported=None):
        self.answer = {"name": "rule", "entity": entity, "conditions": conditions or [], "join": "all", "unsupported_reason": unsupported}
        self.calls = 0

    def generate_json(self, system, user, schema):
        self.calls += 1
        return self.answer


def compiler(*, zones=(), lines=(), anchors=None, llm=None, geometry=None):
    registry = CapabilityRegistry(ROOT, CLASSES, set(zones), set(lines), False, anchors=anchors)
    return RuleCompiler(registry, llm or Llm(), geometry)


ONE_CHAIR = {"chair_window": {"cls": "chair", "bbox": [1, 1, 5, 5], "label": "chair by the window"}}
TWO_CHAIRS = {**ONE_CHAIR, "chair_door": {"cls": "chair", "bbox": [6, 1, 9, 5], "label": "chair by the door"}}


def test_sits_on_the_chair_is_never_reduced_to_presence():
    llm = Llm([{"type": "entity_present"}])                        # the old failure: a model answer that dropped the clause
    result = compiler(llm=llm).compile("if someone sits on the chair", "cam")
    assert result.support_level == "UNSUPPORTED" and result.needs_setup
    assert "chair" in result.needs_setup[0] and result.spec.feasibility == "NEEDS_SETUP"
    assert llm.calls == 0


def test_sitting_on_a_confirmed_chair_compiles_with_pose_evidence(tmp_path):
    result = compiler(anchors=ONE_CHAIR).compile("if someone sits on the chair", "cam")
    spec = result.spec
    leaf = list(spec.when.leaves())[0]
    assert leaf.type == "sits_on" and leaf.object.anchor == "chair_window"
    assert spec.entity == "person" and spec.schema_version == 2
    assert spec.verification.method == "pose" and spec.verification.vlm_question is None      # no uncalibrated model veto by default
    assert spec.verification.on_unverifiable == "hold_for_review"
    assert spec.feasibility == "POSE" and spec.reliability == "MEDIUM" and "pose" in spec.cost.stages
    if (ROOT / "weights/yolo26n-pose.pt").exists():
        assert result.support_level == "EXPERIMENTAL" and "hidden hand or hips" in result.readback and "never a guess" in result.readback
    else:
        # pose weights are not installed in this checkout: the rule cannot activate yet, and says what to do
        assert result.support_level == "UNSUPPORTED" and result.readback is None
        assert any("fetch_pose_weights" in item for item in result.needs_setup)


def test_which_chair_is_asked_when_it_is_ambiguous():
    result = compiler(anchors=TWO_CHAIRS).compile("alert when a person sits on the chair", "cam")
    assert result.needs_setup and "Which chair" in result.needs_setup[0]
    picked = compiler(anchors=TWO_CHAIRS).compile("alert when a person sits on the chair by the window", "cam")
    assert list(picked.spec.when.leaves())[0].object.anchor == "chair_window"
    anyone = compiler(anchors=TWO_CHAIRS).compile("alert when a person sits on any chair", "cam")
    assert list(anyone.spec.when.leaves())[0].object.cls == "chair"


def test_door_needs_to_be_drawn_and_enters_means_side_a_to_b():
    missing = compiler().compile("if someone enters the door", "cam")
    assert missing.needs_setup and "Draw the door" in missing.needs_setup[0]
    result = compiler(lines={"front_door"}).compile("if someone enters through the front door", "cam")
    leaf = list(result.spec.when.leaves())[0]
    assert (leaf.type, leaf.line, leaf.direction) == ("line_cross", "front_door", "a_to_b")
    assert result.support_level == "SUPPORTED" and result.spec.verification.method == "geometry"
    leaving = compiler(lines={"front_door"}).compile("alert when a person leaves through the front door", "cam")
    assert list(leaving.spec.when.leaves())[0].direction == "b_to_a"
    assert "from side A to side B" in result.readback


def test_door_readback_uses_the_labels_drawn_on_the_line():
    geometry = {"line_sides": {"front_door": {"a": "corridor", "b": "room"}}}
    result = compiler(lines={"front_door"}, geometry=geometry).compile("if someone enters the front door", "cam")
    assert "from corridor to room" in result.readback


def test_enter_then_sit_is_an_ordered_sequence():
    result = compiler(lines={"front_door"}, anchors=ONE_CHAIR).compile("when someone enters the front door and then sits on the chair within 90 seconds", "cam")
    sequence = result.spec.when
    assert [leaf.type for leaf in sequence.sequence] == ["line_cross", "sits_on"] and sequence.within_s == 90


def test_object_missing_and_pick_up_need_a_specific_confirmed_object():
    bag = {"bag": {"cls": "backpack", "bbox": [1, 1, 5, 5], "label": "my bag"}}
    gone = compiler(anchors=bag).compile("alert when the backpack goes missing for 10 seconds", "cam")
    leaf = list(gone.spec.when.leaves())[0]
    assert leaf.type == "object_absent" and leaf.seconds == 10 and gone.support_level == "SUPPORTED" and gone.spec.min_hold_s == 0
    assert compiler().compile("alert when the backpack goes missing", "cam").needs_setup
    anyone = compiler(anchors=bag).compile("alert when someone picks up a backpack", "cam")
    assert anyone.needs_setup or anyone.support_level == "UNSUPPORTED"      # "any bag disappears" is not a meaningful rule


def test_intent_words_are_refused_with_a_useful_alternative():
    steal = compiler().compile("alert when someone steals the bag", "cam")
    assert steal.support_level == "UNSUPPORTED" and "picks up the bag and leaves" in steal.problems[0]
    assert "Authorization" in compiler().compile("alert when an unauthorized person enters", "cam").problems[0]


def test_the_invariant_rejects_a_model_answer_that_ignores_words():
    ignoring = Llm([{"type": "in_zone", "zone": "porch"}])
    result = compiler(zones={"porch"}, llm=ignoring).compile("alert when a person dances in the porch", "cam")
    assert result.support_level == "UNSUPPORTED" and "'dances'" in result.problems[0]
    honest = Llm([{"type": "in_zone", "zone": "porch"}])
    assert compiler(zones={"porch"}, llm=honest).compile("alert when a person is in the porch", "cam").support_level == "SUPPORTED"
    verb = Llm([{"type": "entity_present"}])
    assert compiler(llm=verb).compile("alert when a person touches the laptop", "cam").support_level == "UNSUPPORTED"


def test_existing_phrasings_still_reach_the_model_path():
    llm = Llm([{"type": "in_zone", "zone": "driveway"}, {"type": "dwell_at_least", "seconds": 3}])
    text = "Alert me when a person stays in the driveway for 3 seconds"
    result = compiler(zones={"driveway"}, llm=llm).compile(text, "cam")
    assert llm.calls == 1 and result.support_level == "SUPPORTED"
    assert result.spec.schema_version == 1 and result.spec.verification is None


def test_a_dropped_zone_negation_or_time_window_is_caught():
    """The failures the real model produced with thinking off (measured 2026-10-17): the zone, the negation, the time window."""
    zone_dropped = compiler(zones={"porch"}, llm=Llm([{"type": "entity_present"}])).compile("alert when a person is in the porch", "cam")
    assert zone_dropped.support_level == "UNSUPPORTED" and "'porch' (the zone is mentioned but no condition uses it)" in zone_dropped.problems[0]
    # "no person is visible" is unambiguous, so a model answer without the negation is repaired into an absence rule ...
    repaired = compiler(llm=Llm([{"type": "entity_present"}])).compile("alert when no person is visible", "cam")
    assert repaired.support_level == "SUPPORTED" and repaired.spec.when.all[0].not_.type == "entity_present"
    # ... but a negation the compiler cannot place is refused, never ignored.
    negation_dropped = compiler(zones={"porch"}, llm=Llm([{"type": "in_zone", "zone": "porch"}])).compile("alert when nobody is in the porch", "cam")
    assert negation_dropped.support_level == "UNSUPPORTED" and "'nobody' (a negation needs a 'not' condition)" in negation_dropped.problems[0]
    kept = compiler(llm=Llm([{"type": "entity_present", "negated": True}])).compile("alert when no person is visible", "cam")
    assert kept.support_level == "SUPPORTED"
    # a missing line the text names is filled in; an empty time window the model invented is ignored
    filled = compiler(lines={"gate"}, llm=Llm([{"type": "line_cross"}, {"type": "time_window"}])).compile("alert when a person crosses the gate", "cam")
    assert filled.support_level == "SUPPORTED" and [leaf.line for leaf in filled.spec.when.leaves()] == ["gate"]
    time_dropped = compiler(zones={"porch"}, llm=Llm([{"type": "in_zone", "zone": "porch"}])).compile("alert when a person is in the porch between 20:00 and 22:00", "cam")
    assert time_dropped.support_level == "UNSUPPORTED" and "clock time" in time_dropped.problems[0]
    count_dropped = compiler(lines={"gate"}, llm=Llm([{"type": "line_cross", "line": "gate"}])).compile("alert if at least four people cross gate within 60 seconds", "cam")
    assert count_dropped.support_level == "UNSUPPORTED" and "'at least'" in count_dropped.problems[0]


def test_the_door_is_never_bound_to_a_line_with_a_different_name():
    result = compiler(lines={"gate"}).compile("if someone enters the door", "cam")
    assert result.support_level == "UNSUPPORTED" and "None of the drawn door-like shapes (gate)" in result.needs_setup[0]
    two = compiler(lines={"front_door", "back_door"}).compile("if someone enters the door", "cam")
    assert "Which door" in two.needs_setup[0]
    named = compiler(lines={"front_door", "back_door"}).compile("if someone enters the back door", "cam")
    assert list(named.spec.when.leaves())[0].line == "back_door"


def test_a_refused_model_answer_gets_one_corrective_retry_with_the_reason():
    class Flaky(Llm):
        def generate_json(self, system, user, schema):
            self.calls += 1
            self.last_user = user
            weak = [{"type": "entity_present"}]
            good = [{"type": "in_zone", "zone": "porch"}]
            self.answer = {**self.answer, "conditions": good if "previous answer was refused" in user else weak}
            return self.answer

    llm = Flaky()
    result = compiler(zones={"porch"}, llm=llm).compile("alert when a person is in the porch", "cam")
    assert result.support_level == "SUPPORTED" and llm.calls == 2
    assert "'porch' (the zone is mentioned but no condition uses it)" in llm.last_user
    stubborn = Llm([{"type": "entity_present"}])
    assert compiler(zones={"porch"}, llm=stubborn).compile("alert when a person is in the porch", "cam").support_level == "UNSUPPORTED"
    assert stubborn.calls == 2                                           # one retry, then the refusal stands


def test_everyday_phrasing_for_entering_a_room_through_a_drawn_door():
    for who in ("the user", "someone", "a visitor", "a person"):
        result = compiler(lines={"front_door"}).compile(f"when {who} enters the room from the door", "cam")
        leaf = list(result.spec.when.leaves())[0]
        assert result.support_level == "SUPPORTED" and result.spec.entity == "person", (who, result.problems)
        assert (leaf.type, leaf.line, leaf.direction) == ("line_cross", "front_door", "a_to_b")
    nothing_drawn = compiler().compile("when the user enters the room from the door", "cam")
    assert nothing_drawn.needs_setup and "Crossing line or door" in nothing_drawn.needs_setup[0]
    # "room" is only understood next to a crossing; elsewhere it is an unknown place and the rule is refused
    elsewhere = compiler(llm=Llm([{"type": "entity_present"}])).compile("alert when a person is in the room", "cam")
    assert elsewhere.support_level == "UNSUPPORTED" and "'room'" in elsewhere.problems[0]


DOOR_ZONE = {"zone_roles": {"door": "door"}}


def test_typos_are_read_charitably_and_reported():
    llm = Llm()
    door = compiler(zones={"door"}, geometry=DOOR_ZONE, llm=llm)
    result = door.compile("alert me when the person entres throught the door", "cam")
    leaf = list(result.spec.when.leaves())[0]
    assert result.support_level == "SUPPORTED" and (leaf.type, leaf.zone) == ("enters_zone", "door") and llm.calls == 0
    assert "Read 'entres' as 'enters', 'throught' as 'through'." in result.readback
    assert result.spec.name.startswith("alert me when the person enters through the door")


def test_user_and_room_are_understood_and_a_door_zone_is_not_oversold():
    result = compiler(zones={"door"}, geometry=DOOR_ZONE).compile("when the user enters the room from the door", "cam")
    assert result.support_level == "SUPPORTED" and result.spec.entity == "person"
    assert "appears in the doorway" in result.readback and "walking past the door does neither" in result.readback


def test_unknown_words_are_not_guessed_into_known_ones():
    from rules import grammar
    context = grammar.Context(CLASSES, {"porch"}, {"gate"}, {}, {"someone": "person"}, {})
    text, fixes = grammar.correct_typos("alert when a person dances near the drone in the porch", context)
    assert fixes == [] and text == "alert when a person dances near the drone in the porch"
    assert grammar.correct_typos("a persn sitts on the chiar", context)[1] == [("persn", "person"), ("sitts", "sits"), ("chiar", "chair")]
    assert grammar.correct_typos("somthing entres", context)[1] == [("entres", "enters")]      # one edit away from exactly one known word
    assert grammar._distance("entres", "enters") == 1 and grammar._distance("entres", "metres") == 2
    refused = compiler(zones={"porch"}, llm=Llm([{"type": "in_zone", "zone": "porch"}])).compile("alert when a person dances in the porch", "cam")
    assert refused.support_level == "UNSUPPORTED" and "'dances'" in refused.problems[0]


def test_a_word_one_edit_from_two_known_words_is_not_guessed():
    from rules import grammar
    context = grammar.Context(CLASSES, set(), set(), {}, {}, {})
    assert grammar.correct_typos("a cheir", context)[1] == []          # "cheir" is one edit from both "chair" and "their"


def test_a_typo_is_never_repaired_into_a_negation_or_intent_word():
    from rules import grammar
    context = grammar.Context(CLASSES, set(), set(), {}, {}, {})
    assert grammar.correct_typos("alert when somthing happens", context)[1] == []     # "nothing" is one edit away, and is a negation
    assert grammar.correct_typos("alert withot a person", context)[1] == []           # "without"
    assert grammar.correct_typos("alert when someone stels it", context)[1] == []     # "steals" is an intent word


def test_opening_the_door_needs_the_door_drawn_as_a_zone():
    zone = compiler(zones={"door"}, geometry={"zone_roles": {"door": "door"}}).compile("alert me when someone opens the door", "cam")
    leaf = list(zone.spec.when.leaves())[0]
    assert (leaf.type, leaf.zone) == ("zone_changes", "door") and zone.support_level == "EXPERIMENTAL" and zone.can_activate
    assert zone.spec.min_hold_s == 0.4 and zone.spec.entity == "person" and "people masked out" in zone.readback and zone.readback.startswith("Alert when the picture inside door changes")
    line_only = compiler(lines={"front_door"}).compile("alert me when someone opens the door", "cam")
    assert line_only.needs_setup and "draw the door itself as a zone" in line_only.needs_setup[0]
    assert compiler().compile("alert me when the door opens", "cam").needs_setup


def test_the_three_demo_sentences_compile_on_a_door_zone():
    door = compiler(zones={"door"}, geometry={"zone_roles": {"door": "door"}}, llm=Llm())
    for text, kind in (("alert me when a person comes in through the door", None), ("when someone enters through the door", "enters_zone"),
                       ("when a person sits on a chair", "sits_on"), ("alert when someone opens the door", "zone_changes")):
        result = door.compile(text, "cam")
        if kind:
            assert list(result.spec.when.leaves())[0].type == kind and result.can_activate, (text, result.problems)
