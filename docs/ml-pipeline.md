# ML pipeline: data, training, evaluation, latency

Everything here was trained and measured locally on one RTX 4050 (6 GB). Only open datasets and open-weights models
are used. Numbers live in [benchmarks.md](benchmarks.md) (generated from `storage/benchmarks/*.json`); this page explains
*how* they were produced and what they do and do not mean.

**Scope.** The system detects handguns/rifles, knives and physical fights. Fire and smoke detection was built, measured and then
**removed**: on blind low-resolution CCTV only 1 of 47 Arson clips alerted although at least 15 showed visible flames, and the
detector's false-alarm behaviour on ordinary footage needed a heavy second stage to stay usable. It is listed as unsupported in
`config/models.yaml`; no fire/smoke weights are loaded, no category exists for it and nothing in the runtime, the dashboard, the phone app
or the tests uses it. (Two vestigial pieces remain on purpose: the verifier weights keep two unused class slots because
they were trained with a four-way class input, and the deployed violence head was trained with fire-scene stills among its non-violent
negatives. Retraining would remove both.)

## Architecture: detect -> verify -> decide

```
frame ──▶ YOLO26s gun/knife (640 px) ──▶ proposals (high recall, conf >= 0.10)
                                              │  crop + context, whole-frame feature
                                              ▼
                       DINOv2-base (frozen) ──▶ verifier MLP: "is this proposal a real gun / knife?"
                                              │  per-class thresholds calibrated on validation negatives
                                              ▼
 stream of frames ──▶ DINOv2 temporal head (scene / pose, also scores a single still)
                  └─▶ VideoMAE-K400 + head (motion over ~3 s)      } logistic stack ─▶ violence
                                              ▼
                              k-of-n persistence over sampled frames ─▶ incident
```

* **Why a verifier.** The first system (YOLO only, thresholds picked on its own validation split) looked fine on held-out
  images of the same datasets and failed on real video: it called violins, wine bottles, tennis players and archery sights
  "gun" at 0.7-0.8. The verifier is a second opinion trained on the detector's *own* mistakes plus true positives. Measured effect
  (benchmarks.md section 1, same images, detector-only vs full stack): on the HARIS threat-free images gun/knife false alarms fall from
  15.2 % to 2.7 % while recall rises from 86.5 % to 92.7 %; on threat-free video frames weapon false alarms fall from 2.9 % to 0.6 % (RLVS)
  and from 0.4 % to 0 % (hockey); on the small real-CCTV test set recall rises from 46.3 % to 55.6 % (54 frames).
* **Why a separate weapon detector.** Weapon datasets label only guns and knives; merging them with other domains teaches a detector that an
  unlabeled gun in an unrelated photo is background.
* **Why two violence signals.** A frame-wise encoder sees poses and scenes and works on stills; a Kinetics-pretrained video
  model sees motion. Their errors differ (the scene head is better on low-resolution CCTV, the motion head on RWF-2000). A logistic stack
  fitted on validation clips has the best AUC on blind DCSASS clips (89.1 % vs 86.6 % scene head, 83.9 % motion head) and a low calm-clip
  false-alarm rate (1.3 % vs 3.1 %), but it is *not* better at every operating point: at a common 5 % calm false-alarm budget it recalls 62.7 % of
  blind violent clips, below the scene head alone (65.1 %) and max-of-both (68.7 %) (table in benchmarks.md). It was chosen on validation clips
  and earlier blind samples, for its false-alarm behaviour, and was not changed after the fresh sample was scored.

## Data

| Domain | Sources | Role |
|---|---|---|
| Gun / knife | Seville/Granada real CCTV (1920x1080, split by camera *segment*), HARIS curated web set, Granada pistol detection (3 000 frames), Granada knife detection (2 078 frames) | train / val / test |
| Hard negatives | ~26 000 threat-free frames from RLVS, hockey, SCVD and DCSASS (calm categories only) | train / val / **test (blind false-alarm frames, never trained on)** |
| Violence | RWF-2000 (official split), RLVS, SCVD, Hockey Fights, DCSASS dev parents, threat-free stills | train / val / test |
| Blind video | DCSASS (UCF-Crime CCTV) **parents never used** in training, mining or calibration | evaluation only |

