#!/usr/bin/env bash
# Strictly sequential, priority-ordered fetch (the link is slow and shared; parallel streams just starve each other).
# Every step resumes from partial files.
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
K=.venv/Scripts/kaggle.exe
L=storage/logs
RAW=storage/datasets/raw
export KAGGLE_CONFIG_DIR=~/.kaggle DL_WORKERS=8
echo "[1] haris weapons (Kaggle)";  $K datasets download -d turkikhalidalshuaibi/haris-weapon-detection-dataset-curated -p $RAW/kaggle/haris --unzip > $L/dl_k_haris.log 2>&1
echo "[2] dinov2 encoder";          $PY -c "from huggingface_hub import snapshot_download; snapshot_download('facebook/dinov2-base', allow_patterns=['*.json','model.safetensors'])" > $L/dl_dinov2.log 2>&1
echo "[3] SCVD CCTV violence";      $K datasets download -d toluwaniaremu/smartcity-cctv-violence-detection-dataset-scvd -p $RAW/kaggle/scvd --unzip > $L/dl_k_scvd.log 2>&1
echo "[4] RLVS street violence";    $PY scripts/data/download.py 34data/real-life-violence > $L/dl_rlvs.log 2>&1
echo "[done]"
