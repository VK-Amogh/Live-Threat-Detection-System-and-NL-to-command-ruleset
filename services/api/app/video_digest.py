"""Chat digest of uploaded videos: "summarize the videos uploaded in the past hour".

The question is recognised and its time window read deterministically (no model involved). Every uploaded video in the window
gets key frames (an alert frame if the detector raised one, then the most different sharp frames), a plain-facts line (duration,
objects the detector counted in the key frames, threat alerts) and a short description written by the local Gemma model from
those frames. Frames, facts and descriptions are cached beside the upload, so asking again is instant. If the model is
unavailable the facts alone are shown and labelled as such; the chat always answers.

Stream events (in addition to the ones chat.py already sends): `digest` (the list, summaries pending) and `digest_item`
(one video updated with frames, then with its summary). The dashboard draws these as cards; the mobile app gets the same
videos through `cited`.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import re
import threading
import time
import uuid

import cv2
import httpx
import numpy as np
from fastapi import HTTPException

from . import database as db
from .llm_gateway import GATEWAY, P1_INTERACTIVE
from .settings import ROOT, STORAGE

LOG = logging.getLogger(__name__)
MAX_CAPTIONS = 40       # new AI descriptions per question (about 1.5 s each); cached ones are free, so asking again continues
MAX_VIDEOS = 30         # videos listed with key frames in one answer
KEYFRAMES = 4
POOL = 16               # evenly spaced frames the key frames are chosen from
THUMB_SIDE = 640
CAPTION_SIDE = 448
BUDGET_S = 240          # after this the remaining videos get facts only
DEFAULT_WINDOW_H = 24
CACHE_VERSION = 1

NUMBERS = {'a': 1, 'an': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
           'twelve': 12, 'couple of': 2, 'a couple of': 2, 'few': 3, 'a few': 3, 'half an': .5, 'half a': .5}
NUMBER = r'\d+(?:\.\d+)?|half an?|a couple of|couple of|a few|few|an?|one|two|three|four|five|six|seven|eight|nine|ten|twelve'
UNIT_SECONDS = {'minute': 60, 'hour': 3600, 'day': 86400, 'week': 604800}
SPAN = re.compile(rf'\b(?:past|last|previous|preceding)\s+(?:(?P<n>{NUMBER})\s+)?(?P<u>min(?:ute)?s?|hours?|hrs?|days?|weeks?)\b', re.I)
COUNT = re.compile(rf'\b(?:last|latest|newest|most recent|recent|previous|past)\s+(?P<n>\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?:uploaded\s+)?(?:videos?|uploads?|clips?|recordings?)\b', re.I)
LATEST_ONE = re.compile(r'\b(?:last|latest|newest|most recent)\s+(?:uploaded\s+)?(?:video|upload|clip)\b|\bjust uploaded\b|\bjust now\b', re.I)
NOUN = re.compile(r'\b(videos?|footage|clips?|uploads?|uploaded|recordings?)\b', re.I)
SUMMARISE = re.compile(r'\b(summari[sz]e|summary|summaries|recap|overview|digest|describe|what (?:was|were|is|did)|tell me about|show|list|give me)\b', re.I)
UPLOAD = re.compile(r'\b(upload|uploads|uploaded|added|received)\b', re.I)
ALL = re.compile(r'\b(all|every|each|everything|any)\b', re.I)
INCIDENT = re.compile(r'\b(incidents?|alerts?|events?|threats?|detections?|evt_[0-9a-f]+)\b', re.I)


@dataclass
class Window:
    start: datetime
    end: datetime
    label: str
    explicit: bool
    limit: int | None = None


def _number(text: str | None) -> float:
    if not text:
        return 1.0
    text = text.lower()
    return float(NUMBERS[text]) if text in NUMBERS else float(text)


def parse_window(message: str, now: datetime) -> Window:
    """The time span the question asks about; with no span, the last 24 hours."""
    count = COUNT.search(message)
    if count:
        n = int(_number(count.group('n')))
        return Window(datetime.fromtimestamp(0, timezone.utc), now, f'the last {n} uploaded videos', True, n)
    if LATEST_ONE.search(message):
        return Window(datetime.fromtimestamp(0, timezone.utc), now, 'the latest uploaded video', True, 1)
    span = SPAN.search(message)
    if span:
        unit = span.group('u').lower()
        name = 'minute' if unit.startswith('min') else 'hour' if unit.startswith('h') else 'day' if unit.startswith('d') else 'week'
        n = _number(span.group('n'))
        seconds = UNIT_SECONDS[name] * n
        if n != int(n):                                        # "half an hour" reads better as 30 minutes
            name, n = ('minute', round(seconds / 60)) if seconds < 86400 else ('hour', round(seconds / 3600))
        label = f'the past {name}' if n == 1 else f'the past {n:g} {name}s'
        return Window(now - timedelta(seconds=seconds), now, label, True)
    if re.search(r'\byesterday\b', message, re.I):
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return Window(midnight - timedelta(days=1), midnight, 'yesterday', True)
    if re.search(r'\btoday\b|\bthis (?:morning|afternoon|evening)\b', message, re.I):
        return Window(now.replace(hour=0, minute=0, second=0, microsecond=0), now, 'today', True)
    return Window(now - timedelta(hours=DEFAULT_WINDOW_H), now, f'the past {DEFAULT_WINDOW_H} hours', False)


def wants(message: str) -> bool:
    """True for questions about the uploaded videos as a group or by recency, not about one incident's footage."""
    if not NOUN.search(message):
        return False
    window = bool(SPAN.search(message) or COUNT.search(message) or LATEST_ONE.search(message)
                  or re.search(r'\b(today|yesterday|this (?:morning|afternoon|evening))\b', message, re.I))
    uploaded = bool(UPLOAD.search(message))
    broad = window or bool(ALL.search(message)) or uploaded
    if INCIDENT.search(message) and not uploaded:
        return False
    return bool((SUMMARISE.search(message) and broad) or (uploaded and (window or ALL.search(message))))


