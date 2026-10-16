#!/usr/bin/env bash
# Chain: wait for fire/smoke training -> benchmark+promote it -> immediately train the weapons detector.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
until $PY -c "import json,sys; r=json.load(open('storage/training.json'))['runs']['fire_smoke']; sys.exit(0 if r['status'] in ('completed','failed') else 1)"; do sleep 10; done
W=$($PY -c "import json; print(json.load(open('storage/training.json'))['runs']['fire_smoke'].get('weights',''))")
echo "fire weights: $W"
if [ -n "$W" ]; then
  $PY scripts/benchmark_detector.py --name fire_smoke --weights "$W" --data storage/datasets/fire_smoke/data.yaml \
      --incumbent storage/models/fire.pt --map fire=fire --export-to storage/models/fire_smoke.pt > storage/logs/bench_fire_smoke.log 2>&1
fi
echo "weapons training start"
$PY scripts/train_detector.py --name weapons --data storage/datasets/weapons/data.yaml --model weights/yolo26s.pt --epochs 40 --time 1.2 --imgsz 640 --batch 12 --patience 10 > storage/logs/train_weapons.log 2>&1
echo "weapons training end"
