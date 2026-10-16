"""Weapons dataset v2: real CCTV frames + HARIS + Granada pistol/knife detection sets + real video frames as hard negatives.

python scripts/data/prepare_weapons_v2.py
Canonical classes: 0 gun (pistol, handgun, short rifle), 1 knife.
  cctv     Seville/Granada real CCTV (1920x1080), split by camera segment, no perceptual dedupe (fixed cameras)
  haris    curated web set, its `val` split held out as test
  pistol   Granada "Pistol detection" (3000 frames, many 160x120 surveillance-style), VOC XML
  knife    Granada "Knife_detection" (2078 frames, 1280x720), VOC XML
  video*   threat-free frames from RLVS / hockey / SCVD / DCSASS calm categories (hard negatives; test frames never trained on)
"""
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, ROOT, Item, assign_groups, pool_negatives, prepare_items, resolve_splits, save_provenance, write_yolo  # noqa: E402
from prepare_weapons import cctv_guns, haris  # noqa: E402

NAMES = ['gun', 'knife']
GRANADA = RAW / 'shravya11__weapon-detection-dataset'
VOC = {'pistol': 0, 'handgun': 0, 'gun': 0, 'knife': 1}


def granada(part: str, image_dirs: tuple[str, ...], xml_dirs: tuple[str, ...], source: str) -> list[Item]:
    items = []
    for xml in sorted((GRANADA / part).glob('*/*/*.xml')):
        if xml.parent.name not in xml_dirs:
            continue
        root = ET.parse(xml).getroot()
        w, h = float(root.findtext('size/width') or 0), float(root.findtext('size/height') or 0)
        if not w or not h:
            continue
        image = next((p for d in image_dirs for p in (xml.parent.parent / d).glob(xml.stem + '.*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png')), None)
        if image is None:
            name = root.findtext('filename')
            image = next((p for d in image_dirs for p in (xml.parent.parent / d).glob(Path(name or 'x').stem + '.*')), None) if name else None
        if image is None:
            continue
        boxes = []
        for obj in root.findall('object'):
            cls = VOC.get((obj.findtext('name') or '').lower())
            b = obj.find('bndbox')
            if cls is None or b is None:
                continue
            x1, y1, x2, y2 = [float(b.findtext(k)) for k in ('xmin', 'ymin', 'xmax', 'ymax')]
            x1, x2, y1, y2 = max(0, x1), min(w, x2), max(0, y1), min(h, y2)
            if x2 - x1 > 3 and y2 - y1 > 3:
                boxes.append((cls, (x1 + x2) / 2 / w, (y1 + y2) / 2 / h, (x2 - x1) / w, (y2 - y1) / h))
        if boxes:
            items.append(Item(source, image, 'pool', boxes))
    return items


def main():
    items = cctv_guns(include_empty=False) + haris() + granada('Pistol detection', ('Weapons',), ('xmls',), 'pistol') + granada('Knife_detection', ('Images',), ('annotations',), 'knife')
    print('labelled', Counter((i.source, i.split) for i in items), flush=True)
    items += pool_negatives({'gun', 'knife'}, hard=4000, easy=2500, val=300, test_cap=1500)
    items = prepare_items(items, ROOT / 'storage/datasets/work/weapons_v2', long_side=800)
    groups = assign_groups(items)
    kept = resolve_splits(groups, val_fraction=0.04)
    out = ROOT / 'storage/datasets/weapons_v2'
    stats = write_yolo(kept, out, NAMES)
    by_source = Counter((i.source, i.split) for i in kept)
    save_provenance(out, {'classes': NAMES, 'stats': stats, 'by_source_split': {f'{k[0]}/{k[1]}': v for k, v in by_source.items()},
                          'sources': {'cctv': 'jsalazar/US-Real-time-gun-detection-in-CCTV (HF, CC BY-NC 4.0), by camera segment', 'haris': 'Kaggle turkikhalidalshuaibi/haris-weapon-detection-dataset-curated (CC BY 4.0)',
                                      'pistol': 'Granada pistol detection (HF shravya11/weapon-detection-dataset)', 'knife': 'Granada knife detection (same repo)'},
                          'dedupe': 'dHash64 Hamming<=4 (not for CCTV segments or video negatives)', 'seed': 42})
    print(stats)
    print(dict(by_source))


if __name__ == '__main__':
    main()
