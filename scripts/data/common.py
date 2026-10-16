"""Shared helpers for building leakage-free YOLO detection datasets.

Every source image is resized once (long side <= 640), perceptually hashed, and grouped with its
near-duplicates across *all* sources.  A duplicate group is assigned to a single split
(test > val > train), so no held-out image has a near-copy in the training set.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'storage/datasets/raw'
SPLIT_RANK = {'test': 0, 'val': 1, 'train': 2, 'pool': 2}  # 'pool' = source ships no official split
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


@dataclass
class Item:
    source: str
    image: Path
    split: str                              # official split in the source: train / val / test
    boxes: list[tuple[int, float, float, float, float]] = field(default_factory=list)  # cls cx cy w h
    group: str = ''
    sha: str = ''
    dhash: int = 0
    size: tuple[int, int] = (0, 0)
    negative_kind: str = ''                 # non-empty marks deliberate hard-negative images
    dedupe: bool = True                     # False: split is already leakage-safe (e.g. by video segment); keep every frame


def dhash_of(img: Image.Image) -> int:
    small = img.convert('L').resize((9, 8), Image.BILINEAR)
    px = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def _prepare(args):
    src, dst, long_side = args
    try:
        data = Path(src).read_bytes()
        sha = hashlib.sha1(data).hexdigest()
        with Image.open(src) as im:
            im = im.convert('RGB')
            w, h = im.size
            if w < 32 or h < 32:
                return src, None
            scale = long_side / max(w, h)
            out = im.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS) if scale < 1 else im
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            out.save(dst, 'JPEG', quality=92)
            return src, (sha, dhash_of(out), out.size)
    except Exception:
        return src, None


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count('1')


def prepare_items(items: list[Item], work: Path, long_side: int = 640, workers: int = 6) -> list[Item]:
    """Resize + hash every item into `work/<n>.jpg`; drops unreadable images."""
    work.mkdir(parents=True, exist_ok=True)
    jobs = [(str(it.image), str(work / f'{i:07d}.jpg'), long_side) for i, it in enumerate(items)]
    kept = []
    with ProcessPoolExecutor(workers) as pool:
        for i, (_, result) in enumerate(pool.map(_prepare, jobs, chunksize=64)):
            if result is None:
                continue
            it = items[i]
            it.sha, it.dhash, it.size = result
            it.image = Path(jobs[i][1])
            kept.append(it)
    return kept


def assign_groups(items: list[Item], max_distance: int = 4) -> dict[str, list[Item]]:
    """Union-find over near-duplicate perceptual hashes (banded lookup)."""
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    bands = [defaultdict(list) for _ in range(4)]
    for idx, it in enumerate(items):
        if not it.dedupe:
            continue
        for b in range(4):
            key = (it.dhash >> (16 * b)) & 0xFFFF
            for other in bands[b][key]:
                if hamming(items[other].dhash, it.dhash) <= max_distance:
                    ra, rb = find(idx), find(other)
                    if ra != rb:
                        parent[ra] = rb
            bands[b][key].append(idx)
    groups = defaultdict(list)
    for idx, it in enumerate(items):
        groups[str(find(idx))].append(it)
    return groups


def resolve_splits(groups: dict[str, list[Item]], val_fraction: float, seed: int = 42, pool_test_fraction: float = 0.2, pool_val_fraction: float = 0.1):
    """Leakage control at group level.

    * A group inherits the most protected official split among its members (test > val > train).
    * Members that live in a *less* protected split than their group are dropped (they are near-copies of
      held-out images).
    * Held-out splits keep one representative per group (duplicates would inflate metrics);
      train-only groups keep every member and are randomly sent to val with `val_fraction`
      (group level, so a val image never has a train twin).
    """
    rng = random.Random(seed)
    kept = []
    for key in sorted(groups):
        members = groups[key]
        rank = min(SPLIT_RANK[m.split] for m in members)
        top = [m for m in members if SPLIT_RANK[m.split] == rank]
        if rank == SPLIT_RANK['train']:
            draw = rng.random()
            if any(m.split == 'pool' for m in top):
                split = 'test' if draw < pool_test_fraction else 'val' if draw < pool_test_fraction + pool_val_fraction else 'train'
            else:
                split = 'val' if draw < val_fraction else 'train'
            if split == 'test':  # held-out splits keep one representative per group
                top.sort(key=lambda m: -len(m.boxes))
                top = top[:1]
            for m in top:
                m.split = split
            kept += top
        else:
            top.sort(key=lambda m: -len(m.boxes))
            kept.append(top[0])
    return kept


def write_yolo(items: list[Item], out: Path, names: list[str]) -> dict:
    if out.exists():
        shutil.rmtree(out)
    counts = {s: Counter() for s in ('train', 'val', 'test')}
    images = Counter()
    for it in items:
        for folder in ('images', 'labels'):
            (out / folder / it.split).mkdir(parents=True, exist_ok=True)
        stem = f'{it.source}_{it.sha[:16]}'
        shutil.copy2(it.image, out / 'images' / it.split / f'{stem}.jpg')
        lines = [f'{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}' for c, x, y, w, h in it.boxes]
        (out / 'labels' / it.split / f'{stem}.txt').write_text('\n'.join(lines))
        images[it.split] += 1
        if not it.boxes:
            counts[it.split]['__background__'] += 1
        for c, *_ in it.boxes:
            counts[it.split][names[c]] += 1
    import yaml
    (out / 'data.yaml').write_text(yaml.safe_dump({'path': str(out), 'train': 'images/train', 'val': 'images/val', 'test': 'images/test', 'names': dict(enumerate(names))}))
    return {'images': dict(images), 'instances': {s: dict(c) for s, c in counts.items()}}


def read_yolo_labels(path: Path, class_map: dict[int, int | None]) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    if not path.exists():
        return boxes
    for line in path.read_text(errors='replace').splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            cls = int(float(parts[0]))
            vals = [float(v) for v in parts[1:]]
        except ValueError:
            continue
        mapped = class_map.get(cls)
        if mapped is None:
            continue
        if len(vals) == 4:
            cx, cy, w, h = vals
        else:  # polygon -> enclosing box
            xs, ys = vals[0::2], vals[1::2]
            cx, cy, w, h = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)
        x1, y1, x2, y2 = max(0, cx - w / 2), max(0, cy - h / 2), min(1, cx + w / 2), min(1, cy + h / 2)
        if x2 - x1 < 0.004 or y2 - y1 < 0.004:
            continue
        boxes.append((mapped, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1))
    return boxes


def collect_yolo_split(root: Path, source: str, split_dirs: dict[str, str], class_map: dict[int, int | None], image_sub='images', label_sub='labels') -> list[Item]:
    """Collect images from a `<split>/images` + `<split>/labels` layout."""
    items = []
    for split, folder in split_dirs.items():
        images = root / folder / image_sub
        labels = root / folder / label_sub
        if not images.exists():
            continue
        for img in sorted(images.iterdir()):
            # An image without a label file is *unlabeled*, not a negative (partial downloads, missing annotations).
            if img.suffix.lower() in IMAGE_SUFFIXES and (labels / (img.stem + '.txt')).exists():
                items.append(Item(source, img, split, read_yolo_labels(labels / (img.stem + '.txt'), class_map)))
    return items


def save_provenance(out: Path, info: dict):
    (out / 'provenance.json').write_text(json.dumps(info, indent=2))
