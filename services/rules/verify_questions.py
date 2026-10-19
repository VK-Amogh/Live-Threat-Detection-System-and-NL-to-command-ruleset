"""Forced-choice visual questions for rule candidates, and the evidence images they refer to.

This module only builds prompts and decodes answers; it never talks to a model, so the API process (which owns every
Ollama call) and tests can both use it. Principles: the model chooses one lettered statement or says it cannot tell;
only the positive letter verifies; anything unparseable is "abstain"; geometry (crossing, dwell, zone membership) is never
asked because deterministic code already decided it."""

import base64
import json
import random
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

SUBJECT_COLOR = (0, 200, 0)      # BGR green: the person
OBJECT_COLOR = (255, 120, 0)     # BGR blue: the marked object
MAX_IMAGE_WIDTH = 640


@dataclass(frozen=True)
class Question:
    stem: str
    positive: str
    negatives: tuple[str, ...]
    abstain: str = "I cannot tell from these images."


QUESTIONS: dict[str, Question] = {
    "sits_on": Question(
        "Which statement is directly visible in the LAST image? The green box marks a person; the blue box marks the seat '{label}'.",
        "The person in the green box is sitting on the seat in the blue box.",
        ("The person is standing or walking near the seat.", "The person is sitting on a different seat or surface.")),
    "touches_object": Question(
        "Which statement is directly visible in the LAST image? The green box marks a person; the blue box marks '{label}'.",
        "The person's hand is touching the object in the blue box.",
        ("The person's hands are not touching the object.", "The person is leaning on or near the object without a hand on it.")),
    "picks_up": Question(
        "The images are in time order. The green box marks a person; the blue box marks where '{label}' was.",
        "The person picked up the object from the blue box and the place is now empty.",
        ("The object is still in the blue box.", "The place is empty but the person did not take the object.")),
}


@dataclass(frozen=True)
class Rendered:
    prompt: str
    schema: dict
    letters: dict[str, str]          # letter -> "positive" | "negative" | "abstain"
    order: tuple[str, ...]

    def decode(self, output: dict) -> str:
        """'positive', 'negative' or 'abstain'. Anything that is not exactly one valid letter is a ValueError."""
        letter = str(output.get("answer", "")).strip().upper()
        if letter not in self.letters:
            raise ValueError(f"unusable answer {letter!r}")
        return self.letters[letter]


def render(question_id: str, label: str, seed: int) -> Rendered:
    question = QUESTIONS[question_id]
    options = [("positive", question.positive), *[("negative", text) for text in question.negatives]]
    random.Random(seed).shuffle(options)                  # position bias is cancelled by shuffling and recorded by `order`
    options.append(("abstain", question.abstain))
    letters = {chr(ord("A") + index): kind for index, (kind, _) in enumerate(options)}
    lines = "\n".join(f"({letter}) {text}" for letter, (_, text) in zip(letters, options))
    prompt = (f"{question.stem.format(label=label)}\n{lines}\n"
              "Choose one letter. Describe only what is visible; do not guess intent. "
              'Reply as JSON: {"answer": "<letter>", "visible_evidence": ["<short fact>", ...]}')
    schema = {"type": "object", "properties": {"answer": {"type": "string", "enum": list(letters)},
                                               "visible_evidence": {"type": "array", "items": {"type": "string"}, "maxItems": 4}},
              "required": ["answer", "visible_evidence"]}
    return Rendered(prompt, schema, letters, tuple(kind for kind, _ in options))


def _draw(frame, box, color):
    if box is not None:
        x1, y1, x2, y2 = (round(v) for v in box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)


def _encode(frame) -> bytes:
    height, width = frame.shape[:2]
    if width > MAX_IMAGE_WIDTH:
        frame = cv2.resize(frame, (MAX_IMAGE_WIDTH, max(1, round(height * MAX_IMAGE_WIDTH / width))))
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise ValueError("evidence frame cannot be encoded")
    return jpeg.tobytes()


def load_pack(folder: Path, object_box=None) -> list[bytes]:
    """Up to three images from the fire-time evidence pack: the earliest frame, the last frame (both whole, with the
    subject box drawn on its own frame, and the marked object in blue) and a close-up of the subject in the last frame.

    Each frame uses its own subject box, so a person who moved between frames is still the one inside the green box."""
    index = json.loads((folder / "pack.json").read_text(encoding="utf-8"))["frames"]
    decoded = []
    for item in index:
        frame = cv2.imdecode(np.frombuffer((folder / item["file"]).read_bytes(), dtype="uint8"), cv2.IMREAD_COLOR)
        if frame is not None:
            decoded.append((frame, item.get("bbox")))
    if not decoded:
        return []
    chosen = [decoded[0], decoded[-1]] if len(decoded) > 1 else [decoded[0]]
    images = []
    for frame, box in chosen:
        annotated = frame.copy()
        _draw(annotated, object_box, OBJECT_COLOR)
        _draw(annotated, box, SUBJECT_COLOR)
        images.append(_encode(annotated))
    frame, box = decoded[-1]
    if box is not None:
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = box
        margin = max(40, round(max(x2 - x1, y2 - y1) * 0.5))
        if object_box is not None:
            x1, y1, x2, y2 = min(x1, object_box[0]), min(y1, object_box[1]), max(x2, object_box[2]), max(y2, object_box[3])
        crop = frame[max(0, round(y1 - margin)):min(height, round(y2 + margin)), max(0, round(x1 - margin)):min(width, round(x2 + margin))].copy()
        if crop.size:
            images.append(_encode(crop))
    return images


def to_base64(images: list[bytes]) -> list[str]:
    return [base64.b64encode(image).decode("ascii") for image in images]
