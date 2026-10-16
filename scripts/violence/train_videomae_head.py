"""Train the motion-aware violence head on cached VideoMAE (Kinetics-400) clip features and evaluate it blind.

python scripts/violence/train_videomae_head.py [--out violence_videomae]
Splits/labels come from storage/datasets/violence/manifest.json (video clips only). Thresholds are calibrated on validation
clips only: the lowest score whose false-alarm rate on validation negatives is <= --far (per-dataset medians guard against one
source dominating). DCSASS blind parents (storage/datasets/violence/videomae_blind) are scored but never used to choose anything.
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
from motion import Head  # noqa: E402

CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}


def scores(model, X):
    model.eval()
    with torch.no_grad():
        return torch.sigmoid(model(torch.from_numpy(X.astype(np.float32)).cuda())).cpu().numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='violence_videomae')
    ap.add_argument('--epochs', type=int, default=60)
    ap.add_argument('--far', type=float, default=0.03)
    ap.add_argument('--dcsass-weight', type=float, default=2.0, help='extra weight on surveillance-domain DCSASS/SCVD/RWF training clips')
    a = ap.parse_args()
    d = ROOT / 'storage/datasets/violence/videomae'
    X = np.load(d / 'features.npy')
    meta = json.loads((d / 'meta.json').read_text())
    current = {r['path']: r for r in json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text())}
    keep = [i for i, m in enumerate(meta) if m['path'] in current]
    X = X[keep]
    meta = [{**meta[i], **{k: current[meta[i]['path']][k] for k in ('split', 'label', 'dataset')}} for i in keep]
    y = np.array([m['label'] for m in meta], np.float32)
    split = np.array([m['split'] for m in meta])
    view = np.array([m['view'] for m in meta])
    ds = np.array([m['dataset'] for m in meta])
    train = np.where(split == 'train')[0]
    val = np.where((split == 'val') & (view == 0))[0]
    test = np.where((split == 'test') & (view == 0))[0]
    weights = np.array([a.dcsass_weight if str(n).startswith(('DCSASS', 'SCVD', 'RWF')) else 1.0 for n in ds[train]], np.float32)
    Xt, yt, wt = (torch.from_numpy(X[train].astype(np.float32)).cuda(), torch.from_numpy(y[train]).cuda(), torch.from_numpy(weights).cuda())
    torch.manual_seed(0)
    model = Head().cuda()
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.05)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=a.epochs * (len(train) // 256 + 1), pct_start=0.1)
    bce = nn.BCEWithLogitsLoss(reduction='none')
    best, state, stall = -1, None, 0
    for epoch in range(a.epochs):
        model.train()
        perm = torch.randperm(len(train), device='cuda')
        for i in range(0, len(train), 256):
            b = perm[i:i + 256]
            loss = (bce(model(Xt[b] + 0.05 * torch.randn_like(Xt[b]) * Xt[b].std()), yt[b]) * wt[b]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
        auc = roc_auc_score(y[val], scores(model, X[val]))
        if auc > best:
            best, state, stall = auc, {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            stall += 1
            if stall >= 12:
                break
    model.load_state_dict(state)
    sv = scores(model, X[val])
    neg = sv[y[val] == 0]
    thr = float(max(np.quantile(neg, 1 - a.far), 0.3))
    st = scores(model, X[test])
    report = {'generated_at': time.time(), 'train_clips': int(len(train)), 'val_clips': int(len(val)), 'test_clips': int(len(test)), 'val_auc': float(best), 'threshold': thr, 'far_target': a.far, 'by_dataset': {}}
    for name in sorted(set(ds[test])):
        m = ds[test] == name
        yy, ss = y[test][m], st[m]
        report['by_dataset'][name] = {'clips': int(m.sum()), 'auc': float(roc_auc_score(yy, ss)) if len(set(yy)) > 1 else None, 'recall': float(np.mean(ss[yy == 1] >= thr)) if (yy == 1).any() else None, 'false_alarm_rate': float(np.mean(ss[yy == 0] >= thr)) if (yy == 0).any() else None}
    # blind DCSASS parents
    bd = ROOT / 'storage/datasets/violence/videomae_blind'
    Xb = np.load(bd / 'features.npy')
    mb = json.loads((bd / 'meta.json').read_text())
    cat = np.array([m['category'] for m in mb])
    lab = np.array([m['dcsass_label'] for m in mb])
    sb = scores(model, Xb)
    pos = np.isin(cat, ['Fighting', 'Assault', 'Abuse']) & (lab == 1)
    calm = np.isin(cat, list(CALM))
    msk = pos | calm
    report['blind'] = {'violent_vs_calm_auc': float(roc_auc_score(pos[msk], sb[msk])), 'recall': float(np.mean(sb[pos] >= thr)), 'calm_false_alarm': float(np.mean(sb[calm] >= thr)),
                       'recall_at_calm_far': {f'{f:.0%}': float(np.mean(sb[pos] >= np.quantile(sb[calm], 1 - f))) for f in (0.02, 0.05, 0.10)},
                       'per_category': {f'{c}/{l}': {'clips': int(((cat == c) & (lab == l)).sum()), 'flagged': float(np.mean(sb[(cat == c) & (lab == l)] >= thr))} for c in sorted(set(cat)) for l in (0, 1) if ((cat == c) & (lab == l)).any()}}
    torch.save(state, ROOT / f'storage/models/{a.out}.pt')
    (ROOT / f'storage/models/{a.out}.json').write_text(json.dumps({'threshold': thr, 'far_target': a.far, 'encoder': 'MCG-NJU/videomae-base-finetuned-kinetics', 'benchmark': f'storage/benchmarks/{a.out}.json'}, indent=2))
    (ROOT / f'storage/benchmarks/{a.out}.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ('val_auc', 'threshold', 'by_dataset')}, indent=1))
    print(json.dumps({k: v for k, v in report['blind'].items() if k != 'per_category'}, indent=1))
    for k, v in report['blind']['per_category'].items():
        print(f'  {k:18s} {v["clips"]:4d} clips flagged {v["flagged"]:.1%}')


if __name__ == '__main__':
    main()
