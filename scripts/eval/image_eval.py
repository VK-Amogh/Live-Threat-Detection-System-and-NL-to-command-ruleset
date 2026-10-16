"""End-to-end still-image evaluation of the deployed stack (YOLO proposals -> verifier -> thresholds) on held-out images.

python scripts/eval/image_eval.py --out storage/benchmarks/stack_images.json
Positives: fire/smoke and weapon test images with annotations (image counts as detected when any alert of the right class
appears — box position is not required for an alarm). Negatives: threat-free test frames from videos the system never saw
(RLVS, hockey, SCVD, DCSASS calm categories) and the annotated datasets' own clean test images.
Reports YOLO-only (raw detector thresholds) vs the full stack, per source.
"""
import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402

CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}
FAMILY = {'fire': 'FIRE/SMOKE', 'smoke': 'FIRE/SMOKE', 'gun': 'WEAPON', 'knife': 'WEAPON'}
FAMILIES = ('FIRE/SMOKE', 'WEAPON', 'FIGHT')


def gt_classes(label_file, names):
    return {names[int(line.split()[0])] for line in label_file.read_text().splitlines() if line.strip()} if label_file.exists() else set()


def alerts(raw, use_verifier):
    out = set()
    for p in raw['proposals']:
        if use_verifier and 'verifier' in p:
            ok = p['verifier'] >= server.VERIFIER[1][p['cls']]
        else:
            ok = p['conf'] >= p['thresholds'].get(p['cls'], 1.0)
        if ok:
            out.add(FAMILY[p['cls']])
    if raw.get('violence'):
        score, frames = raw['violence']
        if score >= server.VIOLENCE.threshold(frames):     # a still image: T=1 threshold of the scene head
            out.add('FIGHT')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-neg-per-source', type=int, default=1500)
    a = ap.parse_args()
    server.load_models()
    cases = []   # (path, source, truth family set)
    for domain, names in (('fire_smoke_v2', ['fire', 'smoke']), ('weapons_v2', ['gun', 'knife'])):
        root = ROOT / 'storage/datasets' / domain
        for img in sorted((root / 'images/test').glob('*.jpg')):
            truth = {FAMILY[c] for c in gt_classes(root / 'labels/test' / (img.stem + '.txt'), names)}
            if img.stem.startswith('video'):   # video-frame negatives are reported once, below, with the blind frames
                continue
            cases.append((str(img), f'{domain.split("_")[0]}:{img.stem.split("_")[0]}', truth))
    clip_cat = {r['clip']: r['category'] for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text())}
    per_source = defaultdict(int)
    for item in json.loads((ROOT / 'storage/datasets/negpool/index.json').read_text()):
        if item['split'] != 'test':
            continue
        if item['source'] == 'dcsass' and clip_cat.get(Path(item['path']).stem.rsplit('_', 1)[0]) not in CALM:
            continue
        if per_source[item['source']] >= a.max_neg_per_source:
            continue
        per_source[item['source']] += 1
        cases.append((item['path'], f'video-frames:{item["source"]}', set()))
    # Violent frames: 3 frames from every violent TEST clip (RWF-2000 / SCVD / RLVS / hockey) + DCSASS blind Fighting clips.
    sys.path.insert(0, str(ROOT / 'scripts/data'))
    from extract_frames import grab
    temp = ROOT / 'storage/eval/violent_frames'
    temp.mkdir(parents=True, exist_ok=True)
    violent = [r for r in json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text()) if r['split'] == 'test' and r['label'] == 1 and r['dataset'] != 'Threat-free stills (fire scenes, CCTV, hard negatives)']
    violent += [{'path': r['path'], 'dataset': 'DCSASS blind Fighting'} for r in json.loads((ROOT / 'storage/datasets/violence/blind_manifest.json').read_text()) if r['category'] == 'Fighting' and r['label'] == 1]
    for r in violent:
        for frame in grab((r['path'], str(temp), Path(r['path']).stem.replace(' ', '_') + '_v', 3)):
            cases.append((frame, 'violent-frames:' + r['dataset'].split(' (')[0], {'FIGHT'}))
    stats = defaultdict(lambda: defaultdict(int))
    for n, (path, source, truth) in enumerate(cases):
        raw = server.analyse(Image.open(path).convert('RGB'), None)
        for mode, flag in (('detector_only', False), ('full_stack', True)):
            got = alerts(raw, flag)
            s = stats[(source, mode)]
            s['images'] += 1
            for fam in FAMILIES:
                if fam in truth:
                    s[f'{fam}_pos'] += 1
                    s[f'{fam}_hit'] += fam in got
                elif not truth:
                    s[f'{fam}_false_alarm'] += fam in got
            if not truth:
                s['clean'] += 1
        if n % 1000 == 0:
            print(n, '/', len(cases), flush=True)
    report = {f'{src}|{mode}': dict(v) for (src, mode), v in stats.items()}
    Path(a.out).write_text(json.dumps(report, indent=1))
    for (src, mode), v in sorted(stats.items()):
        parts = [f"{src:28s} {mode:14s} n={v['images']:5d}"]
        for fam in FAMILIES:
            if v[f'{fam}_pos']:
                parts.append(f"{fam} recall {v[f'{fam}_hit'] / v[f'{fam}_pos']:.1%}")
            if v['clean']:
                parts.append(f"{fam} false-alarm {v[f'{fam}_false_alarm'] / v['clean']:.2%}")
        print('  '.join(parts))


if __name__ == '__main__':
    main()
