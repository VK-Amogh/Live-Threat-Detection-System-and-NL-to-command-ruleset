"""Shared loading and metrics for the crime-type scripts (feature join, parent-grouped bootstrap, decision rule)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from crime_head import CLASSES, TYPES, DINO_DIM, VMAE_DIM, pool_features  # noqa: E402

DATA = ROOT / 'storage/datasets/crime'
NONE = CLASSES.index('none')
VIOLENCE_GROUP = ('Abuse', 'Assault', 'Fighting')
PROPERTY_GROUP = ('Burglary', 'Stealing', 'Shoplifting', 'Vandalism')


def load_rows():
    return json.loads((DATA / 'manifest.json').read_text())


def load_features():
    """(rows, X) with X = pooled [DINOv2 mean | DINOv2 std | VideoMAE] for every manifest clip that both caches hold (view 0)."""
    cache = DATA / 'pooled.npz'
    sources = [DATA / 'dino/features.npy', DATA / 'videomae/features.npy', DATA / 'manifest.json']
    if cache.exists() and cache.stat().st_mtime > max(p.stat().st_mtime for p in sources):
        z = np.load(cache, allow_pickle=False)
        keep = json.loads(str(z['keep']))
        rows = load_rows()
        return [rows[i] for i in keep], z['X']
    rows = load_rows()
    dX, dm = np.load(DATA / 'dino/features.npy', mmap_mode='r'), json.loads((DATA / 'dino/meta.json').read_text())
    vX, vm = np.load(DATA / 'videomae/features.npy'), json.loads((DATA / 'videomae/meta.json').read_text())
    d_at = {m['path']: i for i, m in enumerate(dm) if m['view'] == 0}
    v_at = {m['path']: i for i, m in enumerate(vm) if m['view'] == 0}
    keep = [i for i, r in enumerate(rows) if r['path'] in d_at and r['path'] in v_at]
    parts = []
    for s in range(0, len(keep), 1024):
        chunk = keep[s:s + 1024]
        parts.append(pool_features(np.asarray(dX[[d_at[rows[i]['path']] for i in chunk]]), vX[[v_at[rows[i]['path']] for i in chunk]]))
    X = np.concatenate(parts)
    np.savez(cache, X=X, keep=json.dumps(keep))
    return [rows[i] for i in keep], X


def label_index(rows):
    """Class index of each row's target; -1 for rows without a trustworthy type label (Arson, label-0 clips of violent categories)."""
    return np.array([CLASSES.index(r['target']) if r['target'] else -1 for r in rows])


def predict_types(prob, taus):
    """Decision rule: the most probable crime type, kept only if its probability reaches that type's calibrated threshold, else 'none'.

    prob: (N, len(CLASSES)). taus: {type: threshold or None}. Returns (class index per clip, probability of the chosen type).
    """
    top = prob[:, :NONE].argmax(1)
    p_top = prob[np.arange(len(prob)), top]
    limit = np.array([np.inf if taus.get(TYPES[c]) is None else taus[TYPES[c]] for c in range(NONE)])
    fired = p_top >= limit[top]
    return np.where(fired, top, NONE), p_top


def per_parent_counts(pred, truth, parents, cls):
    """For each parent: true positives, predicted-as-cls clips, actual cls clips (rows with truth == -1 never count as actual)."""
    out = {}
    for p in np.unique(parents):
        m = parents == p
        out[p] = (int(((pred[m] == cls) & (truth[m] == cls)).sum()), int((pred[m] == cls).sum()), int((truth[m] == cls).sum()))
    return out


def bootstrap_precision_recall(pred, truth, parents, cls, reps=2000, seed=0):
    """Parent-cluster bootstrap 95 % intervals: sub-clips of one source video are correlated, so videos are resampled, not clips."""
    counts = per_parent_counts(pred, truth, parents, cls)
    keys = list(counts)
    arr = np.array([counts[k] for k in keys], float)      # P x 3
    rng = np.random.default_rng(seed)
    prec, rec = [], []
    for _ in range(reps):
        s = arr[rng.integers(0, len(arr), len(arr))].sum(0)
        if s[1] > 0:
            prec.append(s[0] / s[1])
        if s[2] > 0:
            rec.append(s[0] / s[2])
    tp, n_pred, n_true = arr.sum(0)
    interval = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [None, None]
    return {'tp': int(tp), 'predicted': int(n_pred), 'actual': int(n_true), 'precision': float(tp / n_pred) if n_pred else None, 'precision_ci95': interval(prec),
            'recall': float(tp / n_true) if n_true else None, 'recall_ci95': interval(rec), 'parents_with_class': int((arr[:, 2] > 0).sum()),
            'parents_hit': int(((arr[:, 0] > 0)).sum())}


def macro_f1(pred, truth, classes):
    f = []
    for c in classes:
        tp = ((pred == c) & (truth == c)).sum()
        p, r = tp / max((pred == c).sum(), 1), tp / max((truth == c).sum(), 1)
        f.append(2 * p * r / (p + r) if p + r else 0.0)
    return float(np.mean(f))
