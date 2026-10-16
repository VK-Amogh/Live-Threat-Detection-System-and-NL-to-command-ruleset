"""Visual + per-stage audit of the blind fire/smoke clips (run after blind_cache.py; needs no GPU).

python scripts/eval/audit_fire_blind.py storage/eval/dcsass_fresh_s0.json storage/eval/dcsass_fresh_s1.json

Writes storage/benchmarks/blind_fresh_fire_audit.json (rendered by report.py) and contact sheets to storage/eval/audit/: one middle-ish frame of every Arson/1 clip (is fire visible at all?) and the frame at
which each Explosion/0 clip alerted (is the alert a real smoke cloud?).  Prints, per Arson parent video, how many sampled frames had any
fire/smoke proposal and the best raw-detector and verifier scores, i.e. at which stage the clips are lost.  Look at the images yourself
before quoting a number: the dataset's labels are coarse.
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

os.environ['CUDA_VISIBLE_DEVICES'] = ''  # scoring from cached model outputs only; keep the GPU free
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts/eval')]
import blind_score  # noqa: E402
import cv2  # noqa: E402
import numpy as np  # noqa: E402


def grab(path, t_ms=None, frac=None):
    cap = cv2.VideoCapture(path)
    n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 25
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(int(t_ms / 1000 * fps) if t_ms is not None else int(n * frac), n - 1)))
    ok, image = cap.read()
    cap.release()
    return image if ok else np.zeros((240, 320, 3), np.uint8)


def sheet(items, out, cols, w, h):
    canvas = np.zeros((((len(items) + cols - 1) // cols) * h, cols * w, 3), np.uint8)
    for i, (image, label) in enumerate(items):
        tile = cv2.resize(image, (w, h))
        cv2.putText(tile, label, (3, 12), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 255, 255), 1)
        canvas[(i // cols) * h:(i // cols + 1) * h, (i % cols) * w:(i % cols + 1) * w] = tile
    cv2.imwrite(str(out), canvas)


def main():
    clips = [c for p in sys.argv[1:] for c in json.loads(Path(p).read_text())['clips']]
    result, _ = blind_score.evaluate(clips, True)
    out = ROOT / 'storage/eval/audit'
    out.mkdir(parents=True, exist_ok=True)
    arson = [c for c in clips if c['category'] == 'Arson' and c['label'] == 1]
    print(f"FIRE/SMOKE recall {result['FIRE/SMOKE']['detected']}/{result['FIRE/SMOKE']['positive_clips']}")
    sheet([(grab(c['path'], frac=.6), ('ALERT ' if 'FIRE/SMOKE' in c['_alerts'] else '') + c['id'][-12:]) for c in arson], out / 'arson1.jpg', 8, 200, 150)
    explosion = [c for c in clips if c['category'] == 'Explosion' and c['label'] == 0 and 'FIRE/SMOKE' in c['_alerts']]
    if explosion:
        sheet([(grab(c['path'], t_ms=c['_alerts']['FIRE/SMOKE']), c['id'][-14:]) for c in explosion], out / 'explosion0_alerts.jpg', 3, 420, 315)
    per_parent = defaultdict(lambda: [0, 0, 0, 0.0, 0.0])
    for c in arson:
        row = per_parent[c['parent']]
        row[0] += 1
        for f in c['frames']:
            row[1] += 1
            props = [p for p in f['proposals'] if p['model'] == 'fire_smoke']
            row[2] += bool(props)
            for p in props:
                row[3], row[4] = max(row[3], p['conf']), max(row[4], p['verifier'] if isinstance(p.get('verifier'), float) else 0.0)
    print('parent                  clips frames frames-with-proposal best-detector best-verifier')
    for parent, (n, frames, with_props, det, ver) in sorted(per_parent.items()):
        print(f'{parent:22s} {n:5d} {frames:6d} {with_props:19d} {det:13.2f} {ver:13.2f}')
    bench = ROOT / 'storage/benchmarks'
    (bench / 'blind_fresh_fire_audit.json').write_text(json.dumps({
        'arson1_clips': len(arson), 'arson1_alerted': sum('FIRE/SMOKE' in c['_alerts'] for c in arson), 'explosion0_alerted': len(explosion),
        'per_parent': {k: {'clips': v[0], 'frames': v[1], 'frames_with_proposal': v[2], 'best_detector_conf': round(v[3], 2), 'best_verifier_prob': round(v[4], 2)} for k, v in sorted(per_parent.items())}}, indent=2))
    print(f'sheets in {out}')


if __name__ == '__main__':
    main()
