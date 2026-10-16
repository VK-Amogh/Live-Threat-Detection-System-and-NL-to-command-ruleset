"""Build the verifier training set: DINOv2 features of detection crops with real-world hard negatives.

python scripts/verify/build_crops.py
Records (claimed class = what the detector said or what the annotation says):
  gt    annotated instance (train: two jittered views to imitate detector noise; val/test: the exact box)
  det   YOLO detection on a labelled image; label 1 if it matches an annotation of the same class (IoU >= 0.4)
        (train images: false alarms only, true positives come from the `gt` records)
  neg   YOLO detection on a threat-free video frame (always a false alarm)
  rand  random box on a threat-free frame with a random claimed class (teaches "no object" for any region)
Splits follow the source dataset / negative-pool split, so test records never touch training.
"""
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from verifier import CLASSES, crop_square  # noqa: E402
from vision_features import encode_frames, load_encoder  # noqa: E402

FLOOR = 0.10   # proposals below the detector's alert floor are never shown to the verifier at runtime either (config/models.yaml inference.floor_confidence)
rng = random.Random(13)


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0


def inside(a, b):
    """fraction of box a covered by box b"""
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    area = (a[2] - a[0]) * (a[3] - a[1])
    return max(0, ix2 - ix1) * max(0, iy2 - iy1) / area if area > 0 else 0


def dataset_records(name, classes):
    root = ROOT / 'storage/datasets' / name
    raw = json.loads((ROOT / f'storage/eval/{name}_raw.json').read_text())
    out = []
    for path, info in raw.items():
        p = Path(path)
        split = p.parent.name
        w, h = info['size']
        gts = []
        label_file = root / 'labels' / split / (p.stem + '.txt')
        for line in label_file.read_text().splitlines() if label_file.exists() else []:
            c, cx, cy, bw, bh = line.split()[:5]
            cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
            if bw >= 10 and bh >= 10:
                gts.append((classes[int(c)], [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]))
        for cls, box in gts:
            for view in range(2 if split == 'train' else 1):
                out.append({'path': path, 'box': box, 'cls': cls, 'label': 1, 'split': split, 'kind': 'gt', 'jitter': split == 'train' and view == 1 or split == 'train', 'source': name})
        for d in info['det']:
            if d['conf'] < FLOOR:
                continue
            same = [b for c, b in gts if c == d['cls']]
            match = any(iou(b, d['box']) >= 0.2 or inside(d['box'], b) >= 0.5 for b in same)
            if same and not match:
                continue    # ambiguous: the image has this class but the box does not line up (loose / missing annotation)
            if split == 'train' and match:
                continue    # true positives for training come from the jittered annotation crops
            out.append({'path': path, 'box': d['box'], 'cls': d['cls'], 'label': int(match), 'split': split, 'kind': 'det', 'jitter': False, 'source': name, 'conf': d['conf']})
    return out


def detector_training_frames(datasets):
    """sha1[:16] of every threat-free video frame the YOLO detectors trained on (named video<source>_<sha>)."""
    used = set()
    for name in datasets:
        for folder in ('train',):
            for f in (ROOT / 'storage/datasets' / name / 'images' / folder).glob('video*_*.jpg'):
                used.add(f.stem.split('_', 1)[1])
    return used


def negative_records(skip_trained_on=()):
    """False alarms of the deployed detectors on video frames they have NOT been trained on. Frames used as YOLO background images
    are skipped: the detector learned to suppress exactly those, so their remaining errors are unrepresentative of new footage."""
    import hashlib
    used = detector_training_frames(skip_trained_on)
    index = {i['path']: i for i in json.loads((ROOT / 'storage/datasets/negpool/index.json').read_text())}
    raw = json.loads((ROOT / 'storage/eval/negpool_raw.json').read_text())
    out = []
    skipped = 0
    for path, info in raw.items():
        meta = index[path]
        if used and meta['split'] == 'train' and hashlib.sha1(Path(path).read_bytes()).hexdigest()[:16] in used:
            skipped += 1
            continue
        w, h = info['size']
        for d in info['det']:
            if d['conf'] >= FLOOR:
                out.append({'path': path, 'box': d['box'], 'cls': d['cls'], 'label': 0, 'split': meta['split'], 'kind': 'neg', 'jitter': False, 'source': meta['source'], 'conf': d['conf']})
        for _ in range(2 if meta['split'] == 'train' else 1):
            bw, bh = rng.uniform(0.08, 0.55) * w, rng.uniform(0.08, 0.55) * h
            x, y = rng.uniform(0, w - bw), rng.uniform(0, h - bh)
            out.append({'path': path, 'box': [x, y, x + bw, y + bh], 'cls': rng.choice(CLASSES), 'label': 0, 'split': meta['split'], 'kind': 'rand', 'jitter': False, 'source': meta['source']})
    print('skipped', skipped, 'negative frames the detectors trained on', flush=True)
    return out


class Crops(Dataset):
    def __init__(self, records):
        self.records = records
        self.cache = {}

    def __len__(self):
        return len(self.records)

    def __getitem__(self, i):
        r = self.records[i]
        image = cv2.cvtColor(cv2.imread(r['path']), cv2.COLOR_BGR2RGB)
        expand, shift = 1.35, (0.0, 0.0)
        box = r['box']
        if r['jitter']:
            expand = random.uniform(1.15, 1.6)
            shift = (random.uniform(-0.12, 0.12), random.uniform(-0.12, 0.12))
            s = random.uniform(0.85, 1.15)
            cx, cy, bw, bh = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, (box[2] - box[0]) * s, (box[3] - box[1]) * s
            box = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
        return torch.from_numpy(crop_square(image, box, expand, shift))


class Frames(Dataset):
    def __init__(self, paths):
        self.paths = paths

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        image = cv2.cvtColor(cv2.imread(self.paths[i]), cv2.COLOR_BGR2RGB)
        return torch.from_numpy(cv2.resize(image, (224, 224), interpolation=cv2.INTER_AREA))


def main():
    records = dataset_records('fire_smoke_v2', ['fire', 'smoke']) + dataset_records('weapons_v2', ['gun', 'knife']) + negative_records(('fire_smoke_v2', 'weapons_v2'))
    from collections import Counter
    print(len(records), Counter((r['kind'], r['split'], r['label']) for r in records))
    encoder = load_encoder('cuda')
    loader = DataLoader(Crops(records), batch_size=128, num_workers=6, shuffle=False)
    feats = []
    for n, batch in enumerate(loader):
        feats.append(encode_frames(encoder, batch).cpu().numpy().astype(np.float16))
        if n % 50 == 0:
            print(n * 128, '/', len(records), flush=True)
    out = ROOT / 'storage/datasets/verifier'
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / 'features.npy', np.concatenate(feats))
    # Whole-frame context (same 224x224 squash the violence recogniser uses) for every distinct image, joined by path.
    paths = sorted({r['path'] for r in records})
    index = {p: i for i, p in enumerate(paths)}
    gfeats = [encode_frames(encoder, b).cpu().numpy().astype(np.float16) for b in DataLoader(Frames(paths), batch_size=128, num_workers=6)]
    np.save(out / 'global.npy', np.concatenate(gfeats))
    for r in records:
        r['gi'] = index[r['path']]
    (out / 'meta.json').write_text(json.dumps(records))
    print('saved', len(records))


if __name__ == '__main__':
    main()