def stamp_of(source: dict) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(source.get('created_at')))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def uploaded_videos(window: Window) -> list[tuple[datetime, dict]]:
    rows = []
    for source in db.all_objects('source'):
        stamp = stamp_of(source)
        if source.get('kind') == 'video' and stamp and window.start <= stamp <= window.end:
            rows.append((stamp, source))
    rows.sort(key=lambda row: row[0], reverse=True)
    return rows[:window.limit] if window.limit else rows


def latest_upload() -> tuple[datetime, dict] | None:
    rows = [(stamp_of(s), s) for s in db.all_objects('source') if s.get('kind') == 'video' and stamp_of(s)]
    return max(rows, key=lambda row: row[0]) if rows else None


# ---------------------------------------------------------------------------------------------- time words

def clock(stamp: datetime, now: datetime) -> str:
    local = stamp.astimezone(now.tzinfo)
    text = local.strftime('%I:%M %p').lstrip('0')
    return text if local.date() == now.date() else local.strftime('%b %d, ') + text


def ago(stamp: datetime, now: datetime) -> str:
    seconds = max(0, (now - stamp).total_seconds())
    if seconds < 90:
        return 'just now'
    if seconds < 3600:
        return f'{round(seconds / 60)} min ago'
    if seconds < 86400:
        return f'{seconds / 3600:.1f} h ago'.replace('.0 h', ' h')
    return f'{round(seconds / 86400)} days ago'


def mmss(ms: float) -> str:
    if ms < 60000:
        return f'{ms / 1000:.1f} s'                            # clips are short: 0.4 s and 0.9 s must not both read 0:00
    seconds = int(round(ms / 1000))
    return f'{seconds // 60}:{seconds % 60:02d}'


def length(seconds: float | None) -> str:
    if not seconds:
        return 'length unknown'
    return f'{seconds:.0f} s' if seconds < 90 else f'{int(seconds // 60)} min {int(seconds % 60):02d} s'


# ---------------------------------------------------------------------------------------------- key frames

_YOLO = None
_YOLO_LOCK = threading.Lock()


def detector():
    """The same small COCO detector the rules use, on CPU (the GPU belongs to the chat model)."""
    global _YOLO
    if _YOLO is None:
        import yaml
        from ultralytics import YOLO
        config = yaml.safe_load((ROOT / 'config/rules.yaml').read_text(encoding='utf-8'))
        _YOLO = YOLO(str(ROOT / config['detector']['weights']))
    return _YOLO


