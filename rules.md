# SafeSpace — Codebase Rules & Engineering Standards

This document establishes the strict architectural rules, process boundaries, security requirements, and engineering guidelines for the **SafeSpace** on-premises CCTV Threat Detection System. All developers and AI agents must strictly adhere to these rules without exception.

---

## 1. Core Architecture & System Boundaries

SafeSpace is an **on-premises, local-first CCTV Video Threat Detection System** with local AI/VLM verification, a real-time web dashboard, and an Android-first Flutter mobile application.

### 1.1 Process Boundaries & Port Allocations
- **Single Monorepo**:
  - `contracts/`: Canonical Pydantic v2 schemas (`td_contracts`).
  - `services/api`: FastAPI REST + WebSocket application (Port `8000`).
  - `services/inference`: Worker daemon for video ingest, YOLO detection, temporal filter, and VLM escalation.
  - `apps/mobile`: Android-first Flutter application (same Wi-Fi / LAN).
  - `services/Dashboard` & `apps/dashboard`: Next.js / Vite web dashboard (Port `3000` / `5173`).
  - `storage/`: Local keyframes, incident media, and SQLite database.
  - `Model/`: Pre-trained notebooks, training runs, and fine-tuned weights (`best.pt`, SlowFast models).
- **Strict Boundary Rule**: `services/api` and `services/inference` **NEVER** import each other. Both import only `td_contracts`.
- **Zero Cloud Ingestion for Core Function**: Video ingestion, object detection, local VLM reasoning, and alert dispatch operate 100% locally on-premises without external cloud dependency. Cloud services (Supabase) are used strictly for optional multi-device backup and authenticated cloud synchronization.

---

## 2. Contracts & Code Generation

`td_contracts` is the **single source of truth** for all data models, API schemas, and WebSocket envelopes across backend, web, and mobile.

- **Pydantic v2 Single Source**: All schemas reside in `contracts/src/td_contracts/` with `extra="forbid"` on inbound payloads.
- **Automated Code Generation**:
  - TypeScript types: `scripts/export-contracts.py` generates `apps/dashboard/src/api/generated/schema.ts`.
  - Dart models: `scripts/export-contracts.py` generates `apps/mobile/lib/data/generated/models.dart`.
  - JSON Schemas: Exported to `contracts/generated/jsonschema/`.
  - OpenAPI 3.1: Exported to `contracts/generated/openapi.json`.
- **Never Hand-Edit Generated Code**: Any modification to data structures must be applied to `contracts/src/td_contracts/` and re-exported via `python scripts/export-contracts.py`.

---

## 3. Detection, Inference & VLM Verification

### 3.1 Inference Pipeline
1. **Video Ingest**: Support for local webcams, file uploads, and RTSP camera streams.
2. **YOLO Detection Engine**: Real-time object detection using fine-tuned weights (`storage/models/best.pt`, `Model/Notebooks/runs/detect/train4/weights/best.pt`) detecting weapons, violence, and intrusion at 5 FPS sampling, 640px, FP16.
3. **Temporal Filtering**: Sliding-window temporal aggregation to suppress noise and deduplicate detections before alert escalation.
4. **VLM Verification Escalation**: High-confidence candidates trigger local Vision-Language Models (e.g. Ollama MiniCPM / LLaVA) via `/api/v1/internal/vlm-verify` for contextual threat verification and natural language summary generation.
5. **Event Dispatch**: Worker ingests confirmed events via `POST /api/v1/internal/events`, which broadcasts real-time alerts over WebSocket and stores incident records.

---

## 4. Authentication, Networking & Security

- **Web Dashboard Authentication**:
  - Session managed via HttpOnly, SameSite=Strict, Secure cookies holding opaque session tokens.
- **Mobile Device Authentication**:
  - `Authorization: Bearer <device_token>`.
  - Devices are paired via 10-minute pairing codes generated from the dashboard (`POST /api/v1/auth/pair`).
- **WebSocket Ticket Architecture**:
  - WebSockets NEVER accept ambient cookies or raw credentials directly.
  - Clients must request a short-lived, single-use ticket (`POST /api/v1/ws-tickets`) and connect via `/api/v1/ws?ticket=<ticket>`.
- **Media & Keyframe Protection**:
  - Incident media and keyframes are served through authenticated REST endpoints (`/api/v1/events/{id}/media/{file}`).
  - Never generate or rely on unauthenticated signed public URLs for sensitive CCTV footage.
- **Zero Secrets in Codebase**:
  - Strictly use `.env` and `.env.local` for credentials.
  - Never commit API keys, service role JWTs, or private tokens to Git. `.env`, `.env.local`, and `.agents/` are strictly ignored.

---

## 5. Mobile App Engineering Standards (`apps/mobile`)

- **Platform Focus**: Android-first Flutter application designed for real-time security alerts.
- **Design Language**:
  - **Three Colors Only**: Pitch Black `#000000` background, Dark Grey `#1A1A1A` cards/bars, and White `#FFFFFF` text/icons.
  - **Severity Badging**: Red `#EF4444` (Critical), Orange `#F97316` (High), Yellow `#EAB308` (Medium), Blue `#3B82F6` (Low).
  - Floating pill navigation bar, high-contrast dark theme, no unnecessary bright accents.
- **Resilient Connectivity**:
  - Dynamic LAN base URL detection (Android emulator `10.0.2.2:8000`, local Wi-Fi `192.168.x.x:8000`).
  - WebSocket auto-reconnect with exponential backoff.
  - Native heads-up local notifications on `HIGH` and `CRITICAL` threat events.
- **Clean Architecture Structure**:
  - `lib/core/`: API client (Dio), Secure Storage, WebSocket service, AppConfig.
  - `lib/data/`: Auto-generated contract models and repositories (`EventsRepository`, `ChatRepository`).
  - `lib/features/`: UI screens and state (`incidents`, `chat`, `pairing`, `status`).
  - `lib/services/`: System notification service.

---

## 6. Testing, CI & Quality Assurance

- **Contract Tests**: Every contract model and golden JSON fixture must pass validation:
  ```bash
  pytest tests/contracts/
  ```
- **Mobile Tests & Linting**:
  ```bash
  cd apps/mobile
  flutter test
  dart analyze lib/ test/
  ```
- **Real Data Only**: No fake mock buttons or non-functional placeholders in shipped screens.
- **Git Hygiene**:
  - Review all diffs with `git status` and `git diff --stat` before committing.
  - Keep model weights tracked in `storage/models` and `Model/`, but never commit temporary runtime data, caches, or virtual environments (`.venv`, `node_modules`, `build/`, `.dart_tool`).
