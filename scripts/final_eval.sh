#!/usr/bin/env bash
# Frozen-configuration evaluation: fresh blind DCSASS sample (excluding every clip inspected before) + still-image stack.
# Run with the detector service STOPPED (each process loads the models itself; 6 GB cannot hold everything).
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
EX="storage/eval/dcsass_blind_v1_s0.json storage/eval/dcsass_blind_v1_s1.json storage/eval/dcsass_blind_v2_s0.json storage/eval/dcsass_blind_v2_s1.json"
for i in 0 1; do
  $PY -u scripts/eval/blind_cache.py --set dcsass-blind --per-category 50 --fps 4 --seed 11 --shard $i/2 --exclude $EX --out storage/eval/dcsass_fresh_s$i.json > storage/logs/blind_fresh_s$i.log 2>&1 &
done
wait
$PY scripts/eval/blind_score.py --cache storage/eval/dcsass_fresh_s0.json storage/eval/dcsass_fresh_s1.json --json storage/benchmarks/blind_fresh.json --errors 25 > storage/logs/blind_fresh_score.log 2>&1
$PY scripts/eval/blind_score.py --cache storage/eval/dcsass_fresh_s0.json storage/eval/dcsass_fresh_s1.json --no-verifier > storage/logs/blind_fresh_score_noverifier.log 2>&1
$PY -u scripts/eval/image_eval.py --out storage/benchmarks/stack_images.json > storage/logs/image_eval.log 2>&1
echo "final eval done"
