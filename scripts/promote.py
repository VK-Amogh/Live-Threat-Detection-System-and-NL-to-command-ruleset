"""Promote a benchmarked candidate to the deployed model name, keeping the previous weights as <name>_prev.

python scripts/promote.py fire_smoke fire_smoke_v2
Copies storage/models/<candidate>.{pt,json} -> <name>.{pt,json} and storage/benchmarks/<candidate>.json -> <name>.json.
The detector service reads weights by the names in config/models.yaml, so a restart (or POST /reload) activates them.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(name, candidate):
    models, bench = ROOT / 'storage/models', ROOT / 'storage/benchmarks'
    for suffix, folder in (('.pt', models), ('.json', models), ('.json', bench)):
        current, new = folder / f'{name}{suffix}', folder / f'{candidate}{suffix}'
        if not new.exists():
            sys.exit(f'missing {new}')
        if current.exists():
            shutil.copy2(current, folder / f'{name}_prev{suffix}')
        shutil.copy2(new, current)
    print(f'promoted {candidate} -> {name}; previous kept as {name}_prev')


if __name__ == '__main__':
    main(*sys.argv[1:3])
