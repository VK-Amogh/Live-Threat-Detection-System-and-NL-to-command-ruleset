#!/usr/bin/env bash
# Extra fire/smoke sources for diversity (sequential, resumable).
cd "$(dirname "$0")/../.."
K=.venv/Scripts/kaggle.exe
RAW=storage/datasets/raw/kaggle
export KAGGLE_CONFIG_DIR=~/.kaggle
for d in simuletic/cctv-smoke-and-fire-emergency-detection-dataset roscoekerby/firesmoke-detection-yolo-v9 ironwolf437/fire-detection-dataset; do
  $K datasets download -d $d -p $RAW/$(basename $d) --unzip >> storage/logs/dl_fire_extra.log 2>&1
done
echo done >> storage/logs/dl_fire_extra.log
