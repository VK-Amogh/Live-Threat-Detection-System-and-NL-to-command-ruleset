"""Build the weapons YOLO dataset (gun, knife) from real-CCTV and curated web sources.

python scripts/data/prepare_weapons.py
Canonical classes: 0 gun (handgun + rifles/firearms), 1 knife.
Sources
  * cctv_guns : Univ. of Granada/Seville real CCTV frames, 1920x1080, VOC XML (Handgun, Short_rifle, Knife).
                Split by camera *segment* (video chunk) so adjacent frames never straddle train/test.
  * haris     : HARIS curated weapons set (Kaggle turkikhalidalshuaibi/haris-weapon-detection-dataset-curated),
                YOLO format, includes UCF-Crime hard negatives; its `val` split is held out as test.
Near-duplicate groups (perceptual hash) are resolved so no held-out image has a training twin.
"""
import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, Item, assign_groups, collect_yolo_split, prepare_items, resolve_splits, save_provenance, write_yolo  # noqa: E402

NAMES = ['gun', 'knife']
WORK = ROOT / 'storage/datasets/work'
VOC_MAP = {'handgun': 0, 'short_rifle': 0, 'rifle': 0, 'pistol': 0, 'gun': 0, 'knife': 1}


def segment_split(key: str) -> str:
    draw = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 1000 / 1000
    return 'test' if draw < 0.25 else 'val' if draw < 0.35 else 'train'


def cctv_guns(include_empty: bool = True) -> list[Item]:
    folder = WORK / 'cctv_guns/Images'
    if not folder.exists():
        return []
    items, negatives = [], []
    for xml in sorted(folder.glob('*.xml')):
        image = xml.with_suffix('.jpg')
        if not image.exists():
            continue
        root = ET.parse(xml).getroot()
        w, h = float(root.findtext('size/width')), float(root.findtext('size/height'))
        boxes = []
        for obj in root.findall('object'):
            cls = VOC_MAP.get((obj.findtext('name') or '').lower())
            b = obj.find('bndbox')
            if cls is None or b is None:
                continue
            x1, y1, x2, y2 = [float(b.findtext(k)) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
            x1, x2, y1, y2 = max(0, x1), min(w, x2), max(0, y1), min(h, y2)
            if x2 - x1 > 3 and y2 - y1 > 3:
                boxes.append((cls, (x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h))
        parts = xml.stem.split('_frame_')[0]  # CamN-From..To_Segment_K_x264
        # Fixed cameras make neighbouring frames perceptually identical; the split is by video segment instead.
        item = Item('cctv', image, segment_split(parts), boxes, dedupe=False)
        (items if boxes else negatives).append(item)
    # Un-annotated CCTV frames are NOT reliable negatives: reviewing the verifier's top 'false alarms' showed real handguns in
    # frames with no annotation. v1 trained on half of them as background; v2 (include_empty=False) drops them and uses
    # video frames from other sources as negatives instead.
    keep = max(len(items) // 2, 1) if include_empty else 0
    negatives.sort(key=lambda i: hashlib.sha1(str(i.image).encode()).hexdigest())
    return items + negatives[:keep]


def haris() -> list[Item]:
    base = RAW / 'kaggle/haris'
    out = []
    if not base.exists():
        return out
    for yaml_path in base.rglob('data.yaml'):
        root = yaml_path.parent
        cfg = yaml.safe_load(yaml_path.read_text())
        names = cfg['names'] if isinstance(cfg['names'], list) else [cfg['names'][k] for k in sorted(cfg['names'])]
        cmap = {i: (0 if n.lower() in ('gun', 'pistol', 'handgun', 'rifle') else 1 if n.lower() == 'knife' else None) for i, n in enumerate(names)}
        # Official `val` is a held-out split in this set; `train` carries a 5% group-level validation slice.
        out += collect_yolo_split(root, 'haris', {'train': 'train', 'test': 'val'}, cmap)
    return out


def main():
    items = cctv_guns() + haris()
    counts = Counter((i.source, i.split) for i in items)
    print('collected', len(items), dict(counts))
    items = prepare_items(items, WORK / 'weapons', long_side=800)
    groups = assign_groups(items)
    kept = resolve_splits(groups, val_fraction=0.05)
    out = ROOT / 'storage/datasets/weapons'
    stats = write_yolo(kept, out, NAMES)
    by_source = Counter((i.source, i.split) for i in kept)
    save_provenance(out, {'classes': NAMES, 'stats': stats, 'by_source_split': {f'{k[0]}/{k[1]}': v for k, v in by_source.items()},
                          'sources': {'cctv': 'jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset (Hugging Face, CC BY-NC 4.0), split by camera segment',
                                      'haris': 'Kaggle turkikhalidalshuaibi/haris-weapon-detection-dataset-curated (CC BY 4.0)'},
                          'dedupe': 'dHash64 Hamming<=4, group assigned to most protected split', 'seed': 42})
    print(stats)
    print(dict(by_source))


if __name__ == '__main__':
    main()
