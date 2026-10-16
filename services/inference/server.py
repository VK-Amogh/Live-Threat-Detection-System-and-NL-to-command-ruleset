"""Loopback-only detector service. API and inference share contracts, never code.

Loads whatever weights exist under config/models.yaml: YOLO object detectors (fire/smoke, weapons) and the
DINOv2 + temporal-head violence recognizer.  Thresholds come from calibration sidecars written by the
benchmark scripts (storage/models/<weights>.json), not from constants in this file.
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
STREAMS = {}         # source_id -> deque[(monotonic, feature tensor)]
STREAM_WINDOW = 8
STREAM_TTL_S = 12


class Violence:
    """Frozen encoder + temporal head. T=1 scores a still frame; longer windows use temporal context."""

    def __init__(self, head_path: Path, device: str):
        import torch
        from violence_head import TemporalHead
        from vision_features import load_encoder
        self.torch = torch
        self.device = 'cuda' if device != 'cpu' else 'cpu'
        self.encoder = load_encoder(self.device)
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

    def score(self, image: Image.Image, source_id: str | None):
        import cv2
        torch = self.torch
        from vision_features import encode_frames
        frame = cv2.resize(np.asarray(image), (224, 224), interpolation=cv2.INTER_AREA)
        feature = encode_frames(self.encoder, torch.from_numpy(frame)[None])[0]
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


def load_models():
    global DEVICE, VIOLENCE, CONFIG, MAPPINGS
    CONFIG = yaml.safe_load((ROOT / 'config/models.yaml').read_text())          # re-read so promoting weights needs no restart
    MAPPINGS = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4) // 2)))
    DEVICE = '0' if torch.cuda.is_available() else 'cpu'
    MODELS.clear()
    ERRORS.clear()
    VIOLENCE = None
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
    spec = CONFIG.get('violence')
    if spec:
        head = ROOT / spec['head']
        if head.exists():
            try:
                VIOLENCE = Violence(head, DEVICE)
            except Exception as exc:
                ERRORS.append(f'violence: {type(exc).__name__}: {str(exc)[:120]}')
        else:
            ERRORS.append('violence: weights not installed')


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
    if VIOLENCE:
        models.append({'name': 'violence', 'classes': ['violence'], 'thresholds': {str(k): v for k, v in VIOLENCE.thresholds.items()}})
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
    return {'ok': True}


def predict(data, source_id):
    try:
        image = Image.open(io.BytesIO(data))
        if image.width * image.height > 25_000_000:
            raise ValueError('Image exceeds 25 megapixels')
        image = image.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(422, 'Invalid or oversized image') from exc
    start = time.perf_counter()
    boxes, classes = [], set()
    floor = float(CONFIG['inference'].get('floor_confidence', 0.15))
    for name, model, _, thresholds, imgsz in MODELS:
        classes.update(model.names.values())
        result = model.predict(image, imgsz=imgsz, conf=floor, device=DEVICE, half=DEVICE != 'cpu', verbose=False)[0]
        for box in result.boxes:
            label = result.names[int(box.cls.item())]
            conf = float(box.conf.item())
            rule = MAPPINGS.get(label.lower(), {})
            limit = thresholds.get(label, rule.get('min_confidence', 1))
            if conf < limit:
                continue
            threat = rule.get('trigger_incident', False)
            boxes.append(Detection(class_name=label, confidence=conf, box=box.xyxy[0].tolist(), model=name, category=rule.get('category') if threat else None, severity=rule.get('severity') if threat else None))
    models = [m[0] for m in MODELS]
    if VIOLENCE:
        classes.add('violence')
        models.append('violence')
        score, frames = VIOLENCE.score(image, source_id)
        rule = MAPPINGS.get('violence', {})
        if score >= VIOLENCE.threshold(frames):
            boxes.append(Detection(class_name='violence', confidence=min(1.0, score), box=[0.0, 0.0, float(image.width), float(image.height)], model='violence', category=rule.get('category'), severity=rule.get('severity')))
    return FrameResult(detections=boxes, threat_detected=any(b.category for b in boxes), inference_ms=round((time.perf_counter() - start) * 1000, 1), width=image.width, height=image.height, models=models, covered_classes=sorted(classes))


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
