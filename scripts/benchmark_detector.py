"""Held-out benchmark for a YOLO detector domain, with operating-point calibration and incumbent comparison.

python scripts/benchmark_detector.py --name fire_smoke --weights storage/training/<run>/weights/best.pt \
    --data storage/datasets/fire_smoke/data.yaml [--incumbent storage/models/fire.pt --map fire=fire]

Method
  * Detections are collected once at a very low confidence for the val and test splits.
  * Per class, the confidence threshold is chosen on **val** (max F1 with precision >= --min-precision when
    reachable) and then applied unchanged to **test**.  Test data never influences a threshold.
  * Reported on test: AP50 / AP50-95 (ultralytics), object P/R/F1 at the operating threshold, image-level
    alert precision / recall / false-alarm rate on images that contain no labelled threat, latency, VRAM.
  * An incumbent weight file is scored on the identical test images (class names mapped via --map).
Writes storage/benchmarks/<name>.json and updates storage/models/<name>.json (thresholds sidecar).
"""
import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'storage/benchmarks'
IMG_SUFFIX = {'.jpg', '.jpeg', '.png'}


def load_gt(label_file: Path, w: int, h: int):
    boxes = []
    if label_file.exists():
        for line in label_file.read_text().splitlines():
            p = line.split()
            if len(p) >= 5:
                c, cx, cy, bw, bh = int(p[0]), *map(float, p[1:5])
                boxes.append((c, (cx - bw / 2) * w, (cy - bh / 2) * h, (cx + bw / 2) * w, (cy + bh / 2) * h))
    return boxes


def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0


def collect(model, images, labels_dir, names, class_alias=None, imgsz=640, batch=32, device='0'):
    """-> list of dict(gt=[(cls,x1,y1,x2,y2)], det=[(cls,conf,x1,y1,x2,y2)])  (classes in canonical names)."""
    records = []
    for i in range(0, len(images), batch):
        chunk = images[i:i + batch]
        results = model.predict([str(p) for p in chunk], imgsz=imgsz, conf=0.02, iou=0.6, device=device, half=True, verbose=False, max_det=100)
        for path, res in zip(chunk, results):
            h, w = res.orig_shape
            gt = [(names[c], *b) for c, *b in load_gt(labels_dir / (path.stem + '.txt'), w, h)]
            det = []
            for b in res.boxes:
                cname = res.names[int(b.cls)]
                cname = class_alias.get(cname, cname) if class_alias else cname
                det.append((cname, float(b.conf), *b.xyxy[0].tolist()))
            records.append({'gt': gt, 'det': det, 'source': path.stem.split('_')[0]})
    return records


def match_at(records, cls, thr):
    tp = fp = fn = 0
    for r in records:
        gts = [g for g in r['gt'] if g[0] == cls]
        dets = sorted([d for d in r['det'] if d[0] == cls and d[1] >= thr], key=lambda d: -d[1])
        used = set()
        for d in dets:
            best, bi = 0.0, -1
            for gi, g in enumerate(gts):
                if gi in used:
                    continue
                v = iou(d[2:], g[1:])
                if v > best:
                    best, bi = v, gi
            if best >= 0.5:
                tp += 1
                used.add(bi)
            else:
                fp += 1
        fn += len(gts) - len(used)
    return tp, fp, fn


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def choose_threshold(records, cls, min_precision):
    best = None
    grid = np.round(np.arange(0.05, 0.96, 0.025), 3)
    for t in grid:
        p, r, f = prf(*match_at(records, cls, t))
        feasible = p >= min_precision
        key = (feasible, f if feasible else p)
        if best is None or key > best[0]:
            best = (key, float(t), p, r, f)
    return best[1]


def image_level(records, thresholds, classes):
    """Image alert = any detection above its class threshold. Positive image = has any GT of those classes."""
    tp = fp = fn = tn = 0
    for r in records:
        positive = any(g[0] in classes for g in r['gt'])
        alert = any(d[0] in classes and d[1] >= thresholds[d[0]] for d in r['det'])
        if positive and alert:
            tp += 1
        elif positive:
            fn += 1
        elif alert:
            fp += 1
        else:
            tn += 1
    p, r_, f = prf(tp, fp, fn)
    return {'precision': p, 'recall': r_, 'f1': f, 'false_alarm_rate_on_clean_images': fp / (fp + tn) if fp + tn else 0.0, 'images': {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}}


def regroup(records, groups, thresholds=None):
    """Relabel classes into comparison groups (e.g. gun+knife -> weapon). With `thresholds`, detections below
    their own class threshold are dropped first, so the group alert means 'any member class alerted'."""
    def group_of(name):
        return next((g for g, members in groups.items() if name in members), name)
    out = []
    for r in records:
        dets = [(group_of(d[0]), *d[1:]) for d in r['det'] if thresholds is None or d[1] >= thresholds.get(d[0], 0)]
        out.append({'gt': [(group_of(g[0]), *g[1:]) for g in r['gt']], 'det': dets, 'source': r['source']})
    return out


def by_source(records, thresholds, classes):
    sources = sorted({r['source'] for r in records})
    out = {}
    for s_ in sources:
        subset = [r for r in records if r['source'] == s_]
        out[s_] = {'images': len(subset), 'clean_images': sum(1 for r in subset if not r['gt']), **image_level(subset, thresholds, classes)}
    return out


