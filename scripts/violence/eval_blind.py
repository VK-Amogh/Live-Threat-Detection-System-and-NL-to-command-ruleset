"""Evaluate violence heads on the DCSASS blind clips (parents never seen in training or calibration).

python scripts/violence/eval_blind.py violence_head_v1 violence_head_v2
Reports, per DCSASS category, the share of clips flagged at the head's own calibrated 8-frame threshold, and the
threshold-free AUC of violent categories (Fighting/Assault/Abuse, anomalous sub-clips) vs calm categories.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
sys.path.insert(0, str(ROOT / 'scripts/violence'))
from train_head import evaluate_windows  # noqa: E402
from violence_head import TemporalHead  # noqa: E402

CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}


def main():
    names = sys.argv[1:] or ['violence_head']
    d = ROOT / 'storage/datasets/violence/blind_features'
    X = np.load(d / 'features.npy')
    meta = json.loads((d / 'meta.json').read_text())
    cat = np.array([m['category'] for m in meta])
    lab = np.array([m['dcsass_label'] for m in meta])
    for name in names:
        model = TemporalHead().cuda().eval()
        model.load_state_dict(torch.load(ROOT / f'storage/models/{name}.pt'))
        thr = json.loads((ROOT / f'storage/models/{name}.json').read_text())['thresholds']
        t8 = thr['8']
        s = evaluate_windows(model, X, 8, 2, 'cuda')
        print(f'\n== {name}  (8-frame threshold {t8:.3f})')
        rows = defaultdict(list)
        for c, l, v in zip(cat, lab, s):
            rows[(c, l)].append(v)
        for (c, l), v in sorted(rows.items()):
            print(f'{c:14s} label {l}: {len(v):4d} clips, flagged {np.mean(np.array(v) >= t8):6.1%}, median score {np.median(v):.2f}')
        pos = np.isin(cat, ['Fighting', 'Assault', 'Abuse']) & (lab == 1)
        neg = np.isin(cat, list(CALM))
        m = pos | neg
        print(f'violent (Fighting/Assault/Abuse) vs calm: AUC {roc_auc_score(pos[m], s[m]):.3f}; recall {np.mean(s[pos] >= t8):.1%} at calm false-alarm {np.mean(s[neg] >= t8):.1%}')
        for far in (0.02, 0.05, 0.10):
            t = np.quantile(s[neg], 1 - far)
            print(f'   at calm false-alarm {far:.0%}: recall {np.mean(s[pos] >= t):.1%} (threshold {t:.2f})')


if __name__ == '__main__':
    main()
