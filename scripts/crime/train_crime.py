"""Train the crime-type head on cached DINOv2 + VideoMAE features with parent-grouped cross-validation (dev parents only).

python scripts/crime/train_crime.py [--final] [--configs name,name]
1. For each config, 5-fold cross-validation over DEV parents (folds come from build_manifest.py and never split a parent video) gives
   out-of-fold (OOF) probabilities for every dev clip. The full-feature config with the best OOF macro-F1 is selected; blind parents are
   never loaded here.
2. A temperature (OOF NLL) and one threshold per crime type (the lowest threshold whose OOF precision >= PRECISION_TARGET, with minimum
   support) are fitted on the OOF predictions. A type with no such threshold gets null and never fires.
3. --final fits the selected config on all dev clips and writes storage/models/crime_type.pt/.json. The sidecar starts with an EMPTY
   `supported` list: only scripts/crime/score_blind.py --write may fill it, after the blind parents pass the pre-registered bar.
Dev numbers printed here guided model selection; they are NOT a result (see score_blind.py for the blind numbers).
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parent))
from crime_common import CLASSES, DATA, DINO_DIM, NONE, ROOT, TYPES, VMAE_DIM, label_index, load_features, macro_f1  # noqa: E402
from crime_head import CrimeHead, softmax  # noqa: E402

PRECISION_TARGET = 0.70      # OOF precision a type must reach at its threshold
MIN_CORRECT, MIN_PARENTS, MIN_RECALL = 10, 3, 0.05
PARENT_POWER, CLASS_POWER = 0.5, 0.5     # sample weight ~ 1/n_parent_clips^p, class weight ~ 1/n_class^p
CONFIGS = {
    'linear': dict(hidden=0, dropout=0.5, wd=0.05, epochs=30, lr=1e-3, features='all'),
    'mlp256': dict(hidden=256, dropout=0.5, wd=0.05, epochs=30, lr=1e-3, features='all'),
    'mlp512': dict(hidden=512, dropout=0.6, wd=0.1, epochs=40, lr=1e-3, features='all'),
    'mlp256_dino_only': dict(hidden=256, dropout=0.5, wd=0.05, epochs=30, lr=1e-3, features='dino'),
    'mlp256_videomae_only': dict(hidden=256, dropout=0.5, wd=0.05, epochs=30, lr=1e-3, features='vmae'),
}
COLUMNS = {'all': (slice(0, None), (DINO_DIM, DINO_DIM, VMAE_DIM)), 'dino': (slice(0, 2 * DINO_DIM), (DINO_DIM, DINO_DIM)), 'vmae': (slice(2 * DINO_DIM, None), (VMAE_DIM,))}


def sample_weights(y, parents):
    """Down-weight parents that contribute many clips to a class, and classes with many clips (mean weight 1)."""
    w = np.ones(len(y), np.float32)
    for c in np.unique(y):
        m = np.where(y == c)[0]
        _, inv, counts = np.unique(parents[m], return_inverse=True, return_counts=True)
        w[m] = counts[inv] ** -PARENT_POWER
        w[m] *= len(m) ** -CLASS_POWER
    return w / w.mean()


def fit(X, y, w, cfg, seed=0, device='cuda'):
    cols, blocks = COLUMNS[cfg['features']]
    torch.manual_seed(seed)
    model = CrimeHead(hidden=cfg['hidden'], dropout=cfg['dropout'], blocks=blocks).to(device)
    Xt = torch.from_numpy(np.ascontiguousarray(X[:, cols])).to(device)
    yt, wt = torch.from_numpy(y).long().to(device), torch.from_numpy(w).to(device)
    steps = cfg['epochs'] * (len(y) // 256 + 1)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg['lr'], weight_decay=cfg['wd'])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg['lr'], total_steps=steps, pct_start=0.1)
    ce = nn.CrossEntropyLoss(reduction='none', label_smoothing=0.1)
    g = torch.Generator(device=device)
    g.manual_seed(seed)
    for _ in range(cfg['epochs']):
        model.train()
        perm = torch.randperm(len(y), device=device, generator=g)
        for i in range(0, len(y), 256):
            b = perm[i:i + 256]
            x = Xt[b]
            x = x + 0.05 * torch.randn_like(x) * x.std()          # feature-space noise instead of re-decoding augmented video
            loss = (ce(model(x), yt[b]) * wt[b]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
    return model.eval()


@torch.no_grad()
def logits_of(model, X, features, device='cuda'):
    cols, _ = COLUMNS[features]
    return torch.cat([model(torch.from_numpy(np.ascontiguousarray(X[i:i + 1024, cols])).to(device)).cpu() for i in range(0, len(X), 1024)]).numpy()


def fit_temperature(logits, y):
    ok = y >= 0
    nll = lambda t: float(-np.log(softmax(logits[ok], t)[np.arange(ok.sum()), y[ok]] + 1e-9).mean())
    return min(((t, nll(t)) for t in np.linspace(0.5, 4.0, 71)), key=lambda pair: pair[1])


def fit_thresholds(prob, y, parents):
    """Lowest threshold per type whose OOF precision >= PRECISION_TARGET with minimum support; None when the type has no usable operating point."""
    taus, table = {}, {}
    ok = y >= 0
    top = prob[:, :NONE].argmax(1)
    p_top = prob[np.arange(len(prob)), top]
    for c, name in enumerate(TYPES):
        chosen, info = None, {'oof_clips': int((y == c).sum()), 'oof_parents': int(len(set(parents[y == c])))}
        for t in np.linspace(0.2, 0.99, 80):
            sel = ok & (top == c) & (p_top >= t)
            correct = sel & (y == c)
            if sel.sum() == 0:
                continue
            precision, recall = correct.sum() / sel.sum(), correct.sum() / max((y == c).sum(), 1)
            if precision >= PRECISION_TARGET and correct.sum() >= MIN_CORRECT and len(set(parents[correct])) >= MIN_PARENTS and recall >= MIN_RECALL:
                chosen, info = round(float(t), 4), {**info, 'oof_precision': float(precision), 'oof_recall': float(recall)}
                break
        taus[name] = chosen
        table[name] = info
    return taus, table


def cross_validate(X, y, parents, folds, cfg):
    oof = np.zeros((len(y), len(CLASSES)), np.float32)
    for f in sorted(set(folds)):
        tr, te = np.where(folds != f)[0], np.where(folds == f)[0]
        keep = tr[y[tr] >= 0]
        model = fit(X[keep], y[keep], sample_weights(y[keep], parents[keep]), cfg)
        oof[te] = logits_of(model, X[te], cfg['features'])
    return oof


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--configs', default=','.join(CONFIGS))
    ap.add_argument('--final', action='store_true', help='fit the selected config on all dev clips and write storage/models/crime_type.*')
    ap.add_argument('--select', default=None, help='skip selection and use this config')
    ap.add_argument('--name', default='crime_type')
    a = ap.parse_args()
    rows, X = load_features()
    dev = np.array([r['role'] == 'dev' for r in rows])
    X, rows = X[dev], [r for r, d in zip(rows, dev) if d]
    y, parents = label_index(rows), np.array([r['parent'] for r in rows])
    folds = np.array([r['fold'] for r in rows])
    print(f'{len(rows)} dev clips, {len(set(parents))} parents, classes {len(CLASSES)}')
    results = {}
    started = time.time()
    for name in a.configs.split(','):
        cfg = CONFIGS[name]
        oof = cross_validate(X, y, parents, folds, cfg)
        t, nll = fit_temperature(oof, y)
        prob = softmax(oof, t)
        ok = y >= 0
        pred = prob.argmax(1)
        types_only = ok & (y < NONE)
        results[name] = {'oof_logits': oof, 'temperature': t, 'nll': nll, 'macro_f1': macro_f1(pred[ok], y[ok], range(len(CLASSES))),
                         'type_top1': float((prob[types_only, :NONE].argmax(1) == y[types_only]).mean()), 'none_recall': float((pred[ok & (y == NONE)] == NONE).mean())}
        r = results[name]
        print(f'{name:22s} OOF macro-F1 {r["macro_f1"]:.3f}  type top-1 (closed set) {r["type_top1"]:.3f}  none recall {r["none_recall"]:.3f}  NLL {nll:.3f}  T={t:.2f}  [{time.time()-started:.0f}s]', flush=True)
    best = a.select or max((n for n in results if CONFIGS[n]['features'] == 'all'), key=lambda n: results[n]['macro_f1'])
    print('selected (best OOF macro-F1 among full-feature configs):', best)
    res = results[best]
    prob = softmax(res['oof_logits'], res['temperature'])
    taus, table = fit_thresholds(prob, y, parents)
    print('type           clips parents  threshold  OOF precision  OOF recall')
    for n in TYPES:
        row = table[n]
        shown = 'None' if taus[n] is None else f'{taus[n]:.2f}'
        print(f'{n:14s} {row["oof_clips"]:5d} {row["oof_parents"]:7d}  {shown:>9s}  {row.get("oof_precision", float("nan")):13.2f}  {row.get("oof_recall", float("nan")):10.2f}')
    report = {'generated_at': time.time(), 'note': 'dev-parent cross-validation used for model selection and threshold fitting; NOT a performance claim', 'dev_clips': int(len(rows)),
              'dev_parents': int(len(set(parents))), 'configs': {n: {k: v for k, v in r.items() if k != 'oof_logits'} for n, r in results.items()}, 'selected': best, 'thresholds': taus,
              'threshold_table': table, 'precision_target': PRECISION_TARGET}
    (ROOT / 'storage/benchmarks').mkdir(exist_ok=True)
    (ROOT / 'storage/benchmarks/crime_type_cv.json').write_text(json.dumps(report, indent=2))
    np.savez(DATA / 'oof.npz', logits=res['oof_logits'], y=y, parents=parents, temperature=res['temperature'])
    if a.final:
        cfg = CONFIGS[best]
        keep = np.where(y >= 0)[0]
        model = fit(X[keep], y[keep], sample_weights(y[keep], parents[keep]), cfg)
        torch.save({k: v.detach().cpu() for k, v in model.state_dict().items()}, ROOT / f'storage/models/{a.name}.pt')
        _, blocks = COLUMNS[cfg['features']]
        sidecar = {'classes': CLASSES, 'config': {**cfg, 'blocks': list(blocks)}, 'temperature': res['temperature'], 'thresholds': taus, 'precision_target': PRECISION_TARGET,
                   'supported': [], 'supported_note': 'filled by scripts/crime/score_blind.py --write after the blind parents pass the pre-registered bar; an empty list means advisory-off',
                   'encoder': {'frames': 'facebook/dinov2-base (frozen)', 'motion': 'MCG-NJU/videomae-base-finetuned-kinetics (frozen)'}, 'out_of_scope': ['Arson'],
                   'benchmark': f'storage/benchmarks/{a.name}.json'}
        (ROOT / f'storage/models/{a.name}.json').write_text(json.dumps(sidecar, indent=2))
        print(f'wrote storage/models/{a.name}.pt and .json (supported list empty until evaluated on blind parents)')


if __name__ == '__main__':
    main()
