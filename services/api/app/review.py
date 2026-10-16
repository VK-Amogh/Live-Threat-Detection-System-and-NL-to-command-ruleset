"""AI second opinion on an incident: a vision-language model looks at the evidence and says whether it agrees.

The detector stack (YOLO -> DINOv2 verifier -> thresholds) decides whether an incident is raised. This optional step asks an
open-weights VLM (local Gemma 4 through Ollama, or Qwen on Groq when selected) to look at the annotated keyframe(s) and judge
whether they visibly support the claim. It never confirms or dismisses an incident (the human decision stays final, D-008): it
records its reasoning and sets `ai_disagrees` so the operator can prioritise.
"""
import asyncio
import json
import os
import re

import httpx

from . import database as db
from .chat import annotated_keyframe, ollama_runtime, read_detections, sample_clip_frames, settings
from .security import now
from .settings import OLLAMA_URL

SLOT = asyncio.Semaphore(1)
PENDING = set()

PROMPT = '''You are a careful CCTV incident reviewer. An automated detector reports: {category} (detector classes: {classes}; confidence {confidence:.0%}; source type: {source}).
The first image is the evidence frame; red boxes mark what the detector flagged. {extra}
Decide whether the images visibly support the detector's claim. Reply with JSON only:
{{"supports_detection": true | false | null, "confidence": <0..1>, "visible_facts": ["<short fact>", ...], "cannot_determine": ["<short item>", ...], "explanation": "<at most 25 words>"}}
Use null when the evidence is too small, blurry or ambiguous. Describe only what is visible; never infer identity, intent or protected attributes. Common false alarms: fog/haze/steam/shadows for smoke, musical instruments/bottles/tools/phones for weapons, sport or dancing for violence.'''


def detector_classes(event):
    detections = read_detections(event['id']) or {}
    return sorted({d['class_name'] for d in detections.get('detections', [])})


async def ask_model(prompt, images):
    config = settings()
    provider = config['chat_provider']
    if provider == 'groq' and not os.getenv('GROQ_API_KEY'):
        provider = 'ollama'
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
        if provider == 'groq':
            body = {'model': config['groq_model'], 'temperature': 0, 'max_completion_tokens': 400, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}] + [{'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + b}} for b in images[:1]]}]}
            response = await client.post('https://api.groq.com/openai/v1/chat/completions', headers={'Authorization': f"Bearer {os.getenv('GROQ_API_KEY')}"}, json=body)
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content'], config['groq_model'], 'groq'
        body = {'model': config['ollama_model'], 'stream': False, 'think': False, 'keep_alive': '30m', 'messages': [{'role': 'user', 'content': prompt, 'images': images[:3]}],
                'options': {**ollama_runtime(), 'temperature': 0, 'num_predict': 300}}
        response = await client.post(f'{OLLAMA_URL}/api/chat', json=body)
        response.raise_for_status()
        return response.json()['message']['content'], config['ollama_model'], 'ollama'


def parse(text):
    match = re.search(r'\{.*\}', text, re.S)
    if not match:
        raise ValueError('Model did not return JSON')
    data = json.loads(match.group(0))
    supports = data.get('supports_detection')
    return {'supports': supports if isinstance(supports, bool) else None, 'confidence': max(0.0, min(1.0, float(data.get('confidence') or 0))),
            'facts': [str(x)[:160] for x in (data.get('visible_facts') or [])][:6], 'unknown': [str(x)[:160] for x in (data.get('cannot_determine') or [])][:6],
            'explanation': str(data.get('explanation') or '')[:240]}


async def review(event_id, publish=None):
    """Run (or re-run) the second opinion for one incident and store it on the event. Returns the updated event."""
    event = db.get('event', event_id)
    if not event:
        return None
    images = await asyncio.to_thread(lambda: [x for x in [annotated_keyframe(event)] if x] + sample_clip_frames(event, 2))
    if not images:
        return event
    sources = {s['id']: s for s in db.all_objects('source')}
    source = sources.get(event.get('_source_id') or '')
    prompt = PROMPT.format(category=event['category']['label'], classes=', '.join(detector_classes(event)) or 'n/a', confidence=event['peak_confidence'], source=(source or {}).get('kind', 'unknown'),
                           extra='Further frames from the same clip follow.' if len(images) > 1 else '')
    async with SLOT:
        text, model, provider = await ask_model(prompt, images)
    result = parse(text)
    event = db.get('event', event_id) or event
    event['reasoning'] = {'confidence': result['confidence'], 'uncertainty': result['explanation'] or 'No explanation returned.', 'evidence_insufficient': result['supports'] is None,
                          'visible_facts': result['facts'], 'cannot_determine': result['unknown']}
    event['ai_disagrees'] = result['supports'] is False and result['confidence'] >= 0.6
    event['models'] = {**(event.get('models') or {}), 'vlm': {'name': model, 'version': provider}}
    if event['ai_disagrees'] and event['status'] == 'NEEDS_REVIEW':
        event['status_reason'] = 'AI second opinion disagrees with the detector; operator review required'
    event['updated_at'] = now()
    db.save_event(event)
    if publish:
        from td_contracts import EventOut
        await publish('event.updated', {'event': EventOut.model_validate(event).model_dump(mode='json', by_alias=True)})
    return event


async def auto_review(event_id, publish=None):
    """Background hook: at most one review per incident, bounded queue, failures are silent (the operator can retry)."""
    if event_id in PENDING or len(PENDING) >= 6:
        return
    PENDING.add(event_id)
    try:
        await review(event_id, publish)
    except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError):
        pass
    finally:
        PENDING.discard(event_id)
