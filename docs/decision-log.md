# SafeSpace Decision Log

| ID | Status | Decision | Rationale |
|---|---|---|---|
| D-001 | Frozen | One primary YOLO model with ByteTrack and temporal filter (3 of 5 hits) | Eliminates false triggers before candidate creation |
| D-002 | Frozen | Local VLM reasoning on candidate events only | Preserves GPU budget and guarantees low latency |
| D-003 | Frozen | Single FastAPI uvicorn worker process on `:8000` | In-process WebSocket broadcast requires a single process |
| D-004 | Frozen | Outbound-only inference worker with disk outbox | Eliminates incoming firewall port and broker dependencies |
| D-005 | Frozen | Native Ollama service on `127.0.0.1:11434` | Direct GPU access without Docker WSL overhead |
| D-006 | Frozen | PostgreSQL in Docker on `127.0.0.1:5432` only | Isolated structured data store, WAL, concurrent access |
| D-007 | Frozen | Two-phase event alerting: `DETECTED` before VLM verification | User receives immediate alert (≤1.5s) without waiting for VLM |
| D-008 | Frozen | Human-only confirmation/false-positive decision; AI never dismisses | Safety and auditing guarantee: AI cannot dismiss real threats |
| D-009 | Frozen | Web dashboard (React+TS) & Mobile app (Flutter Android-first) on LAN | Same Wi-Fi offline operation, zero cloud dependency |
| D-010 | Frozen | Single source contracts in Pydantic (`td_contracts`), generated TS/Dart | Zero model drift between Python, TypeScript, and Dart |
| D-011 | Frozen | Opaque revocable device tokens; internal calls require service token + loopback | Eliminates JWT revocation complexity; enforces defense-in-depth |
| D-012 | Frozen | Missed event recovery via `/api/v1/changes?after=<seq>` | Client synchronization is robust against WebSocket disconnects |
| D-013 | Frozen | Live preview at ~2 FPS JPEG snapshot/MJPEG stream | WebRTC/HLS are excessive complexity for v1 |
| D-014 | Frozen | WebSocket authentication using 30-second single-use tickets | Keeps tokens out of URL query parameters and access logs |
| D-015 | Frozen | Pydantic models in `contracts/` are single source of truth | Exported OpenAPI, JSON schemas, TS types, and Dart models |
| D-021 | Frozen | One repo, 3 Python packages (`td_contracts`, `services/api`, `services/inference`) | No circular dependencies; API and worker never import each other |
| D-025 | Frozen | Dashboard auth: HttpOnly SameSite=Strict cookie; Mobile: Bearer token | Secure platform-native auth practices |
| D-026 | Frozen | Internal base URL `http://127.0.0.1:8000` in dev, `https://127.0.0.1:8000` in prod | Verified loopback communication |
| D-029 | Frozen | Config files in `config/*.yaml`, secrets strictly in `.env` | Clean separation between committed declarative config and secrets |
