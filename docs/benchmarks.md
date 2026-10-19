# Benchmarks

_Generated 2026-10-16 23:24 from `storage/benchmarks/`. Method, data and caveats: [ml-pipeline.md](ml-pipeline.md). Thresholds are chosen on validation data only. Earlier blind samples shaped design decisions; section 2 uses a fresh sample taken after the configuration was frozen._

## 1. Still images through the whole deployed stack

Held-out annotated images (never trained on, near-duplicates of training images removed) and **blind video frames** the system never saw. "Detector only" = raw YOLO thresholds; "full stack" = YOLO proposals re-scored by the DINOv2 verifier. Recall is per positive image (any alert of the right family); false alarm = share of threat-free images with an alert of that family.

| Source | Images | Mode | Weapon recall | Weapon false alarm | Fight recall | Fight false alarm |
|---|---|---|---|---|---|---|
| video-frames:dcsass | 1500 | detector only | — | 0.1% | — | 2.3% |
| video-frames:dcsass | 1500 | full stack | — | 0.1% | — | 2.3% |
| video-frames:hockey | 225 | detector only | — | 0.4% | — | 0.0% |
| video-frames:hockey | 225 | full stack | — | 0.0% | — | 0.0% |
| video-frames:rlvs | 480 | detector only | — | 2.9% | — | 1.0% |
| video-frames:rlvs | 480 | full stack | — | 0.6% | — | 1.0% |
| video-frames:scvd | 138 | detector only | — | 0.0% | — | 0.0% |
| video-frames:scvd | 138 | full stack | — | 0.0% | — | 0.0% |
| violent-frames:DCSASS blind Fighting | 156 | detector only | — | — | 73.1% | — |
| violent-frames:DCSASS blind Fighting | 156 | full stack | — | — | 73.1% | — |
| violent-frames:Hockey fights | 375 | detector only | — | — | 85.1% | — |
| violent-frames:Hockey fights | 375 | full stack | — | — | 85.1% | — |
| violent-frames:RWF-2000 | 600 | detector only | — | — | 40.8% | — |
| violent-frames:RWF-2000 | 600 | full stack | — | — | 40.8% | — |
| violent-frames:Real Life Violence Situations | 360 | detector only | — | — | 74.2% | — |
| violent-frames:Real Life Violence Situations | 360 | full stack | — | — | 74.2% | — |
| violent-frames:SCVD | 108 | detector only | — | — | 20.4% | — |
| violent-frames:SCVD | 108 | full stack | — | — | 20.4% | — |
| weapons:cctv | 54 | detector only | 46.3% | — | — | — |
| weapons:cctv | 54 | full stack | 55.6% | — | — | — |
| weapons:haris | 2072 | detector only | 86.5% | 15.2% | — | 0.0% |
| weapons:haris | 2072 | full stack | 92.7% | 2.7% | — | 0.0% |
| weapons:knife | 10 | detector only | 80.0% | — | — | — |
| weapons:knife | 10 | full stack | 100.0% | — | — | — |
| weapons:pistol | 13 | detector only | 100.0% | — | — | — |
| weapons:pistol | 13 | full stack | 100.0% | — | — | — |

## 2. Blind video: DCSASS (UCF-Crime CCTV, 320x240) fresh sample

Clips from *parent videos never used in training, mining or calibration*, replayed like an upload with the production decision code (verifier on, 3-of-4 persistence). Ground truth is by DCSASS category because sub-clip labels are coarse.

| Threat | Positive clips detected | Clean clips with a false alarm |
|---|---|---|
| FIGHT | 61.8% (63/102) | 1.7% (10/589) |
| WEAPON | not scored (a Shooting/Robbery clip may not show the weapon) | 0.0% (0/741) |