### Label-noise lessons (each one changed a number)

* DCSASS sub-clip labels are coarse: a "normal" sub-clip of an Arson/Explosion/Shooting/fight video can show the event.
  Using them as negatives made early false-alarm figures meaningless (the top-scoring "false alarms" were real events).
  Negatives now come from calm *categories* (RoadAccidents, Shoplifting, Stealing, Vandalism, Burglary), never from labels alone.
* Un-annotated CCTV frames are not clean negatives: the verifier's highest-scoring "gun false alarms" included real handguns
  in frames nobody annotated. v2 drops them.
* Violence clips are split in blocks of consecutive clip numbers; a per-clip random split gave validation AUC 0.998 and held-out
  CCTV AUC 0.72.

### Leakage control

dHash-64 groups near-duplicates across all sources; a group inherits its most protected split (test > val > train) and the
copies in weaker splits are dropped. Fixed-camera CCTV frames and video-frame negatives are exempt (split by segment / clip).

## Training

* Detector: `scripts/train_detector.py` — YOLO26s, AMP, mosaic + HSV/scale/rotation, cosine LR, a wall-clock budget so a run
  always ends on schedule; weapons v2 is fine-tuned from the v1 weights on the merged set.
  Progress streams to `storage/training.json` (System screen).
* Verifier: `scripts/verify/build_crops.py` + `train_verifier.py` — DINOv2 features of every YOLO proposal (crop with 35 % context +
  whole frame), positives from annotations (jittered like detector noise), negatives from the detector's false alarms on train frames.
  Thresholds are the lowest verifier probability whose frame-level false-alarm rate on *validation* video frames is <= 0.1 %, never below
  0.6. The deployed verifier was trained before fire/smoke was removed; the scripts now build weapons-only data but retraining was not
  re-run after the removal.
* Violence: frozen DINOv2 features (16 frames/clip, flipped + cropped training views) -> 2-layer temporal transformer
  (`train_head.py`); VideoMAE-K400 clip features -> MLP (`train_videomae_head.py`); logistic stack + threshold on validation
  clips (`ensemble_eval.py`). Training each head takes about a minute once features are cached.

## Evaluation protocol

1. **Component benchmarks** (`benchmark_detector.py`, `train_verifier.py`, `ensemble_eval.py`): mAP / precision / recall at the
   deployed thresholds, per source, previous weights on the same images, latency and VRAM.
2. **Still-image stack** (`scripts/eval/image_eval.py`): held-out annotated weapon images + blind video frames through the whole
   deployed stack, detector-only vs full stack, including violence on stills.
