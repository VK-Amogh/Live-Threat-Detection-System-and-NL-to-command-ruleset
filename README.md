# SafeSpace — local CCTV threat detection

Your PC is the server. A web dashboard and an Android app connect to it over the local network; every
detection comes from models that ran on your own GPU. No cloud is needed for detection, storage, or
the incident assistant (Groq is an optional, explicitly selected alternative for the assistant).

```
 Upload image/video ─┐                  ┌─ 1. YOLO26s proposals: fire/smoke, gun/knife (trained here)
 Browser camera ─────┼─▶ API :8000 ───▶ │─ 2. DINOv2 verifier re-scores every proposed box
 Webcam / RTSP ──────┘   auth · SQLite   └─ 3. Violence: DINOv2 scene head + VideoMAE motion head, logistic stack
                         WebSocket                │  detector service :8001 (loopback only)
        Dashboard (React) ◀──┤                   ▼  k-of-n persistence → incidents + evidence frames + clips
        Android app (Flutter)◀┘
                         │
                         └─▶ Incident assistant ─▶ local Gemma 4 (Ollama)  or  Groq (open-weights Qwen)
                             answers from dossiers + real frames, streams the footage back;
                             optional "AI second opinion" on each incident (advisory only)
```

## What it detects

| Threat | Model | Notes |
|---|---|---|
| Fire, smoke | YOLO26s proposals → frozen DINOv2-base crop verifier | the verifier is what removes "smoke on a wall / face" false alarms; per-class thresholds are calibrated on threat-free validation data |
| Handguns / rifles, knives | YOLO26s proposals → DINOv2 verifier | trained on real CCTV frames plus curated sets; hard negatives mined from real video |
| Physical violence / fights | DINOv2 temporal head + VideoMAE-K400 motion head, logistic stack | video uses both heads; a still image uses the scene head only (and is much less sensitive) |

Uploaded video needs 3 of 4 consecutive sampled frames (5 fps) to agree before an incident is raised; live
streams need 2 of 4. The only exception is a single frame where the raw detector itself is ≥ 0.85 confident
*and* the verifier agrees. Violence never skips persistence.

Everything else (falls, intrusion, intent, concealed weapons…) is listed as **unsupported** in the
dashboard rather than silently ignored. A clean result means "none of the supported classes crossed
their thresholds", never "safe".

## How accurate is it, honestly

The headline numbers are on **blind footage**: DCSASS CCTV clips from parent videos that never took part in
training, mining or calibration, replayed through the same decision code as an upload. In-distribution test
splits are reported too but are not the headline. The weak spots are listed next to the numbers rather than hidden:
low-resolution CCTV fire/smoke is the worst (1 of 47 blind arson clips alerts, although at least 15 show visible fire), subtle
assault recall is moderate, still-image violence is insensitive and CCTV gun recall is modest. What the cascade fixed is
false alarms: 0 of 1,155 clean blind clips raised fire/smoke, 0 of 741 raised a weapon and 10 of 589 raised a fight.
See [docs/benchmarks.md](docs/benchmarks.md) (generated from `storage/benchmarks/*.json`, also shown on the
dashboard **System** screen) and [docs/ml-pipeline.md](docs/ml-pipeline.md) for method, data provenance and
limits. `docs/video-evaluation.md` is an older diagnostic of the first model and is kept for history only.

## Run it

```powershell
scripts/setup.ps1            # python 3.11 venv, CUDA torch, dashboard build
.venv\Scripts\python scripts/install-local-chat.py   # optional: Ollama + gemma4:e2b under storage/
scripts/start.ps1            # detector :8001, API + dashboard :8000, Ollama
```

Open `http://localhost:8000`, sign in with the account from `.env`
(`INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`; the test default is `admin@gmail.com` / `admin123` —
change it under System → Change your password). `start.ps1` prints the LAN address for the phone app.

* **Upload or live — same pipeline.** Dashboard → Analyze: drop an image/video, use the browser camera
  (5-second clips), or add a server webcam/RTSP camera. Phone: the Analyze tab does the same.
* **Phone.** `flutter run --dart-define=API_BASE_URL=http://<pc-ip>:8000`, sign in with the same
  account, or pair with a single-use code from System → Generate pairing code.
* **Assistant.** Investigation tab (dashboard) / Ask tab (phone). Choose *Local · Gemma* or *Groq*; the
  Groq key lives only in `.env` (`GROQ_API_KEY`). Answers cite incident ids, and the matching clip is
  played inline starting just before the detection.
* **AI second opinion (optional).** System → *AI second opinion* (or the button on an incident) asks the
  assistant model to look at the evidence frame and say whether it agrees. It is advisory: it never
  confirms or dismisses an incident, and a disagreement shows as an "AI disagrees" badge.

## Reproduce the training

```powershell
.venv\Scripts\python scripts/data/prepare_fire_v2.py       # D-Fire + extra fire/smoke + hard negatives -> storage/datasets/fire_smoke_v2
.venv\Scripts\python scripts/data/prepare_weapons_v2.py    # CCTV guns + curated weapons + hard negatives -> storage/datasets/weapons_v2
.venv\Scripts\python scripts/train_detector.py --name fire_smoke_v2 --data storage/datasets/fire_smoke_v2/data.yaml --imgsz 512 --time 1.0
.venv\Scripts\python scripts/benchmark_detector.py --name fire_smoke_v2 --weights <best.pt> --data ... --export-to storage/models/fire_smoke.pt
bash scripts/pipeline_v3.sh                                 # proposals -> verifier crops -> train + calibrate the verifier
.venv\Scripts\python scripts/violence/build_manifest.py   # then extract_features.py, train_head.py, extract_videomae.py,
                                                           # train_videomae_head.py, ensemble_eval.py (fits the logistic stack)
bash scripts/final_eval.sh                                  # fresh blind DCSASS sample + still-image stack (stop :8001 first)
.venv\Scripts\python scripts/report.py                     # rewrites docs/benchmarks.md
```

Datasets are downloaded by `scripts/data/fetch_queue.sh` (open datasets only; sources and licences are
recorded in each `storage/datasets/*/provenance.json`).

## Verify the whole ecosystem

```powershell
# detector on :8001 (scripts/start.ps1), then an isolated API so your own records stay untouched:
$env:SAFESPACE_STORAGE="storage/validation"; .venv\Scripts\python -m uvicorn app.main:app --app-dir services/api --port 8002
.venv\Scripts\python scripts/verify_ecosystem.py           # real held-out images/clips, WebSocket, media, chat
.venv\Scripts\pytest tests -q                               # API/pipeline contracts
```

## Repository layout

`contracts/` Pydantic contracts → generated TypeScript/Dart · `services/api` FastAPI (auth, incidents,
WebSocket, chat) · `services/inference` detector service · `apps/dashboard` React · `apps/mobile` Flutter ·
`config/` declarative config · `scripts/` data, training, benchmarks · `storage/` models, media, SQLite
(git-ignored runtime data).