| Category / label | Clips | Weapon alerts | Fight alerts |
|---|---|---|---|
| Abuse/0 | 99 | 1 | 42 |
| Abuse/1 | 50 | 0 | 26 |
| Arrest/1 | 20 | 0 | 5 |
| Arson/0 | 57 | 0 | 5 |
| Arson/1 | 47 | 0 | 2 |
| Assault/0 | 64 | 0 | 30 |
| Assault/1 | 40 | 0 | 26 |
| Burglary/0 | 40 | 0 | 3 |
| Burglary/1 | 50 | 0 | 5 |
| Explosion/0 | 48 | 0 | 0 |
| Fighting/1 | 12 | 0 | 11 |
| RoadAccidents/0 | 100 | 0 | 0 |
| RoadAccidents/1 | 48 | 0 | 0 |
| Robbery/0 | 100 | 2 | 12 |
| Robbery/1 | 50 | 0 | 14 |
| Shooting/0 | 100 | 0 | 6 |
| Shooting/1 | 31 | 0 | 11 |
| Shoplifting/0 | 100 | 0 | 2 |
| Stealing/0 | 51 | 0 | 0 |
| Stealing/1 | 50 | 0 | 0 |
| Vandalism/0 | 100 | 0 | 0 |
| Vandalism/1 | 50 | 0 | 0 |

Label 1 = anomalous sub-clip, 0 = "normal" sub-clip of an anomaly video (these can still show the event). The weapon false-alarm count uses the calm categories plus Arson and Explosion; the fight count uses only the calm categories (RoadAccidents, Shoplifting, Stealing, Vandalism, Burglary).

## 3. Components

Component benchmarks use each detector's benchmark resolution. In production the gun/knife detector runs at 640 px (the verifier was trained on proposals made at that size); the stack numbers in sections 1 and 2 use the deployed configuration.

### Gun / knife detector (stage 1)

Test images: 3648 (2057 threat-free). mAP50 **84.5%**, mAP50-95 54.6%. Latency 10.88 ms/frame (p95 13.37 ms) at 704 px.

| Class | AP50 | Precision | Recall | F1 | Raw-detector alert threshold | Test instances |
|---|---|---|---|---|---|---|
| gun | 81.2% | 85.2% | 71.6% | 77.8% | 0.400 | 1269 |
| knife | 87.7% | 83.3% | 81.4% | 82.4% | 0.350 | 522 |

| Source | Images | Clean | New weights recall | New false alarm | Previous recall | Previous false alarm |
|---|---|---|---|---|---|---|
| cctv | 54 | 0 | 38.9% | — | 42.6% | — |
| haris | 2072 | 558 | 85.7% | 15.8% | 84.9% | 16.1% |
| knife | 10 | 0 | 90.0% | — | 90.0% | — |
| pistol | 13 | 0 | 100.0% | — | 100.0% | — |
| videodcsass | 1154 | 1154 | — | 0.9% | — | 2.6% |
| videohockey | 98 | 98 | — | 0.0% | — | 5.1% |
| videorlvs | 194 | 194 | — | 2.6% | — | 8.2% |
| videoscvd | 53 | 53 | — | 0.0% | — | 0.0% |

### Verifier (stage 2)

ROC AUC on held-out *actual detector proposals*: gun 99.6%, knife 99.6%. The weights were trained jointly on four classes; two slots are unused and never scored. Frame-level false-alarm rate on blind video frames at the validation-chosen thresholds:

| Class | Threshold | Recall of correct detections | dcsass | hockey | rlvs | scvd |
|---|---|---|---|---|---|---|
| gun | 0.995 | 95.9% | 0.04% | 0.00% | 0.00% | 0.00% |
| knife | 0.600 | 98.9% | 0.00% | 0.00% | 0.21% | 0.00% |

### Violence (scene head + motion head, logistic stack)

Threshold 0.813 (validation false-alarm target 3%). Held-out clips per dataset (the in-domain test splits; RWF-2000 `val` is the official test set):

| Dataset | AUC | Recall | False alarm |
|---|---|---|---|
| Hockey fights | 98.9% | 92.0% | 2.7% |
| RWF-2000 (surveillance) | 95.3% | 79.0% | 9.0% |
| Real Life Violence Situations | 99.3% | 93.3% | 1.2% |
| SCVD (CCTV) | 96.1% | 50.0% | 0.0% |
| DCSASS blind (Fighting/Assault/Abuse vs calm categories) | 89.1% | 46.0% | 1.3% |

How the stack compares with its parts on the **blind DCSASS clips** (each at its own validation-chosen threshold, and at a common 5 % calm-clip false-alarm budget). The stack has the best AUC and a low false-alarm rate; at a fixed false-alarm budget it is not better than the best single head, so it was chosen for its false-alarm behaviour, not for recall.

