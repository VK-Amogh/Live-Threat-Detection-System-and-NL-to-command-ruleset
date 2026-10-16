"""Combine the DINOv2 temporal head (scenes/pose, works on stills) and the VideoMAE head (motion) for video windows.

python scripts/violence/ensemble_eval.py [--far 0.03] [--write]
Calibration uses validation clips only (pooled over all sources, video negatives); in-domain test and the DCSASS blind
parents are reported at that single threshold. --write stores storage/models/violence_ensemble.json for the inference service.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'scripts/violence')]
from train_head import evaluate_windows  # noqa: E402
from motion import Head  # noqa: E402
from train_videomae_head import scores  # noqa: E402
from violence_head import TemporalHead  # noqa: E402

CALM = ['RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary']


def dino_scores(name, X):
    h = TemporalHead().cuda().eval()
    h.load_state_dict(torch.load(ROOT / f'storage/models/{name}.pt'))
    return evaluate_windows(h, X, 8, 2, 'cuda')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dino', default='violence_head_v2')
    ap.add_argument('--vmae', default='violence_videomae')
    ap.add_argument('--far', type=float, default=0.03)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    v = ROOT / 'storage/datasets/violence'
    manifest = {r['path']: r for r in json.loads((v / 'manifest.json').read_text())}
    # --- in-domain val/test
    dX, dm = np.load(v / 'features/features.npy', mmap_mode='r'), json.loads((v / 'features/meta.json').read_text())
    mX, mm = np.load(v / 'videomae/features.npy'), json.loads((v / 'videomae/meta.json').read_text())
    dino_idx = {m['path']: i for i, m in enumerate(dm) if m['view'] == 0}
    paths = [m['path'] for m in mm if m['view'] == 0 and m['path'] in manifest and m['path'] in dino_idx and manifest[m['path']]['split'] in ('val', 'test')]
    vm_idx = {m['path']: i for i, m in enumerate(mm) if m['view'] == 0}
    sd = dino_scores(a.dino, np.asarray(dX[[dino_idx[p] for p in paths]]))
    sv = scores_from(a.vmae, mX[[vm_idx[p] for p in paths]])
    rows = [manifest[p] for p in paths]
    y = np.array([r['label'] for r in rows])
    split = np.array([r['split'] for r in rows])
    ds = np.array([r['dataset'] for r in rows])
    from sklearn.linear_model import LogisticRegression
    logit = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
    val_mask = split == 'val'
    lr = LogisticRegression(C=1.0).fit(np.stack([logit(sd), logit(sv)], 1)[val_mask], y[val_mask])      # fitted on validation clips only
    coef, intercept = [float(c) for c in lr.coef_[0]], float(lr.intercept_[0])
    stack = lambda d, m: 1 / (1 + np.exp(-(coef[0] * logit(d) + coef[1] * logit(m) + intercept)))
    combos = {'dinov2': lambda d, m: d, 'videomae': lambda d, m: m, 'mean': lambda d, m: (d + m) / 2, 'max': lambda d, m: np.maximum(d, m), 'stack': stack}
    # --- blind
    bX, bm = np.load(v / 'blind_features/features.npy'), json.loads((v / 'blind_features/meta.json').read_text())
    bV = np.load(v / 'videomae_blind/features.npy')
    cat = np.array([m['category'] for m in bm])
    lab = np.array([m['dcsass_label'] for m in bm])
    bd, bv = dino_scores(a.dino, bX), scores_from(a.vmae, bV)
    pos = np.isin(cat, ['Fighting', 'Assault', 'Abuse']) & (lab == 1)
    calm = np.isin(cat, CALM)
    out = {}
    for name, f in combos.items():
        val = split == 'val'
        thr = float(np.quantile(f(sd, sv)[val & (y == 0)], 1 - a.far))
        s = f(sd, sv)
        res = {'threshold': thr, 'val_far': a.far, 'test': {}}
        for d in sorted(set(ds[split == 'test'])):
            m = (split == 'test') & (ds == d)
            if (y[m] == 1).any() and (y[m] == 0).any():
                res['test'][d] = {'auc': float(roc_auc_score(y[m], s[m])), 'recall': float(np.mean(s[m & (y == 1)] >= thr)), 'false_alarm': float(np.mean(s[m & (y == 0)] >= thr))}
        sb = f(bd, bv)
        mk = pos | calm
        res['blind_dcsass'] = {'auc': float(roc_auc_score(pos[mk], sb[mk])), 'recall': float(np.mean(sb[pos] >= thr)), 'calm_false_alarm': float(np.mean(sb[calm] >= thr)),
                               'recall_at_calm_far_5pct': float(np.mean(sb[pos] >= np.quantile(sb[calm], 0.95)))}
        out[name] = res
        print(f'\n== {name} threshold {thr:.3f}')
        for d, r in res['test'].items():
            print(f'  {d[:30]:30s} AUC {r["auc"]:.3f} recall {r["recall"]:.1%} false-alarm {r["false_alarm"]:.1%}')
        print(f'  DCSASS blind: AUC {res["blind_dcsass"]["auc"]:.3f} recall {res["blind_dcsass"]["recall"]:.1%} calm false-alarm {res["blind_dcsass"]["calm_false_alarm"]:.1%} (recall at 5% FAR {res["blind_dcsass"]["recall_at_calm_far_5pct"]:.1%})')
    if a.write:
        (ROOT / 'storage/benchmarks/violence_ensemble.json').write_text(json.dumps({'combinations': out, 'stack_coef': coef, 'stack_intercept': intercept}, indent=2))
        (ROOT / 'storage/models/violence_ensemble.json').write_text(json.dumps({'method': 'stack', 'coef': coef, 'intercept': intercept, 'threshold': out['stack']['threshold'], 'far_target': a.far,
                                                                                  'dino': a.dino, 'motion': a.vmae, 'benchmark': 'storage/benchmarks/violence_ensemble.json'}, indent=2))
        print('wrote storage/benchmarks/violence_ensemble.json and storage/models/violence_ensemble.json')


def scores_from(name, X):
    m = Head().cuda().eval()
    m.load_state_dict(torch.load(ROOT / f'storage/models/{name}.pt'))
    return scores(m, X)


if __name__ == '__main__':
    main()