def count_objects(frames: list) -> dict[str, int]:
    """Most of each class seen in any single key frame (people and objects, not threats)."""
    try:
        best: dict[str, int] = {}
        with _YOLO_LOCK:
            results = detector().predict(frames, conf=.4, imgsz=640, device='cpu', verbose=False)
        for result in results:
            seen: dict[str, int] = {}
            for cls in result.boxes.cls.tolist():
                name = result.names[int(cls)]
                seen[name] = seen.get(name, 0) + 1
            for name, n in seen.items():
                best[name] = max(best.get(name, 0), n)
        return dict(sorted(best.items(), key=lambda item: -item[1])[:6])
    except Exception as exc:                                  # noqa: BLE001 - facts are optional, the digest must still work
        LOG.warning('Object counting for the video digest failed: %s', exc)
        return {}


def playable(folder):
    path = folder / 'playback.mp4'
    return path if path.is_file() else next(iter(sorted(folder.glob('original.*'))), None)


def histogram(frame) -> np.ndarray:
    small = cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA)
    hist = cv2.calcHist([small], [0, 1, 2], None, [4, 4, 4], [0, 256] * 3).flatten()
    return hist / max(hist.sum(), 1)


def choose(candidates: list[dict], count: int) -> list[dict]:
    """An alert frame first, then repeatedly the sharp frame least like those already chosen."""
    if not candidates:
        return []
    bright = [c for c in candidates if c['bright'] >= 12] or candidates
    top_sharp = max(c['sharp'] for c in bright) or 1.0
    first = next((i for i, c in enumerate(bright) if c['event']), None)
    chosen = [first if first is not None else max(range(len(bright)), key=lambda i: bright[i]['sharp'])]
    while len(chosen) < min(count, len(bright)):
        best, best_score = None, 0.0
        for i, c in enumerate(bright):
            if i in chosen:
                continue
            distance = min(float(np.abs(c['hist'] - bright[k]['hist']).sum()) / 2 for k in chosen)
            score = distance * (.5 + .5 * c['sharp'] / top_sharp)
            if score > best_score:
                best, best_score = i, score
        if best is None or best_score < .01:
            break
        chosen.append(best)
    # a still scene has no "different" frames: spread the rest over time so the summary still covers the whole video
    for fraction in (.15, .5, .85, .3, .7):
        if len(chosen) >= min(3, len(bright)):
            break
        left = [i for i in range(len(bright)) if i not in chosen]
        if left:
            chosen.append(min(left, key=lambda i: abs(bright[i]['t_ms'] - fraction * bright[-1]['t_ms'])))
    return [bright[i] for i in sorted(chosen, key=lambda i: bright[i]['t_ms'])]


def prepare_frames(source_id: str, alert_ms: list[int]) -> dict:
    """Key frames for one upload: {'duration_s', 'frames': [{'n', 't_ms', 'alert'}], 'objects'}; cached beside the upload."""
    folder = STORAGE / 'uploads' / source_id
    meta_path = folder / 'keyframes.json'
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('version') == CACHE_VERSION and all((folder / 'keyframes' / f"{f['n']}.jpg").is_file() for f in meta['frames']):
            return meta
    except (OSError, ValueError, KeyError):
        pass
    meta = {'version': CACHE_VERSION, 'duration_s': None, 'frames': [], 'objects': {}}
    path = playable(folder) if folder.is_dir() else None
    cap = cv2.VideoCapture(str(path)) if path else None
    if cap is None or not cap.isOpened():
        return meta
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            return meta
        meta['duration_s'] = round(total / fps, 1)
        indices = {int(total * (i + .5) / POOL) for i in range(POOL)}
        alert_at = {min(total - 1, max(0, int(ms / 1000 * fps))) for ms in alert_ms[:4]}
        candidates = []
        for index in sorted(indices | alert_at):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
            candidates.append({'frame': frame, 't_ms': round(index / fps * 1000), 'hist': histogram(frame), 'sharp': float(cv2.Laplacian(gray, cv2.CV_64F).var()),
                               'bright': float(gray.mean()), 'event': index in alert_at})
        picked = choose(candidates, KEYFRAMES)
        out = folder / 'keyframes'
        out.mkdir(exist_ok=True)
        for n, c in enumerate(picked, 1):
            frame = c['frame']
            h, w = frame.shape[:2]
            scale = THUMB_SIDE / max(h, w)
            small = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else frame
            cv2.imwrite(str(out / f'{n}.jpg'), small, [cv2.IMWRITE_JPEG_QUALITY, 82])
            meta['frames'].append({'n': n, 't_ms': c['t_ms'], 'alert': c['event']})
        meta['objects'] = count_objects([c['frame'] for c in picked])
        meta_path.write_text(json.dumps(meta), encoding='utf-8')
    finally:
        cap.release()
    return meta


