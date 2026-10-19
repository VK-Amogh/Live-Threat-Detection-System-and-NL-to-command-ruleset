# SafeSpace v3: Live Camera Network, Rulesets and On-Prem Assistant
## Implementation plan

| | |
|---|---|
| Status | Proposed, for review |
| Date | 2026-10-16 |
| Scope | `apps/mobile`, `apps/dashboard`, `services/api`, `services/rules`, `services/reasoner`, `contracts`, `config`, `scripts` |
| Server | The Windows laptop (RTX 4050 6 GB) runs everything: API, detectors, Gemma 4 (Ollama), recording, storage |
| Supersedes | Decision log **D-013** ("live preview ≈2 fps JPEG for v1"). See §4.4 |
| Design source of truth | `DESIGN.md` (binding for both the app and the dashboard) |
| Numbers in this document | Every latency, fps, memory or accuracy figure is a **target** unless it cites a measurement. Targets are verified in §7. |

**How to read this.** §1–§3 cover what we are building and what already exists. §4 is the architecture. §5 is the detailed design for each
workstream. §6 is the phased delivery plan with exit criteria. §7 is testing and verification, done last, as requested. §8–§10
cover risks, open questions and reference material.

---

## 1. Summary

SafeSpace becomes a closed, local camera network. **The laptop is the only server.** Phones running the SafeSpace APK join it with
no typing, and each phone picks one of two roles (it can switch later):

1. **Camera station.** The phone's camera streams live to the laptop. The laptop records continuously, saves screenshots on request,
   runs YOLO detection and rule evaluation on every camera, and shares the feed with every viewer.
2. **Control center (admin console).** Live view of every camera with detection overlays, alerts, rulesets, recordings, screenshots,
   and the Gemma assistant. Every question is processed on the laptop and streamed back.

The web dashboard on the laptop is the full-size control center and has the same capabilities.

**Product pillars**

| # | Pillar | What the user experiences |
|---|---|---|
| P1 | Any phone is a CCTV camera | Install the APK, tap **Camera**, name it "Front door". It is live on the laptop within seconds and recording. |
| P2 | Watch from anywhere on the LAN | Dashboard and any admin phone show every camera live, with boxes for what YOLO sees. |
| P3 | Rulesets | Describe what to watch in plain words, or pick a template. Choose cameras, draw the zone on the live picture, set a schedule and severity, test it on past recordings, arm it. When it comes true, the laptop alerts every admin phone within about 3 s, and Gemma adds a visual summary. |
| P4 | Ask your laptop | Phone and dashboard questions are answered by Gemma on the laptop. Answers are grounded in incidents, recordings, screenshots and live frames, with the footage played inline. |
| P5 | Zero-config fleet | The server addresses, server identity, camera enrollment code and the two admin accounts are compiled into the APK. A new phone needs no typing beyond its role choice (and a camera name). |

**Success criteria (targets, verified in §7)**

| Metric | Target |
|---|---|
| Time from opening a fresh APK to a live camera on the dashboard | ≤ 30 s, no typing except camera name |
| Live ingest (v1) | ≥ 10 fps at 960×540 on 5 GHz Wi-Fi, adaptive down to 5 fps |
| Glass-to-glass live latency (v1, LAN) | p95 ≤ 600 ms on the dashboard, ≤ 700 ms on an admin phone |
| Rule condition true → notification on a backgrounded admin phone | p95 ≤ 3.0 s, including the default 1.5 s hold (phase-6 fixture measured p95 1.84 s over USB) |
| Gemma visual summary attached to the alert | p95 ≤ 15 s |
| Assistant first token on the phone | p95 ≤ 2 s (laptop-side measured ≈0.1 s text / ≈0.46 s with a frame; `docs/benchmarks.md` §4) |
| Recording continuity | ≤ 1 % gap over an 8 h soak with healthy Wi-Fi |
| GPU memory, 4 live cameras + Gemma loaded | ≤ 5.5 GB of 6 GB |

**Non-goals for this plan:** cloud services or push through FCM (D-009 stays: no cloud); remote access from outside the LAN; iOS;
audio capture; face recognition or identity; PTZ; Gemma deciding whether an alert fires or dismissing one (D-008); re-adding
fire/smoke detection (removed by decision on 2026-10-16).

---

## 2. Requirements traceability

Each request in the brief maps to a design section, a delivery phase and an acceptance test in §7.5.

| ID | Requirement (from the brief) | Design | Phase | Acceptance |
|---|---|---|---|---|
| R1 | Any phone with the app acts as a live CCTV camera | §5.3 | 2 | AT-01 |
| R2 | Live video from the phone visible on the laptop | §5.3.4, §5.11 | 2, 6 | AT-02 |
| R3 | The same live video visible on other phones | §5.3.4, §5.10 | 2, 6 | AT-03 |
| R4 | Screenshots, stored on the laptop | §5.3.5 | 2 | AT-04 |
| R5 | The live stream is recorded and stored on the laptop | §5.3.6–5.3.8 | 2 | AT-05 |
| R6 | A "create ruleset" screen | §5.5 | 3, 6 | AT-06 |
| R7 | A ruleset is armed against selected live cameras | §5.5.2, §5.5.7 | 3 | AT-07 |
| R8 | When a ruleset comes true, the server processes it with YOLO and Gemma and alerts the phone | §5.4, §5.5.8, §5.6 | 3, 4 | AT-08 |
| R9 | Every phone Q&A is processed by Gemma on the laptop and streamed back | §5.7 | 5 | AT-09 |
| R10 | The assistant reads and analyses stored clips, recordings, screenshots and incidents | §5.7.3 | 5 | AT-10 |
| R11 | A phone is either admin console or live CCTV, chosen on screen, changeable | §5.2.5 | 1 | AT-11 |
| R12 | Server URL, pairing and configuration hardcoded into the APK | §5.1, App. B | 1 | AT-12 |
| R13 | Login only `admin1@safespace.com` / `admin2@safespace.com`, password `admin123` | §5.2.1 | 1 | AT-13 |
| R14 | Professional UI/UX on app and dashboard, with visible images and video in every card | §5.10–5.12 | 6 | AT-14 |
| R15 | Phones, dashboard and server behave as one consistent ecosystem | §4, §5.13 | all | AT-15 |

---

## 3. Where we are today (audit)

A first version of most features already exists in the working tree; much of it is uncommitted (see `git status`). This plan closes
the gaps in that code rather than rebuilding it.

| Area | Exists today | Gap or defect | Target |
|---|---|---|---|
| Connectivity | Manual server URL on `features/pairing/pairing_screen.dart`; default `http://10.0.2.2:8000` in `core/config.dart`; `scripts/start.ps1` prints LAN IPs | `tests/phase6_phone_gate.md`: **phone→PC over Wi-Fi never worked** (curl timed out, the test used USB forwarding). A hardcoded IP breaks when DHCP changes it. There is no discovery and no server identity check. | §5.1 |
| Accounts | `security.bootstrap()` seeds **one** user, only when `users` is empty (`admin@gmail.com` in `.env`) | No admin1/admin2. Sessions expire after 7 days, so a camera phone silently drops after a week. | §5.2 |
| Device identity | `create_session()` mints a new `device_id` uuid on every login | Phone camera id is `cam_phone_<device_id>` (`main.py` `register_phone_camera`), so **every re-login creates a new camera** and orphans its rules and recordings. | §5.2.3 |
| Roles | Mode chooser in `app.dart`, stored in SharedPreferences `safespace_phone_mode`; switching from `StatusScreen` and `CameraStationScreen` | The server does not know a device's role. A camera phone holds a full-admin token. Switching camera → admin needs no authentication. | §5.2.5 |
| Camera ingest | `camera_station_screen.dart`: `takePicture()` → read file → HTTP POST → sleep 250 ms | About 1–3 fps, a temp file per frame, and capture stops on any lifecycle change other than `resumed`. | §5.3.1–5.3.2 |
| Live viewing | `live_cameras_screen.dart` and `Analyze.tsx` poll `/cameras/{id}/frame` every 500 ms | ≤ 2 fps, one HTTP request per frame per viewer, no overlay on the phone. | §5.3.4 |
| Recording | `mobile_camera.py`: ffmpeg rawvideo at **4 fps with duplicated frames**, 300 s files | Phone cameras only; webcam/RTSP cameras are not recorded. `retention_days: 14` in `config/rules.yaml` is **enforced nowhere** (grep confirms). | §5.3.6–5.3.8 |
| Screenshots | Copy of `storage/previews/<id>.jpg` | Works. Resolution is whatever the last ingest frame was. | §5.3.5 |
| Phone inference | `PhoneCameraSession` builds a YOLO `CameraDetector` **inside the API process** per phone, plus calls the threat pipeline per frame | There are two detection code paths (server cameras use `services/rules/worker.py` processes). GPU work runs inside the API process, and each camera loads its own model. | §5.4 |
| Rules | Natural language → Gemma → `RuleSpec` DSL (`services/rules/compiler.py`), readback-hash confirmation, activation (`rule_routes.py`), engine + worker | One rule = one camera. No grouping, schedules, arming, severity, notification routing, templates or dry-run. Zones are drawn only on the dashboard (`GeometryEditor.tsx`). | §5.5 |
| Alerts | `ws_client.dart` + `notification_service.dart`; change-feed catch-up (D-012) | Notifications arrive **only while the app process is alive** (no FCM by design). No image, no actions. `DeviceOut.notify_enabled/min_severity` exist in contracts but are unused. | §5.6 |
| Assistant | `chat.py`: NDJSON streaming, events-only retrieval, ≤ 6 images, `SLOT` semaphore | Cannot answer about recordings, screenshots or live frames. The rule compiler (`services/rules/llm.py`) and the reasoner (`services/reasoner/loop.py`) call Ollama outside the semaphore, so there is no prioritisation. | §5.7 |
| UI | `DESIGN.md` (three colours, Stratis icons, serif headings, real data only) | `Colors.greenAccent` LIVE dot (`live_cameras_screen.dart`) breaks the three-colour rule. Material `Icons.*` are used in 6 files, but only 17 Stratis SVGs ship in `assets/icons`. The dashboard is one 15 KB `App.tsx` with tab state. | §5.10–5.12 |
| Contracts | `td_contracts` is the source of truth (D-010/D-015) | Phone-camera, recording and snapshot endpoints return untyped dicts; Dart reads `Map<String, dynamic>`. | §5.13 |
| Docs/config | `.env.example` and `docker-compose.yml` describe PostgreSQL (D-006) | The code uses SQLite (`database.py`). The docs are stale. | §5.14 |

---

## 4. Target architecture

### 4.1 System context

```
 Camera phones (role: CAMERA_STATION)            Laptop  (Windows · RTX 4050 6 GB · the only server)
 ┌──────────────────────┐      ┌───────────────────────────────────────────────────────────────────────────────┐
 │ Camera station       │      │ API  :8000  FastAPI, single process (D-003)                                   │
 │  CameraX frames      │  WS  │  auth · devices/roles · rulesets · incidents · change feed · assistant        │
 │  → JPEG (native)     ├─────▶│  ┌──────────────── Media hub (per camera: latest frame, fan-out) ──────────┐ │
 │  ← commands          │      │  │  ├─▶ Recorder: ffmpeg → 5-min H.264 fMP4 segments → storage/recordings  │ │
 └──────────────────────┘      │  │  ├─▶ Snapshots → storage/snapshots                                     │ │
                               │  │  ├─▶ Viewer sockets (admin phones, dashboard) + observation overlays    │ │
 Admin phones (CONTROL_CENTER) │  │  └─▶ Internal frame tap (loopback only) ──────────────┐                │ │
 ┌──────────────────────┐  WS  │  └───────────────────────────────────────────────────────┼────────────────┘ │
 │ Live · Alerts · Rules├◀────▶│  Event socket /api/v1/ws (alerts, status, change feed)   │                  │
 │ Assistant · Settings │ HTTP │  LLM gateway (priority queue) ─▶ Ollama :11434 gemma4:e2b │                  │
 └──────────────────────┘      │  Discovery responder UDP :47800 (LAN)                     │                  │
 Dashboard (browser) ◀────────▶│                                                           │                  │
                               ├───────────────────────────────────────────────────────────┼──────────────────┤
                               │ Rule manager ─▶ one camera worker per live camera ◀────────┘                  │
                               │   YOLO26n + ByteTrack → RuleEngine → RuleEvents (disk outbox) → API          │
                               │   sampled frames → API /internal/live-frame → Detector :8001                 │
                               │   (gun/knife YOLO26s → DINOv2 verifier; violence stack)                      │
                               │ PC webcam / RTSP capture ─▶ publishes into the hub over loopback             │
                               │ Reasoner loop ─▶ LLM gateway (visual summaries after rule alerts)            │
                               └───────────────────────────────────────────────────────────────────────────────┘
```

