"""Build the leakage-free fire/smoke YOLO dataset from D-Fire (Kaggle mirror) and Jimei (Hugging Face).

python scripts/data/prepare_fire.py
Canonical classes: 0 fire, 1 smoke.  Official test/val splits are kept held out; near-duplicate groups
(perceptual hash, Hamming <= 4) are resolved to a single split so no held-out image has a training copy.
"""
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, Item, assign_groups, collect_yolo_split, prepare_items, resolve_splits, save_provenance, write_yolo  # noqa: E402

NAMES = ['fire', 'smoke']
SOURCES = [
    ('dfire', RAW / 'kaggle/dfire', 'D-Fire (Venancio et al.), Kaggle mirror sayedgamal99/smoke-fire-detection-yolo'),
    ('jimei', RAW / 'betasecond__jimei-fire-smoke-yolo-dataset', 'Hugging Face betasecond/jimei-fire-smoke-yolo-dataset'),  # skipped until fully downloaded
]


def find_dataset_roots(base: Path):
    """Yield directories that hold a data.yaml (the zip may nest one level)."""
    for yaml_path in base.rglob('data.yaml'):
        yield yaml_path.parent, yaml.safe_load(yaml_path.read_text())


def class_map_from(cfg) -> dict[int, int | None]:
    names = cfg['names']
    names = dict(enumerate(names)) if isinstance(names, list) else {int(k): v for k, v in names.items()}
    out = {}
    for idx, name in names.items():
        low = str(name).lower()
        out[idx] = NAMES.index('fire') if low == 'fire' else NAMES.index('smoke') if low == 'smoke' else None
    return out


def split_dirs(root: Path):
    mapping = {}
    for split, aliases in (('train', ('train',)), ('val', ('valid', 'val', 'validation')), ('test', ('test',))):
        for alias in aliases:
            for prefix in ('', 'data/'):
                if (root / prefix / alias / 'images').exists() and (root / prefix / alias / 'labels').exists():
                    mapping[split] = prefix + alias
                    break
            if split in mapping:
                break
    return mapping


def main():
    items: list[Item] = []
    provenance = {'sources': {}, 'classes': NAMES}
    for source, base, citation in SOURCES:
        if not base.exists():
            print('skip (not downloaded):', source)
            continue
        for root, cfg in find_dataset_roots(base):
            dirs = split_dirs(root)
            cmap = class_map_from(cfg)
            found = collect_yolo_split(root, source, dirs, cmap)
            print(source, root.name, {k: v for k, v in Counter(i.split for i in found).items()}, 'classes', cfg['names'])
            items += found
            provenance['sources'][source] = {'citation': citation, 'split_dirs': dirs, 'source_names': cfg['names'], 'images': len(found)}
    print('collected', len(items))
    items = prepare_items(items, ROOT / 'storage/datasets/work/fire_smoke')
    print('prepared', len(items))
    groups = assign_groups(items)
    kept = resolve_splits(groups, val_fraction=0.0)
    dropped = len(items) - len(kept)
    out = ROOT / 'storage/datasets/fire_smoke'
    stats = write_yolo(kept, out, NAMES)
    provenance.update(stats=stats, near_duplicates_removed=dropped, dedupe='dHash64 Hamming<=4, group assigned to most protected split', seed=42)
    save_provenance(out, provenance)
    print(stats, 'dropped duplicates:', dropped)


if __name__ == '__main__':
    main()