def caption_images(source_id: str, meta: dict) -> list[str]:
    images = []
    for frame in meta['frames']:
        image = cv2.imread(str(STORAGE / 'uploads' / source_id / 'keyframes' / f"{frame['n']}.jpg"))
        if image is None:
            continue
        h, w = image.shape[:2]
        scale = CAPTION_SIDE / max(h, w)
        if scale < 1:
            image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        images.append(base64.b64encode(cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()).decode())
    return images


# ---------------------------------------------------------------------------------------------- facts and words

def alerts_of(source: dict) -> list[dict]:
    out = []
    for ident in source.get('event_ids') or []:
        event = db.get('event', ident)
        if event:
            out.append({'id': ident, 'label': event['category']['label'], 'status': event.get('status'), 'severity': event.get('severity'),
                        'confidence': round(float(event.get('peak_confidence') or 0), 3), 't_ms': int(event.get('media_offset_ms') or 0)})
    return out


def facts_line(meta: dict, alerts: list[dict]) -> str:
    objects = ', '.join(f'{name} x{n}' for name, n in (meta.get('objects') or {}).items())
    threat = ('; '.join(f"{a['label']} at {mmss(a['t_ms'])} ({a['confidence']:.0%}, {str(a['status'] or '').replace('_', ' ').lower()})" for a in alerts[:3])
              if alerts else 'no threat alerts')
    return f"Objects the detector counted in the key frames: {objects or 'none found'}. Threat detector: {threat}."


CAPTION_SYSTEM = ('You describe key frames taken from one video from a home or office security camera or phone. Use only what is visible. '
                  'Say who or what is there, what they do and where, and how the scene changes between frames. Do not identify anyone, do not guess '
                  'intent, mood or anything you cannot see, and do not repeat the timestamps. Reply with two or three plain sentences and no list.')


def caption_prompt(frames: list[dict], meta: dict, alerts: list[dict]) -> str:
    times = ', '.join(f"image {i} at {mmss(f['t_ms'])}" for i, f in enumerate(frames, 1))
    text = f'The images are key frames of one {length(meta.get("duration_s"))} video, in time order: {times}.\n{facts_line(meta, alerts)}\n'
    return text + 'The counts are hints from a small detector and can be wrong. Describe what happens in the video.'


def clean(text: str) -> str:
    text = re.sub(r'[*_#`]+', '', text or '').strip()
    return re.sub(r'\s+', ' ', text)


