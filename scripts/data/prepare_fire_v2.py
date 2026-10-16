"""Fire/smoke dataset v2: four open fire sources + thousands of real threat-free video frames as hard negatives.

python scripts/data/prepare_fire_v2.py
Sources: D-Fire (official split), Roboflow Fire&Smoke v9 (Kaggle roscoekerby), Roboflow fire-detection (Kaggle ironwolf437; its
'light' / 'nonfire' classes become background), Simuletic CCTV smoke/fire. Duplicate groups across ALL sources are resolved so no
held-out image has a training twin. Training is capped per source to keep a single epoch under ~5 minutes on the 6 GB card.
"""
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, Item, assign_groups, collect_yolo_split, pool_negatives, prepare_items, resolve_splits, save_provenance, write_yolo  # noqa: E402

NAMES = ['fire', 'smoke']
CAPS = {'dfire': None, 'v9': 6500, 'ironwolf': 5500}
SOURCES = [
    ('dfire', RAW / 'kaggle/dfire', 'D-Fire (Venancio et al.), Kaggle mirror sayedgamal99/smoke-fire-detection-yolo'),
    ('v9', RAW / 'kaggle/firesmoke-detection-yolo-v9', 'Roboflow Fire and Smoke Dataset, Kaggle roscoekerby/firesmoke-detection-yolo-v9'),
    ('ironwolf', RAW / 'kaggle/fire-detection-dataset', 'Roboflow fire-detection (iron-wolf), CC BY 4.0, Kaggle ironwolf437/fire-detection-dataset'),
    ('cctvsim', RAW / 'kaggle/cctv-smoke-and-fire-emergency-detection-dataset', 'Simuletic CCTV Smoke & Fire Emergency dataset (CC BY-NC 4.0)'),
]


def class_map(cfg):
    names = cfg['names']
    names = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    return {i: (NAMES.index(str(n).lower()) if str(n).lower() in NAMES else None) for i, n in names.items()}


def split_dirs(root):
    found = {}
    for split, aliases in (('train', ('train',)), ('val', ('valid', 'val')), ('test', ('test',))):
        for alias in aliases:
            if (root / alias / 'images').exists() and (root / alias / 'labels').exists():
                found[split] = alias
                break
            if (root / 'data' / alias / 'images').exists():
                found[split] = f'data/{alias}'
                break
    return found


def main():
    rng = random.Random(3)
    items, provenance = [], {'sources': {}, 'classes': NAMES}
    for source, base, citation in SOURCES:
        for yaml_path in sorted(base.rglob('data.yaml')):
            root = yaml_path.parent
            cfg = yaml.safe_load(yaml_path.read_text())
            cmap = class_map(cfg)
            dirs = split_dirs(root)
            if source == 'cctvsim':                      # flat images/ + labels/ with no splits: treat as a pool
                found = collect_yolo_split(root, source, {'pool': '.'}, cmap)
            else:
                found = collect_yolo_split(root, source, dirs, cmap)
            cap = CAPS.get(source)
            train = [i for i in found if i.split == 'train']
            if cap and len(train) > cap:
                keep = set(map(id, rng.sample(train, cap)))
                found = [i for i in found if i.split != 'train' or id(i) in keep]
            print(source, Counter(i.split for i in found), cfg['names'], flush=True)
            items += found
            provenance['sources'][source] = {'citation': citation, 'splits': dict(Counter(i.split for i in found)), 'source_names': cfg['names']}
    items += pool_negatives({'fire', 'smoke'}, hard=3500, easy=2500, val=300, test_cap=1500)
    print('collected', len(items), flush=True)
    items = prepare_items(items, ROOT / 'storage/datasets/work/fire_smoke_v2')
    groups = assign_groups(items)
    kept = resolve_splits(groups, val_fraction=0.02)
    out = ROOT / 'storage/datasets/fire_smoke_v2'
    stats = write_yolo(kept, out, NAMES)
    provenance.update(stats=stats, near_duplicates_removed=len(items) - len(kept), dedupe='dHash64 Hamming<=4 across all sources; groups assigned to the most protected split; video negatives are never deduped',
                      hard_negatives='real threat-free video frames (RLVS, hockey, SCVD, DCSASS calm categories); test negatives are the blind frames', seed=42)
    save_provenance(out, provenance)
    print(stats)


if __name__ == '__main__':
    main()
