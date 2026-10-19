"""Render frame strips of the clips behind the numbers, so the errors can be looked at instead of only counted.

python scripts/crime/inspect_errors.py blind-confusions --out storage/eval/crime/blind_errors.png      # highest-confidence wrong flags on blind parents
python scripts/crime/inspect_errors.py recordings --out storage/eval/crime/recordings_top.png         # top-scoring windows on real footage
python scripts/crime/inspect_errors.py type --type Robbery --kind hit|miss --out ...                   # correct / missed clips of one type
python scripts/crime/inspect_errors.py flagged --type Abuse --source dcsass_noncalm_label0 --out ...  # what a flagged type looks like
Each row is one clip (first, middle and last frame) with the true category, DCSASS label and what the system said.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from crime_common import CLASSES, NONE, ROOT, TYPES, label_index, load_features, predict_types  # noqa: E402
from score_blind import load_model, probabilities  # noqa: E402


def strip(path, caption, start_s=None, span_s=3.2):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    first = int((start_s or 0) * fps)
    last = min(n - 1, first + int(span_s * fps)) if start_s is not None else n - 1
    tiles = []
    for pos in (first, (first + last) // 2, last):
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        h, w = frame.shape[:2] if ok else (144, 192)
        tiles.append(cv2.resize(frame, (192, int(192 * h / w))) if ok else np.zeros((144, 192, 3), np.uint8))
    cap.release()
    height = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, height - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    img = np.hstack(tiles)
    cv2.putText(img, caption, (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
    return img


def grid(strips, columns=2):
    height = max(s.shape[0] for s in strips)
    strips = [cv2.copyMakeBorder(s, 0, height - s.shape[0], 0, 0, cv2.BORDER_CONSTANT) for s in strips]
    while len(strips) % columns:
        strips.append(np.zeros_like(strips[0]))
    return np.vstack([np.hstack(strips[i:i + columns]) for i in range(0, len(strips), columns)])


def blind_rows():
    model, side = load_model()
    rows, X = load_features()
    keep = [i for i, r in enumerate(rows) if r['role'] == 'blind']
    rows, X = [rows[i] for i in keep], X[keep]
    prob = probabilities(model, side, X)
    pred, p_top = predict_types(prob, side['thresholds'])
    return rows, prob, pred, p_top


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['blind-confusions', 'recordings', 'type', 'flagged'])
    ap.add_argument('--out', required=True)
    ap.add_argument('--type', default=None)
    ap.add_argument('--kind', default='hit', choices=['hit', 'miss'])
    ap.add_argument('--source', default=None, help='flagged mode: only clips of this manifest source (e.g. dcsass_noncalm_label0, arson_out_of_scope)')
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    strips, listing = [], []
    if a.mode == 'recordings':
        data = json.loads((ROOT / 'storage/benchmarks/crime_type_recordings.json').read_text())
        for w in data['top_scoring_windows'][:a.n]:
            strips.append(strip(ROOT / w['video'], f"{Path(w['video']).name[-24:]} t={w['start_s']:.1f}s -> {w['type']} p={w['p']:.2f}", w['start_s']))
            listing.append(w)
    else:
        rows, prob, pred, p_top = blind_rows()
        truth = label_index(rows)
        rng = np.random.default_rng(a.seed)
        if a.mode == 'blind-confusions':
            wrong = [i for i in np.argsort(-p_top) if pred[i] != NONE and rows[i]['target'] is not None and truth[i] != pred[i]]
            chosen = wrong[:a.n]
        elif a.mode == 'flagged':
            sel = np.where((pred == TYPES.index(a.type)) & ((np.array([r['source'] for r in rows]) == a.source) if a.source else True))[0]
            chosen = list(rng.permutation(sel)[:a.n])
        else:
            c = TYPES.index(a.type)
            mask = (truth == c) & (np.array([r['source'] for r in rows]) == 'dcsass_label1')
            idx = np.where(mask & ((pred == c) if a.kind == 'hit' else (pred != c)))[0]
            chosen = list(rng.permutation(idx)[:a.n])
        for i in chosen:
            r = rows[i]
            said = CLASSES[pred[i]] if pred[i] != NONE else 'none'
            strips.append(strip(r['path'], f"{r['clip'][:24]} L{r['dcsass_label']} said {said} p={p_top[i]:.2f}"))
            listing.append({'clip': r['clip'], 'truth': r['target'] or r['category'], 'said': said, 'p': float(p_top[i])})
    cv2.imwrite(str(out), grid(strips))
    print(json.dumps(listing, indent=1))


if __name__ == '__main__':
    main()
