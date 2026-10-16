# SafeSpace — local CCTV threat detection

Your PC is the server. A web dashboard and an Android app connect to it over the local network; every
detection comes from models that ran on your own GPU. No cloud is needed for detection, storage, or
the incident assistant (Groq is an optional, explicitly selected alternative for the assistant).

```
 Upload image/video ─┐                    ┌─ Fire / smoke  (YOLO26s, trained here)
 Browser camera ─────┼─▶ API :8000 ─────▶ │─ Gun / knife   (YOLO26s, trained here)
 Webcam / RTSP ──────┘   auth · SQLite     └─ Violence      (DINOv2 + temporal head, trained here)
                         WebSocket                │  detector service :8001 (loopback only)
        Dashboard (React) ◀──┤                   ▼
        Android app (Flutter)◀┘        incidents + evidence frames + clips
                         │
                         └─▶ Incident assistant ─▶ local Gemma 4 (Ollama)  or  Groq (open-weights Qwen)
                             answers from dossiers + real frames, streams the footage back
```

## What it detects

| Threat | Model | Notes |
|---|---|---|
| Fire, smoke | YOLO26s detector | boxes, per-class calibrated threshold |
| Handguns / rifles, knives | YOLO26s detector | trained on real CCTV frames plus curated sets |
| Physical violence / fights | frozen DINOv2-base features + temporal transformer | scores a single still *and* temporal windows of video/live frames |

Everything else (falls, intrusion, intent, concealed weapons…) is listed as **unsupported** in the
dashboard rather than silently ignored. A clean result means "none of the supported classes crossed
their thresholds", never "safe".

Measured accuracy, false-alarm rates, latency and the dataset provenance are in
[docs/benchmarks.md](docs/benchmarks.md) (generated from `storage/benchmarks/*.json`, also shown on the
dashboard **System** screen) and [docs/ml-pipeline.md](docs/ml-pipeline.md).

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

## Reproduce the training

```powershell
.venv\Scripts\python scripts/data/prepare_fire.py          # D-Fire (+Jimei) -> storage/datasets/fire_smoke
.venv\Scripts\python scripts/data/prepare_weapons.py       # CCTV guns + HARIS -> storage/datasets/weapons
.venv\Scripts\python scripts/train_detector.py --name fire_smoke --data storage/datasets/fire_smoke/data.yaml --imgsz 512 --time 1.0
.venv\Scripts\python scripts/benchmark_detector.py --name fire_smoke --weights <best.pt> --data ... --export-to storage/models/fire_smoke.pt
.venv\Scripts\python scripts/violence/build_manifest.py && scripts/violence/extract_features.py --manifest ... && scripts/violence/train_head.py
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
