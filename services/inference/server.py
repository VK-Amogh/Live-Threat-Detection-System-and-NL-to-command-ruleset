"""Loopback-only detector service. API and inference share contracts, never code.

Pipeline per frame: YOLO detectors propose boxes (high recall) -> DINOv2 crop verifier re-scores every proposal
(precision) -> calibrated per-class thresholds decide -> violence recogniser scores the scene (temporal window).
Thresholds come from calibration sidecars written by the benchmark/training scripts (storage/models/<weights>.json).
"""
import asyncio
import io
import json
import os
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import yaml
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from td_contracts import Detection, FrameResult

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
MODELS = []          # (name, YOLO, mtime, thresholds, imgsz)
ERRORS = []
LOCK = asyncio.Lock()
CONFIG = yaml.safe_load((ROOT / 'config/models.yaml').read_text())
MAPPINGS = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
DEVICE = 'cpu'
VIOLENCE = None
VERIFIER = None      # (MLP, thresholds) or None
MOTION = None        # VideoMAE-based motion scorer (video/live streams only)
ENSEMBLE = None      # {'threshold': float}: mean of DINOv2 temporal head and motion head
ENCODER = None       # frozen DINOv2 shared by the violence recogniser and the verifier
STREAMS = {}         # source_id -> deque[(monotonic, feature tensor)]
STREAM_WINDOW = 8
STREAM_TTL_S = 12


class Violence:
    """Frozen features + temporal head. T=1 scores a still frame; longer windows use temporal context."""

    def __init__(self, head_path: Path, device: str, encoder):
        import torch
        from violence_head import TemporalHead
        self.torch = torch
        self.device = 'cuda' if device != 'cpu' else 'cpu'
        self.encoder = encoder
        self.head = TemporalHead().to(self.device).eval()
        state = torch.load(head_path, map_location=self.device, weights_only=True)
        self.head.load_state_dict(state)
        meta_path = head_path.with_suffix('.json')
        self.meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        self.thresholds = {int(k): v for k, v in self.meta.get('thresholds', {}).items()}

    def threshold(self, frames: int) -> float:
        if not self.thresholds:
            return 1.1  # uncalibrated head never raises alerts
        usable = [k for k in self.thresholds if k <= frames] or [min(self.thresholds)]
        return self.thresholds[max(usable)]

    def score(self, feature, source_id: str | None):
        torch = self.torch
        now = time.monotonic()
        if source_id:
            for key in [k for k, v in STREAMS.items() if v and now - v[-1][0] > 120]:
                STREAMS.pop(key, None)
            buffer = STREAMS.setdefault(source_id, deque(maxlen=STREAM_WINDOW))
            buffer.append((now, feature))
            while buffer and now - buffer[0][0] > STREAM_TTL_S:
                buffer.popleft()
            window = torch.stack([f for _, f in buffer])
        else:
            window = feature[None]
        with torch.inference_mode():
            logit, _ = self.head(window[None])
        return float(torch.sigmoid(logit)[0]), window.shape[0]


def frame_feature(image_rgb: np.ndarray):
    """DINOv2 feature of the whole frame (224x224 squash) — identical preprocessing to training."""
    import cv2
    import torch
    from vision_features import encode_frames
    small = cv2.resize(image_rgb, (224, 224), interpolation=cv2.INTER_AREA)
    return encode_frames(ENCODER, torch.from_numpy(small)[None])[0]


