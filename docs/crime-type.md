# Crime-type classifier (DCSASS categories)

**Outcome: trained, scored honestly on blind videos, and *not* surfaced.** No crime type met the pre-registered reliability bar, so `supported` in
`storage/models/crime_type.json` is empty and `config/models.yaml` lists the crime types as unsupported. The model is evaluation-only: nothing in the
runtime loads it. The closest candidate is **Stealing** (precision 0.75 but 8 blind videos make its interval too wide); **Abuse** looks good on precision and
fails the test that matters (it recognises the *setting*, not the act); **Explosion** works but is a fire/flash recogniser and overlaps the removed fire/smoke scope.

Numbers come from `scripts/crime/*` and are stored in `storage/benchmarks/crime_type*.json` (git-ignored like every other benchmark file; rerun the scripts below to regenerate).

## What was asked and what was built

The request was to train a model for the crime types in the DCSASS Kaggle dataset (`mateohervas/dcsass-dataset`). DCSASS is already on disk
(`storage/datasets/raw/kaggle/dcsass`, 16 593 sub-clips of 1–4 s at 30 fps and 320x240 cut from 13 UCF-Crime anomaly categories), so nothing was downloaded
and no Kaggle credentials were used.

* **Classes**: 12 crime types — Abuse, Arrest, Assault, Burglary, Explosion, Fighting, RoadAccidents, Robbery, Shooting, Shoplifting, Stealing, Vandalism — plus `none`.
* **Arson is not a class.** It is mostly visible fire, and fire/smoke detection was removed on purpose (blind low-resolution CCTV recall was unusable). Arson is
  never trained on; blind Arson clips are only scored to show where they land. It is listed as unsupported in `config/models.yaml`.
* **There is no "Normal" folder in this copy of DCSASS.** The only normal footage is label-0 sub-clips of anomaly videos, and those are coarse (a "normal" sub-clip
  of a Shooting/Abuse/Arrest video often shows people, the lead-up, or the event itself; a visual audit of random label-0 clips of violent categories agreed).
  `none` is therefore built from label-0 sub-clips of the *calm* categories (RoadAccidents, Shoplifting, Stealing, Vandalism, Burglary) plus ordinary footage from
  the violence collection (SCVD normal, RLVS non-violence, RWF-2000 non-fight, hockey non-fight). Label-0 clips of the other categories are never training data.
* **Model**: frozen DINOv2-base frame features (16 frames, mean and std over time) + frozen VideoMAE-K400 clip feature -> 512-unit MLP head
  (`services/inference/crime_head.py`, 4 240 -> 512 -> 13). Same encoders and 16-frame sampling as the violence stack, so features can be shared at runtime.
  Selected by out-of-fold macro-F1 among 3 full-feature configs (linear, MLP-256, MLP-512); Ablations: DINOv2-only reached OOF macro-F1 0.291, VideoMAE-only 0.331 (nearly as good as the full 0.335), so most of the signal is motion/scene from VideoMAE.
* Training data: 10 816 dev clips from 1 031 groups (parents, or blocks for the ordinary-footage sources). Training one configuration takes under a minute on the RTX 4050.

## Protocol (what keeps the numbers honest)

* **Split by source video, never by clip.** Sub-clips of one parent video are near-identical scenes. DCSASS keeps the existing parent split (sha1 of the parent name,
  30 % *blind*, the same blind parents every other SafeSpace model is scored on; no model was trained, mined or calibrated on them). Model selection, the temperature and the
  per-type thresholds use 5-fold cross-validation *grouped by parent* over the dev parents only (`build_manifest.py`, `train_crime.py`). Those dev numbers guided choices and are not a result.
* **Blind parents were scored once** (`score_blind.py`) against a bar written down before any blind clip was scored (below). Reporting-only additions (same-video flag rates,
  one-vs-rest AUC) were added to the script after the first run; the model, thresholds and bar were not touched.
* **Intervals are parent-cluster bootstrap**, not clip-level Wilson intervals: resampling clips would treat 30 sub-clips of one video as 30 independent observations.
  Counts of clips *and* parent videos are shown everywhere.
