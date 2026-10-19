"""Manifest for the crime-type classifier: DCSASS (UCF-Crime CCTV) categories + a 'none' class, split by source video.

python scripts/crime/build_manifest.py
Reuses the DCSASS dev/blind parent split of scripts/data/prepare_dcsass.py (sha1 of the parent video name, 30 % blind), so the blind parents
are the same ones every other SafeSpace model is scored on and no model has been trained on them. Rules that came from earlier mistakes:
* Split by PARENT video, never by clip: sub-clips of one source video are near-identical scenes. Cross-validation folds (dev only) are grouped by parent.
* DCSASS has no 'Normal' folder in this copy and its label-0 sub-clips are coarse (a "normal" sub-clip of a Shooting/Abuse/Arrest video often
  shows people, pre-event or the event itself - see docs/ml-pipeline.md). 'none' training clips therefore come only from calm categories'
  label-0 sub-clips plus ordinary footage from the violence collection (SCVD normal, RLVS non-violence, RWF non-fight, hockey non-fight).
  Label-0 sub-clips of the other categories are kept for the blind diagnostics only (target = null).
* Arson (visible fire) is out of scope because fire/smoke detection was removed on purpose: never trained, scored only to show where it lands.
Types (label-1 sub-clips only) are the 12 remaining DCSASS categories. Blind parents hold every clip (all categories, both labels), never trained on.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/inference'))
from crime_head import TYPES  # noqa: E402,F401  (12 DCSASS categories the head is trained on; Arson is excluded on purpose)

OUT = ROOT / 'storage/datasets/crime/manifest.json'
OUT_OF_SCOPE = ['Arson']
CALM = {'RoadAccidents', 'Shoplifting', 'Stealing', 'Vandalism', 'Burglary'}
EXTERNAL_NONE = ('Hockey fights', 'RWF-2000 (surveillance)', 'Real Life Violence Situations', 'SCVD (CCTV)')
FOLDS = 5


def number_of(path):
    digits = re.findall(r'\d+', Path(path).stem)
    return int(digits[0]) if digits else 0


def build():
    rows = []
    for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text()):
        cat, label, blind = r['category'], r['label'], r['split'] == 'blind'
        if cat in OUT_OF_SCOPE:
            if not blind:
                continue
            target, source = None, 'arson_out_of_scope'
        elif label == 1:
            target, source = cat, 'dcsass_label1'
        elif cat in CALM:
            target, source = 'none', 'dcsass_calm_label0'
        elif blind:
            target, source = None, 'dcsass_noncalm_label0'     # ambiguous ground truth: diagnostics only
        else:
            continue
        rows.append({'path': r['path'], 'clip': r['clip'], 'parent': r['parent'], 'category': cat, 'dcsass_label': label, 'target': target, 'source': source,
                     'role': 'blind' if blind else 'dev', 'split': 'test' if blind else 'train', 'dataset': 'DCSASS'})
    for r in json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text()):
        if r['dataset'] not in EXTERNAL_NONE or r['label'] != 0:
            continue
        blind = r['split'] == 'test'      # the collections' own official/blocked test splits stay untouched by training
        stem = Path(r['path']).stem
        unit = stem.rsplit('_', 1)[0] if r['dataset'].startswith('RWF') else str(number_of(r['path']) // 25)   # RWF: <video id>_<segment>; others: blocks of consecutive clips
        group = f"{r['dataset']}:{r['split']}:{unit}"
        rows.append({'path': r['path'], 'clip': Path(r['path']).stem, 'parent': group, 'category': 'external', 'dcsass_label': None, 'target': 'none', 'source': 'external_none',
                     'role': 'blind' if blind else 'dev', 'split': 'test' if blind else 'train', 'dataset': r['dataset']})
    dev = [i for i, r in enumerate(rows) if r['role'] == 'dev']
    folds = StratifiedGroupKFold(FOLDS, shuffle=True, random_state=0)
    y = [rows[i]['target'] for i in dev]
    groups = [rows[i]['parent'] for i in dev]
    for fold, (_, held) in enumerate(folds.split(dev, y, groups)):
        for j in held:
            rows[dev[j]]['fold'] = fold
    for r in rows:
        r.setdefault('fold', -1)
    return rows


def summarize(rows):
    table = defaultdict(lambda: [0, set()])
    for r in rows:
        key = (r['role'], r['target'] or f"({r['source']})")
        table[key][0] += 1
        table[key][1].add(r['parent'])
    print(f'{len(rows)} clips; {len({r["parent"] for r in rows})} parent videos / blocks')
    for key in sorted(table, key=lambda k: (k[0], str(k[1]))):
        print(f'  {key[0]:5s} {key[1]:28s} clips {table[key][0]:5d}  parents {len(table[key][1]):4d}')
    dev_parents = {r['parent'] for r in rows if r['role'] == 'dev'}
    blind_parents = {r['parent'] for r in rows if r['role'] == 'blind'}
    assert not dev_parents & blind_parents, 'a parent video is in both dev and blind'
    for f in range(FOLDS):
        in_fold = {r['parent'] for r in rows if r['fold'] == f}
        assert not in_fold & {r['parent'] for r in rows if r['role'] == 'dev' and r['fold'] != f}, 'parent split across folds'
    print('fold sizes', dict(sorted(Counter(r['fold'] for r in rows if r['role'] == 'dev').items())))


def main():
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows))
    summarize(rows)


if __name__ == '__main__':
    main()