def load_models():
    global DEVICE, VIOLENCE, VERIFIER, ENCODER, MOTION, ENSEMBLE, CONFIG, MAPPINGS
    CONFIG = yaml.safe_load((ROOT / 'config/models.yaml').read_text())          # re-read so promoting weights needs no restart
    MAPPINGS = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4) // 2)))
    DEVICE = '0' if torch.cuda.is_available() else 'cpu'
    MODELS.clear()
    ERRORS.clear()
    VIOLENCE = None
    VERIFIER = None
    ENCODER = None
    MOTION = None
    ENSEMBLE = None
    for spec in CONFIG['models']:
        path = ROOT / spec['path']
        if not path.exists():
            ERRORS.append(f"{spec['name']}: weights not installed")
            continue
        try:
            model = YOLO(str(path))
            model.fuse(verbose=False)
            sidecar = path.with_suffix('.json')
            thresholds = json.loads(sidecar.read_text()).get('thresholds', {}) if sidecar.exists() else {}
            MODELS.append((spec['name'], model, path.stat().st_mtime, thresholds, int(spec.get('imgsz', CONFIG['inference']['image_size']))))
        except Exception as exc:
            ERRORS.append(f"{spec['name']}: {type(exc).__name__}")
    vspec, rspec = CONFIG.get('violence'), CONFIG.get('verifier')
    if (vspec and (ROOT / vspec['head']).exists()) or (rspec and (ROOT / rspec['weights']).exists()):
        from vision_features import load_encoder
        ENCODER = load_encoder('cuda' if DEVICE != 'cpu' else 'cpu')
    if vspec:
        head = ROOT / vspec['head']
        if head.exists():
            try:
                VIOLENCE = Violence(head, DEVICE, ENCODER)
            except Exception as exc:
                ERRORS.append(f'violence: {type(exc).__name__}: {str(exc)[:120]}')
        else:
            ERRORS.append('violence: weights not installed')
        motion, ensemble = ROOT / vspec['motion'] if vspec.get('motion') else None, ROOT / vspec['ensemble'] if vspec.get('ensemble') else None
        if motion and motion.exists() and ensemble and ensemble.exists():
            try:
                from motion import MotionScorer
                MOTION = MotionScorer(motion, 'cuda' if DEVICE != 'cpu' else 'cpu')
                ENSEMBLE = json.loads(ensemble.read_text())
            except Exception as exc:
                ERRORS.append(f'violence motion: {type(exc).__name__}: {str(exc)[:120]}')
    if rspec:
        path = ROOT / rspec['weights']
        if path.exists():
            try:
                from verifier import VerifierMLP
                mlp = VerifierMLP().to('cuda' if DEVICE != 'cpu' else 'cpu').eval()
                mlp.load_state_dict(torch.load(path, map_location=next(mlp.parameters()).device, weights_only=True))
                meta = json.loads(path.with_suffix('.json').read_text())
                VERIFIER = (mlp, meta['thresholds'])
            except Exception as exc:
                ERRORS.append(f'verifier: {type(exc).__name__}: {str(exc)[:120]}')
        else:
            ERRORS.append('verifier: weights not installed (falling back to detector thresholds)')


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(load_models)
    yield


async def internal(authorization: str = Header(default='')):
    token = os.getenv('INTERNAL_SERVICE_TOKEN', '')
    if not token or not secrets.compare_digest(authorization, f'Bearer {token}'):
        raise HTTPException(401, 'Internal authentication required')


app = FastAPI(title='SafeSpace detector', lifespan=lifespan, dependencies=[Depends(internal)])


def coverage():
    models = [{'name': name, 'classes': list(model.names.values()), 'thresholds': thresholds, 'imgsz': imgsz} for name, model, _, thresholds, imgsz in MODELS]
    if VERIFIER:
        models.append({'name': 'verifier', 'classes': ['gun', 'knife'], 'thresholds': {k: v for k, v in VERIFIER[1].items() if k in ('gun', 'knife')}})
    if VIOLENCE:
        models.append({'name': 'violence', 'classes': ['violence'], 'thresholds': {str(k): v for k, v in VIOLENCE.thresholds.items()}, 'motion': bool(MOTION), 'ensemble_threshold': ENSEMBLE['threshold'] if ENSEMBLE else None})
    return models


@app.get('/health')
async def health():
    return {'ready': bool(MODELS) or VIOLENCE is not None, 'device': DEVICE, 'models': coverage(), 'errors': ERRORS, 'unsupported': CONFIG.get('unsupported', [])}


@app.post('/reload')
async def reload_models():
    async with LOCK:
        await asyncio.to_thread(load_models)
    return await health()


@app.delete('/streams/{source_id}')
async def forget_stream(source_id: str):
    STREAMS.pop(source_id, None)
    if MOTION:
        MOTION.forget(source_id)
    return {'ok': True}


