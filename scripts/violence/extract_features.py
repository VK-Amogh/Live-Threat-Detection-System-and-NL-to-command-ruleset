"""Cache frozen DINOv2 features for violence clips.

python scripts/violence/extract_features.py --manifest storage/datasets/violence/manifest.json
Each clip contributes T=16 uniformly spaced frames; training clips also get a horizontally flipped and a
crop-jittered view so the temporal head sees augmentation without re-decoding video.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from vision_features import load_encoder, encode_frames  # noqa: E402

T = 16
SIDE = 224


def sample_frames(path: str):
    if Path(path).suffix.lower() in {'.jpg', '.jpeg', '.png'}:  # a still is a clip of identical frames
        frame = cv2.imread(path)
        return None if frame is None else [frame] * T
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        frames = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
        cap.release()
        total = len(frames)
        if not total:
            return None
        idx = set(np.linspace(0, total - 1, T).round().astype(int).tolist())
        return [frames[i] for i in sorted(idx)] if len(idx) == T else [frames[i] for i in np.linspace(0, total - 1, T).round().astype(int)]
    wanted = np.linspace(0, max(0, total - 1), T).round().astype(int)
    out, pos, last = [], 0, None
    targets = iter(wanted)
    target = next(targets)
    while True:
        ok = cap.grab()
        if not ok:
            break
        if pos == target:
            ok, frame = cap.retrieve()
            if not ok:
                break
            last = frame
            out.append(frame)
            try:
                target = next(targets)
                while target == pos:  # repeated index for very short clips
                    out.append(frame)
                    target = next(targets)
            except StopIteration:
                break
        pos += 1
    cap.release()
    while out and len(out) < T:
        out.append(out[-1])
    return out if len(out) == T else None


def squash(frame, flip=False, jitter=None):
    h, w = frame.shape[:2]
    if jitter:
        s = jitter
        ch, cw = int(h * s), int(w * s)
        y0, x0 = (h - ch) // 2, (w - cw) // 2
        frame = frame[y0:y0 + ch, x0:x0 + cw]
    frame = cv2.resize(frame, (SIDE, SIDE), interpolation=cv2.INTER_AREA)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if flip:
        frame = frame[:, ::-1]
    return np.ascontiguousarray(frame)


class Clips(Dataset):
    def __init__(self, rows, train_views):
        self.rows, self.train_views = rows, train_views

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        row = self.rows[i]
        frames = sample_frames(row['path'])
        if frames is None:
            return i, torch.zeros(0)
        views = [[squash(f) for f in frames]]
        if row['split'] == 'train' and self.train_views:
            views.append([squash(f, flip=True) for f in frames])
            views.append([squash(f, jitter=0.8) for f in frames])
        return i, torch.from_numpy(np.stack(views))  # V,T,H,W,3 uint8


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--out', default='storage/datasets/violence/features')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--no-aug', action='store_true')
    p.add_argument('--append', action='store_true', help='keep features already cached for the same paths and extract only new clips')
    a = p.parse_args()
    rows = json.loads(Path(a.manifest).read_text())
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    old_feats, old_meta = [], []
    if a.append and (out / 'features.npy').exists():
        old_feats = list(np.load(out / 'features.npy'))
        old_meta = json.loads((out / 'meta.json').read_text())
        done = {m['path'] for m in old_meta}
        rows = [r for r in rows if r['path'] not in done]
        print(f'{len(old_meta)} cached samples, {len(rows)} new clips', flush=True)
    encoder = load_encoder('cuda')
    loader = DataLoader(Clips(rows, not a.no_aug), batch_size=None, num_workers=a.workers, prefetch_factor=4, shuffle=False)
    feats, meta, bad = list(old_feats), list(old_meta), 0
    started = time.time()
    for n, (i, views) in enumerate(loader):
        if views.numel() == 0:
            bad += 1
            continue
        V = views.shape[0]
        x = views.reshape(V * T, SIDE, SIDE, 3)
        f = encode_frames(encoder, x).reshape(V, T, -1).cpu().numpy().astype(np.float16)
        for v in range(V):
            feats.append(f[v])
            meta.append({**rows[i], 'view': v})
        if n % 100 == 0:
            print(f'{n}/{len(rows)} clips  {time.time()-started:.0f}s  bad={bad}', flush=True)
    np.save(out / 'features.npy', np.stack(feats))
    (out / 'meta.json').write_text(json.dumps(meta))
    print('saved', len(feats), 'samples; unreadable clips:', bad, flush=True)


if __name__ == '__main__':
    main()
