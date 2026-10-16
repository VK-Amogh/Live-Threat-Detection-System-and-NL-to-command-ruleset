"""Run the YOLO detectors on an image index and cache every raw detection (conf >= floor).

python scripts/eval/raw_detections.py --index storage/datasets/negpool/index.json --out storage/eval/negpool_raw.json
Thresholds, policies and verifiers can then be tuned offline against these caches without re-running the GPU.
"""
import argparse
import json
from pathlib import Path

import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]


def load_models(overrides):
    spec = yaml.safe_load((ROOT / 'config/models.yaml').read_text())
    models = []
    for m in spec['models']:
        path = Path(overrides.get(m['name']) or ROOT / m['path'])
        model = YOLO(str(path))
        model.fuse(verbose=False)
        models.append((m['name'], model, int(m.get('imgsz', 640))))
    return models


def scan(paths, models, floor=0.10, batch=32):
    out = {}
    for name, model, imgsz in models:
        for i in range(0, len(paths), batch):
            chunk = paths[i:i + batch]
            for p, res in zip(chunk, model.predict(chunk, imgsz=imgsz, conf=floor, iou=0.6, device=0, half=True, verbose=False, max_det=50)):
                h, w = res.orig_shape
                out.setdefault(p, {'size': [w, h], 'det': []})['det'] += [
                    {'model': name, 'cls': res.names[int(b.cls)], 'conf': round(float(b.conf), 4), 'box': [round(v, 1) for v in b.xyxy[0].tolist()]} for b in res.boxes]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', required=True, help='JSON list of {path,...} or a directory of images')
    ap.add_argument('--out', required=True)
    ap.add_argument('--floor', type=float, default=0.10)
    ap.add_argument('--fire', help='override fire_smoke weights')
    ap.add_argument('--weapons', help='override weapons weights')
    a = ap.parse_args()
    src = Path(a.index)
    paths = [r['path'] for r in json.loads(src.read_text())] if src.suffix == '.json' else sorted(str(p) for p in src.rglob('*.jpg'))
    models = load_models({'fire_smoke': a.fire, 'weapons': a.weapons})
    result = scan(paths, models, a.floor)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result))
    print(len(paths), 'images,', sum(len(v['det']) for v in result.values()), 'detections ->', a.out)


if __name__ == '__main__':
    main()