3. **Blind video** (`scripts/eval/blind_cache.py` + `blind_score.py`): DCSASS clips replayed exactly like an upload (JPEG
   frames at the configured fps, per-clip stream), scored with the *production* `decide()` code and the API's k-of-n rule.
   Ground truth is by category (see the scorer's docstring). Weapon recall is not scored because a Shooting/Robbery clip may
   not show the weapon.
4. **Fresh sample.** Earlier blind samples guided design decisions (cleaning negatives, the threshold floor, the ensemble). After
   freezing every configuration the final numbers come from a new sample that excludes every clip inspected before. `TestVideos/*`
   are SCVD clips that were in the training/validation manifest: they are demo clips, not blind data.

## How detections become incidents

`/predict` returns detections whose class maps to a category in `config/class_map.yaml`. Still images raise an incident on the
first verified detection. For video and live sources a category must persist in 3 of the last 4 sampled frames (uploads, 5 fps)
or 2 of 4 (live); a single frame bypasses this only when the *raw detector score* is >= 0.85 and the verifier approved (verifier
and violence probabilities saturate near 1.0, so they cannot be used for the bypass). The violence stack uses the scene head alone
until a stream has buffered 8 frames. Humans make the final call: incidents are `NEEDS_REVIEW` until an operator confirms or
dismisses them. An optional AI second opinion (open-weights VLM) can double-check the evidence and flags disagreement without
ever deciding.

## Assistant latency choices

* NDJSON streaming; static system prompt placed first (a prefix Ollama can reuse); the local model is loaded at
  API start (`keep_alive` 30 min); Gemma 4 "thinking" is switched off (it made the first visible token wait on hidden reasoning).
* Groq's on-demand tier allows ~7 000 input tokens/min, so Groq gets one annotated keyframe per question and a text-only retry on HTTP 429.
* Local model: Gemma 4 E2B — the only Gemma 4 size that fits next to the detectors on a 6 GB card. The stock `gemma4:e2b` build
  ships its multi-token-prediction drafter (speculative decoding). Measured with a different incident id in every request (so nothing is
  served from the KV prefix cache), see benchmarks.md section 4: with every layer on the GPU the drafter raises decode speed from ~81 to
  ~130-140 tokens/s; on the CPU from ~25 to ~33-47 tokens/s (run-to-run spread; with only 12 layers offloaded the gain was inconsistent, so
  no claim is made there). The bigger lever was GPU offload: first token arrives in ~0.1 s (text) / ~0.46 s (with an evidence frame) versus
  ~1.6 s / ~10-11 s on the CPU, so `OLLAMA_NUM_GPU` defaults to 99; the detectors plus the assistant peaked at 4.8 GB of the 6 GB card in the
  ecosystem check. The first local answer right after a restart can still take ~14 s while the model finishes loading (observed once).
* Ollama reloads the model whenever `num_ctx` or `num_gpu` differ between requests; warm-up, chat, AI review and the rules reasoner therefore
  share one setting (`ollama_runtime()` in `services/api/app/chat.py`, `llm:` in `config/rules.yaml`). Before this, a different `num_ctx` per call
  made the first local answer take 10-16 s.
* The YOLO26s weapon detector takes ~11 ms per frame on the RTX 4050 (`weapons.json`); the verifier and motion head add DINOv2/VideoMAE
  forward passes on top. An image upload returns end to end in tens of milliseconds once the service is warm (benchmarks.md section 5), and sampling is
  2-5 fps, so detection is not the bottleneck; ONNX/TensorRT was not pursued.

## Known limits

* CCTV gun recall is modest (46.3 % of annotated frames with the detector alone, 55.6 % with the verifier, on only 54 frames) and the verifier may have learned
  camera-specific cues; objects it has never seen as negatives (it still confuses archery sights with guns at times) need more mining.
* Violence recall on subtle assaults/abuse in DCSASS is moderate (stack recall 46 % at its threshold on blind clips; 61.8 % of Fighting/Assault/Abuse
  clips alert under the production persistence rule) and still-image violence recall is low (the single-frame threshold is 0.999).
* Blind *weapon* recall is not scored: a DCSASS Shooting/Robbery clip may not show the weapon. Weapon numbers on video are false-alarm rates only.
* Everything outside guns, knives and physical fights, including fire and smoke, is listed as unsupported in `config/models.yaml`.
* Crime-type labels (the 12 DCSASS categories except Arson): a classifier on the same frozen DINOv2 + VideoMAE features was trained with parent-grouped splits and scored once on blind parents.
  No type met the pre-registered bar (Abuse has good precision but is flagged on as many quiet sub-clips of the same videos as on crime sub-clips; Stealing, the closest, has only 8 blind videos),
  so the head is evaluation-only and nothing is surfaced.
  Method, per-type numbers, error analysis and the DCSASS / VideoMAE licence caveat are in [crime-type.md](crime-type.md).
