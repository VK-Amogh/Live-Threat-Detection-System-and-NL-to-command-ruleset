"""Train and calibrate the detection verifier; report on held-out validation/test detections.

python scripts/verify/train_verifier.py
Operating thresholds are chosen on validation only: per class, the lowest verifier probability whose frame-level
false-alarm rate on threat-free validation frames stays below --far, which maximises recall under that constraint.
Everything on the test split (including the blind video-frame negatives) is read once for the report.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from verifier import CLASSES, VerifierMLP  # noqa: E402


CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}


def load():
    """Main set + real-CCTV adaptation positives; DCSASS negatives restricted to calm categories (label noise otherwise:
    'normal' sub-clips of Arson/Explosion/Shooting videos can show the event)."""
    root = ROOT / 'storage/datasets/verifier'
    X = np.load(root / 'features.npy')
    G = np.load(root / 'global.npy')
    meta = json.loads((root / 'meta.json').read_text())
    if (root / 'meta_adapt.json').exists():
        extra = json.loads((root / 'meta_adapt.json').read_text())
        for r in extra:
            r['gi'] += len(G)
        X = np.concatenate([X, np.load(root / 'features_adapt.npy')])
        G = np.concatenate([G, np.load(root / 'global_adapt.npy')])
        meta = meta + extra
    clip_category = {r['clip']: r['category'] for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text())}
    keep = []
    for i, r in enumerate(meta):
        if r['source'] == 'dcsass' and r['kind'] in ('neg', 'rand'):
            clip = Path(r['path']).stem.rsplit('_', 1)[0]
            if clip_category.get(clip) not in CALM:
                continue
        keep.append(i)
    if len(keep) != len(meta):
        X, meta = X[keep], [meta[i] for i in keep]
    return X, G, meta


def calm_negpool():
    clip_category = {r['clip']: r['category'] for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text())}
    return [i for i in json.loads((ROOT / 'storage/datasets/negpool/index.json').read_text())
            if i['source'] != 'dcsass' or clip_category.get(Path(i['path']).stem.rsplit('_', 1)[0]) in CALM]


def alerts_by_image(meta, idx, prob, cls, thr):
    """image path -> True if any record of class `cls` with prob >= thr."""
    hit = defaultdict(bool)
    for i, p in zip(idx, prob):
        if meta[i]['cls'] == cls:
            hit[meta[i]['path']] |= bool(p >= thr)
    return hit


def operating_points(meta, split, prob_by_index, far, min_thr=0.5):
    """Per class: threshold meeting the frame-level FAR on negative frames of `split`, and the resulting recall."""
    neg_frames = defaultdict(list)
    pos_images = defaultdict(set)
    for i, r in enumerate(meta):
        if r['split'] != split:
            continue
        if r['kind'] == 'neg':
            neg_frames[r['path']].append(i)
        if r['kind'] in ('gt', 'det') and r['label'] == 1:
            pos_images[r['cls']].add(r['path'])
    # frames with no detection never alert, so they only dilute the denominator
    all_neg = {i['path'] for i in calm_negpool() if i['split'] == split}
    result = {}
    for c in CLASSES:
        grid = np.round(np.linspace(min_thr, 0.995, 140), 4)
        chosen = None
        for t in grid:
            alerting = {path for path, ids in neg_frames.items() if any(meta[i]['cls'] == c and prob_by_index[i] >= t for i in ids)}
            frame_far = len(alerting) / max(len(all_neg), 1)
            if frame_far <= far:
                chosen = (float(t), frame_far)
                break
        chosen = chosen or (float(grid[-1]), 0.0)
        det_pos = defaultdict(float)
        for i, r in enumerate(meta):
            if r['split'] == split and r['cls'] == c and r['kind'] == 'det' and r['label'] == 1:
                det_pos[r['path']] = max(det_pos[r['path']], prob_by_index.get(i, 0))
        recall = float(np.mean([p >= chosen[0] for p in det_pos.values()])) if det_pos else None
        result[c] = {'threshold': chosen[0], 'val_frame_far': chosen[1], 'val_recall_of_detected': recall}
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=25)
    ap.add_argument('--min-thr', type=float, default=0.6, help='never alert below this verifier probability, whatever the validation negatives say')
    ap.add_argument('--far', type=float, default=0.001, help='target frame-level false-alarm rate on threat-free validation frames')
    a = ap.parse_args()
    X, G, meta = load()
    gi = np.array([r['gi'] for r in meta])
    y = np.array([r['label'] for r in meta], dtype=np.float32)
    split = np.array([r['split'] for r in meta])
    cls = np.array([CLASSES.index(r['cls']) for r in meta])
    kind = np.array([r['kind'] for r in meta])
    device = 'cuda'
    train = np.where(split == 'train')[0]
    w = np.where(np.isin(kind[train], ['det', 'neg']), 2.0, 1.0).astype(np.float32)     # hard negatives count double
    Xt, Gt, yt, ct, wt = (torch.from_numpy(X[train].astype(np.float32)).to(device), torch.from_numpy(G[gi[train]].astype(np.float32)).to(device),
                          torch.from_numpy(y[train]).to(device), torch.from_numpy(cls[train]).to(device), torch.from_numpy(w).to(device))
    torch.manual_seed(0)
    model = VerifierMLP().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.05)
    steps = a.epochs * (len(train) // 512 + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=steps, pct_start=0.1)
    bce = nn.BCEWithLogitsLoss(reduction='none')
    started = time.time()
    for epoch in range(a.epochs):
        model.train()
        perm = torch.randperm(len(train), device=device)
        for i in range(0, len(train), 512):
            b = perm[i:i + 512]
            loss = (bce(model(Xt[b] + 0.02 * torch.randn_like(Xt[b]) * Xt[b].std(), Gt[b], ct[b]), yt[b]) * wt[b]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
    model.eval()
    prob = np.zeros(len(meta), dtype=np.float32)
    with torch.no_grad():
        for i in range(0, len(meta), 4096):
            prob[i:i + 4096] = torch.sigmoid(model(torch.from_numpy(X[i:i + 4096].astype(np.float32)).to(device), torch.from_numpy(G[gi[i:i + 4096]].astype(np.float32)).to(device), torch.from_numpy(cls[i:i + 4096]).to(device))).cpu().numpy()

    prob_by_index = {i: float(p) for i, p in enumerate(prob)}
    report = {'generated_at': time.time(), 'train_records': int(len(train)), 'train_seconds': round(time.time() - started), 'auc': {}, 'far_target': a.far}
    realistic = np.isin(kind, ['det', 'neg'])          # actual detector outputs: what the verifier sees at runtime
    for s in ('val', 'test'):
        m = (split == s) & realistic
        report['auc'][s] = {'all': float(roc_auc_score(y[m], prob[m]))}
        for c, name in enumerate(CLASSES):
            mc = m & (cls == c)
            if len(set(y[mc])) > 1:
                report['auc'][s][name] = float(roc_auc_score(y[mc], prob[mc]))
        # how much does the verifier improve on the detector's own confidence?
        conf = np.array([r.get('conf', 0.0) for r in meta])
        mm = m & (conf > 0)
        report['auc'][s]['yolo_confidence_only'] = float(roc_auc_score(y[mm], conf[mm]))
    points = operating_points(meta, 'val', prob_by_index, a.far, a.min_thr)
    report['operating_points'] = points
    # Test: frame-level FAR on blind negative frames and recall on detected positives at the val-chosen thresholds
    all_neg = defaultdict(set)
    for i in calm_negpool():
        if i['split'] == 'test':
            all_neg[i['source']].add(i['path'])
    test = {}
    for c in CLASSES:
        t = points[c]['threshold']
        alerting = defaultdict(set)
        for i, r in enumerate(meta):
            if r['split'] == 'test' and r['kind'] == 'neg' and r['cls'] == c and prob[i] >= t:
                alerting[r['source']].add(r['path'])
        pos = [prob[i] for i, r in enumerate(meta) if r['split'] == 'test' and r['kind'] == 'det' and r['label'] == 1 and r['cls'] == c]
        test[c] = {'threshold': t, 'blind_negative_frame_far': {s: len(alerting[s]) / len(all_neg[s]) for s in all_neg},
                   'recall_of_correct_detections': float(np.mean([p >= t for p in pos])) if pos else None, 'positives': len(pos)}
    report['test'] = test
    out = ROOT / 'storage/models'
    torch.save(model.state_dict(), out / 'verifier.pt')
    (out / 'verifier.json').write_text(json.dumps({'thresholds': {c: points[c]['threshold'] for c in CLASSES}, 'classes': CLASSES, 'far_target': a.far, 'benchmark': 'storage/benchmarks/verifier.json'}, indent=2))
    (ROOT / 'storage/benchmarks/verifier.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'auc': report['auc'], 'operating_points': points, 'test': test}, indent=2))


if __name__ == '__main__':
    main()