def latency(model, sample, device='0', runs=60, imgsz=640):
    torch.cuda.reset_peak_memory_stats()
    for _ in range(8):
        model.predict(sample, imgsz=imgsz, device=device, half=True, verbose=False)
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        model.predict(sample, imgsz=imgsz, device=device, half=True, verbose=False)
        times.append((time.perf_counter() - t) * 1000)
    return {'median_ms': round(statistics.median(times), 2), 'p95_ms': round(float(np.percentile(times, 95)), 2), 'peak_vram_mb': round(torch.cuda.max_memory_allocated() / 1e6)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--weights', required=True)
    ap.add_argument('--data', required=True)
    ap.add_argument('--incumbent', action='append', default=[])
    ap.add_argument('--map', action='append', default=[], help='incumbent_class=comparison_group (repeatable)')
    ap.add_argument('--group', action='append', default=[], help='comparison_group=class1,class2 of the NEW model (repeatable), e.g. weapon=gun,knife')
    ap.add_argument('--min-precision', type=float, default=0.80)
    ap.add_argument('--device', default='0')
    ap.add_argument('--imgsz', type=int, default=None, help='defaults to the size the weights were trained at (args.yaml)')
    ap.add_argument('--export-to', default=None, help='copy weights here when written (deployment path)')
    a = ap.parse_args()

    from ultralytics import YOLO
    cfg = yaml.safe_load(Path(a.data).read_text())
    root = Path(cfg['path'])
    names = {int(k): v for k, v in cfg['names'].items()}
    split_images = {s: sorted(p for p in (root / cfg[s]).iterdir() if p.suffix.lower() in IMG_SUFFIX) for s in ('val', 'test')}
    model = YOLO(a.weights)
    args_file = Path(a.weights).parent.parent / 'args.yaml'
    imgsz = a.imgsz or (yaml.safe_load(args_file.read_text()).get('imgsz', 640) if args_file.exists() else 640)
    records = {s: collect(model, imgs, root / 'labels' / s, names, imgsz=imgsz, device=a.device) for s, imgs in split_images.items()}
    classes = list(names.values())

    thresholds = {c: choose_threshold(records['val'], c, a.min_precision) for c in classes}
    per_class = {}
    for c in classes:
        tp, fp, fn = match_at(records['test'], c, thresholds[c])
        p, r, f = prf(tp, fp, fn)
        per_class[c] = {'threshold': thresholds[c], 'precision': p, 'recall': r, 'f1': f, 'tp': tp, 'fp': fp, 'fn': fn,
                        'test_instances': tp + fn}
    official = model.val(data=a.data, split='test', imgsz=imgsz, batch=16, device=a.device, workers=2, plots=False, verbose=False)
    for i, c in enumerate(classes):
        per_class[c]['ap50'] = float(official.box.ap50[i])
        per_class[c]['ap50_95'] = float(official.box.ap[i])
    clean_test = sum(1 for r in records['test'] if not r['gt'])
    import cv2
    sample = cv2.imread(str(split_images['test'][0]))  # decoded once: latency covers resize + inference + NMS, not disk I/O
    report = {
        'name': a.name, 'weights': a.weights, 'generated_at': time.time(),
        'splits': {s: len(v) for s, v in split_images.items()}, 'clean_test_images': clean_test,
        'selection_rule': f'per-class threshold from val: max F1 with precision >= {a.min_precision} when reachable',
        'overall': {'mAP50': float(official.box.map50), 'mAP50_95': float(official.box.map), 'precision': float(official.box.mp), 'recall': float(official.box.mr)},
        'per_class': per_class,
        'image_level': image_level(records['test'], thresholds, set(classes)),
        'latency': latency(model, sample, a.device, imgsz=imgsz), 'imgsz': imgsz,
    }

    alias = dict(m.split('=') for m in a.map)
    groups = {g.split('=')[0]: g.split('=')[1].split(',') for g in a.group} or {c: [c] for c in set(alias.values())}
    report['by_source'] = by_source(records['test'], thresholds, set(classes))
    comparisons = []
    for inc in a.incumbent:
        inc_model = YOLO(inc)
        inc_val = regroup(collect(inc_model, split_images['val'], root / 'labels' / 'val', names, class_alias=alias, imgsz=imgsz, device=a.device), groups)
        inc_test = regroup(collect(inc_model, split_images['test'], root / 'labels' / 'test', names, class_alias=alias, imgsz=imgsz, device=a.device), groups)
        row = {'weights': inc, 'classes_compared': {}}
        for g in groups:
            t = choose_threshold(inc_val, g, a.min_precision)
            p, r, f = prf(*match_at(inc_test, g, t))
            row['classes_compared'][g] = {'threshold': t, 'precision': p, 'recall': r, 'f1': f}
        row['image_level'] = image_level(inc_test, {g: row['classes_compared'][g]['threshold'] for g in groups}, set(groups))
        row['by_source'] = by_source(inc_test, {g: row['classes_compared'][g]['threshold'] for g in groups}, set(groups))
        comparisons.append(row)
    report['incumbents'] = comparisons
    if comparisons:  # like-for-like: new model's alerts re-expressed in the same groups (any member class above its own threshold)
        new_grouped = regroup(records['test'], groups, thresholds)
        report['image_level_comparable'] = {'classes': sorted(groups), **image_level(new_grouped, {g: 0.0 for g in groups}, set(groups))}
        report['by_source_comparable'] = by_source(new_grouped, {g: 0.0 for g in groups}, set(groups))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{a.name}.json').write_text(json.dumps(report, indent=2))
    if a.export_to:
        dst = ROOT / a.export_to
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(Path(a.weights).read_bytes())
        (dst.with_suffix('.json')).write_text(json.dumps({'name': a.name, 'classes': classes, 'thresholds': thresholds, 'imgsz': imgsz, 'benchmark': f'storage/benchmarks/{a.name}.json'}, indent=2))
    print(json.dumps({k: report[k] for k in ('overall', 'image_level', 'latency')}, indent=2))


if __name__ == '__main__':
    main()