**Two invariants make this an ecosystem rather than a set of apps.**

1. **One hub.** Every camera (phone, PC webcam, RTSP) publishes into the hub, and every consumer reads from it: viewers, the recorder,
   snapshots, the inference workers.
2. **One state.** All state lives on the laptop (SQLite + `storage/`). Every change is broadcast on the event socket, so phones and
   dashboard converge within about 1 s, and the change feed (D-012) repairs anything missed.

### 4.2 Processes and ports

| Process | Bind | Port | Reachable from LAN | Notes |
|---|---|---|---|---|
| API (uvicorn) | 0.0.0.0 | 8000/tcp | **yes** | REST, WebSockets (events, publish, view), dashboard static files, APK download |
| Discovery responder (inside API) | 0.0.0.0 | 47800/udp | **yes** | Replies to SafeSpace discovery queries only (§5.1.4) |
| Detector service | 127.0.0.1 | 8001 | no | Existing threat models |
| Ollama | 127.0.0.1 | 11434 | no | gemma4:e2b, `num_gpu 99`, shared `num_ctx 6144` |
| Rule manager + camera workers | — | outbound only | no | One worker process per live camera |
| Reasoner loop | — | outbound only | no | Claims review jobs, calls the LLM gateway |
| Recorder (ffmpeg children of API) | — | pipes | no | One per live camera |
| *(v2 only)* MediaMTX | 0.0.0.0 / 127.0.0.1 | 8889/tcp, 8189/udp+tcp on LAN; 8554, 9996, 9997 on loopback | partly | §5.3.10 |

### 4.3 Key flows

**F1. A camera goes live**
1. The app starts, and the `ConnectionResolver` races the baked server candidates (§5.1.3), accepting only the baked `SERVER_ID`.
2. Role = Camera. If the device has no camera token: `POST /api/v1/devices/enroll` with the baked enrollment code and the
   installation id. The response is a **camera-scoped** token (365 days).
3. `POST /api/v1/media/tickets {camera_id, action: "publish"}` returns a 30 s single-use ticket (same pattern as D-014).
4. Open `WS /api/v1/cameras/{camera_id}/publish?ticket=…`. The server's `hello` carries the capture profile and quality ladder.
5. The phone streams binary frames. The server acknowledges each one (flow control, §5.3.1).
6. The hub fans each frame out to viewers, the recorder and the internal tap, and broadcasts `camera.status` (LIVE).
7. The rule manager sees the camera active and starts its worker with source `hub://<camera_id>`. The worker samples at 5 fps.

**F2. Watching live (admin phone or dashboard)**
1. The live grid shows thumbnails from `GET /cameras/{id}/frame.jpg?w=320`, refreshed every 2 s. Grids never open N video sockets.
2. Tapping a tile requests a `view` ticket and opens `WS /cameras/{id}/view`. The client receives binary frames plus `observation`
   messages (track boxes) and draws the overlay.
3. The player shows fps, latency and viewer count. The camera phone shows "2 watching".

**F3. A ruleset fires**
1. Worker observation → `RuleEngine` `Fire` (after `min_hold_s`) → `RuleEvent` carrying `ruleset_id` → disk outbox → API ingest.
   Ingest is idempotent: `Idempotency-Key = event_id`.
2. The API persists the event with a change sequence and broadcasts `event.created`.
3. On each admin phone, the foreground service receives it and posts a notification with the keyframe, routed by the ruleset's
   severity and that device's preferences.
4. If the ruleset has visual summaries on: review job → reasoner → LLM gateway (priority P0) → Gemma describes the sampled frames →
   `event.updated` → the notification updates silently with the "AI view" line.
5. The evidence clip is cut from the recording segments (8 s before, 8 s after) and attached as a later `event.updated`.

**F4. A question asked on the phone**
1. `POST /api/v1/chat/stream` (NDJSON) to the laptop. The phone never talks to Ollama.
2. Retrieval plan: a Gemma structured output, validated by Pydantic, with a deterministic fallback.
3. Server-side retrieval over incidents, recording frames, screenshots, live frames, rules and system state.
4. The stream sends `plan`, then `evidence` (thumbnails), then token `delta`s, then `done` with the cited media. The phone plays clips
   inline.

**F5. Screenshot**
1. Any client sends `POST /cameras/{id}/snapshots {quality: "stream" | "full"}`.
2. `full` asks the camera phone, over its publish socket, to take a full-resolution still and upload it. After 3 s the server falls
   back to the latest hub frame.
3. The file is saved under `storage/snapshots/<camera>/` and `snapshot.created` is broadcast, so every gallery updates.

**F6. Role switch**
- Control center → Camera: confirm sheet, then the admin token is logged out and the device uses its camera token.
- Camera → Control center: **requires an admin sign-in with a typed password**, so an unattended camera phone cannot be used to
  watch every camera.

### 4.4 Architecture decisions (to append to `docs/decision-log.md`)

| ID | Decision | Rationale and consequences |
|---|---|---|
| **D-030** | **Live transport ladder.** v1: WebSocket JPEG through the API hub (always available, port 8000 only). v2: WebRTC through MediaMTX, adopted only after spike S4 passes. **Supersedes D-013.** | The brief requires real live video on several viewers plus recording, which a 2 fps preview cannot provide. WS-JPEG reuses the existing auth, tickets and code, and needs no extra firewall ports, so it de-risks the critical path while Wi-Fi reachability is unproven (phase-6 note). WebRTC (hardware H.264, about 1.5 Mbps at 720p) is better on bandwidth and frame rate, but adds a binary, two ports, ICE, and `flutter_webrtc`. Clients choose from a `StreamDescriptor`, so moving to v2 needs no UI change. |
| **D-031** | **One media hub.** Every camera publishes into the hub in the API process; every consumer reads from it. No inference runs in the API process. | Removes the second detection path (YOLO in `mobile_camera.py`). Server webcams and RTSP cameras get recording and snapshots too. |
| **D-032** | **Device identity = installation id.** The camera id is stable: `cam_<sha256(installation_id)[:12]>`. | Re-login no longer orphans rules and recordings. |
| **D-033** | **Token scopes.** `admin`: 30 days, sliding. `camera`: 365 days, may only publish and manage its own stream. Camera → admin switch requires a password. | Least privilege. A lost camera phone exposes one stream, not the system. |
| **D-034** | **Rulesets compile to per-camera `RuleSpec`s.** The existing engine and worker run unchanged. One readback hash covers the whole ruleset. | Reuses the verified engine and the confirmation flow. |
| **D-035** | **Gemma never decides whether a rule fires and never dismisses an alert** (restates D-008). Gemma compiles rules, plans retrieval and writes summaries. | Keeps alerts deterministic and auditable. |
| **D-036** | **All Ollama traffic goes through one LLM gateway with priorities.** Every call uses `ollama_runtime()`. | Prevents model reloads (measured cause of 10–16 s first-token delays) and lets alert summaries go ahead of chat. |
| **D-037** | **No cloud push.** An Android foreground service keeps the event socket open on admin phones. | Consistent with D-009. Reliability depends on battery-optimisation exemptions (§5.6). |
| **D-038** | **Build-time client configuration** (`--dart-define-from-file`) is generated from `.env`. Secrets are never committed. | Meets "hardcode into the APK" without putting secrets in git (D-029). |
| **D-039** | **Recording = continuous, segmented, fragmented H.264 MP4 on the laptop.** Retention runs by age and by a free-disk floor, enforced by a sweeper. | Fragmented segments stay playable after a crash. Retention is finally enforced. |

---

## 5. Detailed design

### 5.1 Connectivity and zero-config

**5.1.1 Network modes, in order of preference**

| Mode | How | Why |
|---|---|---|
| A. Laptop hotspot | Windows Mobile Hotspot on the laptop. Phones join it. | The Windows ICS host address is deterministically `192.168.137.1`, so the hardcoded URL never changes. There is no router client isolation. *Verify in Phase 0:* some Windows builds refuse to start a hotspot with no upstream connection. |
| B. Home or venue router | DHCP reservation for the laptop, phones on the same SSID | Hardcoded IP stays valid. Fails if the router isolates clients. |
| C. USB (development) | `adb reverse tcp:8000 tcp:8000` → `http://127.0.0.1:8000` | The method the phase-6 gate used. Always works for one phone. |

**5.1.2 Baked candidates.** `SERVER_URLS` is compiled into the APK (Appendix B), for example
`["http://192.168.137.1:8000", "http://<reserved-ip>:8000", "http://127.0.0.1:8000"]`. To that list the app adds its last known good
URL and any discovery result.

**5.1.3 `ConnectionResolver` (Dart, `lib/core/connection/resolver.dart`)**
- Probes all candidates in parallel with a 1.5 s timeout: `GET /api/v1/health/live` returns `{status, server_id, server_name, version, features}`.
- Accepts only `server_id == BAKED_SERVER_ID`. It then proves the server knows the shared secret:
  `GET /api/v1/health/identity?nonce=<random>` returns `hmac_sha256(CAMERA_ENROLLMENT_CODE, nonce)`.
  This stops the app from talking to a wrong or rogue host on a shared network.
- Caches the winner. Re-resolves after 3 consecutive network failures, or when Wi-Fi changes (`connectivity_plus`).
- Exposes its state to a **Connection diagnostics** page: each candidate, latency, result, and a plain explanation such as
  "Reached the network but not the laptop: Windows Firewall or Wi-Fi client isolation is likely".

**5.1.4 Discovery.** The phone broadcasts `{"q":"safespace","id":SERVER_ID}` to `255.255.255.255:47800`. The API's asyncio
`DatagramProtocol` replies by unicast with `{"id", "port", "urls"}`. A query-response design is used because sending a broadcast needs
no Android multicast lock; only listening for one does.

**5.1.5 Laptop setup scripts**
- `scripts/network-setup.ps1` (run once as admin):
  - Sets the active profile to **Private**.
  - **Removes inbound Block rules for the venv `python.exe`.** Dismissing the first Windows Firewall prompt creates one, and that is a
    likely cause of the phase-6 timeout.
  - Adds Allow rules (Private profile, program-scoped) for TCP 8000 and UDP 47800, plus TCP 8889 and UDP/TCP 8189 for v2.
  - Prints hotspot instructions.
- `scripts/doctor.ps1`: lists IPv4 addresses, profile, listening ports and firewall rules, calls `/api/v1/health/live` on every LAN IP
  from the laptop itself, and prints a verdict.
- `scripts/start.ps1`: prints the candidate URLs and a terminal QR code for APK download (§5.1.6).

