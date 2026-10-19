"""Claim one persisted review at a time; detector and API never await Gemma."""

import os
from pathlib import Path
import time

import httpx
import psutil
import yaml
from dotenv import load_dotenv

from td_contracts import ReviewResult
from services.rules.llm import LocalLLM
from .frames import selected_frames
from .prompts import SYSTEM, validate_review


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def review_once(client: httpx.Client, api: str, token: str, llm: LocalLLM, media_root: Path) -> bool:
    headers = {"Authorization": f"Bearer {token}"}
    claim = client.post(api + "/api/v1/internal/review-jobs/claim", headers=headers)
    claim.raise_for_status()
    job = claim.json()["job"]
    if job is None:
        return False
    event = job["event"]
    ident = event["id"]
    lease = job["claim_token"]
    try:
        clip = media_root / ident / "clip.mp4"
        frames = selected_frames(clip, event.get("evidence_bbox"), media_root / ident)
        context = (
            f"Rule: {event['category']['label']}\n"
            f"Detector class and track IDs: {event['track_refs']}\n"
            f"Camera event time: {event['first_seen_at']} to {event['last_seen_at']}\n"
            "Describe only visible evidence in these sampled frames. Say what is unclear."
        )
        output = llm.describe(frames, SYSTEM, context, ReviewResult.model_json_schema())
        result = validate_review(output)
        response = client.post(
            api + f"/api/v1/internal/review-jobs/{ident}/complete",
            headers=headers,
            json={"claim_token": lease, "result": result.model_dump()},
        )
        response.raise_for_status()
    except (httpx.HTTPError, OSError, ValueError, KeyError, RuntimeError) as exc:
        # A failed model cannot leave an incident in VERIFYING or an endless retry loop.
        # This describes the detector report only; it makes no claim about unseen pixels.
        category = event.get('category', {}).get('label', 'an incident')
        camera = event.get('camera', {}).get('name', 'the camera')
        confidence = event.get('peak_confidence')
        score = f" ({float(confidence):.0%} confidence)" if confidence is not None else ''
        fallback = ReviewResult(
            visible_evidence=f'Detector reported {category} on {camera}{score}. Visual details were not available.',
            uncertainty='The model could not inspect the footage. Review the saved clip manually; the detection is unconfirmed.',
            possible_false_positive=True,
        )
        response = client.post(
            api + f"/api/v1/internal/review-jobs/{ident}/complete",
            headers=headers,
            json={"claim_token": lease, "result": fallback.model_dump()},
        )
        response.raise_for_status()
    return True


def main():
    token = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if not token:
        raise RuntimeError("INTERNAL_SERVICE_TOKEN is required")
    config = yaml.safe_load((ROOT / "config/rules.yaml").read_text(encoding="utf-8"))["llm"]
    llm = LocalLLM(
        config["base_url"],
        config["model"],
        min(float(config["timeout_s"]), 25.0),
        int(config.get("num_gpu", 99)),
        int(config.get("num_ctx", 6144)),
    )
    api = os.getenv("SAFESPACE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    if os.name == "nt":
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    with httpx.Client(timeout=15) as client:
        while True:
            try:
                worked = review_once(client, api, token, llm, ROOT / "storage/media")
            except httpx.HTTPError:
                worked = False
            time.sleep(.5 if worked else 3)


if __name__ == "__main__":
    main()
