"""Sample frames from video clips into a flat, indexed image pool.

python scripts/data/extract_frames.py --name negpool --frames 3 --source rlvs hockey scvd
Frames come from clips known to contain none of the threats (violence label 0). They serve two purposes:
hard negatives for training/verification (splits train/val) and a blind false-alarm test (split test).
Sampling is evenly spaced between 8% and 92% of each clip so title cards and fades are skipped.
Index: storage/datasets/<name>/index.json  [{path, source, split, clip, group}]
"""
import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'storage/datasets/violence/manifest.json'
LONG_SIDE = 640


def grab(args):
    clip, out_dir, stem, count = args
    cap = cv2.VideoCapture(clip)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < 4:
        return []
    done = []
    for k, pos in enumerate(np.linspace(total * 0.08, total * 0.92, count).astype(int)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        scale = LONG_SIDE / max(h, w)
        if scale < 1:
            frame = cv2.resize(frame, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        path = Path(out_dir) / f'{stem}_{k}.jpg'
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        done.append(str(path))
    cap.release()
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='negpool')
    ap.add_argument('--frames', type=int, default=3)
    ap.add_argument('--source', nargs='+', default=['rlvs', 'hockey', 'scvd'])
    ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    keys = {'rlvs': 'Real Life Violence', 'hockey': 'Hockey', 'scvd': 'SCVD', 'rwf': 'RWF'}
    rows = [r for r in json.loads(MANIFEST.read_text()) if r['label'] == 0 and not r['dataset'].startswith('Threat-free')
            and any(r['dataset'].startswith(keys[s]) for s in a.source)]
    out = ROOT / 'storage/datasets' / a.name
    jobs, meta = [], []
    for r in rows:
        source = next(s for s in a.source if r['dataset'].startswith(keys[s]))
        folder = out / source / r['split']
        folder.mkdir(parents=True, exist_ok=True)
        stem = Path(r['path']).stem.replace(' ', '_')
        jobs.append((r['path'], str(folder), stem, a.frames))
        meta.append((source, r['split'], stem))
    index = []
    with ProcessPoolExecutor(a.workers) as pool:
        for (source, split, stem), paths in zip(meta, pool.map(grab, jobs, chunksize=8)):
            index += [{'path': p, 'source': source, 'split': split, 'clip': stem, 'group': f'{source}:{stem}'} for p in paths]
    (out / 'index.json').write_text(json.dumps(index))
    from collections import Counter
    print(len(index), 'frames', dict(Counter((i['source'], i['split']) for i in index)))


if __name__ == '__main__':
    main()
