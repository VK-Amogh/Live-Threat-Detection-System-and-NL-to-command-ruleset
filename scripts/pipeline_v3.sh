#!/usr/bin/env bash
# After weapons v2: regenerate proposals with the v2 detectors, rebuild verifier data, retrain and calibrate the verifier.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
until grep -q "weapons v2 benchmarked" storage/logs/pipeline_v2.log; do sleep 20; done
W=storage/models/weapons_v2.pt
for d in fire_smoke_v2 weapons_v2; do
  $PY scripts/eval/raw_detections.py --index storage/datasets/$d/images --out storage/eval/${d}_raw.json --weapons $W > storage/logs/raw_$d.log 2>&1
done
$PY scripts/eval/raw_detections.py --index storage/datasets/negpool/index.json --out storage/eval/negpool_raw.json --weapons $W > storage/logs/raw_negpool.log 2>&1
echo "raw caches done"
$PY scripts/verify/adapt_crops.py > storage/logs/adapt_crops.log 2>&1
$PY scripts/verify/build_crops.py > storage/logs/build_crops.log 2>&1
echo "crops done"
$PY scripts/verify/train_verifier.py > storage/logs/train_verifier.log 2>&1
echo "verifier trained"
