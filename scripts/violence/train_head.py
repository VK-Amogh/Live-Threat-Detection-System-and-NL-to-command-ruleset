"""Train the temporal violence head on cached DINOv2 features and benchmark it on held-out clips.

python scripts/violence/train_head.py [--features storage/datasets/violence/features]
Calibration happens on the validation split only; the test split is touched once for the final report.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from violence_head import TemporalHead  # noqa: E402


def window_batch(x, length, stride, rng):
    """x: B,16,D -> B,length,D with a random start for each sample."""
    span = (length - 1) * stride + 1
    starts = rng.integers(0, 16 - span + 1, size=len(x))
    idx = starts[:, None] + np.arange(length)[None] * stride
    return np.take_along_axis(x, idx[:, :, None], axis=1)


def evaluate_windows(model, feats, length, stride, device):
    """Deterministic windows covering the clip; scores averaged per clip."""
    span = (length - 1) * stride + 1
    starts = sorted({0, (16 - span) // 2, 16 - span})
    scores = np.zeros(len(feats))
    model.eval()
    with torch.no_grad():
        for s in starts:
            w = torch.from_numpy(feats[:, s:s + span:stride].astype(np.float32)).to(device)
            scores += torch.sigmoid(model(w)[0]).cpu().numpy()
    return scores / len(starts)


def frame_scores(model, feats, device):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(feats), 256):
            x = torch.from_numpy(feats[i:i + 256].astype(np.float32)).to(device)
            b, t, d = x.shape
            logit, _ = model(x.reshape(b * t, 1, d))
            out.append(torch.sigmoid(logit).reshape(b, t).cpu().numpy())
    return np.concatenate(out)


def pick_threshold(y, s, min_precision):
    best = None
    for t in np.linspace(0.05, 0.98, 94):
        pred = s >= t
        if pred.sum() == 0:
            continue
        p, r = precision_score(y, pred, zero_division=0), recall_score(y, pred, zero_division=0)
        f = 2 * p * r / (p + r) if p + r else 0
        key = (p >= min_precision, f if p >= min_precision else p)
        if best is None or key > best[0]:
            best = (key, float(t))
    return best[1]


def pick_threshold_far(y, s, max_far):
    """Highest-recall threshold whose false-alarm rate on negatives stays <= max_far (used for single stills)."""
    negatives = s[y == 0]
    return float(max(np.quantile(negatives, 1 - max_far), 0.05)) if len(negatives) else 0.9


def metrics(y, s, t):
    pred = s >= t
    return {'accuracy': float(accuracy_score(y, pred)), 'precision': float(precision_score(y, pred, zero_division=0)), 'recall': float(recall_score(y, pred, zero_division=0)),
            'f1': float(f1_score(y, pred, zero_division=0)), 'roc_auc': float(roc_auc_score(y, s)) if len(set(y)) > 1 else None, 'threshold': t,
            'false_alarm_rate': float(((pred) & (y == 0)).sum() / max((y == 0).sum(), 1)), 'n': int(len(y))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--features', default='storage/datasets/violence/features')
    ap.add_argument('--epochs', type=int, default=60)
    ap.add_argument('--batch', type=int, default=128)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--min-precision', type=float, default=0.85)
    ap.add_argument('--still-far', type=float, default=0.03, help='max false-alarm rate allowed for single uploaded stills')
    a = ap.parse_args()
    d = ROOT / a.features
    X = np.load(d / 'features.npy', mmap_mode='r')
    meta = json.loads((d / 'meta.json').read_text())
    # Splits/labels come from the current manifest, so re-splitting never needs re-extraction.
    current = {r['path']: r for r in json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text())}
    keep = [i for i, m in enumerate(meta) if m['path'] in current]
    X = X[keep] if len(keep) != len(meta) else X
    meta = [{**meta[i], 'split': current[meta[i]['path']]['split'], 'label': current[meta[i]['path']]['label'], 'dataset': current[meta[i]['path']]['dataset']} for i in keep]
    y_all = np.array([m['label'] for m in meta])
    split = np.array([m['split'] for m in meta])
    view = np.array([m['view'] for m in meta])
    ds = np.array([m['dataset'] for m in meta])
    train_idx = np.where(split == 'train')[0]
    X_train = np.asarray(X[train_idx])
    y_train = y_all[train_idx].astype(np.float32)
    val_idx = np.where((split == 'val') & (view == 0))[0]
    test_idx = np.where((split == 'test') & (view == 0))[0]
    X_val, y_val = np.asarray(X[val_idx]), y_all[val_idx]
    device = 'cuda'
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    model = TemporalHead().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.05)
    steps = a.epochs * (len(train_idx) // a.batch + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.1)
    bce = nn.BCEWithLogitsLoss()
    best, best_state, stall, started = -1, None, 0, time.time()
    for epoch in range(a.epochs):
        model.train()
        perm = rng.permutation(len(train_idx))
        total = 0.0
        for i in range(0, len(perm), a.batch):
            b = perm[i:i + a.batch]
            length = int(rng.choice([1, 2, 4, 8, 8, 16]))
            stride = int(rng.choice([1, 2])) if length > 1 and (length - 1) * 2 + 1 <= 16 else 1
            x = torch.from_numpy(window_batch(X_train[b], length, stride, rng).astype(np.float32)).to(device)
            x = x + 0.02 * torch.randn_like(x) * x.std()
            y = torch.from_numpy(y_train[b]).to(device)
            clip_logit, frame_logits = model(x)
            loss = bce(clip_logit, y) + 0.5 * bce(frame_logits, y[:, None].expand_as(frame_logits))
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            total += loss.item() * len(b)
        s8 = evaluate_windows(model, X_val, 8, 2, device)
        s1 = frame_scores(model, X_val, device).mean(1)
        auc = (roc_auc_score(y_val, s8) + roc_auc_score(y_val, s1)) / 2
        print(f'epoch {epoch+1:02d} loss {total/len(perm):.4f} val_auc(T=8)={roc_auc_score(y_val, s8):.4f} val_auc(frame mean)={roc_auc_score(y_val, s1):.4f}', flush=True)
        if auc > best:
            best, best_state, stall = auc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            stall += 1
            if stall >= 12:
                break
    model.load_state_dict(best_state)

    # Calibrate on validation, using video clips and threat-free stills separately and keeping the stricter threshold.
    # Stills score near zero, so calibrating on them alone would set the bar too low for ordinary people-in-video frames.
    ds_val = ds[val_idx]
    still_val = np.array([str(n).startswith('Threat-free') for n in ds_val])
    frames_val = frame_scores(model, X_val, device)
    s8_val = evaluate_windows(model, X_val, 8, 2, device)
    thr8 = max(pick_threshold(y_val[~still_val], s8_val[~still_val], a.min_precision), pick_threshold_far(y_val[still_val], s8_val[still_val], a.still_far / 3) if still_val.any() else 0)
    thr1 = max(pick_threshold_far(np.repeat(y_val[~still_val], 16), frames_val[~still_val].reshape(-1), a.still_far),
               pick_threshold_far(np.repeat(y_val[still_val], 16), frames_val[still_val].reshape(-1), a.still_far / 3) if still_val.any() else 0)

    X_test, y_test = np.asarray(X[test_idx]), y_all[test_idx]
    report = {'generated_at': time.time(), 'train_clips': int(len(train_idx)), 'val_clips': int(len(val_idx)), 'test_clips': int(len(test_idx)),
              'train_seconds': round(time.time() - started), 'selection_rule': f'val thresholds, video clips and threat-free stills calibrated separately, stricter wins: 8-frame window = max F1 with precision >= {a.min_precision}; single frame = highest recall with false-alarm rate <= {a.still_far} on video frames and <= {a.still_far/3:.3f} on stills',
              'encoder': 'facebook/dinov2-base (frozen)', 'overall': {}, 'by_dataset': {}}
    s8 = evaluate_windows(model, X_test, 8, 2, device)
    s16 = evaluate_windows(model, X_test, 16, 1, device)
    sf = frame_scores(model, X_test, device)
    # 'overall' covers real video clips only; threat-free stills are easy negatives that would inflate accuracy,
    # so their false-alarm rate is reported on its own line.
    video = np.array([not str(n).startswith('Threat-free') for n in ds[test_idx]])
    report['overall'] = {'clip_8_frames': metrics(y_test[video], s8[video], thr8), 'clip_16_frames': metrics(y_test[video], s16[video], thr8),
                         'single_frame': metrics(np.repeat(y_test[video], 16), sf[video].reshape(-1), thr1)}
    if (~video).any():
        report['overall']['clean_stills_single_frame'] = metrics(np.repeat(y_test[~video], 16), sf[~video].reshape(-1), thr1)
    for name in sorted(set(ds[test_idx])):
        m = ds[test_idx] == name
        report['by_dataset'][name] = {'clips': int(m.sum()), 'clip_8_frames': metrics(y_test[m], s8[m], thr8), 'single_frame': metrics(np.repeat(y_test[m], 16), sf[m].reshape(-1), thr1)}
    out = ROOT / 'storage/models'
    out.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, out / 'violence_head.pt')
    (out / 'violence_head.json').write_text(json.dumps({'thresholds': {'1': thr1, '8': thr8}, 'encoder': 'facebook/dinov2-base', 'benchmark': 'storage/benchmarks/violence.json'}, indent=2))
    (ROOT / 'storage/benchmarks').mkdir(parents=True, exist_ok=True)
    (ROOT / 'storage/benchmarks/violence.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report['overall'], indent=2))


if __name__ == '__main__':
    main()
