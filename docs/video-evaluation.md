> **Superseded.** This is an early diagnostic of the first model (YOLO-only fire/smoke and a DINOv2 violence head, before the verifier cascade, the motion head and the DCSASS blind evaluation). Its numbers describe weights that are no longer deployed. Current results: [benchmarks.md](benchmarks.md); method and limits: [ml-pipeline.md](ml-pipeline.md). Kept for history.

# Video detection evaluation — 16 October 2026

## Scope and method

The upload path was replayed on all five files in `TestVideos` and on the 82-clip SCVD CCTV test split
(36 labelled violence/weaponized, 46 labelled normal). The replay uses the deployed YOLO and DINOv2
weights, JPEG frame encoding, the same sampling stride as uploaded video, and the same temporal hit rule.
Three representative clips were also sent through the authenticated upload API with real inference and
isolated storage, including AVI-to-MP4 transcoding. The final frame-by-frame reports are in local
`runs/scvd-test-final.json` and `runs/testvideos-final.json`.

These numbers are diagnostic, not an independent estimate of performance on all cameras. The SCVD test
set was consulted during this work, some normal clips are consecutive views of one scene, and the SCVD
train/test organization is not guaranteed to separate cameras. All five `TestVideos` files are exact
SHA-256 matches to clips already in the violence manifest: `v001`, `v006`, and `w001` are validation;
`v011` and `v026` are training. None were used as new fine-tuning examples.

## Upload pipeline results

| Configuration | Positive SCVD clips alerted | Normal SCVD clips alerted | `TestVideos` clips alerted |
|---|---:|---:|---:|
| Original: fire/smoke + violence, 2 fps, 2 of 4 | 28/36 | 10/46 | 3/5 |
| Existing weapons checkpoint enabled, 2 fps, 2 of 4 | 31/36 | 11/46 | 3/5 |
| Final: weapons enabled, CCTV-tuned fire/smoke, 5 fps, 3 of 4 | **33/36** | **5/46** | **4/5** |

The final held-out misses were `t_w001`, `t_w002`, and `t_w024` (weaponized clips). The five normal
false alerts were one SMOKE, two WEAPON_DETECTED, and two FIGHT. Higher video-only weapon confidence
thresholds were rejected on the validation clips because they removed most weaponized detections.
On the separate SCVD validation clips, the final 5 fps / 3-of-4 rule alerted on 27/30 positives and
9/40 normals; this higher false-alert count is a reminder that the test split is small and scene-dependent.

| `TestVideos` clip | Original | Final | Note |
|---|---|---|---|
| `v001` | FIGHT | FIGHT | Existing validation clip. |
| `v006` | none | none | Violence score stays near zero; a sampled frame shows a person crossing an airport-security barrier, with no clear fight visible. |
| `v011` | none | FIGHT | Recovered by 5 fps sampling; verified through the upload API. |
| `v026` | FIGHT | FIGHT, WEAPON_DETECTED | Existing training clip. |
| `w001` | FIGHT, SMOKE | FIGHT, WEAPON_DETECTED, SMOKE | Weapon detection recovered; SMOKE appears false on an inspected frame. |

The final upload API check processed 44 frames of `v011`, 30 of `v006`, and 26 of `w001`; all three
uploads reached DONE. This verifies the dashboard's backend route as well as direct model inference.

## Fire/smoke fine-tuning gate

Two candidates were trained from the deployed fire/smoke checkpoint using only SCVD **training** normal
clips as hard negatives; validation normal clips were reserved for model selection and no SCVD test or
`TestVideos` clip entered training. The first limited-data candidate lost too much fire/smoke performance.
The promoted candidate used all 7,238 original fire/smoke training images plus 480 CCTV negative frames.

| Original held-out fire/smoke image test | Previous | Promoted |
|---|---:|---:|
| Fire recall (2,763 boxes) | 1,132 / 2,763 | 1,130 / 2,763 |
| Smoke recall (1,823 boxes) | 1,253 / 1,823 | 1,252 / 1,823 |
| mAP50 | 0.699 | 0.695 |
| Image alert recall (1,874 positive images) | 1,585 / 1,874 | 1,592 / 1,874 |
| False alerts on 954 clean images | 36 / 954 | 42 / 954 |

This is a real tradeoff: CCTV smoke false alerts improved substantially, while the original image test
shows a small precision and mAP cost. The previous weights and sidecar remain in
`storage/models/fire_smoke_previous.pt` and `storage/models/fire_smoke_previous.json`; the previous
benchmark is in `storage/benchmarks/fire_smoke_previous.json`. Those runtime artifacts are local and
ignored by Git.

## Coverage and next data requirement

An additional violence-head candidate repeated CCTV training views four times. It recognized `v006`,
but was rejected: its broad held-out single-frame recall fell from 78.7% to 67.0%, broad clip false
alarms rose from 1.8% to 5.7%, and it raised FIGHT on 27/40 normal CCTV validation clips. The original
`storage/models/violence_head.pt` remains deployed. The candidate is retained locally as
`storage/models/violence_head_cctv.pt` for analysis only.

The deployed models cover visible fire, smoke, guns, knives, and physical violence. They do not infer
robbery, theft, intrusion intent, accidents, or all crime categories. `v006` illustrates that a clip
labelled as violence may depict an action outside the present FIGHT category. A broader classifier needs
camera-disjoint, category-specific positive and normal examples with event timestamps, plus an untouched
test set. [DCSASS](https://www.kaggle.com/datasets/mateohervas/dcsass-dataset) is one possible source
for additional activity classes; it was not downloaded or trained into this release.

Reproduce the local checks with `scripts/evaluate_video_pipeline.py`,
`scripts/compare_video_policies.py`, and `scripts/verify_real_video_upload.py`.
