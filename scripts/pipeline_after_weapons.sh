#!/usr/bin/env bash
# Wait for the weapons run, then benchmark it against the previous weapon model and stage it as storage/models/weapons.pt.
# Enabling it in config/models.yaml stays a deliberate step after reading the report.
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python.exe
until $PY -c "import json,sys; r=json.load(open('storage/training.json'))['runs']['weapons']; sys.exit(0 if r['status'] in ('completed','failed') else 1)"; do sleep 15; done
W=$($PY -c "import json; print(json.load(open('storage/training.json'))['runs']['weapons'].get('weights',''))")
echo "weapons weights: $W"
[ -n "$W" ] && $PY scripts/benchmark_detector.py --name weapons --weights "$W" --data storage/datasets/weapons/data.yaml \
    --incumbent storage/models/best.pt --map weapon=weapon --group weapon=gun,knife --export-to storage/models/weapons.pt > storage/logs/bench_weapons.log 2>&1
echo "weapons benchmark done"
