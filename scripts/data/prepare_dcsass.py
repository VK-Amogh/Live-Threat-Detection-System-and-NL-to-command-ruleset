"""Index DCSASS (UCF-Crime CCTV, 4 s clips at 320x240) with leakage-safe parent-video splits.

python scripts/data/prepare_dcsass.py
* Labels: Labels/<Category>.csv gives 1 = anomalous sub-clip, 0 = normal sub-clip of an anomaly video.
* Split by PARENT video (all sub-clips of one source video stay together): `blind` (30%) is never used for
  training, mining or threshold selection; `dev` (70%) feeds hard-negative mining and training.
* Frames for the image-level negative pool are taken from clips that cannot contain the threat in question:
  every label-0 clip, plus whole categories without fire/weapons (RoadAccidents, Shoplifting, Stealing).
Outputs: storage/datasets/dcsass/manifest.json and frames in storage/datasets/negpool/dcsass/<split>/ (index appended).
"""
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from extract_frames import grab  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'storage/datasets/raw/kaggle/dcsass/DCSASS Dataset'
OUT = ROOT / 'storage/datasets/dcsass'
POOL = ROOT / 'storage/datasets/negpool'
CLEAN_CATEGORIES = {'RoadAccidents', 'Shoplifting', 'Stealing'}   # no fire / weapon scenes expected in these anomaly types


def parent_split(parent: str) -> str:
    return 'blind' if int(hashlib.sha1(parent.encode()).hexdigest(), 16) % 100 < 30 else 'dev'


def main():
    rows = []
    for csv_path in sorted((BASE / 'Labels').glob('*.csv')):
        category = csv_path.stem
        for fields in csv.reader(csv_path.open()):
            if len(fields) < 3 or fields[2].strip() not in ('0', '1'):
                continue  # header / malformed rows
            name, cat, label = fields[0], fields[1], fields[2].strip()
            parent = name.rsplit('_', 1)[0]
            clip = BASE / category / (parent + '.mp4') / (name + '.mp4')
            if clip.exists():
                rows.append({'path': str(clip), 'clip': name, 'parent': parent, 'category': category, 'label': int(label), 'split': parent_split(parent)})
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / 'manifest.json').write_text(json.dumps(rows))
    print(len(rows), 'clips', dict(Counter((r['split'], r['category']) for r in rows if r['label'] == 1)))
    print('parents', len({r['parent'] for r in rows}), 'blind parents', len({r['parent'] for r in rows if r['split'] == 'blind'}))

    jobs, meta = [], []
    for r in rows:
        if r['label'] == 0 or r['category'] in CLEAN_CATEGORIES:
            if r['category'] == 'Shooting' and r['label'] == 0:
                continue
            split = 'test' if r['split'] == 'blind' else ('val' if int(hashlib.sha1(r['parent'].encode()).hexdigest(), 16) % 10 == 0 else 'train')
            folder = POOL / 'dcsass' / split
            folder.mkdir(parents=True, exist_ok=True)
            jobs.append((r['path'], str(folder), r['clip'], 2))
            meta.append((split, r['clip'], r['parent']))
    index = []
    with ProcessPoolExecutor(6) as pool:
        for (split, clip, parent), paths in zip(meta, pool.map(grab, jobs, chunksize=16)):
            index += [{'path': p, 'source': 'dcsass', 'split': split, 'clip': clip, 'group': f'dcsass:{parent}'} for p in paths]
    existing = json.loads((POOL / 'index.json').read_text())
    existing = [e for e in existing if e['source'] != 'dcsass']
    (POOL / 'index.json').write_text(json.dumps(existing + index))
    print(len(index), 'dcsass negative frames', dict(Counter(i['split'] for i in index)))


if __name__ == '__main__':
    main()
