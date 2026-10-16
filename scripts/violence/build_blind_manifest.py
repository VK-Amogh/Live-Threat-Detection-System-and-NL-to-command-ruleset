"""DCSASS blind-parent clips for offline violence evaluation (never used for training or calibration)."""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
rng = random.Random(5)
rows = [r for r in json.loads((ROOT / 'storage/datasets/dcsass/manifest.json').read_text()) if r['split'] == 'blind']
by = {}
for r in rows:
    by.setdefault((r['category'], r['label']), []).append(r)
out = []
for (category, label), items in sorted(by.items()):
    rng.shuffle(items)
    out += [{'path': r['path'], 'label': 1 if (label == 1 and category in ('Fighting', 'Assault', 'Abuse')) else 0, 'split': 'test', 'dataset': f'DCSASS blind/{category}/{label}',
             'category': category, 'dcsass_label': label} for r in items[:120]]
dest = ROOT / 'storage/datasets/violence/blind_manifest.json'
dest.write_text(json.dumps(out))
print(len(out), 'blind clips')
