"""Score a cached blind replay with the PRODUCTION decision code: server.decide() + the API's temporal persistence rule.

python scripts/eval/blind_score.py --cache storage/eval/dcsass_blind_v3_s0.json storage/eval/dcsass_blind_v3_s1.json [--errors 20]

Nothing here re-implements thresholds or fusion: raw model outputs come from the cache (written by blind_cache.py through
server.analyse), `decide()` turns them into detections exactly as the running service does (verifier thresholds, scene+motion
violence ensemble, still-threshold fallback for the first frames of a stream), and the k-of-n rule with the strong-detector
bypass mirrors app.pipeline.process_frame for uploaded video (config/worker.yaml).

Ground truth (clip level). DCSASS sub-clip labels are coarse: a "normal" sub-clip of a fight/arson video can show the event,
so clean clips are chosen by CATEGORY (both labels), never by label alone.
  FIGHT      : positive = Fighting/Assault/Abuse label 1.  clean = RoadAccidents, Shoplifting, Stealing, Vandalism, Burglary
  WEAPON     : positives are NOT scored as recall (a Shooting/Robbery clip may not show the weapon on screen);
               clean = RoadAccidents, Shoplifting, Stealing, Vandalism, Burglary, Arson, Explosion
"""
import argparse
import json
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402

ALL = {'Abuse', 'Arrest', 'Arson', 'Assault', 'Burglary', 'Explosion', 'Fighting', 'RoadAccidents', 'Robbery', 'Shooting', 'Shoplifting', 'Stealing', 'Vandalism'}
CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}
FAMILY = {'WEAPON_DETECTED': 'WEAPON', 'FIGHT': 'FIGHT'}
GROUPS = {
    'FIGHT': {'pos': {'Fighting', 'Assault', 'Abuse'}, 'clean_cats': CALM},
    'WEAPON': {'pos': set(), 'clean_cats': CALM | {'Arson', 'Explosion'}},
}


def install_production_config():
    """Point server.decide at the deployed thresholds (the same sidecars the service reads)."""
    server.MAPPINGS = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
    verifier = json.loads((ROOT / 'storage/models/verifier.json').read_text())['thresholds']
    server.VERIFIER = (None, verifier)
    yolo = {}
    for spec in yaml.safe_load((ROOT / 'config/models.yaml').read_text())['models']:
        sidecar = (ROOT / spec['path']).with_suffix('.json')
        if sidecar.exists():
            yolo[spec['name']] = json.loads(sidecar.read_text()).get('thresholds', {})
    head = json.loads((ROOT / 'storage/models/violence_head.json').read_text())['thresholds']
    thresholds = {int(k): v for k, v in head.items()}

    def threshold(frames):
        usable = [k for k in thresholds if k <= frames] or [min(thresholds)]
        return thresholds[max(usable)]

    server.VIOLENCE = SimpleNamespace(threshold=threshold)
    ensemble = ROOT / 'storage/models/violence_ensemble.json'
    server.ENSEMBLE = json.loads(ensemble.read_text()) if ensemble.exists() else None
    return yolo


def worker_policy():
    t = yaml.safe_load((ROOT / 'config/worker.yaml').read_text())['temporal_filter']
    return int(t.get('uploaded_video_k_hits', t['k_hits'])), int(t['n_window']), float(t['immediate_confidence'])


def clip_alerts(clip, yolo_thresholds, use_verifier, policy):
    k, n, immediate = policy
    windows = defaultdict(lambda: deque(maxlen=n))
    alerts = {}
    verifier = server.VERIFIER
    if not use_verifier:
        server.VERIFIER = None
    try:
        for f in clip['frames']:
            proposals = [{**p, 'thresholds': yolo_thresholds.get(p['model'], {})} for p in f['proposals']]
            detections = server.decide({'proposals': proposals, 'violence': f['violence'], 'motion': f.get('motion'), 'size': (1, 1)})
            hit = {}
            for d in detections:
                if d.category:
                    hit[d.category] = max(hit.get(d.category, 0.0), d.detector_confidence or 0.0)
            for cat in set(windows) | set(hit):
                windows[cat].append(cat in hit)
                if cat not in alerts and cat in hit and (sum(windows[cat]) >= k or hit[cat] >= immediate):
                    alerts[cat] = f['t_ms']
    finally:
        server.VERIFIER = verifier
    return alerts


def evaluate(clips, use_verifier=True):
    yolo = install_production_config()
    policy = worker_policy()
    for c in clips:
        c['_alerts'] = {FAMILY[k]: v for k, v in clip_alerts(c, yolo, use_verifier, policy).items() if k in FAMILY}
    out, errors = {}, []
    for name, g in GROUPS.items():
        pos = [c for c in clips if c['label'] == 1 and c['category'] in g['pos']]
        clean = [c for c in clips if c['category'] in g['clean_cats']]
        tp = sum(name in c['_alerts'] for c in pos)
        fp = [c for c in clean if name in c['_alerts']]
        out[name] = {'positive_clips': len(pos), 'detected': tp, 'recall': tp / len(pos) if pos else None, 'clean_clips': len(clean), 'false_alarm_clips': len(fp), 'clip_false_alarm_rate': len(fp) / max(len(clean), 1)}
        errors += [(name, c['id'], c['category'], c['label'], c['_alerts'][name]) for c in fp]
    by_cat = defaultdict(Counter)
    for c in clips:
        by_cat[f"{c['category']}/{c['label']}"]['clips'] += 1
        for fam in c['_alerts']:
            by_cat[f"{c['category']}/{c['label']}"][fam] += 1
    out['by_category'] = {k: dict(v) for k, v in sorted(by_cat.items())}
    out['policy'] = {'k_hits': policy[0], 'n_window': policy[1], 'strong_detector_bypass': policy[2], 'verifier': use_verifier}
    return out, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', required=True, nargs='+', help='one or more caches (shards are merged)')
    ap.add_argument('--no-verifier', action='store_true')
    ap.add_argument('--errors', type=int, default=0)
    ap.add_argument('--json', help='write the result here')
    a = ap.parse_args()
    clips = [c for p in a.cache for c in json.loads(Path(p).read_text())['clips']]
    result, errors = evaluate(clips, not a.no_verifier)
    print('policy', result['policy'])
    for name in GROUPS:
        r = result[name]
        rec = '—' if r['recall'] is None else f"{r['recall']:.1%} ({r['detected']}/{r['positive_clips']})"
        print(f"{name:11s} recall {rec:18s} clean-clip false alarms {r['clip_false_alarm_rate']:.1%} ({r['false_alarm_clips']}/{r['clean_clips']})")
    if a.json:
        Path(a.json).write_text(json.dumps(result, indent=2))
    for e in errors[:a.errors]:
        print('FA', e)


if __name__ == '__main__':
    main()
