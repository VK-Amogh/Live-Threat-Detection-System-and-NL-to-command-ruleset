"""Cache VideoMAE-base (Kinetics-400 fine-tuned) clip features: motion/action cues the frame-wise DINOv2 head cannot see.

python scripts/violence/extract_videomae.py --manifest storage/datasets/violence/manifest.json --out storage/datasets/violence/videomae
Feature = [mean-pooled last hidden state (768) | Kinetics-400 logits (400)]. 16 frames uniformly over the clip; training clips
get a horizontally flipped second view. Threat-free still images are skipped (a static clip carries no motion).
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
sys.path.insert(0, str(Path(__file__).parent))
from extract_features import sample_frames  # noqa: E402

MODEL = 'MCG-NJU/videomae-base-finetuned-kinetics'
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png'}


def prep(frame):
    h, w = frame.shape[:2]
    scale = 224 / min(h, w)
    frame = cv2.resize(frame, (max(224, round(w * scale)), max(224, round(h * scale))), interpolation=cv2.INTER_AREA)
    h, w = frame.shape[:2]
    y, x = (h - 224) // 2, (w - 224) // 2
    return frame[y:y + 224, x:x + 224]


class Clips(Dataset):
    def __init__(self, rows, flip_train):
        self.rows, self.flip_train = rows, flip_train

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        frames = sample_frames(r['path'])
        if frames is None:
            return i, torch.zeros(0)
        clip = np.stack([cv2.cvtColor(prep(f), cv2.COLOR_BGR2RGB) for f in frames]).astype(np.float32) / 255.0   # T,H,W,3
        views = [clip]
        if self.flip_train and r['split'] == 'train':
            views.append(clip[:, :, ::-1])
        out = [torch.from_numpy(((v - MEAN) / STD).transpose(0, 3, 1, 2).copy()) for v in views]    # T,3,H,W
        return i, torch.stack(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--append', action='store_true')
    ap.add_argument('--no-aug', action='store_true')
    a = ap.parse_args()
    from transformers import VideoMAEForVideoClassification
    rows = [r for r in json.loads(Path(a.manifest).read_text()) if Path(r['path']).suffix.lower() not in IMAGE_SUFFIXES]
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    feats, meta = [], []
    if a.append and (out / 'features.npy').exists():
        feats, meta = list(np.load(out / 'features.npy')), json.loads((out / 'meta.json').read_text())
        done = {m['path'] for m in meta}
        rows = [r for r in rows if r['path'] not in done]
        print(len(meta), 'cached;', len(rows), 'new', flush=True)
    model = VideoMAEForVideoClassification.from_pretrained(MODEL, dtype=torch.float16).cuda().eval()
    loader = DataLoader(Clips(rows, not a.no_aug), batch_size=None, num_workers=a.workers, prefetch_factor=3)
    started = time.time()
    with torch.inference_mode():
        for n, (i, views) in enumerate(loader):
            if views.numel() == 0:
                continue
            o = model(pixel_values=views.cuda().half(), output_hidden_states=True)
            pooled = o.hidden_states[-1].mean(1) if o.hidden_states[-1].dim() == 3 else o.hidden_states[-1]
            f = torch.cat([pooled.float(), o.logits.float()], dim=1).cpu().numpy().astype(np.float16)
            for v in range(len(f)):
                feats.append(f[v])
                meta.append({**rows[i], 'view': v})
            if n % 100 == 0:
                print(f'{n}/{len(rows)} clips {time.time() - started:.0f}s', flush=True)
    np.save(out / 'features.npy', np.stack(feats))
    (out / 'meta.json').write_text(json.dumps(meta))
    print('saved', len(feats), flush=True)


if __name__ == '__main__':
    main()
