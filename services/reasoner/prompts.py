"""Conservative visual-review prompt and output validation."""

import re

from td_contracts import ReviewResult


SYSTEM = (
    "You review selected frames from a security camera after a detector flagged a rule. "
    "Describe only directly visible people, objects, positions, and movement. "
    "Do not infer intent, identity, ownership, relationships, crimes, or actions hidden between frames. "
    "Do not label the setting as indoor, outdoor, a home, business, or street. "
    "Do not name an object unless clearly visible; put uncertainty in the uncertainty field. "
    "Use simple statements such as 'People and tables are visible' rather than guesses. "
    "Do not claim that the rule is true. State what cannot be seen or is unclear. "
    "Output JSON matching the schema only."
)

UNSAFE_VISIBLE = re.compile(
    r"\b(?:trying to|intends? to|wants? to|planning to|about to|steal(?:ing)?|"
    r"thief|criminal|suspect|owner|employee|trespass(?:ing|er)?|"
    r"scratch(?:es|ing|ed)?|assault(?:ing|ed)?|fight(?:ing|s)?|"
    r"identif(?:y|ied)|recogniz(?:e|ed)|suspicious|indoors?|outdoors?|"
    r"possibly|perhaps|maybe|likely|seems?|appears?|resembling)\b", re.IGNORECASE
)


def validate_review(payload: dict) -> ReviewResult:
    result = ReviewResult.model_validate(payload)
    unsafe = UNSAFE_VISIBLE.search(result.visible_evidence)
    if unsafe:
        raise ValueError(f"Visual summary has an unsupported inference: {unsafe.group(0)}")
    return result
