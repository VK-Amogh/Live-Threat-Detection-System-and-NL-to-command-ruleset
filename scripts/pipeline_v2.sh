#!/usr/bin/env bash
# v2 chain: fire/smoke v2 finishes -> benchmark vs v1 -> weapons v2 training -> benchmark vs v1.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
wait_for() { until $PY -c "import json,sys; r=json.load(open('storage/training.json'))['runs'].get('$1',{}); sys.exit(0 if r.get('status') in ('completed','failed') else 1)"; do sleep 20; done; }
weights() { $PY -c "import json; print(json.load(open('storage/training.json'))['runs']['$1'].get('weights',''))"; }
wait_for fire_smoke_v2
W=$(weights fire_smoke_v2); echo "fire v2 weights: $W"
[ -n "$W" ] && $PY scripts/benchmark_detector.py --name fire_smoke_v2 --weights "$W" --data storage/datasets/fire_smoke_v2/data.yaml \
   --incumbent storage/models/fire_smoke.pt --map fire=fire --map smoke=smoke --export-to storage/models/fire_smoke_v2.pt > storage/logs/bench_fire_smoke_v2.log 2>&1
echo "fire v2 benchmarked"
until grep -q "^{'images'" storage/logs/prepare_weapons_v2.log; do sleep 15; done
$PY scripts/train_detector.py --name weapons_v2 --data storage/datasets/weapons_v2/data.yaml --model storage/models/weapons.pt --epochs 30 --time 1.25 --imgsz 704 --batch 12 --patience 8 > storage/logs/train_weapons_v2.log 2>&1
W=$(weights weapons_v2); echo "weapons v2 weights: $W"
[ -n "$W" ] && $PY scripts/benchmark_detector.py --name weapons_v2 --weights "$W" --data storage/datasets/weapons_v2/data.yaml \
   --incumbent storage/models/weapons.pt --map gun=gun --map knife=knife --export-to storage/models/weapons_v2.pt > storage/logs/bench_weapons_v2.log 2>&1
echo "weapons v2 benchmarked"