**5.1.6 APK distribution.** `scripts/build-apk.ps1` builds the signed release APK into `storage/dist/`. On the dashboard,
**Devices → Add a phone** shows a QR code for a 10-minute single-use URL `/download/{token}/SafeSpace.apk`. A new phone scans it,
installs (allowing "install unknown apps" once) and opens. Discovery and role choice follow. The download link is single-use because
the APK contains the enrollment code.

### 5.2 Identity, accounts, devices and roles

**5.2.1 Accounts**
- `.env`: `SEED_ACCOUNTS=admin1@safespace.com:admin123:Admin 1,admin2@safespace.com:admin123:Admin 2`.
- `bootstrap()` becomes an idempotent upsert: insert the account if it is missing, and never overwrite a changed password.
- Any other existing user (today `admin@gmail.com`) is marked `disabled=1` (new column). It is **not deleted**, so the existing
  incidents and conversations stay intact. Login rejects disabled users. Open question Q4 covers whether to remove it instead.
- Both accounts are full admins over one shared home: cameras, incidents and rulesets are shared, conversations are per user. Every
  change records who made it (§5.2.6).
- Stated once: credentials compiled into an APK can be extracted from it. This is acceptable only on a private LAN. Never port-forward
  8000.

**5.2.2 Login screen (app and dashboard).** Two account tiles, **Admin 1** and **Admin 2**. A tile pre-fills the email; the password
is typed. The build flag `DEMO_AUTOFILL_PASSWORD=true` allows one-tap sign-in on the **first-run** screen only. It never applies when
leaving camera mode. The dashboard login offers the same two tiles.

**5.2.3 Devices table and stable identity**
- On first launch the app generates an `installation_id` (UUIDv4) and keeps it in secure storage.
- Login, pairing and enrollment send `{installation_id, platform, model, app_version}`.
- The server upserts a `devices` row keyed on `installation_id`, so `device_id` is stable across logins. Sessions reference
  `device_id`.
- The camera id is `cam_<sha256(installation_id)[:12]>`.
- Existing `cam_phone_<uuid>` cameras become legacy and offline. Their rules can be re-targeted by adding the new camera to the
  ruleset.

**5.2.4 Token scopes and lifetime (D-033)**

| Scope | Issued by | Lifetime | May call |
|---|---|---|---|
| `admin` | login (admin1/admin2), single-use pairing code | 30 days, sliding: renewed on use when < 7 days remain, at most once per hour | Everything under `/api/v1` |
| `camera` | `POST /devices/enroll` with the baked enrollment code | 365 days | `GET /health/*`; `GET/PATCH /devices/me`; `POST /media/tickets` (publish, own camera only); `WS /cameras/{own}/publish`; `POST /cameras/{own}/stills` |

Enforcement: a `require_scope("admin")` dependency on every router by default, with explicit camera-scope routes. A test asserts that
the camera scope gets 403 on every other route (§7.3).

**5.2.5 Roles**
- `devices.role ∈ {UNASSIGNED, CONTROL_CENTER, CAMERA_STATION}`, set through `PATCH /devices/me {role}` and broadcast as `device.status`.
- Control center → Camera: one confirm sheet. The admin session is logged out and the device keeps or obtains its camera token.
- Camera → Control center: sign-in sheet with the account tiles and a typed password. The camera stream stops cleanly first.
- On first enrollment the camera asks for a name, with suggestions ("Front door", "Living room", "Garage", "Back gate"). Admins can
  rename it from any client.

**5.2.6 Audit log.** An `audit_log` table records:
- Device enrolled, role changed, token revoked.
- Ruleset created, armed, disarmed.
- Incident confirmed or dismissed.
- Live view started (who and which device), snapshot taken, recording exported.
- Password changed.

It is shown on the dashboard Devices and System screens and under Settings → Activity on phones.

### 5.3 Media plane

**5.3.1 Publish protocol: `WS /api/v1/cameras/{id}/publish?ticket=…`**

| Direction | Message |
|---|---|
| server → phone (text) | `hello {camera_id, profile:{width:960,height:540,fps:10,jpeg_quality:75}, ladder:[…], record:true, server_time_ms}` |
| phone → server (binary) | 16-byte header `"SSF1" · seq:uint32 · capture_ts_ms:uint64` + JPEG (≤ 1 MB) |
| server → phone (text) | `ack {seq, rx_ts_ms}` for every frame; `profile {…}` to adapt; `command {id, name}` where name is `capture_still`, `switch_lens`, `torch`, `set_profile` or `locate`; `viewers {count}` |
| phone → server (text) | `telemetry {battery_pct, charging, temp_c, net:{type,rssi}, capture_fps, encode_ms, inflight}` every 10 s; `command_result {id, ok, error}` |

- **Flow control.** At most 2 un-acknowledged frames. When the window is full, new frames are dropped on the phone; there is never a
  backlog.
- **Adaptive ladder.** 960×540@10 → 640×360@8 → 480×270@5. Step down when ack RTT p50 > 300 ms or more than 10 % of frames drop over
  5 s. Step up after 30 s healthy.
- **Clock.** Ping/pong at handshake estimates the phone-server clock offset, which is used only for latency metrics. Server receipt
  time is authoritative for recording and rules.
- **Validation.** JPEG SOI/EOI markers, ≤ 1 MB, ≤ 15 fps (excess dropped), owner device must match, camera scope only.

**5.3.2 Capture on Android (v1)**
- The `camera` plugin's `startImageStream` delivers NV21/YUV frames.
- A Kotlin platform channel (`JpegEncoder`: `YuvImage.compressToJpeg`, rotation applied natively) encodes them. Encoding in Dart is too
  slow at this resolution.
- The publish client sends the result. Capture fps is throttled at the source; frames are not taken and then discarded.
- Phase 0 spike S1 measures the A069 (encode ms, fps, CPU, temperature, battery drain per hour) and confirms which image formats the
  plugin delivers on it. **Do not assume a format before the spike.**

**5.3.3 Hub (`services/api/app/media/hub.py`)**
- One `CameraChannel` per camera, holding the latest `(seq, ts, jpeg)` behind an `asyncio.Condition`.
- Each subscriber gets a **latest-only mailbox**: one slot, overwritten. Memory is bounded at one frame per subscriber and a slow
  viewer can never slow down ingest.
- Stats: fps in and out, bytes, viewers, `last_frame_age_s`. These feed `camera.status`, rate-limited to 1 per second per camera.
- Video is never sent on the event socket. `broadcast()` validates the session with a DB read per socket per message, so it should also
  cache that check for 5 s.

**5.3.4 Viewing**
- `WS /api/v1/cameras/{id}/view?ticket=…` (scope admin) sends binary frames at `min(source fps, requested fps)`. Interleaved text
  messages:
  - `observation {frame_ts, width, height, tracks:[{id, cls, conf, box}]}` at analysis fps
  - `status {live, fps, viewers, recording, analysis_fps}`
  - `ended {reason}`

  The client may send `set_fps`.
- `GET /cameras/{id}/frame.jpg?w=320`: latest frame, downscaled server-side and cached for 1 s per size. Used for grid thumbnails.
- `GET /cameras/{id}/live.mjpg`: multipart MJPEG fallback for a plain `<img>` (same-origin cookie auth).
- Clients:
  - **Dashboard:** the binary frame goes to `createImageBitmap`, then to a `<canvas>`, with an SVG overlay.
  - **Phone:** `decodeImageFromList` → `CustomPaint` with an overlay painter. This avoids rebuilding an `Image` widget per frame.
- **Overlay honesty.** Boxes and video can be up to one analysis interval apart (about 200 ms). The player shows the box timestamp age
  and hides boxes older than 1 s.

**5.3.5 Screenshots**
- `POST /cameras/{id}/snapshots {quality:"stream"|"full"}`.
  - `full` sends `capture_still` to the camera phone. The phone calls `takePicture()` at full sensor resolution and uploads to
    `POST /cameras/{id}/stills` (camera scope, ≤ 10 MB, JPEG validated). After 3 s the server falls back to the hub frame.
  - `stream` saves the latest hub frame.
- Storage: `storage/snapshots/<camera>/<id>.jpg` plus a 320-px thumbnail. Rows go in a `snapshots` table (time-indexed). The server
  broadcasts `snapshot.created`.
- Snapshots can be taken from the camera station, an admin phone, or the dashboard, including from a recording frame.
- Gallery: paginated by camera and day. Share and download (dashboard) or save to phone. "Ask the assistant about this".
- Delete moves the file to `storage/trash`, recoverable for 7 days, and is audit-logged.

**5.3.6 Recorder (`services/api/app/media/recorder.py`)**
- One ffmpeg child per live camera. JPEG bytes are **piped straight from the hub** with no decode in Python:
  `-f image2pipe -c:v mjpeg -use_wallclock_as_timestamps 1 -i pipe:0 -fps_mode vfr -c:v <h264_nvenc|libx264> -b:v 1.5M -g 20`
  `-f segment -segment_time 300 -reset_timestamps 1 -strftime 1`
  `-segment_format_options movflags=+frag_keyframe+empty_moov+default_base_moof <dir>/%Y%m%d-%H%M%S.mp4`
- Fragmented MP4 keeps a segment playable if the process is killed.
- NVENC is used if `ffmpeg -encoders` lists `h264_nvenc`; otherwise `libx264 -preset veryfast`. Phase 0 checks whether the bundled
  `imageio-ffmpeg` build includes NVENC.
