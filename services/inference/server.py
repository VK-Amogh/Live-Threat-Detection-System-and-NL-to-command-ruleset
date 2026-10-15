"""Loopback-only detector service. API and inference share contracts, never code."""
import asyncio
import io
import os
from pathlib import Path
import secrets
import time
from contextlib import asynccontextmanager
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile, Depends
from PIL import Image, UnidentifiedImageError
from td_contracts import FrameResult, Detection

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
MODELS = []
ERRORS = []
LOCK = asyncio.Lock()
CONFIG = yaml.safe_load((ROOT / 'config/models.yaml').read_text())
MAPPINGS = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
DEVICE = 'cpu'


def load_models():
    global DEVICE
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4)//2)))
    DEVICE = '0' if torch.cuda.is_available() else 'cpu'
    MODELS.clear()
    ERRORS.clear()
    for spec in CONFIG['models']:
        path = ROOT / spec['path']
        if not path.exists():
            ERRORS.append(f"{spec['name']}: weights not installed")
            continue
        try:
            model = YOLO(str(path))
            model.fuse(verbose=False)
            MODELS.append((spec['name'], model, path.stat().st_mtime))
        except Exception as exc:
            ERRORS.append(f"{spec['name']}: {type(exc).__name__}")


@asynccontextmanager
async def lifespan(app):
    await asyncio.to_thread(load_models)
    yield


async def internal(authorization: str = Header(default='')):
    token = os.getenv('INTERNAL_SERVICE_TOKEN', '')
    if not token or not secrets.compare_digest(authorization, f'Bearer {token}'):
        raise HTTPException(401, 'Internal authentication required')


app = FastAPI(title='SafeSpace detector', lifespan=lifespan, dependencies=[Depends(internal)])


@app.get('/health')
async def health():
    return {'ready': bool(MODELS), 'device': DEVICE, 'models': [{'name': name, 'classes': list(model.names.values())} for name, model, _ in MODELS], 'errors': ERRORS, 'unsupported': CONFIG.get('unsupported', [])}


@app.post('/reload')
async def reload_models():
    async with LOCK:
        await asyncio.to_thread(load_models)
    return await health()


def predict(data):
    try:
        image = Image.open(io.BytesIO(data))
        if image.width*image.height > 25_000_000:
            raise ValueError('Image exceeds 25 megapixels')
        image = image.convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(422, 'Invalid or oversized image') from exc
    start = time.perf_counter()
    boxes, classes = [], set()
    for name, model, _ in MODELS:
        classes.update(model.names.values())
        result = model.predict(image, imgsz=CONFIG['inference']['image_size'], conf=CONFIG['inference']['confidence'], device=DEVICE, half=DEVICE != 'cpu', verbose=False)[0]
        for box in result.boxes:
            label = result.names[int(box.cls.item())]
            conf = float(box.conf.item())
            rule = MAPPINGS.get(label.lower(), {})
            threat = rule.get('trigger_incident', False) and conf >= rule.get('min_confidence', 1)
            boxes.append(Detection(class_name=label, confidence=conf, box=box.xyxy[0].tolist(), model=name, category=rule.get('category') if threat else None, severity=rule.get('severity') if threat else None))
    return FrameResult(detections=boxes, threat_detected=any(b.category for b in boxes), inference_ms=round((time.perf_counter()-start)*1000, 1), width=image.width, height=image.height, models=[m[0] for m in MODELS], covered_classes=sorted(classes))


@app.post('/predict', response_model=FrameResult)
async def predict_frame(file: UploadFile = File(...)):
    data = await file.read(20*1024*1024+1)
    if len(data)>20*1024*1024:
        raise HTTPException(413, 'Frame exceeds 20 MB')
    if not MODELS:
        raise HTTPException(503, 'No detector weights loaded')
    if LOCK.locked():
        raise HTTPException(429, 'Detector busy; retry with latest frame')
    async with LOCK:
        return await asyncio.to_thread(predict, data)