* **Camera leakage between parents is possible** (UCF-Crime contains several videos from the same camera). The script also splits the blind parents by how similar their scenes are to
  the nearest dev parent (DINOv2 mean-embedding cosine, median 0.69). A dHash near-duplicate check was tried first and discarded: on 8x8 grayscale thumbnails dark scenes collide at distance 0.
* **Same-video diagnostic**: AUC of a type's probability on label-1 vs label-0 sub-clips of the *same* videos. If the model only recognised the scene (shop, road, nursery), it could not
  separate the crime from the quiet part of the same video.
* **Ground-truth rules for precision/recall** (fixed in advance): the types' label-1 clips and the `none` sources are scored; none-source clips, other types **and Arson clips** count as wrong when flagged as a type;
  label-0 clips of violent categories (1 448 blind clips) are excluded because their ground truth is ambiguous, and reported separately.

### Pre-registered bar for surfacing a type as an advisory label

A type is surfaced only if **all** hold on blind parents (constants at the top of `score_blind.py`):

1. at least 5 blind parent videos contain the type (an interval on 2–4 videos cannot certify anything);
2. open-set precision ≥ 0.70 with the parent-bootstrap 95 % lower bound ≥ 0.50;
3. recall of label-1 clips ≥ 0.30 and at least half of the type's blind parents have a correctly flagged clip;
4. same-video AUC ≥ 0.70;
5. ≤ 2 % of ordinary-footage windows flag the type.

Explosion, even if it passed, would not be surfaced automatically: it overlaps the removed fire/smoke scope, so that call is the user's.
Thresholds are per type: the lowest threshold whose dev out-of-fold precision is ≥ 0.70 with ≥ 10 correct clips from ≥ 3 parents and recall ≥ 0.05; otherwise the type has no operating point and never fires.

## Results (blind parents, scored once)

5 181 blind clips from 321 parent videos/blocks. Types with a threshold on dev: Abuse 0.21, Arrest 0.25, Explosion 0.20, Stealing 0.57. **Eight types have no operating point**
(on dev they never reach 0.70 precision with support), so they never fire and their open-set recall is 0 by construction.

| Type | Blind videos | Label-1 clips | Flagged | Precision (95 % CI) | Recall (95 % CI) | Videos hit | Flagged on label-1 vs label-0 of same videos | Same-video AUC (95 % CI) | Bar |
|---|---|---|---|---|---|---|---|---|---|
| Abuse | 13 | 237 | 126 | 0.87 (0.60–0.98) | 0.46 (0.16–0.81) | 7/13 | 46 % vs **51 %** | **0.44** (0.29–0.64) | fails #4 |
| Arrest | 4 | 60 | 29 | 0.14 (0.00–0.46) | 0.07 (0.00–0.21) | 1/4 | 7 % vs 0 % | 0.75 (0.48–0.96) | fails #1–3 |
| Assault | 7 | 80 | 0 | – | 0.00 | 0/7 | – | 0.57 (0.39–0.74) | no operating point |
| Burglary | 12 | 264 | 0 | – | 0.00 | 0/12 | – | 0.76 (0.58–0.90) | no operating point |
| Explosion | 4 | 32 | 37 | 0.57 (0.00–0.97) | 0.66 (0.00–1.00) | 3/4 | 66 % vs 9 % | 0.84 (0.50–1.00) | fails #1, #2 |
| Fighting | 2 | 52 | 0 | – | 0.00 | 0/2 | – | 0.91 (0.85–1.00) | no operating point, 2 videos |
| RoadAccidents | 18 | 88 | 0 | – | 0.00 | 0/18 | – | 0.58 (0.44–0.75) | no operating point |
| Robbery | 39 | 676 | 0 | – | 0.00 | 0/39 | – | 0.66 (0.55–0.75) | no operating point |
| Shooting | 8 | 71 | 0 | – | 0.00 | 0/8 | – | 0.72 (0.51–0.82) | no operating point |
| Shoplifting | 7 | 33 | 0 | – | 0.00 | 0/7 | – | 0.70 (0.47–0.78) | no operating point |
| Stealing | 8 | 125 | 57 | 0.75 (0.24–0.95) | 0.34 (0.04–0.73) | 4/8 | 34 % vs 6 % | 0.76 (0.57–0.90) | fails #2 (lower bound 0.24) |
| Vandalism | 12 | 141 | 0 | – | 0.00 | 0/12 | – | 0.78 (0.62–0.89) | no operating point |

