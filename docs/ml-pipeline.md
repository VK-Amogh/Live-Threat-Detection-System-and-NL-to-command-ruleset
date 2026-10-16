# ML pipeline: data, training, evaluation, latency

All models are trained locally on the RTX 4050 (6 GB). Only open datasets are used; each prepared dataset
carries a `provenance.json` (sources, licences, split rules, duplicate removal counts).

## Why three detectors instead of one merged model

Fire/smoke datasets label only fire and smoke; weapon datasets label only guns and knives. Merging them
into one training set teaches a detector that an unlabeled gun in a fire image is *background*. One
detector per domain avoids that, costs ~10 ms each at 512–640 px, and the inference service runs them
together (`config/models.yaml`). Violence has no box, so it uses a separate scene-level recogniser.

## Data

| Domain | Sources | Role |
|---|---|---|
| Fire / smoke | D-Fire (Kaggle mirror of the official split), Jimei (Hugging Face, test portion) | train / val / held-out test |
| Gun / knife | Univ. of Granada–Seville real CCTV frames (1920×1080, VOC XML), HARIS curated set (web + UCF-Crime hard negatives) | CCTV split by **camera segment**; HARIS `val` held out as test |
| Violence | SCVD (CCTV), RWF-2000 (surveillance), Real-Life Violence Situations, Hockey Fights | official splits where they exist, otherwise **block** splits |

### Leakage control (the part that makes the benchmark honest)

* Perceptual hashing (dHash-64, Hamming ≤ 4) groups near-duplicates across *all* sources. A group inherits
  its most protected split (test > val > train); copies in weaker splits are dropped. On D-Fire this removed
  roughly half of the official training images: its random train/test split contains frames of the same
  fires from the same fixed cameras (verified by eye on a contact sheet).
* Fixed-camera CCTV frames are perceptually identical by construction, so dedupe is disabled for that source
  and the split is by video segment instead (adjacent frames never straddle train/test).
* Violence clips are split in **blocks of consecutive clip numbers**. A per-clip random split gave a
  validation AUC of 0.998 and a held-out CCTV AUC of 0.72 — the validation set was a near-copy of training.
* Thresholds are selected on the validation split only. For the two YOLO detectors the test split was evaluated
  once per trained model. **For violence it was not**: the data mix, split scheme and still-image negatives were
  chosen over several iterations while looking at held-out results (a per-clip split exposed leakage; SCVD
  CCTV false alarms exposed the missing non-person negatives). Treat the violence test numbers — especially the
  82-clip SCVD CCTV figure — as moderately optimistic, not as a clean one-shot estimate.

## Training

* `scripts/train_detector.py`: YOLO26s from COCO weights, AMP, mosaic + mild HSV/scale/rotation
  augmentation, cosine LR, wall-clock budget (`--time`) so a run always ends on schedule. Progress and
  metrics stream to `storage/training.json` (System screen).
* Violence: frozen DINOv2-base features (CLS + mean patch, 224²) cached for 16 frames per clip, plus flipped
  and cropped views of training clips; a 2-layer temporal transformer is trained on windows of
  1/2/4/8/16 frames, so the *same weights score a single uploaded still and a live/video window*. The
  per-frame auxiliary head keeps stills meaningful. Training takes about a minute once features exist.

## Evaluation (`scripts/benchmark_detector.py`, `scripts/violence/train_head.py`)

* mAP50 / mAP50-95 (Ultralytics), per-class precision/recall/F1 at the **deployed** threshold, image-level
  alert precision/recall, and the **false-alarm rate on threat-free images** (the "all clear" case).
* The previous weights (`fire.pt`, `best.pt`) are scored on the same images; new weights are promoted only
  if they win.
* Violence is reported per dataset and as clip-level (8 frames) and single-frame results.
* Latency is the warm per-frame time (FP16, resize + inference + NMS) and peak VRAM.

## How detections become incidents

`/predict` returns detections whose class maps to a category in `config/class_map.yaml`
(`fire→FIRE`, `smoke→SMOKE`, `gun|knife→WEAPON_DETECTED`, `violence→FIGHT`). For still images the first
detection above its calibrated threshold creates an incident. For video and live sources a candidate must
persist in 2 of the last 4 sampled frames (2 fps) unless a single frame is already ≥ 0.85 confident; the
violence recogniser keeps a per-source window of the last 8 frames in the detector service.
Humans make the final call: incidents are `NEEDS_REVIEW` until an operator confirms or dismisses them.

## Assistant latency choices

* Streaming (NDJSON) so the first tokens appear while the rest generates.
* Gemma 4's "thinking" mode is switched off (`think: false`): with it on, the first visible token waited on
  hidden reasoning (first token was ~43 s cold on CPU under training load; ~0.1 s warm with a cached prefix and
  thinking off — a warm, text-only, prefix-cached number, not a typical one).
* The local model is loaded at API start-up (`keep_alive` 30 min) so the first question does not pay the load.
* A static system prompt + stable dossier layout so Ollama can reuse its KV prefix; flash attention and q8 KV
  cache on the Ollama server.
* Retrieval is a compact dossier (detector boxes with locations, source timeline, aggregate statistics) plus
  at most 6 real frames (annotated keyframe + frames sampled around the detection), not raw logs.
* Local model: Gemma 4 E2B — the only Gemma 4 size that fits next to the detectors on a 6 GB card. The stock
  `gemma4:e2b` Ollama build already ships its official multi-token-prediction drafter (`DRAFT` blob,
  `draft_num_predict 3`). Whether that speeds anything up on this machine is measured in `docs/benchmarks.md`
  against a copy of the same model without the drafter; no speed-up is claimed beyond what is measured there.
* Detector latency is ~12 ms/frame (FP16, fused) while video/live sampling is 2 fps, so the detector is not the
  bottleneck and ONNX/TensorRT export was deliberately not pursued; JPEG transport + the LLM dominate.