- **Gaps are real.** No frames for 5 s closes the pipe. The next frame opens a new segment, so the timeline shows the outage instead of
  frozen duplicate frames (today's code duplicates up to 20 frames).
- An indexer probes each closed segment (`ffprobe` duration) into `recording_segments`. The open segment is shown as `RECORDING`.
- Server webcams and RTSP cameras are recorded the same way, because their worker publishes into the hub (§5.4).

**5.3.7 Recordings API**
- `GET /cameras/{id}/timeline?date=YYYY-MM-DD` returns `{segments:[{id,start,end,url,sprite_url}], events:[{id,ts,category,thumb_url}], gaps:[…]}`.
- `GET /recordings/{segment_id}.mp4` must support **HTTP Range** for seeking in ExoPlayer and browsers. Verify Starlette
  `FileResponse` range support in the installed version; if absent, add a small range handler.
- Scrubbing preview: one sprite sheet per segment, one thumbnail every 10 s, generated after the segment closes.
- `POST /cameras/{id}/exports {start, end}`: ffmpeg concat + trim with `-c copy`, cut at keyframes (≤ 2 s precision at `-g 20`), then
  `GET /exports/{id}.mp4`. Audit-logged.

**5.3.8 Retention (`config/media.yaml` + sweeper)**
- Defaults: `recordings_days: 7`, `snapshots_days: 30`, `min_free_gb: 20`. Incident evidence is kept until the incident is deleted.
- The API background sweeper runs every 10 minutes. It deletes the oldest segments past retention, and also while free space is below
  the floor. It never deletes segments referenced by an incident clip or an unfinished export.
- The System screen shows usage per camera and projected days remaining.

**5.3.9 Capacity (estimates, measured in Phase 0)**

| Item | Estimate |
|---|---|
| Ingest per camera, 960×540 JPEG q75 @ 10 fps | ≈ 60–80 KB × 10 ≈ 5–6 Mbit/s |
| 4 cameras | ≈ 20–25 Mbit/s up, plus viewers down. Fine on 5 GHz, marginal on 2.4 GHz (the ladder handles it) |
| Recording at 1.5 Mbit/s | ≈ 0.68 GB/h ≈ 16 GB/day per camera, so 7 days × 2 cameras ≈ 225 GB. Size retention to the disk (open question Q5) |
| Encoder CPU (libx264 veryfast, 540p10) | ≈ 10–20 % of one core per camera; NVENC ≈ 0 |

**5.3.10 Live v2: WebRTC through MediaMTX (Phase 7, gated by spike S4)**
- MediaMTX, pinned version, SHA-256-verified download into `storage/runtime/mediamtx/`, configured by `config/mediamtx.yml`.
- `authMethod: http` points at `POST /api/v1/internal/media-auth`, which validates media tickets for `publish`/`read` on a path.
- The phone publishes over WHIP with `flutter_webrtc`: hardware H.264, 1280×720 @ 20 fps, about 1.5 Mbit/s. Viewers use WHEP.
  Workers read `rtsp://127.0.0.1:8554/<camera>`.
- MediaMTX's own fMP4 recorder replaces ours for those cameras; the segment indexer and sweeper stay.
- Adds TCP 8889 and UDP/TCP 8189 to the firewall script. Set `webrtcAdditionalHosts` to the LAN IPs.
- The `StreamDescriptor` lists `webrtc-whep` first and `ws-jpeg` second. A client falls back automatically if ICE fails within 4 s.
- **Adopt v2 only if:** WHIP publishes from the A069 over Wi-Fi with p95 latency ≤ 400 ms, survives a 30-minute run, and a Chrome WHEP
  viewer plus a phone WHEP viewer both connect with the firewall rules applied.

### 5.4 Vision processing

- **One worker per live camera**, using the existing `services/rules/manager.py` and `worker.py`, with a pluggable source:
  - `HubSource(camera_id)`: internal WS subscription on loopback with the internal token, latest-only, sampled at `process_fps`.
  - `CaptureSource(uri)`: the existing `capture.frames()`, which additionally publishes every frame into the hub over loopback.
- **Remove YOLO and the rule engine from `mobile_camera.py`.** `/internal/cameras` lists phone cameras with source `hub://<id>`. One
  detection path for every camera.
- **Overlays.** The worker posts compact observations (`tracks`) to the hub's internal endpoint at analysis fps. The hub forwards them
  only to viewers with overlays on.
- **Threat pipeline.** Kept as is (`/internal/live-frame` → detector :8001), behind a new global **ThreatScheduler** in the API:
  - Total budget B frames/s, measured in Phase 0. Fair round-robin across live cameras; drop, never queue.
  - Each camera reports its effective threat-analysis fps, shown in the UI ("Threat analysis 3 fps"), so coverage is never overstated.
- **GPU budget (filled in Phase 0, spike S3)**

  | Component | VRAM (to measure) |
  |---|---|
  | Detector service: weapons YOLO26s + DINOv2 verifier + violence heads | |
  | Ollama gemma4:e2b, `num_ctx 6144`, all layers on GPU | |
  | One rule worker: YOLO26n + CUDA context, × N cameras | |
  | **Total at N = 4 (budget ≤ 5.5 GB)** | |

  If N = 3 already exceeds the budget, run **Phase 4b consolidation**: `services/rules/vision_hub.py`, one process, one YOLO26n,
  batched `predict` across cameras, one `BYTETracker` instance per camera (Ultralytics tracker state is per model, so a shared model
  must not use `model.track(persist=True)`).
- **Evidence clips.** Cut from recording segments (full frame rate, real video). Fall back to the existing `EvidenceBuffer` when no
  segment covers the window.
- **Health.** Workers send heartbeats into `camera.status.analysis {running, fps, last_inference_ms, gpu_ok}`. The existing
  `CameraHealthEvent` behaviour (outage after 5 s, inference failure after 5 s) is kept.

### 5.5 Rulesets (headline feature)

**5.5.1 Concepts**
- **Rule:** the existing `RuleSpec`; one camera, one entity, a `when` tree.
- **Ruleset:** a named, user-facing bundle. What to watch, which cameras, when it is armed, how severe, who is told, and whether
  Gemma summarises.
- **Mode (optional):** Home, Away, Night. One tap arms or disarms a group of rulesets.
- **Always-on protections:** weapon (gun/knife) and fight detection stay on for every live camera and are **not** rules. A ruleset
  cannot mute them.

**5.5.2 Data model (`contracts/src/td_contracts/rulesets.py`)**

```text
RulesetSpec
  ruleset_id, version, name, description
  cameras: [camera_id]
  definition: { source: "text"|"template"|"builder", text?, template_id?, params?,
                entities: [str], when: RuleWhen }        # zone/line referenced by NAME
  schedule:   { mode: "always"|"windows", windows: [{days:[1..7], start:"22:00", end:"06:00"}], tz }
  severity:   LOW|MEDIUM|HIGH|CRITICAL
  notify:     { targets: "all_admins"|[device_id], cooldown_s, group: bool }
  visual_summary: bool
  status:     draft|armed|disarmed
RulesetOut = RulesetSpec + readback, readback_hash,
             per_camera: [{camera_id, rule_ids, support_level, state: READY|NEEDS_SETUP|UNSUPPORTED, problems}],
             last_fired_at, fires_24h, false_alarm_ratio, cover_url
```

- **Compilation.**
  1. The definition is compiled once: Gemma for text, deterministic for templates and the builder.
  2. It then expands to one `RuleSpec` per (camera × entity). `RuleSpec` gains `ruleset_id` and an optional `schedule`.
  3. Each child is assessed by `CapabilityRegistry` against **that camera's** geometry. A camera missing the zone becomes
     `NEEDS_SETUP` with the action "Draw 'driveway' on Back gate".
- **Schedule.** Evaluated by the engine as a gate before the condition tree. Windows that cross midnight and days of week are both
  supported. The readback includes it: "on weekdays from 22:00 to 06:00 (Asia/Kolkata)". This avoids adding new leaf types to the
  closed DSL.
- **Readback and hash.** One sentence for the ruleset plus one line per camera. The hash covers the canonical JSON of every child spec,
  the schedule, severity and notify. Arming requires it, as today. Any geometry change bumps the version and asks for re-confirmation.

**5.5.3 Three ways to create, one review step**
1. **Describe it.** The natural-language composer uses the existing compiler, extended with the union of zone and line names across the
   selected cameras and with template hints. Example chips: "Someone lingers at the front door for 20 seconds at night",
   "A car stops in the driveway".
2. **Start from a template.** A deterministic parameter form (§5.5.4).
3. **Build it.** A visual builder: **Who** (detector class) → **Where** (zone or line on the live frame) → **When** (dwell, count,
   approach, schedule) → **Then** (severity, who is notified, AI summary). It emits the same `RulesetSpec` without calling the LLM.

All three end on the **Review** step: the readback, a per-camera support check, **Test on recordings**, and **Arm**.

**5.5.4 Template catalogue.** Only what the DSL and the `yolo26n` COCO classes actually support.

| ID | Template | Compiles to | Needs |
|---|---|---|---|
| T1 | Someone enters an area | `person` · `in_zone(zone)` | zone |
| T2 | Someone lingers | `person` · `in_zone` ∧ `dwell_at_least(30 s)` | zone |
| T3 | Someone crosses a line | `person` · `line_cross(line)` | line |
| T4 | Anyone after hours | `person` · `entity_present` + schedule 23:00–06:00 | — |
| T5 | A vehicle stops | `car`, `truck`, `motorcycle` · `in_zone` ∧ `dwell_at_least(10 s)` | zone |
| T6 | Crowd at an entrance | `person` · `unique_count_at_least(line, 5, 120 s)` | line |
| T7 | Someone approaches | `person` · `moving_toward(zone)` | zone |
| T8 | Pet in an area | `dog`, `cat` · `in_zone(zone)` | zone |

**Not offered, and shown as such:**
- "Bag left behind": needs a cross-entity condition the DSL lacks.
- Colours, actions such as climbing or stealing, falls, faces or identity, fire and smoke (removed), and sounds.

The Rules screen lists these under **Outside what SafeSpace can watch for**, so users are not left guessing.

**5.5.5 Drawing zones on the phone (`ZoneEditor`)**
- Drawn over the camera's live `frame.jpg`.
- Interactions: tap to add a vertex, drag handles, long-press to delete a vertex, pinch to zoom.
- Line tool: two points and a direction arrow.
- Each zone or line is named in a sheet.
- Saves through the existing `PUT /cameras/{id}/geometry`; the contract already validates bounds.
- The dashboard reuses `GeometryEditor.tsx`, upgraded to the same interactions.

**5.5.6 Test on recordings (dry run)**
- `POST /rulesets/{id}/dry-run {camera_id, start, end ≤ 2 h}` creates a background job.
- The job replays the recording segments through `CameraDetector` + `RuleEngine` at 5 fps (based on `services/rules/replay.py`) at low
  GPU priority. It pauses when live load is high and can be cancelled. Concurrency is 1.
- The result lists the fires, each with a thumbnail and timestamp, plus frames evaluated and time taken.
- The UI says "Would have alerted 3 times in the last hour". Each thumbnail opens the recording at that moment, so a user can tune a
  noisy rule before arming it.

**5.5.7 Arming**
- `POST /rulesets/{id}/arm {expected_version, confirmed_readback_hash, acknowledge_experimental}` activates the child specs.
- `POST /rulesets/{id}/disarm` disables them.
- `POST /modes/{mode}/activate` arms and disarms groups.
- Every transition is broadcast as `ruleset.updated` and audit-logged.

**5.5.8 Runtime**
- Workers already load active specs from `/internal/rules`; the schedule gate is added.
- On `Fire`, the `RuleEvent` carries `ruleset_id`. The API builds `EventOut` with category `RULE_ALERT`, the ruleset name as the label,
  and **the ruleset's severity** (today hardcoded `MEDIUM`).
- Notification routing follows `notify` and each device's preferences.
- The cooldown is per ruleset and camera, on top of the per-rule cooldown.

**5.5.9 Gemma's role, explicitly (D-035)**
- Gemma compiles text into the closed DSL, never into code.
- Gemma writes the optional "AI view" summary after an alert. The summary is advisory and is shown as such.
- Gemma can draft a ruleset from a chat request, for the user to review.
- Gemma never fires, suppresses or dismisses anything.

"Semantic conditions" (asking Gemma yes/no about a crop, e.g. "holding a ladder") are **research, out of scope**. They could only
graduate with measured precision on labelled clips, a cap of 1 query per 3 s per camera, and an EXPERIMENTAL label.

**5.5.10 Ruleset states shown to the user**

| State | When |
|---|---|
| Draft | Created but not armed |
| Needs setup | A selected camera is missing a zone or line the ruleset uses |
| Ready to arm | Every camera is supported and the readback is current |
| Armed · watching 2 cameras | Active, inside its schedule |
| Armed · starts at 22:00 | Active, outside its schedule |
| Disarmed | Turned off |
| Attention | A camera is offline, or its detector is unavailable |

**5.5.11 Ruleset insight**
- Fires in the last 24 h and 7 d, shown as a sparkline.
- Confirmed versus false-alarm ratio, from operator feedback.
- A noisy-rule hint, e.g. "6 false alarms today: try a longer dwell or a smaller zone", which opens the builder at that step.

### 5.6 Alerts and background reliability

- **Admin phone foreground service** (`flutter_foreground_task`, type `specialUse`):
  - Holds the event socket and runs change-feed catch-up. The ongoing notification reads "SafeSpace is watching · 3 cameras live".
  - Do **not** use `dataSync`: Android 15 limits that type to 6 h per day.
- **Battery-optimisation exemption.**
  - The onboarding "Keep alerts reliable" checklist asks for `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` (allowed for a sideloaded APK).
  - It links to OEM auto-start settings and shows a live checkmark for each item.
- **Notification channels**

  | Channel | Used for |
  |---|---|
  | `critical` | Max importance, alarm sound; full-screen intent for CRITICAL (the user may need to grant it on Android 14+) |
  | `high` | Heads-up with sound |
  | `medium` | Default |
  | `low` | Silent, in-app only |
  | `status` | The ongoing foreground-service notification |
  | `camera` | The camera station's ongoing notification |
- **Rich alerts.**
  - Big-picture keyframe with the box, fetched with the bearer token; if that takes > 300 ms, post the text first and update.
  - Actions: **View live**, **Confirm**, **False alarm**. Confirm and False alarm call `/events/{id}/verification` with a
    `client_action_id`, so they are idempotent.
  - Tapping opens the incident.
  - One notification id per event. Summary and clip updates use `onlyAlertOnce`.
- **Offline catch-up.** On reconnect, events older than 10 minutes collapse into one digest ("12 alerts while offline"). Newer events
  notify individually.
- **Per-device preferences** stored on the server (`devices.prefs`), so the dashboard can show who will be told:
  - `notify_enabled`, `min_severity` (fields already in `DeviceOut`)
  - Quiet hours (CRITICAL still alerts)
  - Per-ruleset mute
- **Camera phone.** Foreground service of type `camera`, the screen kept on, and a **Stealth** mode:
  - A black overlay at minimum brightness; a double tap wakes it.
  - In v1 the activity stays in the foreground. Fully screen-off capture needs a native CameraX service and is part of Phase 7.
  - Notifications are suppressed on camera-role devices.
- **Latency budget for R8 (targets)**

  | Stage | Budget |
  |---|---|
  | Frame age at worker | ≤ 300 ms |
  | `min_hold_s` (default) | 1.5 s |
  | Engine + outbox + API persist + broadcast | ≤ 200 ms |
  | Socket → posted notification | ≤ 300 ms |
  | **Total p95** | **≤ 3.0 s** |

- **Android manifest additions:** Appendix C.

### 5.7 Assistant (Gemma 4 on the laptop)

**5.7.1 LLM gateway (`services/api/app/llm_gateway.py`, D-036)**
- One worker coroutine with an `asyncio.PriorityQueue`:

  | Priority | Requests | Output cap |
  |---|---|---|
  | P0 | Alert summaries | `num_predict` ≤ 200 |
  | P1 | Interactive: chat, rule compile, retrieval plan | ≤ 768 |
  | P2 | Background: dry-run notes, moments | ≤ 120 |
- Every request uses `ollama_runtime()`. Mismatched `num_ctx`/`num_gpu` makes Ollama reload the model; measured as 10–16 s on the
  first answer.
- The reasoner process calls a new `POST /api/v1/internal/llm/describe` instead of Ollama directly. The rule compiler's `LocalLLM`
  routes through the gateway.
- Queue wait is reported in the chat stream as a `status` message, e.g. "Finishing an alert summary first (≈3 s)".

**5.7.2 Retrieval planning**
1. A first Gemma call with a JSON schema (the same reliable pattern as the rule compiler) returns
   `RetrievalPlan {intent, camera_ids, time:{after,before}, categories, want_footage, want_counts}`.
2. Relative times ("yesterday evening", "in the last hour") are resolved **server-side** in the configured time zone, not by the
   model.
3. Validated by Pydantic. On failure, fall back to today's keyword relevance plus regex time parsing.

**5.7.3 Retrievers (all read-only)**

| Retriever | Returns |
|---|---|
| Incidents | Today's dossiers: metadata, detections, keyframe, clip frames |
| Recordings | Up to 4 frames sampled across the requested window from the segments, plus **coverage gaps** ("no recording 02:10–02:40, camera offline") |
| Screenshots | By camera and time |
| Live | The latest hub frame for up to 2 cameras ("what's happening at the front door right now?") |
| Rules | Armed rulesets and their recent fires |
| System | Camera, recording, detector and Gemma health |

Budget: ≤ 6 images and about 3,000 text tokens inside `num_ctx 6144`.

**5.7.4 Stream protocol additions**
- `plan` with the resolved scope, shown as chips.
- `evidence` with thumbnails for what was retrieved, shown while Gemma writes.
- `done.cited` gains `recording` (url + start offset), `snapshot` and `live` items.

**5.7.5 Phone parity with the dashboard**
- Scope chips for camera and time.
- "Ask about this" from an incident, screenshot, recording moment or live view.
- Provider toggle: Local Gemma by default. Groq only if configured, labelled "leaves your network".
- Conversation history list (new `GET /chat/conversations`), regenerate, copy.
- **Draft as ruleset** opens the builder pre-filled.

**5.7.6 Guardrails**
- No tool mutates state.
- Retrieved text is data, never instructions (the existing system prompt).
- Never identify people or infer intent.
- Cite incident ids and timestamps. An automated check rejects any cited id that was not retrieved.
- Say plainly when evidence is missing.

### 5.8 Optional: Moments (camera memory)

When a new person or vehicle track appears, a P2 job captions the keyframe. Limits:
- At most 1 per 20 s per camera, and skipped under load.
- Text and thumbnail go into a `moments` table with SQLite FTS5.

This gives a searchable day timeline ("when did a delivery van come?") and an assistant retriever. Before release it is gated by a
spot-check of 50 captions and labelled EXPERIMENTAL. Stretch goal, after the MVP line.

### 5.9 Remote camera control

From an admin client, sent to the camera phone over its publish socket:
- Switch lens, torch
- Quality profile
- Full-resolution still
- **Locate** (plays a sound)
- Stop streaming (with confirmation)

Every command is audit-logged and its result shown. The camera phone displays who issued it.

### 5.10 Mobile app UX

**Principle: media first.** Every card's header is real media:
- Camera card: live thumbnail
- Alert card: keyframe with its box
- Ruleset card: the camera frame with its zone drawn
- Template card: **your** camera frame with the template's zone
- Recording: segment thumbnail
- Screenshot: the image
- Camera device: its last frame
- Chat: cited clips and frames

When no media exists yet, the card shows the DESIGN.md empty state (icon, title, one sentence, action). **Never stock or mock
imagery** (DESIGN.md §0.1 rule 8).

**First run**
1. Splash: one sentence, "Connecting to your laptop…" (no progress counters, per DESIGN.md).
2. **Choose this phone's role.** Two full-width media cards, plus a footer: "You can change this anytime in Settings."
   - **Control center:** a mosaic of up to 4 real camera thumbnails, or the laptop's status if none are live.
   - **Camera:** after camera permission, this phone's own live preview inside the card.
3. Control center → sign-in with the account tiles. Camera → name the camera and start.

**Control center: floating nav pill, 5 destinations**

| Tab | Content |
|---|---|
| **Live** | Hero: the most recently active camera, playing live with the overlay. Below: a 2-column grid of camera tiles with 2-s thumbnails, a LIVE capsule (filled white dot + word), name and status line ("Recording · 10 fps · 2 rulesets armed"). Tap opens Camera detail. |
| **Alerts** | Grouped by day. Card: keyframe with box, title, camera, time, severity (icon + word), status, "AI view" line. Filters: severity, camera, ruleset, status. |
| **Rules** | Modes row, then armed rulesets (cards with zone overlay, armed switch, last-trigger thumbnail, sparkline), then "Start from a template" carousel previewed on your cameras, then "Describe a rule" composer, then "Outside what SafeSpace can watch for". |
| **Assistant** | Chat with evidence strip, inline clips, frames and screenshots, scope chips, suggestions ("What happened at the front door today?", "Show me the last alert", "Is anyone in the driveway right now?"). |
| **Settings** | Account; This device (role switch, notifications, reliability checklist); Devices (fleet); Storage (laptop disk, retention); System health; Activity (audit); Connection diagnostics; About. |

**Pushed pages**
- **Camera detail:**
  - Full-bleed live player with overlay toggle.
  - Floating control bar: screenshot, overlay, fullscreen, more (lens, torch, quality, locate).
  - Sections: **Timeline** (today's segments with incident markers and sprite scrubbing), **Screenshots**, **Rules on this camera**,
    **Device** (battery, temperature, network of the camera phone).
- **Alert detail:**
  - Clip that starts 2 s before the detection, plus the keyframe.
  - Detector facts and the AI view.
  - Actions: **Confirm**, **False alarm**, **Reopen**, **Ask about this**, **Open recording here**.
- **Ruleset builder:** 5 steps (What · Where · When · Then · Review), shown with a step capsule. Review contains the dry-run results
  and **Arm**.
- **Zone editor** and **Recording player** (timeline scrubber, export).

**Camera station**
- Full-bleed preview.
- Top glass capsule: "LIVE · Recording on laptop · 2 watching".
- Bottom floating bar: screenshot, lens, torch, Stealth, stop.
- Telemetry chips: battery, temperature, network quality.
- Exit requires sign-in (§5.2.5).
- Designed states: permission denied (explanation + open settings), laptop unreachable (diagnostics link), reconnecting
  (one sentence, auto-retry), thermal warning ("Phone is hot: lowering quality").

**Every screen designs all states:** loading skeleton in the real layout, empty, typed error with an action, permission, offline.
**Accessibility:** TalkBack labels, 48-dp targets, 200 % text scale, reduced-motion substitutions (DESIGN.md §6.20).

### 5.11 Dashboard UX

- **Shell** per DESIGN.md §13 (derived web chrome). `App.tsx` is split into routes with `react-router-dom` (already a dependency) and
  domain hooks with `react-query`.
- **Screens**

  | Screen | Content |
  |---|---|
  | Home | Live wall of the 4 most active cameras, alert feed, armed rulesets, health strip |
  | Live | Wall in 1, 4 or 9 layouts; focus view with overlay. Shortcuts: `1–9` focus a camera, `S` screenshot, `O` overlay, `F` fullscreen |
  | Recordings | Camera × day timeline with incident markers, scrub previews, export |
  | Alerts | The existing incidents screen, upgraded to media-first cards |
  | Rulesets | List, builder (shared validation with the phone), zone editor, dry run |
  | Assistant | The Investigation screen moved to the new stream protocol |
  | Devices | Fleet: role, scope, last seen, battery, temperature, stream fps, viewers; rename, revoke, remote commands; **Add a phone** QR |
  | Analyze | The existing upload flow |
  | System | Detector, Gemma, recorder, GPU/VRAM, storage and retention, benchmarks, audit log, log tail |
- **Shared components:**
  - `LivePlayer`: viewer socket, canvas, overlay, reconnect with backoff, stats.
  - `TimelineScrubber`, `RulesetCard`, `TemplateCard`, `ZoneEditor`, `EvidenceStrip`.

### 5.12 Design-system compliance

- **Fix existing violations:**
  - The `Colors.greenAccent` LIVE dot becomes a filled white dot + "LIVE"; OFFLINE is a hollow dot + "Offline".
  - Replace Material `Icons.*` in `app.dart`, `page_header.dart`, `camera_station_screen.dart`, `live_cameras_screen.dart`,
    `chat_screen.dart` and `incidents_screen.dart` with Stratis SVGs through the shared icon widget.
- **Icons to add** from `ICONS/` (Stratis), for both surfaces:
  - Media: video, video-off, camera, image
  - Camera controls: flash, flip-camera
  - Navigation: shield, rule/list-check, chat, settings, bell, bell-off
  - Device: battery, wifi, phone, laptop
  - Time: clock, calendar
  - Playback: play, pause, scissors (export), download, share, trash
  - Visibility and security: eye, eye-off, lock
  - Drawing: polygon, line, target
  - Other: sparkle-free "AI view" glyph (to be chosen), grid layouts
- **Severity without colour:** an icon plus an uppercase word, with CRITICAL using the filled-shield variant. DESIGN.md forbids accent
  hues. Q7 asks whether to propose a single severity token as `[PROPOSED]`.
- **New components flagged `[PROPOSED]` for DESIGN.md approval, specified with existing tokens only:**
  - Live: `LiveTile`, `LivePlayer` + `DetectionOverlay`
  - Recordings: `TimelineScrubber`
  - Rulesets: `ZoneEditor`, `RulesetCard`, `TemplateCard`, `StepCapsule`
  - Shared: `TelemetryChip`, `EvidenceStrip`, `RoleCard`, `StealthOverlay`
- Finish every screen with the DESIGN.md §15.1 checklist (AT-14).

### 5.13 Contracts and API surface

**New or changed models** go in `td_contracts` (new modules `devices.py`, `media.py`, `rulesets.py`, `assistant.py`). TypeScript and
Dart are then regenerated with `scripts/export-contracts.py` (D-010/D-015). Untyped `Map` handling in Dart is removed.

| Module | Models |
|---|---|
| auth | `LoginRequest` + `installation_id, platform, model, app_version`; `LoginResponse` + `scope, expires_at`; `EnrollRequest/Response`; `ServerIdentity` |
| devices | `DeviceOut` + `role, scope, last_seen_at, app_version, telemetry, prefs`; `DeviceRoleUpdate`; `DevicePrefs`; `DeviceCommand` |
| media | `MediaTicketRequest/Response`; `StreamDescriptor {transports:[{kind, url}], width, height, fps}`; `PublishHello`; `ViewerStatus`; `Observation` (wire form); `SnapshotOut`; `RecordingSegmentOut`; `TimelineOut`; `ExportRequest/Out` |
| cameras | `CameraOut` + `publisher_device_id, live:{fps, viewers, last_frame_age_s}, recording, analysis_fps, threat_fps` |
| rulesets | `RulesetSpec`, `RulesetOut`, `RulesetArmRequest`, `Schedule`, `RuleTemplate`, `DryRunRequest/Result`, `Mode` |
| rules | `RuleSpec` + `ruleset_id`, `schedule` (optional) |
| events | `EventOut` + `ruleset_id`, `ai_summary {text, model, status}` |
| chat | `ChatRequest` + `scope {camera_ids, after, before, include}`, `attachments`; stream items `plan`, `evidence`; `ConversationSummary` |
| ws | Envelope types `camera.status`, `device.status`, `ruleset.updated`, `snapshot.created`, `recording.updated` |

**Endpoints:** the catalogue is in Appendix D. The binary frame and socket message catalogue is in Appendix E.

### 5.14 Data and storage

- **SQLite (WAL) stays** as the store. Fix the stale PostgreSQL references in `.env.example` and `docker-compose.yml`, and mark D-006 as
  superseded.
- **Migrations.**
  - A `schema_version` table and ordered, idempotent steps (guarded `ALTER TABLE … ADD COLUMN`).
  - `storage/safespace.db` is copied to `storage/backups/` before each migration.
- **New tables** (DDL in Appendix F): `devices`, `recording_segments`, `snapshots`, `rulesets`, `audit_log`, `exports`, and optionally
  `moments` (+ FTS5).
- **Changed tables:** `users` gains `disabled` and `display_name`; `sessions` gains `device_id` and `scope`; `rules` gains `ruleset_id`.
- **Storage layout:** Appendix G.

### 5.15 Operations

- `scripts/start.ps1`: run the network check, start the recorder supervisor, start MediaMTX (v2), print the candidate URLs and the APK
  QR code. `scripts/stop.ps1` also stops ffmpeg children.
- `scripts/build-apk.ps1`:
  1. Reads `.env` and detects LAN IPv4 addresses.
  2. Writes the git-ignored `apps/mobile/.dart_defines.json`.
  3. Runs `flutter build apk --release --dart-define-from-file=.dart_defines.json`.
  4. Copies the APK to `storage/dist/`.
- **Observability:**
  - Structured JSON log lines with request ids and a per-camera prefix.
  - `/api/v1/system` extended with per-camera ingest fps, viewers, recorder state, analysis and threat fps, GPU memory, Gemma queue
    depth and wait, disk usage and projection.
  - Shown on the System screens of both surfaces.
- `scripts/verify_ecosystem.py` extended for live, recording, ruleset and assistant checks (§7.4).

### 5.16 Security and privacy

- **LAN only.** Port 8000 must never be forwarded. Credentials and the enrollment code in the APK are a deliberate demo trade-off
  (§5.2.1).
- **Internal endpoints** (`/api/v1/internal/*`) currently check only the service token. Add the **loopback check** that D-011 requires.
- **Tickets** for every WebSocket, including publish and view (D-014). Media tickets are scoped to camera and action.
- **Media endpoints** validate ids against hex/uuid patterns, with no path joins from user input. Upload size caps apply; login and
  enrollment are throttled (the existing `throttle()`).
- **Privacy:**
  - The camera phone shows "N watching".
  - Live views are audit-logged.
  - No face recognition. Recordings stay on the laptop. The Groq provider is labelled as leaving the network.
- **Optional hardening (after MVP).** HTTPS with a self-signed certificate created by `setup.ps1`, its SHA-256 pinned in the APK
  through a dart-define, and checked in Dio's certificate callback. This removes cleartext from the LAN.

---

## 6. Delivery plan

Effort is in engineer-days. Priorities: **P0** = needed for the demo (above the MVP line), **P1** = expected, **P2** = stretch.
Another agent session edits `main.py`, `pipeline.py` and contracts concurrently. Phase 1 therefore starts by splitting `main.py` into
routers, a pure move with tests green, and every later phase owns distinct files (Appendix H).

### Phase 0: Foundations and spikes (2–3 d)
| Task | P |
|---|---|
| Commit or stash the in-flight phone-camera work currently uncommitted in the tree (it is the base of Phase 2) | P0 |
| `network-setup.ps1`, `doctor.ps1`; set Private profile; remove Block rules; open 8000/tcp, 47800/udp | P0 |
| **Gate:** both phones reach `/api/v1/health/live` **over Wi-Fi** in hotspot mode (A) and, if available, router mode (B) | P0 |
| S1 capture spike on the A069: image-stream formats, native JPEG encode ms, sustained fps, CPU, temperature, battery drain per hour at 960×540@10 | P0 |
| S2 hub spike: fake publisher (`scripts/fake_camera.py`, streams a `TestVideos` clip over WS) + 3 viewers; measure fan-out CPU and latency | P0 |
| S3 GPU budget: fill the §5.4 table with `nvidia-smi` at N = 1…4 workers + detector + Gemma loaded | P0 |
| S4 WebRTC spike (MediaMTX WHIP from `flutter_webrtc` on the A069, WHEP in Chrome); go or no-go for Phase 7 | P1 |
| S5 retrieval-plan reliability: 30 questions → valid `RetrievalPlan` rate and latency | P1 |
| Check whether `imageio-ffmpeg` includes `h264_nvenc`, and whether Starlette `FileResponse` supports Range | P0 |

**Exit:** Wi-Fi reachability proven; spike numbers recorded in `tests/phase0_spikes.md`; D-030 to D-039 written into the decision log.

### Phase 1: Identity, accounts, roles, zero-config (3–4 d)
| Task | P |
|---|---|
| Split `main.py` into `routes/{auth,devices,cameras,media,recordings,events,chat,system}.py` (pure move) | P0 |
| Schema migrations framework + DB backup | P0 |
| `SEED_ACCOUNTS` upsert; disable other users; display names | P0 |
| `devices` table, `installation_id`, stable `device_id` and camera id; scopes + TTLs; `require_scope` | P0 |
| `POST /devices/enroll`; `GET /health/identity`; discovery responder | P0 |
| Dart: `BuildConfig` (dart-defines), `ConnectionResolver`, discovery, diagnostics page | P0 |
| Role screen + role switch rules; account tiles; dashboard login tiles | P0 |
| `build-apk.ps1`; APK download QR | P1 |
| Audit log | P1 |

**Exit:** fresh install on two phones → connected with no typing; Camera → Control center needs a password; a camera token gets 403
on `/events`; re-login keeps the same camera id; AT-11, AT-12, AT-13 pass.

### Phase 2: Live media v1, recording, screenshots (6–7 d)
| Task | P |
|---|---|
| Media tickets; publish socket; hub; viewer socket; `frame.jpg?w=`; MJPEG fallback | P0 |
| Kotlin `JpegEncoder`; publish client with flow control + ladder; telemetry | P0 |
| Recorder (fMP4 segments, NVENC/x264), indexer, gaps; webcam/RTSP cameras publish into the hub | P0 |
| Remove YOLO and engine from `mobile_camera.py`; `HubSource` in workers; observation overlay path | P0 |
| Snapshots (`stream` and `full`), gallery, `snapshot.created` | P0 |
| Timeline API, Range playback, sprites, exports | P1 |
| Retention sweeper + `config/media.yaml` | P0 |
| ThreatScheduler + per-camera analysis fps reporting | P1 |
| `StreamDescriptor` on `CameraOut` | P0 |

**Exit:** AT-01 through AT-05 pass on real Wi-Fi with one camera phone, one admin phone and the dashboard.

### Phase 3: Rulesets (6–7 d)
| Task | P |
|---|---|
| Contracts + `rulesets` table; compile to per-camera specs; schedule gate in the engine; readback over the whole set | P0 |
| Templates T1–T8 (`config/rule_templates.yaml`), builder, NL path via the gateway | P0 |
| Arm/disarm, `ruleset.updated`, ruleset severity on events, notify routing | P0 |
| Mobile `ZoneEditor`; dashboard `GeometryEditor` upgrade | P0 |
| Dry run on recordings | P1 |
| Modes (Home/Away/Night); insight (sparkline, noisy-rule hint) | P2 |

**Exit:** AT-06 and AT-07 pass; golden rule tests (`tests/golden_rules.json`) still pass; new golden cases for templates and schedules
pass.

### Phase 4: Alerts and background reliability (3–4 d)
| Task | P |
|---|---|
| Admin foreground service (`specialUse`) holding the event socket; reliability checklist | P0 |
| Channels by severity; big-picture keyframe; actions; in-place updates; offline digest | P0 |
| Device preferences on the server; dashboard "who will be notified" | P1 |
| Camera foreground service (`camera`), keep-awake, Stealth | P0 |
| Remote camera commands | P2 |
| *(4b, only if S3 shows over-budget)* `vision_hub.py` consolidation | P0 if triggered |

**Exit:** AT-08 passes with the phone screen off and the app backgrounded for 10 minutes.

### Phase 5: Assistant over the server (4–5 d)
| Task | P |
|---|---|
| LLM gateway; reasoner and compiler routed through it; internal describe endpoint | P0 |
| Retrieval plan + deterministic fallback; recordings, screenshots, live, rules and system retrievers | P0 |
| Stream `plan` and `evidence` messages; cited recordings, screenshots and live items | P0 |
| Phone chat parity (scope chips, "Ask about this", history, Draft as ruleset) | P0 |
| Cited-id validator | P1 |
| Moments | P2 |

**Exit:** AT-09 and AT-10 pass. Chat first-token benchmark rerun with varied prompts (a repeated prompt hits the prefix cache and
flatters the number).

### Phase 6: UI/UX build-out (7–9 d, overlapping Phases 2–5 as each feature lands)
| Task | P |
|---|---|
| Icon import and Material-icon removal; LIVE-dot fix; `[PROPOSED]` components specified in DESIGN.md | P0 |
| Mobile: role screen, Live, Camera detail, Alerts, Rules + builder, Assistant, Settings, Camera station | P0 |
| Dashboard: routing split, Home, Live wall, Recordings, Rulesets, Devices, System upgrades | P0 |
| All states, accessibility, reduced motion, haptics | P0 |

**Exit:** AT-14 passes; screenshots of every screen and state archived in `docs/ux/`.

### Phase 7: Live v2, WebRTC and background camera (5–7 d, only if S4 says go)
MediaMTX bundling and auth hook; WHIP publish; WHEP viewers on both surfaces; RTSP worker source; MediaMTX recording + our indexer;
native CameraX service for screen-off capture; `StreamDescriptor` fallback.
**Exit:** the §5.3.10 criteria hold and the AT-02/AT-03 latency targets improve with no regression in AT-05.

### Phase 8: Hardening and full verification (5 d). See §7.

**MVP line (demo):** every P0 above, in Phases 0–6, plus all AT scenarios in §7.5.
**Critical path:** 0 → 1 → 2 → {3, 4, 5 in parallel, by file ownership} → 6 → 8.
**Estimate:** about 37–48 engineer-days in total; about 3 weeks with three parallel sessions after Phase 2.

---

## 7. Testing and verification (done last, before release)

### 7.1 Strategy

Unit and contract tests guard logic. Integration tests drive the real API with a scripted camera. Device tests on two physical phones
plus the dashboard prove the requirements. Every requirement has a measurable acceptance test (§7.5) and the results are written to
`tests/phase8_acceptance.md`, including failures. Accuracy is reported only on real footage the system never saw.

### 7.2 Unit tests

| Area | Cases |
|---|---|
| Hub | Latest-only mailbox never backlogs; a slow viewer doesn't slow ingest; stats; subscriber cleanup |
| Publish protocol | Header parsing, bad JPEG, oversize, rate cap, flow-control window, ladder step-down and step-up |
| Recorder | Segment roll-over, gap on 5 s silence, crash-truncated fMP4 still plays, indexer durations |
| Retention | Age rule, disk floor, never deletes evidence or exports in progress |
| Identity | Stable device and camera id across logins; scopes; sliding TTL; disabled users; enrollment throttle; HMAC identity |
| Rulesets | Template → spec, builder → spec, NL → spec (mocked gateway); per-camera NEEDS_SETUP; hash covers schedule, severity, notify; schedule crossing midnight; day-of-week; version bump on geometry change |
| Gateway | Priority order, `ollama_runtime()` on every call, `num_predict` caps |
| Assistant | Retrieval-plan validation and fallback; time-phrase resolution in Asia/Kolkata; image and token budgets; cited-id validator |
| Dart | `ConnectionResolver` races and server-id/HMAC rejection; publish client window and ladder; notification dedupe and digest; role-switch guard |
| Dashboard | Viewer-socket frame parser; `LivePlayer` reconnect and backoff |

### 7.3 Contract and security tests
- Regenerate TS and Dart from `td_contracts`. The test fails if the generated files differ from those committed.
- Every file in `contracts/examples` validates.
- **Scope matrix:** for every route, a camera token gets 403 except on its allow-list. Without a token every route returns 401, except
  `/health/live` and `/health/identity`.
- Tickets are single-use and expire after 30 s. Media tickets are bound to camera and action.
- Path traversal attempts on every media endpoint return 404. Internal endpoints reject non-loopback callers.
- From a second LAN machine, `nmap` shows only 8000/tcp and 47800/udp open (plus 8889 and 8189 in v2).

### 7.4 Integration tests (pytest + `scripts/fake_camera.py`)
1. **Live pipeline.** A fake camera streams a clip for 2 minutes. Assert:
   - segments are indexed;
   - the snapshot endpoint returns a frame;
   - viewer sockets receive frames and observations;
   - `camera.status` is broadcast.
2. **Rule pipeline.** Arm a template ruleset and stream a clip with a person entering the zone. Assert:
   - exactly one `RULE_ALERT` with the ruleset's severity;
   - the clip is cut from the recording;
   - a retry with the same `event_id` creates no duplicate.
3. **Assistant.** Golden questions over a seeded store (incidents + recordings + screenshots). Assert:
   - the plan is valid;
   - the evidence is from the requested camera and time;
   - no fabricated ids.
4. `scripts/verify_ecosystem.py` extended. Runs against an isolated API (`SAFESPACE_STORAGE=storage/validation`, port 8002, as today).

### 7.5 Acceptance scenarios (two phones over real Wi-Fi + dashboard)

Phone A = camera station (A069). Phone B = admin2 control center. Dashboard = admin1.

| ID | Scenario | Pass criteria |
|---|---|---|
| AT-01 | Fresh install on A, choose Camera, name it "Front door" | Live tile on the dashboard ≤ 30 s from app open; ingest ≥ 9 fps sustained for 10 min at the top ladder step on 5 GHz |
| AT-02 | Dashboard live view of A | Glass-to-glass p95 ≤ 600 ms (stopwatch method: A films a millisecond clock on the laptop screen beside the dashboard view; 30 photos) |
| AT-03 | B views A live with overlay while the dashboard also watches | B p95 ≤ 700 ms; A's ingest fps unchanged with 3 viewers |
| AT-04 | Screenshot from A, B and the dashboard | File in `storage/snapshots/<cam>/`; visible in every gallery ≤ 2 s; `full` returns the sensor-resolution still ≤ 3 s |
| AT-05 | Record 60 min; kill the API mid-segment; run the sweeper with a test floor | 12 segments, gaps ≤ 5 s total outside the kill; the killed segment plays and seeks; the sweeper deletes oldest first and keeps evidence |
| AT-06 | On B: "Alert me if someone lingers at the front door for more than 20 seconds at night" | Correct readback; NEEDS_SETUP until the zone is drawn on B; dry run lists thumbnails; arms |
| AT-07 | One ruleset on two cameras with a 22:00–06:00 schedule | No fire outside the window; fires inside it on each camera independently; both clients show the state |
| AT-08 | Walk into the zone 20 times with B's screen off and the app backgrounded for ≥ 10 min | 20/20 notifications on B (and on admin1's phone if present); timing measured from episode start to the post time in `adb shell dumpsys notification`, as in phase 6: p50 ≤ 2.2 s, p95 ≤ 3.0 s; keyframe in the notification; AI summary update p95 ≤ 15 s; no duplicates |
| AT-09 | 20 scripted questions on B | First token p95 ≤ 2 s; streaming visible; the laptop's logs show every request; the phone makes no traffic to anything except the laptop |
| AT-10 | "What happened on Front door between 14:00 and 14:30?" plus 19 other storage questions | Human-graded rubric ≥ 16/20 grounded and correct; 0 fabricated incident ids; coverage gaps stated when present |
| AT-11 | Switch B to Camera and back | Control center → Camera is instant; Camera → Control center requires the password; while in camera mode, B's token gets 403 on `/events` |
| AT-12 | Zero-config on hotspot; then router mode with the laptop IP changed | No typing except role and name; after the IP change, B re-resolves through discovery in ≤ 15 s |
| AT-13 | Accounts | Only admin1 and admin2 sign in on both surfaces; `admin@gmail.com` is rejected as disabled; the 11th wrong password in a minute is throttled |
| AT-14 | UX audit | DESIGN.md §15.1 checklist passes on every new screen; every card shows real media or a reasoned empty state; TalkBack walkthrough of the main flows |
| AT-15 | Cross-client consistency | Arm on B → dashboard ≤ 1 s; confirm on the dashboard → B ≤ 1 s; screenshot on the dashboard → B's gallery ≤ 2 s |

### 7.6 Performance measurement

| Metric | Tool or method |
|---|---|
| Ingest and viewer fps | Hub stats via `/api/v1/system` |
| Live latency | Stopwatch photos, plus embedded `capture_ts` with clock-offset correction |
| Alert latency | `adb shell dumpsys notification` post times against event `episode_start` (phase-6 method) |
| GPU memory | `nvidia-smi --query-gpu=memory.used --format=csv -lms 500` |
| CPU and RAM | psutil sampling per process |
| Chat latency | `scripts/benchmark_chat.py`, with a different incident per request so the prefix cache cannot flatter it |
| Wi-Fi throughput (when diagnosing) | `iperf3` |

### 7.7 Resilience (fault injection)

| ID | Fault | Expected |
|---|---|---|
| C1 | A's Wi-Fi off for 30 s | Auto-resume ≤ 10 s after Wi-Fi returns; one recording gap; one "Camera signal lost" event, not a stream of them |
| C2 | Restart the API (lifespan sets phone cameras inactive) | Phones reconnect and re-publish ≤ 15 s; armed rulesets persist; B catches up missed events in order |
| C3 | Laptop IP changes (router mode) | Discovery re-resolves ≤ 15 s |
| C4 | Ollama stopped | Rules still fire; AI summary shows "unavailable"; chat returns a typed error with an action |
| C5 | Detector :8001 down | Rules still fire; threat analysis shows unavailable; health event raised once |
| C6 | GPU out-of-memory injected in a worker | Health event; recovery without a process restart storm |
| C7 | Disk below the floor | Sweeper frees space; recording continues; System shows a warning |
| C8 | A backgrounded or locked (v1) | Documented behaviour: Stealth keeps capture alive; leaving the app stops it cleanly and alerts admins |
| C9 | Token revoked from Devices | Device signed out ≤ 5 s; its sockets closed |
| C10 | 4 cameras, 2 viewers each, chat every 30 s, for 30 min | No stalls; ingest ≥ 8 fps each; VRAM ≤ 5.5 GB |

### 7.8 Soak test
8 hours: 3 cameras, 3 rulesets armed, a scripted walk-through every 15 minutes (32 triggers), and a chat question every 10 minutes.
**Pass:**
- 0 crashes; 32/32 alerts delivered.
- RSS growth < 10 % per process; VRAM flat.
- Recording gaps < 1 % with no injected faults.

### 7.9 Rule accuracy, honestly
- Record at least 30 real clips with the user's own phones that were **not** used to tune anything. Hand-label each zone entry, dwell
  and line crossing.
- Per template, report precision, recall and alert latency, plus **false alarms per hour on at least 2 h of empty-scene recordings**.
- Write the results to `docs/benchmarks.md`, with examples of the failures.
- Fixture replays (as in the phase-6 gate) measure plumbing, not accuracy, and are labelled that way.

### 7.10 Release checklist
1. Every P0 merged.
2. §7.2–7.4 green.
3. AT-01 through AT-15 recorded with numbers.
4. Soak passed.
5. Decision log updated.
6. `README.md` "Run it" rewritten for hotspot mode, `build-apk.ps1` and the two accounts.
7. APK in `storage/dist/`.
8. Demo runbook written: start order, network mode, fallback to `adb reverse`.

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Venue or home Wi-Fi isolates clients, or the firewall blocks the phone (already seen in phase 6) | High | Blocks everything | Phase 0 gate first; hotspot mode with a deterministic IP; firewall script; `adb reverse` fallback; diagnostics page |
| OEM battery management kills the admin phone's foreground service | Medium | Missed alerts | Reliability checklist, exemption request, digest on reconnect; AT-08 run with the screen off |
| Camera phone overheats or drains (continuous capture + encode) | Medium | Stream drops | Charger expected; thermal telemetry → automatic ladder step-down; Stealth dims the screen |
| GPU memory exhaustion with several cameras + Gemma | Medium | Detector OOM | Spike S3 budget; ThreatScheduler; Phase 4b consolidation; existing OOM health events |
| Gemma contention slows chat or summaries | Medium | UX latency | Gateway priorities + output caps; shared runtime options; queue wait shown to the user |
| JPEG bandwidth on 2.4 GHz | Medium | Low fps | Ladder; 5 GHz guidance; WebRTC v2 |
| Recording fills the disk | Medium | Recording stops | Retention + disk floor; projection on System |
| Credentials extracted from the APK | Low on a private LAN | Unauthorized access | LAN only, scopes, revocation, optional pinned TLS; documented trade-off |
| Flutter camera plugin lifecycle stops capture when the activity is not visible | High | No background capture in v1 | Stated v1 behaviour (Stealth keeps it foreground); native service in Phase 7 |
| A 2B-class model produces wrong retrieval plans or rules | Medium | Wrong answers or rules | Schema validation + deterministic fallback; readback confirmation; dry run; cited-id check |
| Concurrent edits by another session on `main.py`, `pipeline.py`, contracts | High | Merge conflicts | Router split first; file ownership map (Appendix H); small anchored patches |
| Range requests unsupported by the installed Starlette | Low | No seeking | Phase 0 check; small range handler |

## 9. Open questions

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | Demo network: laptop hotspot, a home router, or a venue network? | Hotspot (A), with `adb reverse` as the fallback |
| Q2 | Should camera phones enroll with the baked code (camera scope), or sign in as admin1/admin2? | Enrollment code with camera scope (least privilege) |
| Q3 | One-tap password autofill on first run (`DEMO_AUTOFILL_PASSWORD`)? | On for the demo build; never for leaving camera mode |
| Q4 | Disable or delete the existing `admin@gmail.com` account and its sessions? | Disable; keep its data |
| Q5 | Recording retention and disk budget (≈16 GB/day/camera at 1.5 Mbit/s)? | 7 days, 20 GB free floor |
| Q6 | Record audio? | No (privacy and legal; not in the brief) |
| Q7 | DESIGN.md forbids accent colours. Keep severity as icon + word, or propose one severity token? | Icon + word (comply) |
| Q8 | Pursue Live v2 (WebRTC) for the demo, or after? | Only if spike S4 passes before Phase 6 ends |
| Q9 | How many simultaneous cameras must the demo support? | 3 (budget verified up to 4) |

---

## 10. Appendices

### A. `.env` additions
```dotenv
SERVER_ID=ss-7f3c2a                       # random, generated by setup.ps1; baked into the APK
SERVER_NAME=Home laptop
SEED_ACCOUNTS=admin1@safespace.com:admin123:Admin 1,admin2@safespace.com:admin123:Admin 2
CAMERA_ENROLLMENT_CODE=<32 random chars>  # baked into the APK; rotate = rebuild the APK
PUBLIC_SERVER_URLS=http://192.168.137.1:8000,http://192.168.1.50:8000
DISCOVERY_PORT=47800
ADMIN_TOKEN_DAYS=30
CAMERA_TOKEN_DAYS=365
DEMO_AUTOFILL_PASSWORD=true
```

### B. Build-time client configuration (`apps/mobile/.dart_defines.json`, generated, git-ignored)
```json
{
  "SERVER_URLS": "http://192.168.137.1:8000,http://192.168.1.50:8000,http://127.0.0.1:8000",
  "SERVER_ID": "ss-7f3c2a",
  "CAMERA_ENROLLMENT_CODE": "<from .env>",
  "ACCOUNTS": "admin1@safespace.com|Admin 1,admin2@safespace.com|Admin 2",
  "DEMO_AUTOFILL_PASSWORD": "true",
  "DISCOVERY_PORT": "47800"
}
```
`lib/core/build_config.dart` reads these with `String.fromEnvironment`; the passwords live only in the build script's defines when
`DEMO_AUTOFILL_PASSWORD=true`.

### C. Android manifest additions
```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_CAMERA"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_SPECIAL_USE"/>
<uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS"/>
<uses-permission android:name="android.permission.USE_FULL_SCREEN_INTENT"/>
<uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE"/>   <!-- only if listening for broadcasts -->
<uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES"/>      <!-- only if the app updates itself from the laptop -->
<service android:name="…CameraForegroundService" android:foregroundServiceType="camera" android:exported="false"/>
<service android:name="…AlertForegroundService" android:foregroundServiceType="specialUse" android:exported="false">
  <property android:name="android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE" android:value="Local security alert connection to the owner's laptop"/>
</service>
```
`usesCleartextTraffic="true"` stays until the optional pinned TLS (§5.16).

### D. Endpoint catalogue (new or changed)
| Method | Path | Scope | Purpose | Phase |
|---|---|---|---|---|
| GET | `/api/v1/health/live` | none | Adds `server_id, server_name, version, features` | 1 |
| GET | `/api/v1/health/identity?nonce=` | none | HMAC proof of the shared secret | 1 |
| POST | `/api/v1/auth/login` | none | Adds `installation_id`; returns scope and expiry | 1 |
| POST | `/api/v1/devices/enroll` | none (code) | Camera-scoped token | 1 |
| GET/PATCH | `/api/v1/devices/me` | admin, camera | Role, name, preferences | 1 |
| GET | `/api/v1/devices` | admin | Fleet with telemetry | 1 |
| DELETE | `/api/v1/devices/{id}` | admin | Revoke | exists |
| POST | `/api/v1/devices/{id}/commands` | admin | Remote camera control | 4 |
| POST | `/api/v1/media/tickets` | admin, camera | Publish or view ticket | 2 |
| WS | `/api/v1/cameras/{id}/publish` | ticket (camera) | Ingest | 2 |
| WS | `/api/v1/cameras/{id}/view` | ticket (admin) | Live frames + observations | 2 |
| GET | `/api/v1/cameras/{id}/frame.jpg?w=` | admin | Thumbnail | 2 |
| GET | `/api/v1/cameras/{id}/live.mjpg` | admin | MJPEG fallback | 2 |
| GET | `/api/v1/cameras/{id}/stream` | admin | `StreamDescriptor` | 2 |
| POST | `/api/v1/cameras/{id}/snapshots` | admin, camera (own) | `quality: stream \| full` | 2 |
| POST | `/api/v1/cameras/{id}/stills` | camera (own) | Full-resolution still upload | 2 |
| GET | `/api/v1/snapshots?camera_id=&day=` | admin | Gallery | 2 |
| GET | `/api/v1/cameras/{id}/timeline?date=` | admin | Segments, events, gaps | 2 |
| GET | `/api/v1/recordings/{segment}.mp4` | admin | Range playback | 2 |
| POST/GET | `/api/v1/cameras/{id}/exports`, `/api/v1/exports/{id}.mp4` | admin | Clip export | 2 |
| GET/POST/PATCH | `/api/v1/rulesets`, `/api/v1/rulesets/{id}` | admin | CRUD + compile | 3 |
| POST | `/api/v1/rulesets/{id}/arm`, `/disarm` | admin | Arming with readback hash | 3 |
| POST/GET | `/api/v1/rulesets/{id}/dry-run`, `/api/v1/dry-runs/{job}` | admin | Test on recordings | 3 |
| GET | `/api/v1/rule-templates` | admin | Template catalogue | 3 |
| POST | `/api/v1/modes/{mode}/activate` | admin | Home/Away/Night | 3 |
| POST | `/api/v1/chat/stream` | admin | Adds scope, attachments, `plan` and `evidence` items | 5 |
| GET | `/api/v1/chat/conversations` | admin | History | 5 |
| GET | `/api/v1/audit` | admin | Activity | 1 |
| GET | `/download/{token}/SafeSpace.apk` | single-use token | APK install | 1 |
| POST | `/api/v1/internal/llm/describe` | internal + loopback | Gateway for the reasoner | 5 |
| WS | `/api/v1/internal/cameras/{id}/frames` | internal + loopback | Worker frame tap | 2 |
| POST | `/api/v1/internal/cameras/{id}/observation` | internal + loopback | Overlay feed | 2 |
| POST | `/api/v1/internal/media-auth` | internal + loopback | MediaMTX auth (v2) | 7 |

### E. Socket catalogue
- **Binary frame (publish and view):** `magic "SSF1" (4 B) · seq uint32 BE · capture_ts_ms uint64 BE · JPEG`.
- **Publish socket text messages:** `hello`, `ack`, `profile`, `command`, `viewers` (server → phone); `telemetry`, `command_result`
  (phone → server).
- **View socket text messages:** `observation`, `status`, `ended` (server → client); `set_fps` (client → server).
- **Event socket envelope types** (D-012/D-014 unchanged): existing `hello`, `ping`/`pong`, `event.created`, `event.updated`, plus new
  `camera.status`, `device.status`, `ruleset.updated`, `snapshot.created`, `recording.updated`.

### F. New tables (sketch)
```sql
CREATE TABLE devices(id TEXT PRIMARY KEY, installation_id TEXT UNIQUE NOT NULL, user_id TEXT, name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'UNASSIGNED', platform TEXT, model TEXT, app_version TEXT,
  prefs_json TEXT NOT NULL DEFAULT '{}', telemetry_json TEXT, created_at TEXT NOT NULL, last_seen_at TEXT);
CREATE TABLE recording_segments(id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, start_ts REAL NOT NULL, end_ts REAL,
  path TEXT NOT NULL, bytes INTEGER, status TEXT NOT NULL, sprite_path TEXT);
CREATE INDEX segments_camera_time ON recording_segments(camera_id, start_ts);
CREATE TABLE snapshots(id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, ts REAL NOT NULL, quality TEXT NOT NULL,
  width INTEGER, height INTEGER, created_by TEXT, path TEXT NOT NULL, deleted_at TEXT);
CREATE INDEX snapshots_camera_time ON snapshots(camera_id, ts);
CREATE TABLE rulesets(id TEXT PRIMARY KEY, body_json TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
  readback_hash TEXT, updated_at TEXT NOT NULL, updated_by TEXT);
CREATE TABLE audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, user_id TEXT, device_id TEXT,
  action TEXT NOT NULL, target TEXT, detail_json TEXT);
CREATE TABLE exports(id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, start_ts REAL, end_ts REAL, status TEXT, path TEXT, created_by TEXT);
CREATE TABLE schema_version(version INTEGER NOT NULL);
-- ALTERs: users(+disabled, +display_name); sessions(+device_id, +scope); rules(+ruleset_id)
```

### G. Storage layout
```
storage/
  safespace.db              backups/<timestamp>.db
  recordings/<camera>/<YYYYMMDD-HHMMSS>.mp4      (+ .sprite.jpg)
  snapshots/<camera>/<id>.jpg  (+ _thumb.jpg)    trash/
  previews/<camera>.jpg                          (kept for compatibility)
  media/<event_id>/{frame.jpg, clip.mp4, detections.json}
  exports/<id>.mp4          dist/SafeSpace-<version>.apk
  runtime/{ollama, mediamtx}                     logs/
```

### H. File ownership by phase (to avoid concurrent-edit conflicts)
| Phase | Owns |
|---|---|
| 1 | `services/api/app/routes/{auth,devices}.py`, `security.py`, `database.py` (migrations), `contracts/.../auth.py`, `devices.py`; mobile `core/connection/*`, `core/build_config.dart`, `features/onboarding/*`, `features/role/*`; `scripts/{network-setup,doctor,build-apk}.ps1` |
| 2 | `services/api/app/media/*`, `routes/{media,recordings,cameras}.py`, `mobile_camera.py` (slimmed), `services/rules/{sources,worker,manager}.py`, `contracts/.../media.py`, `config/media.yaml`; mobile `services/{publish_client,viewer_client}.dart`, `android/.../JpegEncoder.kt`, `features/camera_station/*`; dashboard `components/LivePlayer.tsx`, `api/viewer.ts` |
| 3 | `services/rules/{rulesets,schedule,templates,dryrun}.py`, `engine.py` (schedule gate), `compiler.py`, `routes/rulesets.py`, `rule_routes.py`, `contracts/.../{rulesets,rules}.py`, `config/rule_templates.yaml`; mobile `features/rulesets/*`; dashboard `routes/Rulesets*.tsx`, `GeometryEditor.tsx` |
| 4 | mobile `services/{foreground_service,notification_service}.dart`, `AndroidManifest.xml`; `routes/devices.py` (preferences, commands) |
| 5 | `services/api/app/{llm_gateway,chat}.py`, `services/api/app/assistant/*`, `services/reasoner/loop.py`, `services/rules/llm.py`, `contracts/.../{chat,assistant}.py`; mobile `features/assistant/*`; dashboard `routes/Assistant.tsx` |
| 6 | `DESIGN.md` (`[PROPOSED]` entries), `apps/mobile/assets/icons/*`, `apps/mobile/lib/core/widgets/*`, every `features/*/` screen layout, `apps/dashboard/src/{App.tsx,routes/*,components/*,styles/app.css}` |
