"""Add real-CCTV fire/smoke/explosion positives (DCSASS dev parents) to the verifier training set.

python scripts/verify/adapt_crops.py
Why: D-Fire (wildfire / house-fire photos) does not look like a 320x240 CCTV explosion, so a verifier trained on it
alone rejects real CCTV fires. Frames come from Arson/Explosion sub-clips labelled anomalous in *dev* parents; a proposal
becomes a positive only if the YOLO detector itself is confident (>= --min-conf), which keeps annotation noise low.
Blind parents are never touched. Outputs features_adapt.npy / global_adapt.npy / meta_adapt.json next to the main set.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'scripts/data'), str(ROOT / 'scripts/eval'), str(ROOT / 'scripts/verify')]
from build_crops import Crops, Frames  # noqa: E402
from extract_frames import grab  # noqa: E402
from raw_detections import load_models, scan  # noqa: E402
from vision_features import encode_frames, load_encoder  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames', type=int, default=4)
    ap.add_argument('--min-conf', type=float, default=0.45)
    a = ap.parse_args()
    manifest = [r for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text())
                if r['split'] == 'dev' and r['label'] == 1 and r['category'] in ('Arson', 'Explosion')]
    out_dir = ROOT / 'storage/datasets/adapt'
    out_dir.mkdir(parents=True, exist_ok=True)
    paths, owner = [], {}
    for r in manifest:
        for p in grab((r['path'], str(out_dir), r['clip'], a.frames)):
            paths.append(p)
            owner[p] = r
    print(len(manifest), 'clips ->', len(paths), 'frames', flush=True)
    models = load_models({})
    raw = scan(paths, [m for m in models if m[0] == 'fire_smoke'], floor=a.min_conf)
    records = []
    for p, info in raw.items():
        parent = owner[p]['parent']
        split = 'val' if int(hashlib.sha1(parent.encode()).hexdigest(), 16) % 10 == 0 else 'train'
        for d in info['det']:
            records.append({'path': p, 'box': d['box'], 'cls': d['cls'], 'label': 1, 'split': split, 'kind': 'adapt', 'jitter': split == 'train', 'source': 'dcsass-adapt', 'conf': d['conf']})
            if split == 'train':   # a second jittered view
                records.append({**records[-1]})
    print(len(records), 'positive crops from', len({r['path'] for r in records}), 'frames', flush=True)
    encoder = load_encoder('cuda')
    feats = [encode_frames(encoder, b).cpu().numpy().astype(np.float16) for b in DataLoader(Crops(records), batch_size=128, num_workers=6)]
    uniq = sorted({r['path'] for r in records})
    index = {p: i for i, p in enumerate(uniq)}
    gfeats = [encode_frames(encoder, b).cpu().numpy().astype(np.float16) for b in DataLoader(Frames(uniq), batch_size=128, num_workers=6)]
    dest = ROOT / 'storage/datasets/verifier'
    np.save(dest / 'features_adapt.npy', np.concatenate(feats))
    np.save(dest / 'global_adapt.npy', np.concatenate(gfeats))
    for r in records:
        r['gi'] = index[r['path']]
    (dest / 'meta_adapt.json').write_text(json.dumps(records))
    print('saved', len(records))


if __name__ == '__main__':
    main()