| Method | Blind AUC | Recall at its threshold | Calm-clip false alarm | Recall at 5 % calm false alarm |
|---|---|---|---|---|
| DINOv2 scene head | 86.6% | 58.3% | 3.1% | 65.1% |
| VideoMAE motion head | 83.9% | 38.5% | 3.8% | 41.3% |
| Mean of both | 88.0% | 40.9% | 1.2% | 63.5% |
| Max of both | 88.1% | 59.5% | 2.9% | 68.7% |
| Logistic stack (deployed) | 89.1% | 46.0% | 1.3% | 62.7% |

## 4. Assistant latency (local Gemma 4 E2B vs Groq)

Streaming requests with a realistic incident dossier. **Every timed request carries a different incident id and question**, so first-token times are not served from the KV prefix cache. "GPU layers" is Ollama's `num_gpu` (0 = CPU only, 99 = everything on the RTX 4050). Decode speed is the model's own `eval_count / eval_duration`. The "without the MTP drafter" rows use the same weights with the multi-token-prediction drafter removed, which isolates what speculative decoding contributes.

| Configuration | First token | Decode tokens/s |
|---|---|---|
| gemma4:e2b (stock build, MTP drafter) · 0 GPU layers | 1.601 s | 47.39 |
| gemma4:e2b (stock build, MTP drafter) · 0 GPU layers + 1 evidence frame | 10.833 s | 32.735 |
| gemma4:e2b (stock build, MTP drafter) · 12 GPU layers | 0.266 s | 37.79 |
| gemma4:e2b (stock build, MTP drafter) · 12 GPU layers + 1 evidence frame | 6.456 s | 44.76 |
| gemma4:e2b (stock build, MTP drafter) · 99 GPU layers | 0.108 s | 141.23 |
| gemma4:e2b (stock build, MTP drafter) · 99 GPU layers + 1 evidence frame | 0.455 s | 129.685 |
| gemma4:e2b without the MTP drafter · 0 GPU layers | 1.538 s | 24.75 |
| gemma4:e2b without the MTP drafter · 0 GPU layers + 1 evidence frame | 9.653 s | 23.685 |
| gemma4:e2b without the MTP drafter · 12 GPU layers | 0.212 s | 39.14 |
| gemma4:e2b without the MTP drafter · 12 GPU layers + 1 evidence frame | 5.88 s | 37.255 |
| gemma4:e2b without the MTP drafter · 99 GPU layers | 0.108 s | 80.93 |
| gemma4:e2b without the MTP drafter · 99 GPU layers + 1 evidence frame | 0.452 s | 81.93 |
| Groq · qwen/qwen3.8-27b | 0.238 s | 522.02 |

## 5. End-to-end verification (13/13 checks passed)

| Check | Result |
|---|---|
| Login with the configured administrator account | pass — HTTP 200 |
| Detector service reports ready with trained weights | pass — weapons, verifier, violence |
| weapons_v2: held-out gun images raise an incident | pass — 11/12 detected |
| weapons_v2: held-out knife images raise an incident | pass — 12/12 detected |
| weapons_v2: clean held-out images stay quiet | pass — 1/24 false alarms |
| violence: held-out fight clips classified correctly | pass — 4/6 correct |
| violence: held-out normal clips classified correctly | pass — 5/6 correct |
| Incident keyframe is served with authentication | pass — /api/v1/events/evt_a2f4ab2e62ab4a38b10e67aaa1d9dc4c/media/frame.jpg |
| Incident clip supports HTTP Range playback | pass — HTTP 206 |
| Evidence is not served without a session | pass — HTTP 401 |
| Live WebSocket delivers incident events | pass — event.created after 96 ms (includes upload + inference) |
| Chat (groq) is grounded, cites the incident and returns footage | pass — first token 0.49 s, cited=1 |
| Chat (ollama) is grounded, cites the incident and returns footage | pass — first token 0.39 s, cited=1 |

Latency (ms): image_upload_to_result_median_ms=79.0, image_upload_to_result_p95_ms=88.4, video_clip_total_s=2.6, chat_groq_first_token_s=0.49, chat_ollama_first_token_s=0.39