**Surfaceable now: none.**

*Closed set* (given a label-1 clip of one of the 12 types, thresholds ignored): top-1 **0.56** (always guessing the biggest class, Robbery, gives 0.36; chance 0.08), macro top-1 **0.42**, top-3 0.78;
majority vote per video is right for 0.51 of 134 videos. Per class top-1: Stealing 0.89, RoadAccidents 0.81, Robbery 0.75, Explosion 0.66, Burglary 0.58, Abuse 0.50, Shoplifting 0.39, Vandalism 0.30, Arrest 0.10,
Assault 0.05, Shooting 0.01, Fighting 0.00. The big-class numbers mostly reflect scene recognition (see the same-video column); the violent categories are barely recognised at all.

### What the errors looked like

(Frames rendered with `scripts/crime/inspect_errors.py`; I looked at them, not only at the counts.)

* **Abuse is the scene, not the act.** Flagged label-0 clips of Abuse videos are the same nurseries, cots and care-home rooms as the label-1 clips; the flag rate is the same on both (46 % vs 51 %), and
  105 label-0 clips of violent categories are flagged Abuse. Counting those as false alarms would take precision from 0.87 to about 0.48. Some of those label-0 clips may genuinely show abuse (label noise),
  so the dataset cannot tell "setting recognised" from "mislabelled"; either way the label cannot be certified as detecting the act.
* **Stealing**: the highest-confidence "wrong" flags are label-0 clips of two night-time videos (people next to parked cars) and a Robbery video of a street scene — plausibly the same event or label noise rather than a clear model failure.
  Its same-video separation is real (34 % vs 6 %) and it holds on the half of blind parents least similar to dev parents (precision 0.83, recall 0.45), but eight videos cannot support the lower bound.
* **Explosion is a fire/flash recogniser.** 8 % of the 224 Arson clips (21 % of the Arson label-1 ones) get a crime label, 16 clips as Explosion, and the frames are visible flames and smoke. That is the removed fire/smoke scope again, so it is held for the user.
* **Confusions inside families**: Shooting -> Robbery (49 of 71 clips), Fighting -> Assault/Abuse/Arrest, Assault -> Burglary/Stealing/RoadAccidents, Burglary -> Robbery (92 of 264), Vandalism -> Burglary/Stealing. In several confusions
  (a man lying on the pavement flagged Arrest for an Assault clip; a pub brawl flagged Arrest; policemen detaining a person in a shop flagged Arrest on an RWF-2000 "non-fight" clip) the model's answer is
  arguable and the label is the weaker party — which is exactly why coarse DCSASS labels cap the score.
* **Merged groups** do not rescue it: violence (Abuse/Assault/Fighting) recall 0.31 at precision 0.90 (dominated by Abuse), property crime (Burglary/Stealing/Shoplifting/Vandalism) recall 0.08. The existing violence stack already covers the former.

### False alarms on ordinary footage

