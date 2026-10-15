# SafeSpace — CCTV Video Threat Detection System

SafeSpace is an intelligent, local-first surveillance and threat detection platform. It uses edge computer vision (YOLOv8 + ByteTrack) for continuous low-latency candidate threat detection and local Vision-Language Models (VLM via Ollama) for structured semantic verification.

## Architecture

```
  SOURCES                      PC (Native Python Worker + Ollama)
  Webcam ─┐
  File  ──┼─▶  Inference Worker (YOLOv8 + ByteTrack + Temporal Filter)
  RTSP* ──┘         │
                    ▼
               Disk Outbox ──▶ FastAPI (:8000) ──▶ PostgreSQL (:5432 Docker)
                    │               │
                    ▼               ├─▶ Web Dashboard (React + TS)
               Ollama VLM           └─▶ Mobile App (Flutter Android)
               (127.0.0.1:11434)
```

## Repository Structure

- `contracts/`: Canonical Pydantic contracts (`td_contracts`), JSON schemas, and golden examples.
- `services/api/`: FastAPI backend service (`:8000`) for ingestion, REST, WebSocket broadcast, and auth.
- `services/inference/`: Native Python worker for camera capture, YOLO detection, and VLM verification.
- `apps/dashboard/`: React + TypeScript + Vite web dashboard.
- `apps/mobile/`: Flutter Android-first mobile application.
- `config/`: Declarative configuration (`categories.yaml`, `class_map.yaml`, `worker.yaml`).
- `storage/`: Local media keyframes, clips, model weights (`best.pt`), and outbox.
- `scripts/`: Dev servers, export-contracts, migration, and test runners.

## Quick Start

### 1. Environment Setup
```powershell
cp .env.example .env
uv venv .venv
uv pip install -e ./contracts
```

### 2. Run Contract Tests
```powershell
.venv\Scripts\pytest tests/contracts -v
```

### 3. Export Contracts & Types
```powershell
.venv\Scripts\python scripts/export-contracts.py
```
