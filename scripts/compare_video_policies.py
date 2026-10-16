"""Compare temporal alert rules using saved, thresholded frame detections."""
import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLASS_TO_CATEGORY = {'fire': 'FIRE', 'smoke': 'SMOKE', 'gun': 'WEAPON_DETECTED',
                     'knife': 'WEAPON_DETECTED', 'violence': 'FIGHT'}


def alerts(frames, k, n, immediate, thresholds=None, k_by_category=None):
    histories = defaultdict(lambda: deque(maxlen=n))
    incidents = set()
    for frame in frames:
        conf = defaultdict(float)
        for detection in frame['detections']:
            if thresholds and detection['confidence'] < thresholds.get(detection['class'].lower(), 0):
                continue
            category = CLASS_TO_CATEGORY.get(detection['class'].lower())
            if category:
                conf[category] = max(conf[category], detection['confidence'])
        for category in histories.keys() | conf.keys():
            histories[category].append(conf[category] > 0)
            required = (k_by_category or {}).get(category, k)
            if conf[category] >= immediate or sum(histories[category]) >= required:
                incidents.add(category)
    return incidents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('report', type=Path)
    parser.add_argument('--weapon-grid', action='store_true')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    if args.weapon_grid:
        weaponized = [c for c in report['clips'] if 'weaponized' in c['file'].lower()]
        normal = [c for c in report['clips'] if not c['label']]
        for threshold in (0.25, 0.35, 0.45, 0.55, 0.65, 0.75):
            limits = {'gun': max(0.325, threshold), 'knife': threshold}
            tp = sum('WEAPON_DETECTED' in alerts(c['frames'], 3, 4, 0.85, limits) for c in weaponized)
            fp = sum('WEAPON_DETECTED' in alerts(c['frames'], 3, 4, 0.85, limits) for c in normal)
            print(f'weapon_threshold={threshold:.2f}: weaponized={tp}/{len(weaponized)}, false={fp}/{len(normal)}')
        return
    for k, n in [(2, 4), (3, 4), (3, 6), (4, 8)]:
        for immediate in (0.85, 1.1):
            positives = [c for c in report['clips'] if c['label']]
            negatives = [c for c in report['clips'] if not c['label']]
            rows = [(c, alerts(c['frames'], k, n, immediate)) for c in report['clips']]
            detected = sum(bool(a) for c, a in rows if c['label'])
            false = sum(bool(a) for c, a in rows if not c['label'])
            print(f'k={k}, n={n}, immediate={immediate:.2f}: detected={detected}/{len(positives)}, '
                  f'false_alerted={false}/{len(negatives)}')
    for category in ('WEAPON_DETECTED', 'FIGHT', 'SMOKE'):
        rows = [(c, alerts(c['frames'], 3, 4, 0.85, k_by_category={category: 2})) for c in report['clips']]
        detected = sum(bool(a) for c, a in rows if c['label'])
        false = sum(bool(a) for c, a in rows if not c['label'])
        print(f'k=3,n=4 except {category}=2: detected={detected}/{len(positives)}, false_alerted={false}/{len(negatives)}')


if __name__ == '__main__':
    main()