def analyse(image: Image.Image, source_id):
    """Raw model outputs for one frame, before any alert decision (also used by the offline evaluation harness)."""
    frame = np.asarray(image)
    floor = float(CONFIG['inference'].get('floor_confidence', 0.15))
    proposals = []
    for name, model, _, thresholds, imgsz in MODELS:
        result = model.predict(image, imgsz=imgsz, conf=floor, device=DEVICE, half=DEVICE != 'cpu', verbose=False)[0]
        for box in result.boxes:
            proposals.append({'model': name, 'cls': result.names[int(box.cls.item())], 'conf': float(box.conf.item()), 'box': box.xyxy[0].tolist(), 'thresholds': thresholds})
    proposals = sorted(proposals, key=lambda p: -p['conf'])[:8]
    feature = frame_feature(frame) if ENCODER is not None else None
    if VERIFIER and proposals:
        from verifier import score_detections
        known = [p for p in proposals if p['cls'] in VERIFIER[1]]
        probs = score_detections(ENCODER, VERIFIER[0], frame, [(p['cls'], p['box']) for p in known], feature)
        for p, prob in zip(known, probs):
            p['verifier'] = prob
    violence = VIOLENCE.score(feature, source_id) if VIOLENCE else None
    motion = None
    if MOTION and source_id:
        MOTION.push(source_id, frame)
        motion = MOTION.score(source_id)
    return {'proposals': proposals, 'violence': violence, 'motion': motion, 'size': image.size}


def fuse(scene: float, motion: float) -> float:
    """Violence probability from the scene head and the motion head (logistic stack fitted on validation clips, else mean)."""
    if ENSEMBLE and ENSEMBLE.get('method') == 'stack':
        import math
        logit = lambda p: math.log(min(max(p, 1e-4), 1 - 1e-4) / (1 - min(max(p, 1e-4), 1 - 1e-4)))
        z = ENSEMBLE['coef'][0] * logit(scene) + ENSEMBLE['coef'][1] * logit(motion) + ENSEMBLE['intercept']
        return 1 / (1 + math.exp(-z))
    return (scene + motion) / 2


def decide(raw) -> list[Detection]:
    boxes = []
    for p in raw['proposals']:
        rule = MAPPINGS.get(p['cls'].lower(), {})
        if VERIFIER and 'verifier' in p:
            confidence, limit = p['verifier'], VERIFIER[1][p['cls']]
        else:
            confidence, limit = p['conf'], p['thresholds'].get(p['cls'], rule.get('min_confidence', 1))
        if confidence < limit:
            continue
        threat = rule.get('trigger_incident', False)
        boxes.append(Detection(class_name=p['cls'], confidence=min(1.0, confidence), detector_confidence=min(1.0, p['conf']), box=p['box'], model=p['model'],
                               category=rule.get('category') if threat else None, severity=rule.get('severity') if threat else None))
    if VIOLENCE and raw['violence']:
        score, frames = raw['violence']
        rule = MAPPINGS.get('violence', {})
        motion = raw.get('motion')
        if motion is not None and ENSEMBLE:          # video / live: scene head + motion head, fused as fitted on validation clips
            score, limit = fuse(score, motion), ENSEMBLE['threshold']
        else:                                        # stills and the first frames of a stream: scene head alone
            limit = VIOLENCE.threshold(frames)
        if score >= limit:
            w, h = raw['size']
            boxes.append(Detection(class_name='violence', confidence=min(1.0, score), box=[0.0, 0.0, float(w), float(h)], model='violence', category=rule.get('category'), severity=rule.get('severity')))
    return boxes


def predict(data, source_id):
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 25_000_000:
            raise ValueError('Image exceeds 25 megapixels')
        image = image.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(422, 'Invalid or oversized image') from exc
    start = time.perf_counter()
    boxes = decide(analyse(image, source_id))
    classes = {c for _, model, *_ in MODELS for c in model.names.values()} | ({'violence'} if VIOLENCE else set())
    models = [m[0] for m in MODELS] + (['verifier'] if VERIFIER else []) + (['violence'] if VIOLENCE else [])
    return FrameResult(detections=boxes, threat_detected=any(b.category for b in boxes), inference_ms=round((time.perf_counter() - start) * 1000, 1),
                       width=image.width, height=image.height, models=models, covered_classes=sorted(classes))


@app.post('/predict', response_model=FrameResult)
async def predict_frame(file: UploadFile = File(...), source_id: str | None = Query(default=None, max_length=64)):
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, 'Frame exceeds 20 MB')
    if not MODELS and not VIOLENCE:
        raise HTTPException(503, 'No detector weights loaded')
    if LOCK.locked():
        raise HTTPException(429, 'Detector busy; retry with latest frame')
    async with LOCK:
        return await asyncio.to_thread(predict, data, source_id)
