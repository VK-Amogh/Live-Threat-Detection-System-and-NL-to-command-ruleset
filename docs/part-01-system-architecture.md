# Part 1 — System Architecture

Status: Approved · Depends on: `00-spec-analysis.md` · Feeds: Parts 2–10

## 1. Objective
Fix the architecture, process boundaries, ports, event flow and technology choices so Parts 2–10 cannot drift.

## 2. Architecture Overview
- **Capture**: Native Python worker with bounded drop-oldest frame queues for live sources.
- **Inference**: Ultralytics YOLOv8 loaded from `storage/models/best.pt` with ByteTrack and temporal filter (K=3 of N=5).
- **Verification**: Ollama local VLM (`qwen2.5-vl:7b`) on candidate events only, concurrency 1.
- **API**: FastAPI single worker process on port `:8000`.
- **Database**: PostgreSQL in Docker on `127.0.0.1:5432`.
- **Clients**: Web dashboard (React+Vite) and Android mobile app (Flutter) communicating over LAN.
