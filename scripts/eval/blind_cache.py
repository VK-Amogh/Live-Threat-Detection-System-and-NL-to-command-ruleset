"""Replay video clips through the deployed analysis stack and cache every raw per-frame output.

python scripts/eval/blind_cache.py --set dcsass-blind --out storage/eval/dcsass_blind.json [--fps 5] [--per-category 150]
Frames are sampled exactly like the API's uploaded-video loop (stride = native fps / --fps), JPEG-encoded at quality 85,
and run through server.analyse() with a per-clip stream id, so the temporal violence window behaves as in production.
Thresholds are NOT applied here; scripts/eval/blind_score.py replays any policy offline from the cache.
"""
import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402


def clips(which, per_category, seed=7, exclude=frozenset()):
    rng = random.Random(seed)
    if which == 'dcsass-blind' or which == 'dcsass-dev':
        want = 'blind' if which.endswith('blind') else 'dev'
        rows = [r for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text()) if r['split'] == want and r['clip'] not in exclude]
        groups = defaultdict(list)
        for r in rows:
            groups[(r['category'], r['label'])].append(r)
        chosen = []
        for key, items in sorted(groups.items()):
            rng.shuffle(items)
            chosen += items[: per_category if key[1] == 1 else per_category * 2]
        return [{'path': r['path'], 'id': r['clip'], 'category': r['category'], 'label': r['label'], 'parent': r['parent']} for r in chosen]
    manifest = json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text())
    if which in ('scvd-test', 'scvd-val'):
        split = which.split('-')[1]
        return [{'path': r['path'], 'id': Path(r['path']).stem, 'category': 'SCVD', 'label': r['label'], 'parent': Path(r['path']).stem} for r in manifest if r['dataset'] == 'SCVD (CCTV)' and r['split'] == split]
    if which == 'testvideos':
        return [{'path': str(p), 'id': p.stem, 'category': 'TestVideos', 'label': 1, 'parent': p.stem} for p in sorted((ROOT / 'TestVideos').glob('*')) if p.suffix.lower() in ('.avi', '.mp4', '.mov', '.mkv')]
    raise SystemExit(f'unknown set {which}')


def run_clip(item, fps_target):
    cap = cv2.VideoCapture(item['path'])
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    stride = max(1, round(fps / fps_target))
    stream = 'eval-' + item['id']
    frames, index = [], 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % stride == 0:
                ok, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                image = Image.open(__import__('io').BytesIO(jpg.tobytes())).convert('RGB')
                raw = server.analyse(image, stream)
                frames.append({'t_ms': round(index / fps * 1000), 'proposals': [{k: p[k] for k in ('model', 'cls', 'conf', 'box', 'verifier') if k in p} for p in raw['proposals']],
                               'violence': raw['violence'], 'motion': raw.get('motion')})
            index += 1
    finally:
        cap.release()
        server.STREAMS.pop(stream, None)
    return frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--fps', type=float, default=5.0)
    ap.add_argument('--per-category', type=int, default=150)
    ap.add_argument('--exclude', nargs='*', default=[], help='cache files whose clips must not be sampled again (fresh, never-inspected sample)')
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--shard', default='0/1', help='i/n: process every n-th clip starting at i (merge caches when scoring)')
    a = ap.parse_args()
    server.load_models()
    if server.ERRORS:
        print('model errors:', server.ERRORS)
    seen = {c['id'] for p in a.exclude for c in json.loads(Path(p).read_text())['clips']}
    items = clips(a.set, a.per_category, a.seed, frozenset(seen))
    shard, total = (int(x) for x in a.shard.split('/'))
    items = items[shard::total]
    out = []
    for n, item in enumerate(items):
        out.append({**item, 'frames': run_clip(item, a.fps)})
        if n % 50 == 0:
            print(n, '/', len(items), flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({'set': a.set, 'fps': a.fps, 'models': server.coverage(), 'clips': out}))
    print('saved', len(out), 'clips ->', a.out)


if __name__ == '__main__':
    main()
