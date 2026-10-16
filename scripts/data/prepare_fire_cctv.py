"""Build a small fire/smoke fine-tuning set with CCTV hard negatives.

Only SCVD train/validation Normal clips are used. The SCVD test clips and
TestVideos are excluded. Existing fire/smoke boxes keep their original labels.
"""
import argparse
import json
import os
import random
from collections import defaultdict
from pathlib import Path

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'storage/datasets/fire_smoke'
DEST = ROOT / 'storage/datasets/fire_smoke_cctv'
MANIFEST = ROOT / 'storage/datasets/violence/manifest.json'


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        os.link(src, dst)


def add_base(split, limits, rng):
    grouped = defaultdict(list)
    for label in sorted((BASE / 'labels' / split).glob('*.txt')):
        classes = {line.split()[0] for line in label.read_text().splitlines() if line.strip()}
        key = 'both' if classes == {'0', '1'} else 'fire' if '0' in classes else 'smoke' if '1' in classes else 'empty'
        grouped[key].append(label)
    counts = {}
    for key, limit in limits.items():
        candidates = grouped[key]
        rng.shuffle(candidates)
        selected = candidates[:limit]
        counts[key] = len(selected)
        for label in selected:
            image = BASE / 'images' / split / (label.stem + '.jpg')
            if not image.exists():
                continue
            name = 'base_' + label.stem
            link(image, DEST / 'images' / split / (name + '.jpg'))
            link(label, DEST / 'labels' / split / (name + '.txt'))
    return counts


def add_cctv(split, samples_per_clip):
    rows = json.loads(MANIFEST.read_text())
    selected = [r for r in rows if r['dataset'] == 'SCVD (CCTV)' and r['split'] == split and r['label'] == 0]
    count = 0
    for row in selected:
        path = Path(row['path'])
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError(f'Cannot read {path}')
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for i in range(samples_per_clip):
            at = round(total * (i + 1) / (samples_per_clip + 1))
            cap.set(cv2.CAP_PROP_POS_FRAMES, at)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'Cannot decode frame {at} of {path}')
            name = f'cctv_{path.stem}_{i}'
            target = DEST / 'images' / split / (name + '.jpg')
            target.parent.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(target), frame):
                raise ValueError(f'Cannot write {target}')
            label = DEST / 'labels' / split / (name + '.txt')
            label.parent.mkdir(parents=True, exist_ok=True)
            label.write_text('')
            count += 1
        cap.release()
    return {'clips': len(selected), 'frames': count}


def main():
    global DEST
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='include every existing fire/smoke training and validation image')
    args = parser.parse_args()
    if args.full:
        DEST = ROOT / 'storage/datasets/fire_smoke_cctv_full'
    rng = random.Random(42)
    train_base = add_base('train', {'fire': 100000, 'smoke': 100000, 'both': 100000, 'empty': 100000} if args.full
                          else {'fire': 450, 'smoke': 450, 'both': 300, 'empty': 350}, rng)
    val_base = add_base('val', {'fire': 100000, 'smoke': 100000, 'both': 100000, 'empty': 100000} if args.full
                        else {'fire': 100, 'smoke': 100, 'both': 80, 'empty': 100}, rng)
    train_cctv = add_cctv('train', 3)
    val_cctv = add_cctv('val', 2)
    (DEST / 'data.yaml').write_text(yaml.safe_dump({'path': str(DEST), 'train': 'images/train',
                                                   'val': 'images/val', 'names': {0: 'fire', 1: 'smoke'}}, sort_keys=False))
    (DEST / 'provenance.json').write_text(json.dumps({'base': 'storage/datasets/fire_smoke',
        'cctv_manifest': str(MANIFEST.relative_to(ROOT)), 'excluded': ['SCVD test', 'TestVideos'],
        'train_base': train_base, 'val_base': val_base, 'train_cctv': train_cctv, 'val_cctv': val_cctv}, indent=2))
    print((DEST / 'provenance.json').read_text())


if __name__ == '__main__':
    main()