async def describe(source_id: str, meta: dict, alerts: list[dict], model_name: str) -> str | None:
    """The model's description of the key frames, cached; None when the model could not be used."""
    path = STORAGE / 'uploads' / source_id / 'digest.json'
    try:
        saved = json.loads(path.read_text(encoding='utf-8'))
        if saved.get('version') == CACHE_VERSION and saved.get('model') == model_name and saved.get('caption') and saved.get('frames') == [f['t_ms'] for f in meta['frames']]:
            return saved['caption']
    except (OSError, ValueError):
        pass
    images = await asyncio.to_thread(caption_images, source_id, meta)
    if not images:
        return None
    frames = meta['frames']
    while images:
        try:
            text = clean(await GATEWAY.describe(images, CAPTION_SYSTEM, caption_prompt(frames[:len(images)], meta, alerts), priority=P1_INTERACTIVE, model=model_name, timeout_s=75))
        except httpx.HTTPStatusError as exc:
            LOG.warning('Ollama rejected the video digest request (HTTP %s, %d images)', exc.response.status_code, len(images))
            if exc.response.status_code == 400 and len(images) > 1:
                images = images[:max(1, len(images) // 2)]            # too much for the shared context: try fewer frames
                continue
            return None
        except (httpx.HTTPError, OSError, ValueError) as exc:
            LOG.warning('Video digest description failed: %s', exc)
            return None
        if len(text) < 12:
            return None
        try:
            path.write_text(json.dumps({'version': CACHE_VERSION, 'model': model_name, 'frames': [f['t_ms'] for f in meta['frames']], 'caption': text, 'at': time.time()}), encoding='utf-8')
        except OSError:
            pass
        return text
    return None


def plain_summary(meta: dict, alerts: list[dict], reason: str) -> str:
    return f"{facts_line(meta, alerts)} {reason}"


# ---------------------------------------------------------------------------------------------- the answer

def item_payload(source: dict, stamp: datetime, now: datetime, meta: dict | None, alerts: list[dict], summary: str | None, kind: str) -> dict:
    ident = source['id']
    frames = [{'url': f'/api/v1/sources/{ident}/keyframes/{f["n"]}.jpg', 't_ms': f['t_ms'], 'alert': f['alert']} for f in (meta or {}).get('frames', [])]
    return {'source_id': ident, 'filename': source.get('filename'), 'uploaded_at': stamp.isoformat(), 'uploaded_label': f'{clock(stamp, now)} ({ago(stamp, now)})',
            'status': source.get('status'), 'duration_s': (meta or {}).get('duration_s'), 'objects': (meta or {}).get('objects') or {}, 'alerts': alerts,
            'frames': frames, 'video_url': f'/api/v1/sources/{ident}/media' if source.get('media_url') else None, 'summary': summary, 'summary_kind': kind}


def block(number: int, item: dict) -> str:
    head = f"**{number}. {item['filename']}** · uploaded {item['uploaded_label']} · {length(item['duration_s'])} · id `{item['source_id'][:8]}`"
    frames = ', '.join(mmss(f['t_ms']) for f in item['frames'])
    tail = f'Key frames at {frames}.' if frames else 'No key frames could be read from this file.'
    return f"{head}\n{item['summary']}\n{tail}\n"


async def stream(req, session):
    from . import chat
    now = datetime.now().astimezone()
    window = parse_window(req.message, now)
    config = chat.settings()
    model_name = config['ollama_model']
    conversation = req.conversation_id or uuid.uuid4().hex
    with db.connection() as con:
        old = con.execute('SELECT * FROM conversations WHERE id=?', (conversation,)).fetchone()
        if old and old['user_id'] != session['user_id']:
            raise HTTPException(404, 'Conversation not found')
        history = json.loads(old['body']) if old else []
    rows = uploaded_videos(window)
    shown, hidden = rows[:MAX_VIDEOS], max(0, len(rows) - MAX_VIDEOS)
    plan = {'intent': 'video_digest', 'camera_ids': [], 'categories': [], 'severities': [], 'statuses': [], 'sources': ['uploads'],
            'time_from': window.start.timestamp() if window.start.year > 1971 else None, 'time_to': window.end.timestamp(), 'needs_visual_describe': True,
            'limit': MAX_VIDEOS, 'rewritten_query': f'Videos uploaded in {window.label}'}
    yield {'type': 'plan', 'plan': plan}
    evidence = [{'id': s['id'], 'kind': 'recording_segment', 'label': s.get('filename') or s['id'], 'summary': f"Uploaded video {s['id']} ({s.get('status')})", 'ts': t.timestamp(),
                 'clip_url': f"/api/v1/sources/{s['id']}/media" if s.get('media_url') else None} for t, s in shown]
    yield {'type': 'evidence', 'items': evidence}
    info = {'conversation_id': conversation, 'event_ids': [], 'media': [], 'counts': {'matched': len(rows), 'included': len(shown), 'evidence_items': len(evidence)},
            'coverage': {'cameras_with_data': [], 'cameras_without_data': [],
                         'note': 'Uploaded videos only (Analyze uploads and phone recordings sent for analysis); live camera feeds are not included.'},
            'plan': plan, 'evidence': evidence}
    yield {'type': 'context', **info, 'provider': 'ollama', 'model': model_name}

    parts: list[str] = []
    items: list[dict] = []
    if not rows:
        last = latest_upload()
        text = f'No videos were uploaded in {window.label} (since {clock(window.start, now)}).' if window.start.year > 1971 else 'No videos have been uploaded yet.'
        if last:
            text += f" The most recent upload was **{last[1].get('filename')}**, {ago(last[0], now)} ({clock(last[0], now)}). Ask for a longer window, for example \"summarize the videos uploaded in the past 7 days\"."
        parts.append(text)
        yield {'type': 'delta', 'text': text}
    else:
        total_s = 0.0
        many = 's' if len(rows) != 1 else ''
        header = (f'**Showing the {len(rows)} most recent uploaded video{many}**, newest first.' if window.limit else
                  f'**{len(rows)} video{many} uploaded in {window.label}**, newest first'
                  + ('' if window.explicit else ' (no time span given, so the last 24 hours)') + '.')
        yield {'type': 'delta', 'text': header + '\n'}
        parts.append(header)
        skeleton = [item_payload(s, t, now, None, [], None, 'pending') for t, s in shown]
        yield {'type': 'digest', 'window': {'label': window.label, 'start': window.start.isoformat(), 'end': window.end.isoformat(), 'explicit': window.explicit},
               'total': len(rows), 'hidden': hidden, 'items': skeleton}
        started, described, flagged = time.monotonic(), 0, 0
        for number, (stamp, source) in enumerate(shown, 1):
            alerts = alerts_of(source)
            yield {'type': 'status', 'message': f'Looking at video {number} of {len(shown)}: {source.get("filename")}'}
            try:
                meta = await asyncio.to_thread(prepare_frames, source['id'], [a['t_ms'] for a in alerts])
            except Exception:                                  # noqa: BLE001 - one unreadable file must not stop the digest
                LOG.exception('Key frames failed for upload %s', source['id'])
                meta = {'duration_s': None, 'frames': [], 'objects': {}}
            item = item_payload(source, stamp, now, meta, alerts, None, 'pending')
            yield {'type': 'digest_item', 'item': item}
            total_s += meta.get('duration_s') or 0
            flagged += bool(alerts)
            if source.get('status') not in ('DONE', 'RUNNING', 'PENDING') and not meta['frames']:
                item.update(summary=f"This upload {str(source.get('status') or 'failed').lower()}: {source.get('error') or 'it has no playable file'}.", summary_kind='unavailable')
            elif not meta['frames']:
                item.update(summary='The video file could not be read, so there are no frames to summarise.', summary_kind='unavailable')
            else:
                caption = None
                if described < MAX_CAPTIONS and time.monotonic() - started < BUDGET_S:
                    yield {'type': 'status', 'message': f'Describing video {number} of {len(shown)} with {model_name}…'}
                    try:
                        caption = await describe(source['id'], meta, alerts, model_name)
                    except Exception:                          # noqa: BLE001
                        LOG.exception('Description failed for upload %s', source['id'])
                        caption = None
                    described += caption is not None
                if caption:
                    item.update(summary=caption, summary_kind='ai')
                else:
                    reason = ('AI description not generated for this one yet; ask again to continue.' if described >= MAX_CAPTIONS or time.monotonic() - started >= BUDGET_S
                              else 'The AI description is unavailable right now, so only detector facts are shown.')
                    item.update(summary=plain_summary(meta, alerts, reason), summary_kind='facts')
            items.append(item)
            parts.append(block(number, item))
            yield {'type': 'digest_item', 'item': item}
            yield {'type': 'delta', 'text': '\n' + block(number, item)}
        closing = f'Total footage {length(total_s)}; {flagged} of {len(shown)} had detector alerts. Descriptions are written by the local {model_name} model from the key frames only, so they can miss or misread details.'
        if hidden:
            closing += f' {hidden} older video{"s" if hidden != 1 else ""} in this window are not shown; narrow the time span to see them.'
        yield {'type': 'delta', 'text': '\n' + closing}
        parts.append(closing)

    answer = '\n'.join(parts)
    cited = [{'event_id': i['source_id'], 'label': f"{i['filename']} · {i['uploaded_label']}", 'clip_url': i['video_url'], 'start_ms': 0,
              'poster_url': i['frames'][0]['url'] if i['frames'] else None} for i in items[:6] if i['video_url']]
    digest = {'window': window.label, 'total': len(rows), 'hidden': hidden, 'items': items} if items else None
    reply = {'role': 'assistant', 'content': answer} | ({'digest': digest} if digest else {})
    saved = history[-8:] + [{'role': 'user', 'content': req.message}, reply]
    with db.connection() as con:
        con.execute('INSERT OR REPLACE INTO conversations VALUES(?,?,?)', (conversation, session['user_id'], json.dumps(saved)))
    yield {'type': 'done', 'answer': answer, **info, 'provider': 'ollama', 'model': model_name, 'cited': cited, 'digest': digest,
           'filters_used': {'window': window.label}}