* Blind `none` clips flagged as a crime type: DCSASS calm label-0 1.1 % of 1 169 (Arrest 5, Stealing 8); RWF non-fight 2.0 % of 200; RLVS non-violence 1.9 % of 160; hockey 0 of 75; SCVD normal 0 of 46.
* `storage/recordings` (the user's own phone/CCTV segments, 3.2 s windows at 5 fps): **0 of 535 windows flagged** (101 videos, ~0.24 h of footage, snapshot at run time — the folder keeps growing).
  This is weaker evidence than it looks: 63 % of windows are reasonably lit but one camera (58 of 101 videos) is dim (median luminance 29/255) and only ~0.24 h exists; 3 events in 535 windows is the rule-of-three
  upper bound ≈ 0.6 % per window, and ≈ 3 % per video because windows of one video are correlated. The top-scoring windows (probability ≤ 0.19, far below every threshold) are near-black frames and a knee close-up.
* `TestVideos` (SCVD clips of real violence/weapons, not counted as false alarms): 2 of 5 are flagged Abuse (a violence clip and a weapon clip), 3 flag nothing.

## Decisions to make / what stays unsupported

* **Surface nothing now.** `config/models.yaml` keeps all 12 types (and Arson) under `unsupported`; the sidecar's `supported` list is empty; `crime_head.surfaced_type()` therefore never returns a label.
* **Explosion needs the user's call** (visually it is fire/smoke/flash; it would partly re-add the removed scope).
* **Stealing** is the one to revisit: it needs more independent videos (8 blind / 52 dev) to certify; Fighting has only 8 videos in all of DCSASS and Explosion 23, so they cannot be certified from this dataset at any threshold.
* Runtime wiring was deliberately not done: with no type passing, adding a new head to the live service would only add latency and a place for false alarms.
  If a type is ever certified, `crime_head.surfaced_type(prob, sidecar)` is the gate to call; it also needs the DINOv2 window feature and the VideoMAE feature that the violence path already computes, 16 frames per window (the live buffer is 8 for DINOv2), which is a deviation to re-evaluate first.

## Limits

* 12 types from 134 blind parent videos with a crime label; per-type interval widths are large and the table says so. DCSASS labels are coarse and many label-1 clips show no obvious crime at 320x240.
* Same-camera videos can sit on both sides of the split; the similarity split is a diagnostic, not a guarantee.
* Training clips are 1–4 s at 30 fps; runtime windows are 16 frames at 5 fps (3.2 s). Not evaluated as a runtime path.
* Frozen encoders only; fine-tuning VideoMAE on this data was out of scope for the 6 GB card shared with Ollama and the detector.
* One training seed; the dev cross-validation gives the spread between configs (macro-F1 0.32–0.34), not between seeds.

## Licensing (read before any commercial use)

* **DCSASS** is derived from **UCF-Crime**. The Kaggle page does not state terms in a form this project could retrieve; **treat DCSASS as research / non-commercial until the licence is confirmed with the dataset author and UCF**.
  UCF's own dataset page says its datasets are intended for research purposes unless stated otherwise and asks users to credit the authors.
* **VideoMAE-K400 weights** (`MCG-NJU/videomae-base-finetuned-kinetics`) appear to be CC-BY-NC (non-commercial); verify on the model card. The existing violence stack already depends on them.
* The trained head inherits both constraints. Shipping this model in a commercial product needs a licence check (or retraining on data and encoders with commercial terms).

## Reproduce

```
python scripts/crime/build_manifest.py                      # storage/datasets/crime/manifest.json (dev folds / blind parents)
python scripts/violence/extract_features.py --manifest storage/datasets/crime/manifest.json --out storage/datasets/crime/dino --no-aug
python scripts/violence/extract_videomae.py --manifest storage/datasets/crime/manifest.json --out storage/datasets/crime/videomae --no-aug
python scripts/crime/train_crime.py --final                       # CV selection + temperature + thresholds -> storage/models/crime_type.pt/.json
python scripts/crime/eval_recordings.py                     # false alarms on storage/recordings, TestVideos listed apart
python scripts/crime/score_blind.py [--write]               # blind parents, scored once; --write stores `supported` in the sidecar
python scripts/crime/inspect_errors.py blind-confusions --out storage/eval/crime/blind_errors.png
python -m pytest tests/test_crime_type.py
```

Extraction of the ~16 000 clips took about 35 minutes on the shared RTX 4050 (both encoders in parallel, 3 workers each). With the inference service resident the card still had ~3.4 GB free; DINOv2 at batch 64 peaked at ~0.5 GB allocated (measured), VideoMAE's peak was not measured.
