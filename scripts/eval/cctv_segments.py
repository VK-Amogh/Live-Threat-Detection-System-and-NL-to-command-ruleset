"""CCTV weapon evaluation with segment-level cleanliness.

Un-annotated frames are only trustworthy negatives when their whole camera segment (video chunk) contains no annotated weapon.
Test segments = the held-out segments of the Seville/Granada CCTV set (same hash split as scripts/data/prepare_weapons.py).
Groups: positive frames | empty frames inside weapon segments (ambiguous, not scored as negatives) | empty frames in weapon-free segments (clean).
"""
import hashlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402
from PIL import Image  # noqa: E402


def segment_split(key):
    draw = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 1000 / 1000
    return 'test' if draw < 0.25 else 'val' if draw < 0.35 else 'train'


def main():
    folder = ROOT / 'storage/datasets/work/cctv_guns/Images'
    frames = defaultdict(list)
    for xml in sorted(folder.glob('*.xml')):
        seg = xml.stem.split('_frame_')[0]
        if segment_split(seg) != 'test':
            continue
        boxes = [o for o in ET.parse(xml).getroot().findall('object') if (o.findtext('name') or '').lower() in ('handgun', 'short_rifle', 'knife')]
        frames[seg].append((xml.with_suffix('.jpg'), bool(boxes)))
    server.load_models()
    groups = defaultdict(lambda: [0, 0])
    for seg, items in frames.items():
        has = any(p for _, p in items)
        for path, positive in items:
            if positive:
                group = 'positive'
            else:
                group = 'empty-in-weapon-segment (ambiguous)' if has else 'empty-in-weapon-free-segment (clean)'
            im = Image.open(path).convert('RGB')
            alert = any(d.category == 'WEAPON_DETECTED' for d in server.decide(server.analyse(im, None)))
            groups[group][0] += 1
            groups[group][1] += alert
    print(f'{len(frames)} test segments')
    for g, (n, a) in sorted(groups.items()):
        print(f'{g:42s} frames {n:4d}  stack alerts {a:4d}  ({a / max(n, 1):.1%})')


if __name__ == '__main__':
    main()
