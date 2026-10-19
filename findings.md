# TRACE Security Assessment Report — LTDC
Threat Reconnaissance & Attack-path Correlation Engine

## Executive Summary
- **Target Application:** `LTDC`
- **Total Correlated Findings:** **130**

| ID | Severity | Confidence | Category | Endpoint | Remediation Action |
|---|---|---|---|---|---|
| `TR-AUTH-001` | **LOW** | MEDIUM | AUTHENTICATION | `POST /predict` | Add API key authentication and rate-limiting middleware (slowapi) to throttle inference. |
| `TR-TRAV-002` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /predict` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-AUTH-003` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/auth/seed-accounts` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-CORS-004` | **MEDIUM** | MEDIUM | CORS | `POST /api/v1/auth/login` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-AUTH-005` | **HIGH** | HIGH | AUTHENTICATION | `GET /auth/me` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-006` | **HIGH** | HIGH | AUTHENTICATION | `POST /auth/logout` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-007` | **CRITICAL** | HIGH | AUTHENTICATION | `POST /auth/password` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-008` | **HIGH** | HIGH | AUTHENTICATION | `POST /auth/pairing-code` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-009` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/auth/pair` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-010` | **HIGH** | HIGH | AUTHENTICATION | `GET /devices` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-011` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /devices/{ident}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-012` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/ws-tickets` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-013` | **MEDIUM** | MEDIUM | AUTHENTICATION | `WEBSOCKET /api/v1/ws` | Validate authentication token during handshake before calling websocket.accept(). |
| `TR-AUTH-014` | **HIGH** | HIGH | AUTHENTICATION | `POST /events/{ident}/verification` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-015` | **HIGH** | HIGH | AUTHENTICATION | `POST /events/{ident}/ai-review` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-016` | **HIGH** | HIGH | AUTHENTICATION | `GET /changes` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-TRAV-017` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `GET /events/{ident}/media/{filename}` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-AUTH-018` | **HIGH** | HIGH | AUTHENTICATION | `POST /sources` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-TRAV-019` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /sources` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-AUTH-020` | **LOW** | MEDIUM | AUTHENTICATION | `POST /inference/predict-frame` | Add API key authentication and rate-limiting middleware (slowapi) to throttle inference. |
| `TR-TRAV-021` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /inference/predict-frame` | Add API key authentication and rate-limiting middleware (slowapi) to throttle inference. |
| `TR-AUTH-022` | **HIGH** | HIGH | AUTHENTICATION | `POST /cameras` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-023` | **HIGH** | HIGH | AUTHENTICATION | `PATCH /cameras/{ident}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-024` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /cameras/{ident}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-025` | **HIGH** | HIGH | AUTHENTICATION | `POST /cameras/{ident}/start` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-026` | **HIGH** | HIGH | AUTHENTICATION | `POST /cameras/{ident}/stop` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-027` | **HIGH** | HIGH | AUTHENTICATION | `POST /phone-cameras/{ident}/frames` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-028` | **HIGH** | HIGH | AUTHENTICATION | `POST /phone-cameras/{ident}/stop` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-029` | **HIGH** | HIGH | AUTHENTICATION | `POST /cameras/{ident}/snapshots` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-030` | **HIGH** | HIGH | AUTHENTICATION | `GET /chat/conversations` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-031` | **HIGH** | HIGH | AUTHENTICATION | `GET /chat/conversations/{conversation_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-032` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /chat/conversations/{conversation_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-033` | **HIGH** | HIGH | AUTHENTICATION | `POST /chat/stream` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-034` | **HIGH** | HIGH | AUTHENTICATION | `POST /chat` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-CORS-035` | **MEDIUM** | MEDIUM | CORS | `POST /llm/describe` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-AUTH-036` | **HIGH** | HIGH | AUTHENTICATION | `POST /settings` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-037` | **HIGH** | HIGH | AUTHENTICATION | `GET /system` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-038` | **HIGH** | HIGH | AUTHENTICATION | `POST /models/reload` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-039` | **HIGH** | HIGH | AUTHENTICATION | `GET /rules/templates` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-SSTI-040` | **CRITICAL** | MEDIUM | SSTI | `GET /rules/templates` | Apply strict access control and input validation on SSTI attack path. |
| `TR-AUTH-041` | **HIGH** | HIGH | AUTHENTICATION | `GET /system/mode` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-042` | **HIGH** | HIGH | AUTHENTICATION | `PUT /system/mode` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-043` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets/{ruleset_id}/activate` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-044` | **HIGH** | MEDIUM | BOLA | `POST /rules/{rule_id}/dry-run` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-045` | **HIGH** | HIGH | AUTHENTICATION | `POST /rules/{rule_id}/dry-run` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-046` | **HIGH** | HIGH | AUTHENTICATION | `GET /system/audit` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-047` | **HIGH** | HIGH | AUTHENTICATION | `POST /devices/{device_id}/command` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-CORS-048` | **MEDIUM** | MEDIUM | CORS | `POST /api/v1/devices/enroll` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-AUTH-049` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/devices/me` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-050` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/devices/me/heartbeat` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-051` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/devices/fleet` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-052` | **HIGH** | MEDIUM | BOLA | `POST /api/v1/devices/{device_id}/commands` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-053` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/devices/{device_id}/commands` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-054` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/devices/apk-token` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-TRAV-055` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `GET /download/{token}/SafeSpace.apk` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-CORS-056` | **MEDIUM** | MEDIUM | CORS | `GET /download/{token}/SafeSpace.apk` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-AUTH-057` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/audit` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-058` | **HIGH** | MEDIUM | BOLA | `WEBSOCKET /api/v1/cameras/{camera_id}/publish` | Validate authentication token during handshake before calling websocket.accept(). |
| `TR-AUTH-059` | **MEDIUM** | MEDIUM | AUTHENTICATION | `WEBSOCKET /api/v1/cameras/{camera_id}/publish` | Validate authentication token during handshake before calling websocket.accept(). |
| `TR-AUTH-060` | **MEDIUM** | MEDIUM | AUTHENTICATION | `WEBSOCKET /api/v1/cameras/{camera_id}/view` | Validate authentication token during handshake before calling websocket.accept(). |
| `TR-AUTH-061` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/cameras/{camera_id}/frame.jpg` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-062` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/cameras/{camera_id}/live.mjpg` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-063` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/cameras/{camera_id}/stream` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-064` | **HIGH** | MEDIUM | BOLA | `GET /api/v1/cameras/{camera_id}/overlay` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-065` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/cameras/{camera_id}/overlay` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-066` | **HIGH** | MEDIUM | BOLA | `POST /api/v1/cameras/{camera_id}/snapshot` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-067` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/cameras/{camera_id}/snapshot` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-068` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/snapshots` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-069` | **HIGH** | MEDIUM | BOLA | `GET /api/v1/snapshots/{snapshot_id}.jpg` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-070` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/snapshots/{snapshot_id}.jpg` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-071` | **HIGH** | MEDIUM | BOLA | `DELETE /api/v1/snapshots/{snapshot_id}` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-072` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /api/v1/snapshots/{snapshot_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-073` | **HIGH** | MEDIUM | BOLA | `GET /api/v1/cameras/{camera_id}/timeline` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-074` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/cameras/{camera_id}/timeline` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-075` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/recordings` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-076` | **HIGH** | MEDIUM | BOLA | `GET /api/v1/recordings/{segment_id}.mp4` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-BOLA-077` | **HIGH** | MEDIUM | BOLA | `DELETE /api/v1/recordings/{segment_id}` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-078` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /api/v1/recordings/{segment_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-079` | **HIGH** | MEDIUM | BOLA | `POST /api/v1/cameras/{camera_id}/exports` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-080` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/cameras/{camera_id}/exports` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-081` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/exports` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-082` | **HIGH** | MEDIUM | BOLA | `GET /api/v1/exports/{export_id}.mp4` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-083` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/storage/summary` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-084` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/storage/sweep` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-085` | **HIGH** | HIGH | AUTHENTICATION | `GET /rulesets/templates` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-SSTI-086` | **CRITICAL** | MEDIUM | SSTI | `GET /rulesets/templates` | Apply strict access control and input validation on SSTI attack path. |
| `TR-AUTH-087` | **HIGH** | HIGH | AUTHENTICATION | `GET /rulesets` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-088` | **HIGH** | MEDIUM | BOLA | `GET /rulesets/{ruleset_id}` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-089` | **HIGH** | HIGH | AUTHENTICATION | `GET /rulesets/{ruleset_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-090` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-091` | **HIGH** | MEDIUM | BOLA | `PATCH /rulesets/{ruleset_id}` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-092` | **HIGH** | HIGH | AUTHENTICATION | `PATCH /rulesets/{ruleset_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-093` | **HIGH** | MEDIUM | BOLA | `POST /rulesets/{ruleset_id}/arm` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-094` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets/{ruleset_id}/arm` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-095` | **HIGH** | MEDIUM | BOLA | `POST /rulesets/{ruleset_id}/disarm` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-096` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets/{ruleset_id}/disarm` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-097` | **HIGH** | MEDIUM | BOLA | `DELETE /rulesets/{ruleset_id}` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-098` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /rulesets/{ruleset_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-099` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets/modes/activate` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-100` | **HIGH** | MEDIUM | BOLA | `POST /rulesets/{ruleset_id}/dry-run` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-101` | **HIGH** | HIGH | AUTHENTICATION | `POST /rulesets/{ruleset_id}/dry-run` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-102` | **HIGH** | HIGH | AUTHENTICATION | `POST /rules/compile` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-103` | **HIGH** | HIGH | AUTHENTICATION | `POST /rules/{ident}/activate` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-104` | **HIGH** | HIGH | AUTHENTICATION | `PATCH /rules/{ident}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-BOLA-105` | **HIGH** | MEDIUM | BOLA | `GET /cameras/{camera_id}/geometry` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-BOLA-106` | **HIGH** | MEDIUM | BOLA | `PUT /cameras/{camera_id}/geometry` | Scope database query to authenticated current_user.tenant_id to enforce isolation. |
| `TR-AUTH-107` | **HIGH** | HIGH | AUTHENTICATION | `PUT /cameras/{camera_id}/geometry` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-TRAV-108` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /live-frame` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-CORS-109` | **MEDIUM** | MEDIUM | CORS | `POST /review-jobs/claim` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-CORS-110` | **MEDIUM** | MEDIUM | CORS | `POST /review-jobs/{ident}/complete` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-CORS-111` | **MEDIUM** | MEDIUM | CORS | `POST /review-jobs/{ident}/retry` | Remove wildcard allow_origins; define explicit list of authorized frontend domains. |
| `TR-AUTH-112` | **HIGH** | HIGH | AUTHENTICATION | `POST /reload` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-113` | **HIGH** | HIGH | AUTHENTICATION | `DELETE /streams/{source_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-114` | **HIGH** | HIGH | AUTHENTICATION | `POST /predict` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-TRAV-115` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /predict` | Sanitize file input with basename() and verify resolved directory containment. |
| `TR-AUTH-116` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/auth/pairing-codes` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-117` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/auth/pair` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-118` | **HIGH** | HIGH | AUTHENTICATION | `GET /api/v1/auth/me` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-119` | **HIGH** | HIGH | AUTHENTICATION | `PATCH /api/v1/devices/me` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-120` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/ws-tickets` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-121` | **MEDIUM** | MEDIUM | AUTHENTICATION | `WEBSOCKET /api/v1/ws` | Validate authentication token during handshake before calling websocket.accept(). |
| `TR-AUTH-122` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/cameras` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-123` | **HIGH** | HIGH | AUTHENTICATION | `PATCH /api/v1/cameras/{camera_id}` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-124` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/events/{event_id}/verification` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-125` | **LOW** | MEDIUM | AUTHENTICATION | `POST /api/v1/inference/predict-frame` | Add API key authentication and rate-limiting middleware (slowapi) to throttle inference. |
| `TR-TRAV-126` | **HIGH** | MEDIUM | PATH_TRAVERSAL | `POST /api/v1/inference/predict-frame` | Add API key authentication and rate-limiting middleware (slowapi) to throttle inference. |
| `TR-AUTH-127` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/chat` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-128` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/internal/events` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-129` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/internal/events/{event_id}/extend` | Protect route with Depends(get_current_user) to block unauthenticated callers. |
| `TR-AUTH-130` | **HIGH** | HIGH | AUTHENTICATION | `POST /api/v1/internal/events/{event_id}/verification` | Protect route with Depends(get_current_user) to block unauthenticated callers. |

---

## Finding Details

### [TR-AUTH-001] Unauthenticated Stateless ML/Inference Endpoint on POST /predict
- **Category:** AUTHENTICATION
- **Severity:** LOW
- **Confidence:** MEDIUM
- **Endpoint:** `POST /predict`
- **Source:** `Model/backend/api.py:236-283`

#### Root Cause & Exploit Mechanics
The compute-intensive inference endpoint `POST /predict` is exposed to the public internet without authentication or request rate-limiting, allowing unauthorized callers to trigger CPU/GPU exhaustion and denial-of-wallet.

#### Attack Path Hops (APM Traversal)
1. `ep_Model_backend_api_py_predict_POST`
1. `fn_services_inference_server_py_predict`

#### Static AST Evidence
- Stateless compute endpoint POST /predict
- No database access or private user data stored
- Risk limited to compute exhaustion / unmetered access

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Add API key or session token verification to authenticate callers.
2. Implement rate-limiting middleware (e.g. `slowapi` or Redis token bucket) to throttle request frequency per client IP.
3. Enforce maximum payload size limits on input telemetry arrays.

---

### [TR-TRAV-002] Potential Path Traversal on POST /predict
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /predict`
- **Source:** `Model/backend/api.py:236-283`

#### Root Cause & Exploit Mechanics
Endpoint `POST /predict` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_Model_backend_api_py_predict_POST`
1. `fn_services_inference_server_py_predict`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: Model/backend/api.py:236-283

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-AUTH-003] Unauthenticated Sensitive Route Exposure on GET /api/v1/auth/seed-accounts
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/auth/seed-accounts`
- **Source:** `services/api/app/main.py:190-214`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/auth/seed-accounts` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_get_seed_accounts_GET`
1. `db_ep_services_api_app_main_py_get_seed_accounts_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/auth/seed-accounts`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-CORS-004] Potential CORS Misconfiguration on POST /api/v1/auth/login
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/auth/login`
- **Source:** `services/api/app/main.py:228-298`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /api/v1/auth/login` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_login_POST`
1. `db_ep_services_api_app_main_py_login_POST`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-AUTH-005] Unauthenticated Sensitive Route Exposure on GET /auth/me
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /auth/me`
- **Source:** `services/api/app/main.py:302-311`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /auth/me` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_me_GET`
1. `fn_services_api_app_main_py_me`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /auth/me`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-006] Unauthenticated Sensitive Route Exposure on POST /auth/logout
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /auth/logout`
- **Source:** `services/api/app/main.py:321-325`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /auth/logout` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_logout_POST`
1. `db_ep_services_api_app_main_py_logout_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /auth/logout`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-007] Unauthenticated Password Reset Allowing Account Takeover on POST /auth/password
- **Category:** AUTHENTICATION
- **Severity:** CRITICAL
- **Confidence:** HIGH
- **Endpoint:** `POST /auth/password`
- **Source:** `services/api/app/main.py:329-340`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /auth/password` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_change_password_POST`
1. `db_ep_services_api_app_main_py_change_password_POST`

#### Static AST Evidence
- Password modification endpoint lacks authentication
- Enables unauthenticated credential reset / account takeover

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /auth/password`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-008] Unauthenticated Sensitive Route Exposure on POST /auth/pairing-code
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /auth/pairing-code`
- **Source:** `services/api/app/main.py:355-367`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /auth/pairing-code` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_pairing_code_POST`
1. `db_ep_services_api_app_main_py_pairing_code_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /auth/pairing-code`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-009] Unauthenticated Sensitive Route Exposure on POST /api/v1/auth/pair
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/auth/pair`
- **Source:** `services/api/app/main.py:371-398`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/auth/pair` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_pair_POST`
1. `db_ep_services_api_app_main_py_pair_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/auth/pair`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-010] Unauthenticated Sensitive Route Exposure on GET /devices
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /devices`
- **Source:** `services/api/app/main.py:402-421`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /devices` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_devices_GET`
1. `db_ep_services_api_app_main_py_devices_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /devices`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-011] Unauthenticated Sensitive Route Exposure on DELETE /devices/{ident}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /devices/{ident}`
- **Source:** `services/api/app/main.py:425-436`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /devices/{ident}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_revoke_device_DELETE`
1. `db_ep_services_api_app_main_py_revoke_device_DELETE`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /devices/{ident}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-012] Unauthenticated Sensitive Route Exposure on POST /api/v1/ws-tickets
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/ws-tickets`
- **Source:** `services/api/app/main.py:440-444`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/ws-tickets` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_ws_ticket_POST`
1. `fn_services_api_app_main_py_ws_ticket`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/ws-tickets`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-013] Unauthenticated WebSocket Connection on WEBSOCKET /api/v1/ws
- **Category:** AUTHENTICATION
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `WEBSOCKET /api/v1/ws`
- **Source:** `services/api/app/main.py:448-470`

#### Root Cause & Exploit Mechanics
The WebSocket route `WEBSOCKET /api/v1/ws` accepts incoming streaming connections and dispatches real-time telemetry without authenticating the client during the handshake, allowing unauthorized eavesdropping or malicious event injection.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_websocket_WEBSOCKET`
1. `db_ep_services_api_app_main_py_websocket_WEBSOCKET`

#### Static AST Evidence
- WebSocket route /api/v1/ws accepts unauthenticated connections
- No token or session check in handshake handler

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract and validate authentication credentials (JWT ticket or session cookie) during the WebSocket connection handshake.
2. Reject unauthenticated handshakes before calling `await websocket.accept()` using WebSocket close code 1008 (Policy Violation).
3. Associate the open WebSocket connection strictly with the validated user ID.

---

### [TR-AUTH-014] Unauthenticated Sensitive Route Exposure on POST /events/{ident}/verification
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /events/{ident}/verification`
- **Source:** `services/api/app/main.py:507-534`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /events/{ident}/verification` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_verify_POST`
1. `db_ep_services_api_app_main_py_verify_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /events/{ident}/verification`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-015] Unauthenticated Sensitive Route Exposure on POST /events/{ident}/ai-review
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /events/{ident}/ai-review`
- **Source:** `services/api/app/main.py:538-546`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /events/{ident}/ai-review` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_ai_review_POST`
1. `ext_ep_services_api_app_main_py_ai_review_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /events/{ident}/ai-review`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-016] Unauthenticated Sensitive Route Exposure on GET /changes
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /changes`
- **Source:** `services/api/app/main.py:550-558`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /changes` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_changes_GET`
1. `db_ep_services_api_app_main_py_changes_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /changes`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-TRAV-017] Potential Path Traversal on GET /events/{ident}/media/{filename}
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /events/{ident}/media/{filename}`
- **Source:** `services/api/app/main.py:562-569`

#### Root Cause & Exploit Mechanics
Endpoint `GET /events/{ident}/media/{filename}` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_media_GET`
1. `fn_services_api_app_main_py_media`

#### Static AST Evidence
- File/path parameter names detected: ['filename']
- Source location: services/api/app/main.py:562-569

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-AUTH-018] Unauthenticated Sensitive Route Exposure on POST /sources
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /sources`
- **Source:** `services/api/app/main.py:581-619`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /sources` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_upload_POST`
1. `db_ep_services_api_app_main_py_upload_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /sources`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-TRAV-019] Potential Path Traversal on POST /sources
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /sources`
- **Source:** `services/api/app/main.py:581-619`

#### Root Cause & Exploit Mechanics
Endpoint `POST /sources` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_upload_POST`
1. `db_ep_services_api_app_main_py_upload_POST`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: services/api/app/main.py:581-619

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-AUTH-020] Unauthenticated Stateless ML/Inference Endpoint on POST /inference/predict-frame
- **Category:** AUTHENTICATION
- **Severity:** LOW
- **Confidence:** MEDIUM
- **Endpoint:** `POST /inference/predict-frame`
- **Source:** `services/api/app/main.py:652-660`

#### Root Cause & Exploit Mechanics
The compute-intensive inference endpoint `POST /inference/predict-frame` is exposed to the public internet without authentication or request rate-limiting, allowing unauthorized callers to trigger CPU/GPU exhaustion and denial-of-wallet.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_predict_frame_POST`
1. `fn_storage_backups_api-main-before-integration_py_predict_frame`

#### Static AST Evidence
- Stateless compute endpoint POST /inference/predict-frame
- No database access or private user data stored
- Risk limited to compute exhaustion / unmetered access

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Add API key or session token verification to authenticate callers.
2. Implement rate-limiting middleware (e.g. `slowapi` or Redis token bucket) to throttle request frequency per client IP.
3. Enforce maximum payload size limits on input telemetry arrays.

---

### [TR-TRAV-021] Potential Path Traversal on POST /inference/predict-frame
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /inference/predict-frame`
- **Source:** `services/api/app/main.py:652-660`

#### Root Cause & Exploit Mechanics
The compute-intensive inference endpoint `POST /inference/predict-frame` is exposed to the public internet without authentication or request rate-limiting, allowing unauthorized callers to trigger CPU/GPU exhaustion and denial-of-wallet.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_predict_frame_POST`
1. `fn_storage_backups_api-main-before-integration_py_predict_frame`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: services/api/app/main.py:652-660

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Add API key or session token verification to authenticate callers.
2. Implement rate-limiting middleware (e.g. `slowapi` or Redis token bucket) to throttle request frequency per client IP.
3. Enforce maximum payload size limits on input telemetry arrays.

---

### [TR-AUTH-022] Unauthenticated Sensitive Route Exposure on POST /cameras
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /cameras`
- **Source:** `services/api/app/main.py:699-708`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /cameras` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_add_camera_POST`
1. `db_ep_services_api_app_main_py_add_camera_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /cameras`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-023] Unauthenticated Sensitive Route Exposure on PATCH /cameras/{ident}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PATCH /cameras/{ident}`
- **Source:** `services/api/app/main.py:712-715`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PATCH /cameras/{ident}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_update_camera_PATCH`
1. `db_ep_services_api_app_main_py_update_camera_PATCH`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PATCH /cameras/{ident}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-024] Unauthenticated Sensitive Route Exposure on DELETE /cameras/{ident}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /cameras/{ident}`
- **Source:** `services/api/app/main.py:719-732`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /cameras/{ident}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_delete_camera_DELETE`
1. `db_ep_services_api_app_main_py_delete_camera_DELETE`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /cameras/{ident}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-025] Unauthenticated Sensitive Route Exposure on POST /cameras/{ident}/start
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /cameras/{ident}/start`
- **Source:** `services/api/app/main.py:736-750`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /cameras/{ident}/start` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_start_camera_POST`
1. `db_ep_services_api_app_main_py_start_camera_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /cameras/{ident}/start`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-026] Unauthenticated Sensitive Route Exposure on POST /cameras/{ident}/stop
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /cameras/{ident}/stop`
- **Source:** `services/api/app/main.py:754-768`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /cameras/{ident}/stop` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_stop_camera_POST`
1. `db_ep_services_api_app_main_py_stop_camera_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /cameras/{ident}/stop`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-027] Unauthenticated Sensitive Route Exposure on POST /phone-cameras/{ident}/frames
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /phone-cameras/{ident}/frames`
- **Source:** `services/api/app/main.py:840-857`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /phone-cameras/{ident}/frames` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_phone_camera_frame_POST`
1. `fn_services_api_app_main_py_phone_camera_frame`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /phone-cameras/{ident}/frames`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-028] Unauthenticated Sensitive Route Exposure on POST /phone-cameras/{ident}/stop
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /phone-cameras/{ident}/stop`
- **Source:** `services/api/app/main.py:861-865`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /phone-cameras/{ident}/stop` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_stop_phone_camera_POST`
1. `fn_services_api_app_main_py_stop_phone_camera`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /phone-cameras/{ident}/stop`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-029] Unauthenticated Sensitive Route Exposure on POST /cameras/{ident}/snapshots
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /cameras/{ident}/snapshots`
- **Source:** `services/api/app/main.py:886-899`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /cameras/{ident}/snapshots` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_camera_snapshot_POST`
1. `db_ep_services_api_app_main_py_camera_snapshot_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /cameras/{ident}/snapshots`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-030] Unauthenticated Sensitive Route Exposure on GET /chat/conversations
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /chat/conversations`
- **Source:** `services/api/app/main.py:945-946`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /chat/conversations` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_get_chat_conversations_GET`
1. `fn_services_api_app_main_py_get_chat_conversations`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /chat/conversations`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-031] Unauthenticated Sensitive Route Exposure on GET /chat/conversations/{conversation_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /chat/conversations/{conversation_id}`
- **Source:** `services/api/app/main.py:950-951`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /chat/conversations/{conversation_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_get_chat_conversation_GET`
1. `fn_services_api_app_main_py_get_chat_conversation`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /chat/conversations/{conversation_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-032] Unauthenticated Sensitive Route Exposure on DELETE /chat/conversations/{conversation_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /chat/conversations/{conversation_id}`
- **Source:** `services/api/app/main.py:955-957`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /chat/conversations/{conversation_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_remove_chat_conversation_DELETE`
1. `fn_services_api_app_main_py_remove_chat_conversation`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /chat/conversations/{conversation_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-033] Unauthenticated Sensitive Route Exposure on POST /chat/stream
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /chat/stream`
- **Source:** `services/api/app/main.py:961-968`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /chat/stream` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_stream_chat_POST`
1. `fn_services_api_app_main_py_stream_chat`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /chat/stream`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-034] Unauthenticated Sensitive Route Exposure on POST /chat
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /chat`
- **Source:** `services/api/app/main.py:972-978`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /chat` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_ask_chat_POST`
1. `fn_services_api_app_main_py_ask_chat`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /chat`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-CORS-035] Potential CORS Misconfiguration on POST /llm/describe
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /llm/describe`
- **Source:** `services/api/app/main.py:982-990`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /llm/describe` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_internal_llm_describe_POST`
1. `fn_services_api_app_main_py_internal_llm_describe`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-AUTH-036] Unauthenticated Sensitive Route Exposure on POST /settings
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /settings`
- **Source:** `services/api/app/main.py:999-1001`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /settings` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_set_settings_POST`
1. `db_ep_services_api_app_main_py_set_settings_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /settings`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-037] Unauthenticated Sensitive Route Exposure on GET /system
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /system`
- **Source:** `services/api/app/main.py:1006-1093`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /system` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_system_GET`
1. `db_ep_services_api_app_main_py_system_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /system`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-038] Unauthenticated Sensitive Route Exposure on POST /models/reload
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /models/reload`
- **Source:** `services/api/app/main.py:1097-1104`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /models/reload` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_main_py_reload_models_POST`
1. `ext_ep_services_api_app_main_py_reload_models_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /models/reload`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-039] Unauthenticated Sensitive Route Exposure on GET /rules/templates
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /rules/templates`
- **Source:** `services/api/app/routes/compat.py:25-44`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /rules/templates` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_rule_templates_GET`
1. `fn_services_api_app_routes_compat_py_rule_templates`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /rules/templates`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-SSTI-040] Potential Template Injection on GET /rules/templates
- **Category:** SSTI
- **Severity:** CRITICAL
- **Confidence:** MEDIUM
- **Endpoint:** `GET /rules/templates`
- **Source:** `services/api/app/routes/compat.py:25-44`

#### Root Cause & Exploit Mechanics
Security vulnerability of category `SSTI` identified in `GET /rules/templates`.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_rule_templates_GET`
1. `fn_services_api_app_routes_compat_py_rule_templates`

#### Static AST Evidence
- Template rendering parameter detected: ['/rules/templates']

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
Apply strict authentication, tenant authorization boundaries, and input validation to this attack path.

---

### [TR-AUTH-041] Unauthenticated Sensitive Route Exposure on GET /system/mode
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /system/mode`
- **Source:** `services/api/app/routes/compat.py:48-49`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /system/mode` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_get_system_mode_GET`
1. `fn_services_api_app_routes_compat_py_get_system_mode`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /system/mode`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-042] Unauthenticated Sensitive Route Exposure on PUT /system/mode
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PUT /system/mode`
- **Source:** `services/api/app/routes/compat.py:53-55`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PUT /system/mode` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_set_system_mode_PUT`
1. `fn_services_api_app_routes_compat_py_set_system_mode`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PUT /system/mode`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-043] Unauthenticated Sensitive Route Exposure on POST /rulesets/{ruleset_id}/activate
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets/{ruleset_id}/activate`
- **Source:** `services/api/app/routes/compat.py:59-60`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets/{ruleset_id}/activate` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_activate_ruleset_POST`
1. `fn_services_api_app_routes_compat_py_activate_ruleset`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets/{ruleset_id}/activate`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-044] Potential BOLA on POST /rules/{rule_id}/dry-run
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /rules/{rule_id}/dry-run`
- **Source:** `services/api/app/routes/compat.py:64-73`

#### Root Cause & Exploit Mechanics
The handler for `POST /rules/{rule_id}/dry-run` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_dry_run_rule_POST`
1. `db_ep_services_api_app_routes_compat_py_dry_run_rule_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['rule_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-045] Unauthenticated Sensitive Route Exposure on POST /rules/{rule_id}/dry-run
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rules/{rule_id}/dry-run`
- **Source:** `services/api/app/routes/compat.py:64-73`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rules/{rule_id}/dry-run` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_dry_run_rule_POST`
1. `db_ep_services_api_app_routes_compat_py_dry_run_rule_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rules/{rule_id}/dry-run`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-046] Unauthenticated Sensitive Route Exposure on GET /system/audit
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /system/audit`
- **Source:** `services/api/app/routes/compat.py:77-87`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /system/audit` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_system_audit_GET`
1. `db_ep_services_api_app_routes_compat_py_system_audit_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /system/audit`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-047] Unauthenticated Sensitive Route Exposure on POST /devices/{device_id}/command
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /devices/{device_id}/command`
- **Source:** `services/api/app/routes/compat.py:94-100`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /devices/{device_id}/command` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_compat_py_device_command_POST`
1. `fn_services_api_app_routes_compat_py_device_command`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /devices/{device_id}/command`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-CORS-048] Potential CORS Misconfiguration on POST /api/v1/devices/enroll
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/devices/enroll`
- **Source:** `services/api/app/routes/devices.py:133-157`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /api/v1/devices/enroll` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_enroll_device_POST`
1. `fn_services_api_app_routes_devices_py_enroll_device`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-AUTH-049] Unauthenticated Sensitive Route Exposure on GET /api/v1/devices/me
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/devices/me`
- **Source:** `services/api/app/routes/devices.py:161-174`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/devices/me` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_get_my_device_GET`
1. `db_ep_services_api_app_routes_devices_py_get_my_device_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/devices/me`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-050] Unauthenticated Sensitive Route Exposure on POST /api/v1/devices/me/heartbeat
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/devices/me/heartbeat`
- **Source:** `services/api/app/routes/devices.py:178-217`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/devices/me/heartbeat` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_heartbeat_my_device_POST`
1. `db_ep_services_api_app_routes_devices_py_heartbeat_my_device_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/devices/me/heartbeat`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-051] Unauthenticated Sensitive Route Exposure on GET /api/v1/devices/fleet
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/devices/fleet`
- **Source:** `services/api/app/routes/devices.py:221-233`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/devices/fleet` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_list_fleet_devices_GET`
1. `db_ep_services_api_app_routes_devices_py_list_fleet_devices_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/devices/fleet`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-052] Potential BOLA on POST /api/v1/devices/{device_id}/commands
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/devices/{device_id}/commands`
- **Source:** `services/api/app/routes/devices.py:237-273`

#### Root Cause & Exploit Mechanics
The handler for `POST /api/v1/devices/{device_id}/commands` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_send_command_to_device_POST`
1. `db_ep_services_api_app_routes_devices_py_send_command_to_device_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['device_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-053] Unauthenticated Sensitive Route Exposure on POST /api/v1/devices/{device_id}/commands
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/devices/{device_id}/commands`
- **Source:** `services/api/app/routes/devices.py:237-273`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/devices/{device_id}/commands` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_send_command_to_device_POST`
1. `db_ep_services_api_app_routes_devices_py_send_command_to_device_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/devices/{device_id}/commands`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-054] Unauthenticated Sensitive Route Exposure on POST /api/v1/devices/apk-token
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/devices/apk-token`
- **Source:** `services/api/app/routes/devices.py:277-300`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/devices/apk-token` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_create_apk_download_token_POST`
1. `db_ep_services_api_app_routes_devices_py_create_apk_download_token_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/devices/apk-token`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-TRAV-055] Potential Path Traversal on GET /download/{token}/SafeSpace.apk
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /download/{token}/SafeSpace.apk`
- **Source:** `services/api/app/routes/devices.py:304-337`

#### Root Cause & Exploit Mechanics
Endpoint `GET /download/{token}/SafeSpace.apk` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_download_apk_with_token_GET`
1. `db_ep_services_api_app_routes_devices_py_download_apk_with_token_GET`

#### Static AST Evidence
- File/path parameter names detected: ['token', 'request']
- Source location: services/api/app/routes/devices.py:304-337

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-CORS-056] Potential CORS Misconfiguration on GET /download/{token}/SafeSpace.apk
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `GET /download/{token}/SafeSpace.apk`
- **Source:** `services/api/app/routes/devices.py:304-337`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `GET /download/{token}/SafeSpace.apk` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_download_apk_with_token_GET`
1. `db_ep_services_api_app_routes_devices_py_download_apk_with_token_GET`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-AUTH-057] Unauthenticated Sensitive Route Exposure on GET /api/v1/audit
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/audit`
- **Source:** `services/api/app/routes/devices.py:341-342`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/audit` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_devices_py_get_audit_entries_GET`
1. `db_ep_services_api_app_routes_devices_py_get_audit_entries_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/audit`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-058] Potential BOLA on WEBSOCKET /api/v1/cameras/{camera_id}/publish
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `WEBSOCKET /api/v1/cameras/{camera_id}/publish`
- **Source:** `services/api/app/routes/media.py:63-182`

#### Root Cause & Exploit Mechanics
The WebSocket route `WEBSOCKET /api/v1/cameras/{camera_id}/publish` accepts incoming streaming connections and dispatches real-time telemetry without authenticating the client during the handshake, allowing unauthorized eavesdropping or malicious event injection.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_camera_publish_ws_WEBSOCKET`
1. `db_ep_services_api_app_routes_media_py_camera_publish_ws_WEBSOCKET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract and validate authentication credentials (JWT ticket or session cookie) during the WebSocket connection handshake.
2. Reject unauthenticated handshakes before calling `await websocket.accept()` using WebSocket close code 1008 (Policy Violation).
3. Associate the open WebSocket connection strictly with the validated user ID.

---

### [TR-AUTH-059] Unauthenticated WebSocket Connection on WEBSOCKET /api/v1/cameras/{camera_id}/publish
- **Category:** AUTHENTICATION
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `WEBSOCKET /api/v1/cameras/{camera_id}/publish`
- **Source:** `services/api/app/routes/media.py:63-182`

#### Root Cause & Exploit Mechanics
The WebSocket route `WEBSOCKET /api/v1/cameras/{camera_id}/publish` accepts incoming streaming connections and dispatches real-time telemetry without authenticating the client during the handshake, allowing unauthorized eavesdropping or malicious event injection.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_camera_publish_ws_WEBSOCKET`
1. `db_ep_services_api_app_routes_media_py_camera_publish_ws_WEBSOCKET`

#### Static AST Evidence
- WebSocket route /api/v1/cameras/{camera_id}/publish accepts unauthenticated connections
- No token or session check in handshake handler

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract and validate authentication credentials (JWT ticket or session cookie) during the WebSocket connection handshake.
2. Reject unauthenticated handshakes before calling `await websocket.accept()` using WebSocket close code 1008 (Policy Violation).
3. Associate the open WebSocket connection strictly with the validated user ID.

---

### [TR-AUTH-060] Unauthenticated WebSocket Connection on WEBSOCKET /api/v1/cameras/{camera_id}/view
- **Category:** AUTHENTICATION
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `WEBSOCKET /api/v1/cameras/{camera_id}/view`
- **Source:** `services/api/app/routes/media.py:186-231`

#### Root Cause & Exploit Mechanics
The WebSocket route `WEBSOCKET /api/v1/cameras/{camera_id}/view` accepts incoming streaming connections and dispatches real-time telemetry without authenticating the client during the handshake, allowing unauthorized eavesdropping or malicious event injection.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_camera_view_ws_WEBSOCKET`
1. `fn_services_api_app_routes_media_py_camera_view_ws`

#### Static AST Evidence
- WebSocket route /api/v1/cameras/{camera_id}/view accepts unauthenticated connections
- No token or session check in handshake handler

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract and validate authentication credentials (JWT ticket or session cookie) during the WebSocket connection handshake.
2. Reject unauthenticated handshakes before calling `await websocket.accept()` using WebSocket close code 1008 (Policy Violation).
3. Associate the open WebSocket connection strictly with the validated user ID.

---

### [TR-AUTH-061] Unauthenticated Sensitive Route Exposure on GET /api/v1/cameras/{camera_id}/frame.jpg
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/frame.jpg`
- **Source:** `services/api/app/routes/media.py:235-256`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/cameras/{camera_id}/frame.jpg` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_get_camera_latest_frame_GET`
1. `fn_services_api_app_routes_media_py_get_camera_latest_frame`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/cameras/{camera_id}/frame.jpg`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-062] Unauthenticated Sensitive Route Exposure on GET /api/v1/cameras/{camera_id}/live.mjpg
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/live.mjpg`
- **Source:** `services/api/app/routes/media.py:295-309`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/cameras/{camera_id}/live.mjpg` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_stream_camera_mjpeg_GET`
1. `fn_services_api_app_routes_media_py_stream_camera_mjpeg`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/cameras/{camera_id}/live.mjpg`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-063] Unauthenticated Sensitive Route Exposure on GET /api/v1/cameras/{camera_id}/stream
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/stream`
- **Source:** `services/api/app/routes/media.py:295-309`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/cameras/{camera_id}/stream` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_stream_camera_mjpeg_GET`
1. `fn_services_api_app_routes_media_py_stream_camera_mjpeg`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/cameras/{camera_id}/stream`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-064] Potential BOLA on GET /api/v1/cameras/{camera_id}/overlay
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/overlay`
- **Source:** `services/api/app/routes/media.py:313-324`

#### Root Cause & Exploit Mechanics
The handler for `GET /api/v1/cameras/{camera_id}/overlay` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_get_camera_overlay_GET`
1. `db_ep_services_api_app_routes_media_py_get_camera_overlay_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-065] Unauthenticated Sensitive Route Exposure on GET /api/v1/cameras/{camera_id}/overlay
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/overlay`
- **Source:** `services/api/app/routes/media.py:313-324`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/cameras/{camera_id}/overlay` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_get_camera_overlay_GET`
1. `db_ep_services_api_app_routes_media_py_get_camera_overlay_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/cameras/{camera_id}/overlay`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-066] Potential BOLA on POST /api/v1/cameras/{camera_id}/snapshot
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/cameras/{camera_id}/snapshot`
- **Source:** `services/api/app/routes/media.py:328-351`

#### Root Cause & Exploit Mechanics
The handler for `POST /api/v1/cameras/{camera_id}/snapshot` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_create_camera_snapshot_POST`
1. `db_ep_services_api_app_routes_media_py_create_camera_snapshot_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-067] Unauthenticated Sensitive Route Exposure on POST /api/v1/cameras/{camera_id}/snapshot
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/cameras/{camera_id}/snapshot`
- **Source:** `services/api/app/routes/media.py:328-351`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/cameras/{camera_id}/snapshot` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_create_camera_snapshot_POST`
1. `db_ep_services_api_app_routes_media_py_create_camera_snapshot_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/cameras/{camera_id}/snapshot`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-068] Unauthenticated Sensitive Route Exposure on GET /api/v1/snapshots
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/snapshots`
- **Source:** `services/api/app/routes/media.py:355-359`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/snapshots` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_list_all_snapshots_GET`
1. `db_ep_services_api_app_routes_media_py_list_all_snapshots_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/snapshots`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-069] Potential BOLA on GET /api/v1/snapshots/{snapshot_id}.jpg
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /api/v1/snapshots/{snapshot_id}.jpg`
- **Source:** `services/api/app/routes/media.py:363-381`

#### Root Cause & Exploit Mechanics
The handler for `GET /api/v1/snapshots/{snapshot_id}.jpg` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_get_snapshot_image_GET`
1. `db_ep_services_api_app_routes_media_py_get_snapshot_image_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['snapshot_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-070] Unauthenticated Sensitive Route Exposure on GET /api/v1/snapshots/{snapshot_id}.jpg
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/snapshots/{snapshot_id}.jpg`
- **Source:** `services/api/app/routes/media.py:363-381`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/snapshots/{snapshot_id}.jpg` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_get_snapshot_image_GET`
1. `db_ep_services_api_app_routes_media_py_get_snapshot_image_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/snapshots/{snapshot_id}.jpg`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-071] Potential BOLA on DELETE /api/v1/snapshots/{snapshot_id}
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `DELETE /api/v1/snapshots/{snapshot_id}`
- **Source:** `services/api/app/routes/media.py:385-398`

#### Root Cause & Exploit Mechanics
The handler for `DELETE /api/v1/snapshots/{snapshot_id}` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_delete_snapshot_endpoint_DELETE`
1. `db_ep_services_api_app_routes_media_py_delete_snapshot_endpoint_DELETE`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['snapshot_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-072] Unauthenticated Sensitive Route Exposure on DELETE /api/v1/snapshots/{snapshot_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /api/v1/snapshots/{snapshot_id}`
- **Source:** `services/api/app/routes/media.py:385-398`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /api/v1/snapshots/{snapshot_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_media_py_delete_snapshot_endpoint_DELETE`
1. `db_ep_services_api_app_routes_media_py_delete_snapshot_endpoint_DELETE`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /api/v1/snapshots/{snapshot_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-073] Potential BOLA on GET /api/v1/cameras/{camera_id}/timeline
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/timeline`
- **Source:** `services/api/app/routes/recordings.py:111-193`

#### Root Cause & Exploit Mechanics
The handler for `GET /api/v1/cameras/{camera_id}/timeline` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_get_camera_timeline_GET`
1. `db_ep_services_api_app_routes_recordings_py_get_camera_timeline_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-074] Unauthenticated Sensitive Route Exposure on GET /api/v1/cameras/{camera_id}/timeline
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/cameras/{camera_id}/timeline`
- **Source:** `services/api/app/routes/recordings.py:111-193`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/cameras/{camera_id}/timeline` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_get_camera_timeline_GET`
1. `db_ep_services_api_app_routes_recordings_py_get_camera_timeline_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/cameras/{camera_id}/timeline`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-075] Unauthenticated Sensitive Route Exposure on GET /api/v1/recordings
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/recordings`
- **Source:** `services/api/app/routes/recordings.py:197-214`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/recordings` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_list_recordings_endpoint_GET`
1. `db_ep_services_api_app_routes_recordings_py_list_recordings_endpoint_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/recordings`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-076] Potential BOLA on GET /api/v1/recordings/{segment_id}.mp4
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /api/v1/recordings/{segment_id}.mp4`
- **Source:** `services/api/app/routes/recordings.py:218-236`

#### Root Cause & Exploit Mechanics
The handler for `GET /api/v1/recordings/{segment_id}.mp4` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_stream_recording_segment_GET`
1. `db_ep_services_api_app_routes_recordings_py_stream_recording_segment_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['segment_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-BOLA-077] Potential BOLA on DELETE /api/v1/recordings/{segment_id}
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `DELETE /api/v1/recordings/{segment_id}`
- **Source:** `services/api/app/routes/recordings.py:240-253`

#### Root Cause & Exploit Mechanics
The handler for `DELETE /api/v1/recordings/{segment_id}` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_delete_recording_segment_endpoint_DELETE`
1. `db_ep_services_api_app_routes_recordings_py_delete_recording_segment_endpoint_DELETE`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['segment_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-078] Unauthenticated Sensitive Route Exposure on DELETE /api/v1/recordings/{segment_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /api/v1/recordings/{segment_id}`
- **Source:** `services/api/app/routes/recordings.py:240-253`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /api/v1/recordings/{segment_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_delete_recording_segment_endpoint_DELETE`
1. `db_ep_services_api_app_routes_recordings_py_delete_recording_segment_endpoint_DELETE`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /api/v1/recordings/{segment_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-079] Potential BOLA on POST /api/v1/cameras/{camera_id}/exports
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/cameras/{camera_id}/exports`
- **Source:** `services/api/app/routes/recordings.py:257-282`

#### Root Cause & Exploit Mechanics
The handler for `POST /api/v1/cameras/{camera_id}/exports` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_create_clip_export_POST`
1. `db_ep_services_api_app_routes_recordings_py_create_clip_export_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-080] Unauthenticated Sensitive Route Exposure on POST /api/v1/cameras/{camera_id}/exports
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/cameras/{camera_id}/exports`
- **Source:** `services/api/app/routes/recordings.py:257-282`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/cameras/{camera_id}/exports` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_create_clip_export_POST`
1. `db_ep_services_api_app_routes_recordings_py_create_clip_export_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/cameras/{camera_id}/exports`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-081] Unauthenticated Sensitive Route Exposure on GET /api/v1/exports
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/exports`
- **Source:** `services/api/app/routes/recordings.py:286-290`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/exports` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_list_exports_endpoint_GET`
1. `db_ep_services_api_app_routes_recordings_py_list_exports_endpoint_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/exports`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-082] Potential BOLA on GET /api/v1/exports/{export_id}.mp4
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /api/v1/exports/{export_id}.mp4`
- **Source:** `services/api/app/routes/recordings.py:294-303`

#### Root Cause & Exploit Mechanics
The handler for `GET /api/v1/exports/{export_id}.mp4` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_download_exported_clip_GET`
1. `db_ep_services_api_app_routes_recordings_py_download_exported_clip_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['export_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-083] Unauthenticated Sensitive Route Exposure on GET /api/v1/storage/summary
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/storage/summary`
- **Source:** `services/api/app/routes/recordings.py:307-308`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/storage/summary` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_storage_summary_endpoint_GET`
1. `fn_services_api_app_routes_recordings_py_storage_summary_endpoint`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/storage/summary`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-084] Unauthenticated Sensitive Route Exposure on POST /api/v1/storage/sweep
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/storage/sweep`
- **Source:** `services/api/app/routes/recordings.py:312-321`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/storage/sweep` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_recordings_py_storage_sweep_endpoint_POST`
1. `db_ep_services_api_app_routes_recordings_py_storage_sweep_endpoint_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/storage/sweep`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-085] Unauthenticated Sensitive Route Exposure on GET /rulesets/templates
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /rulesets/templates`
- **Source:** `services/api/app/routes/rulesets.py:127-128`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /rulesets/templates` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_list_rule_templates_GET`
1. `fn_services_api_app_routes_rulesets_py_list_rule_templates`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /rulesets/templates`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-SSTI-086] Potential Template Injection on GET /rulesets/templates
- **Category:** SSTI
- **Severity:** CRITICAL
- **Confidence:** MEDIUM
- **Endpoint:** `GET /rulesets/templates`
- **Source:** `services/api/app/routes/rulesets.py:127-128`

#### Root Cause & Exploit Mechanics
Security vulnerability of category `SSTI` identified in `GET /rulesets/templates`.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_list_rule_templates_GET`
1. `fn_services_api_app_routes_rulesets_py_list_rule_templates`

#### Static AST Evidence
- Template rendering parameter detected: ['/rulesets/templates']

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
Apply strict authentication, tenant authorization boundaries, and input validation to this attack path.

---

### [TR-AUTH-087] Unauthenticated Sensitive Route Exposure on GET /rulesets
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /rulesets`
- **Source:** `services/api/app/routes/rulesets.py:132-136`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /rulesets` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_list_all_rulesets_GET`
1. `db_ep_services_api_app_routes_rulesets_py_list_all_rulesets_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /rulesets`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-088] Potential BOLA on GET /rulesets/{ruleset_id}
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:140-144`

#### Root Cause & Exploit Mechanics
The handler for `GET /rulesets/{ruleset_id}` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_get_single_ruleset_GET`
1. `db_ep_services_api_app_routes_rulesets_py_get_single_ruleset_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-089] Unauthenticated Sensitive Route Exposure on GET /rulesets/{ruleset_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:140-144`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /rulesets/{ruleset_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_get_single_ruleset_GET`
1. `db_ep_services_api_app_routes_rulesets_py_get_single_ruleset_GET`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /rulesets/{ruleset_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-090] Unauthenticated Sensitive Route Exposure on POST /rulesets
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets`
- **Source:** `services/api/app/routes/rulesets.py:148-364`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_create_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_create_ruleset_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-091] Potential BOLA on PATCH /rulesets/{ruleset_id}
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `PATCH /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:368-423`

#### Root Cause & Exploit Mechanics
The handler for `PATCH /rulesets/{ruleset_id}` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_update_ruleset_PATCH`
1. `db_ep_services_api_app_routes_rulesets_py_update_ruleset_PATCH`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-092] Unauthenticated Sensitive Route Exposure on PATCH /rulesets/{ruleset_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PATCH /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:368-423`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PATCH /rulesets/{ruleset_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_update_ruleset_PATCH`
1. `db_ep_services_api_app_routes_rulesets_py_update_ruleset_PATCH`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PATCH /rulesets/{ruleset_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-093] Potential BOLA on POST /rulesets/{ruleset_id}/arm
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /rulesets/{ruleset_id}/arm`
- **Source:** `services/api/app/routes/rulesets.py:427-487`

#### Root Cause & Exploit Mechanics
The handler for `POST /rulesets/{ruleset_id}/arm` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_arm_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_arm_ruleset_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-094] Unauthenticated Sensitive Route Exposure on POST /rulesets/{ruleset_id}/arm
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets/{ruleset_id}/arm`
- **Source:** `services/api/app/routes/rulesets.py:427-487`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets/{ruleset_id}/arm` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_arm_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_arm_ruleset_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets/{ruleset_id}/arm`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-095] Potential BOLA on POST /rulesets/{ruleset_id}/disarm
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /rulesets/{ruleset_id}/disarm`
- **Source:** `services/api/app/routes/rulesets.py:491-539`

#### Root Cause & Exploit Mechanics
The handler for `POST /rulesets/{ruleset_id}/disarm` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_disarm_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_disarm_ruleset_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-096] Unauthenticated Sensitive Route Exposure on POST /rulesets/{ruleset_id}/disarm
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets/{ruleset_id}/disarm`
- **Source:** `services/api/app/routes/rulesets.py:491-539`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets/{ruleset_id}/disarm` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_disarm_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_disarm_ruleset_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets/{ruleset_id}/disarm`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-097] Potential BOLA on DELETE /rulesets/{ruleset_id}
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `DELETE /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:543-553`

#### Root Cause & Exploit Mechanics
The handler for `DELETE /rulesets/{ruleset_id}` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_delete_ruleset_endpoint_DELETE`
1. `db_ep_services_api_app_routes_rulesets_py_delete_ruleset_endpoint_DELETE`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-098] Unauthenticated Sensitive Route Exposure on DELETE /rulesets/{ruleset_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /rulesets/{ruleset_id}`
- **Source:** `services/api/app/routes/rulesets.py:543-553`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /rulesets/{ruleset_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_delete_ruleset_endpoint_DELETE`
1. `db_ep_services_api_app_routes_rulesets_py_delete_ruleset_endpoint_DELETE`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /rulesets/{ruleset_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-099] Unauthenticated Sensitive Route Exposure on POST /rulesets/modes/activate
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets/modes/activate`
- **Source:** `services/api/app/routes/rulesets.py:557-627`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets/modes/activate` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_activate_security_mode_POST`
1. `db_ep_services_api_app_routes_rulesets_py_activate_security_mode_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets/modes/activate`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-100] Potential BOLA on POST /rulesets/{ruleset_id}/dry-run
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /rulesets/{ruleset_id}/dry-run`
- **Source:** `services/api/app/routes/rulesets.py:631-793`

#### Root Cause & Exploit Mechanics
The handler for `POST /rulesets/{ruleset_id}/dry-run` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_dry_run_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_dry_run_ruleset_POST`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['ruleset_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-101] Unauthenticated Sensitive Route Exposure on POST /rulesets/{ruleset_id}/dry-run
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rulesets/{ruleset_id}/dry-run`
- **Source:** `services/api/app/routes/rulesets.py:631-793`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rulesets/{ruleset_id}/dry-run` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_routes_rulesets_py_dry_run_ruleset_POST`
1. `db_ep_services_api_app_routes_rulesets_py_dry_run_ruleset_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rulesets/{ruleset_id}/dry-run`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-102] Unauthenticated Sensitive Route Exposure on POST /rules/compile
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rules/compile`
- **Source:** `services/api/app/rule_routes.py:57-78`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rules/compile` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_compile_rule_POST`
1. `db_ep_services_api_app_rule_routes_py_compile_rule_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rules/compile`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-103] Unauthenticated Sensitive Route Exposure on POST /rules/{ident}/activate
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /rules/{ident}/activate`
- **Source:** `services/api/app/rule_routes.py:87-113`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /rules/{ident}/activate` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_activate_rule_POST`
1. `db_ep_services_api_app_rule_routes_py_activate_rule_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /rules/{ident}/activate`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-104] Unauthenticated Sensitive Route Exposure on PATCH /rules/{ident}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PATCH /rules/{ident}`
- **Source:** `services/api/app/rule_routes.py:117-130`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PATCH /rules/{ident}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_change_rule_status_PATCH`
1. `db_ep_services_api_app_rule_routes_py_change_rule_status_PATCH`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PATCH /rules/{ident}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-BOLA-105] Potential BOLA on GET /cameras/{camera_id}/geometry
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `GET /cameras/{camera_id}/geometry`
- **Source:** `services/api/app/rule_routes.py:134-138`

#### Root Cause & Exploit Mechanics
The handler for `GET /cameras/{camera_id}/geometry` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_get_geometry_GET`
1. `db_ep_services_api_app_rule_routes_py_get_geometry_GET`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-BOLA-106] Potential BOLA on PUT /cameras/{camera_id}/geometry
- **Category:** BOLA
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `PUT /cameras/{camera_id}/geometry`
- **Source:** `services/api/app/rule_routes.py:142-146`

#### Root Cause & Exploit Mechanics
The handler for `PUT /cameras/{camera_id}/geometry` looks up database records using a client-supplied object ID from the URL or query without verifying that the requested record belongs to the authenticated user's tenant or organization. An attacker can increment or replace the ID to view or modify records belonging to other tenants.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_put_geometry_PUT`
1. `db_ep_services_api_app_rule_routes_py_put_geometry_PUT`

#### Static AST Evidence
- Path parameter matches object ID pattern: ['camera_id']
- Database lookup confirmed in handler source
- Declared auth required: False

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract authenticated caller ID from the verified session context (e.g. `current_user = Depends(get_current_user)`).
2. Scope database queries to both the object ID and the user's tenant: `db.query(Model).filter(Model.id == obj_id, Model.tenant_id == current_user.tenant_id).first()`.
3. Return HTTP 403 Forbidden or 404 Not Found if the resource is not owned by the caller.

---

### [TR-AUTH-107] Unauthenticated Sensitive Route Exposure on PUT /cameras/{camera_id}/geometry
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PUT /cameras/{camera_id}/geometry`
- **Source:** `services/api/app/rule_routes.py:142-146`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PUT /cameras/{camera_id}/geometry` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_put_geometry_PUT`
1. `db_ep_services_api_app_rule_routes_py_put_geometry_PUT`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PUT /cameras/{camera_id}/geometry`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-TRAV-108] Potential Path Traversal on POST /live-frame
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /live-frame`
- **Source:** `services/api/app/rule_routes.py:179-201`

#### Root Cause & Exploit Mechanics
Endpoint `POST /live-frame` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_ingest_live_frame_POST`
1. `db_ep_services_api_app_rule_routes_py_ingest_live_frame_POST`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: services/api/app/rule_routes.py:179-201

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-CORS-109] Potential CORS Misconfiguration on POST /review-jobs/claim
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /review-jobs/claim`
- **Source:** `services/api/app/rule_routes.py:338-345`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /review-jobs/claim` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_claim_review_POST`
1. `db_ep_services_api_app_rule_routes_py_claim_review_POST`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-CORS-110] Potential CORS Misconfiguration on POST /review-jobs/{ident}/complete
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /review-jobs/{ident}/complete`
- **Source:** `services/api/app/rule_routes.py:349-354`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /review-jobs/{ident}/complete` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_complete_review_POST`
1. `db_ep_services_api_app_rule_routes_py_complete_review_POST`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-CORS-111] Potential CORS Misconfiguration on POST /review-jobs/{ident}/retry
- **Category:** CORS
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `POST /review-jobs/{ident}/retry`
- **Source:** `services/api/app/rule_routes.py:358-363`

#### Root Cause & Exploit Mechanics
`CORSMiddleware` on `POST /review-jobs/{ident}/retry` is configured with `allow_origins=['*']` combined with `allow_credentials=True`. This permits arbitrary third-party websites to execute credentialed cross-origin requests against the backend, enabling CSRF-style data exfiltration and session riding.

#### Attack Path Hops (APM Traversal)
1. `ep_services_api_app_rule_routes_py_retry_review_POST`
1. `db_ep_services_api_app_rule_routes_py_retry_review_POST`

#### Static AST Evidence
- Authenticated: True, Sensitive data: True

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Remove wildcard `allow_origins=['*']`.
2. Configure an explicit array of authorized frontend domains (e.g. `allow_origins=['https://app.example.com']`).
3. Never dynamically reflect incoming `Origin` headers into `Access-Control-Allow-Origin` when credentials are enabled.

---

### [TR-AUTH-112] Unauthenticated Sensitive Route Exposure on POST /reload
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /reload`
- **Source:** `services/inference/server.py:185-188`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /reload` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_inference_server_py_reload_models_POST`
1. `fn_services_inference_server_py_reload_models`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /reload`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-113] Unauthenticated Sensitive Route Exposure on DELETE /streams/{source_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `DELETE /streams/{source_id}`
- **Source:** `services/inference/server.py:192-196`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `DELETE /streams/{source_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_inference_server_py_forget_stream_DELETE`
1. `fn_services_inference_server_py_forget_stream`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `DELETE /streams/{source_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-114] Unauthenticated Sensitive Route Exposure on POST /predict
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /predict`
- **Source:** `services/inference/server.py:278-287`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /predict` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_services_inference_server_py_predict_frame_POST`
1. `db_ep_services_inference_server_py_predict_frame_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /predict`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-TRAV-115] Potential Path Traversal on POST /predict
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /predict`
- **Source:** `services/inference/server.py:278-287`

#### Root Cause & Exploit Mechanics
Endpoint `POST /predict` accepts file or path parameters without verifying that the resolved path resides strictly within the intended base directory. Attackers can use path traversal sequences (`..`) to access arbitrary system files.

#### Attack Path Hops (APM Traversal)
1. `ep_services_inference_server_py_predict_frame_POST`
1. `db_ep_services_inference_server_py_predict_frame_POST`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: services/inference/server.py:278-287

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Sanitize file path inputs using `os.path.basename()` or `pathlib.Path.resolve()`.
2. Verify that `resolved_path.is_relative_to(base_dir)` before opening or reading files.

---

### [TR-AUTH-116] Unauthenticated Sensitive Route Exposure on POST /api/v1/auth/pairing-codes
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/auth/pairing-codes`
- **Source:** `storage/backups/api-main-before-integration.py:225-233`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/auth/pairing-codes` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_create_pairing_code_POST`
1. `fn_storage_backups_api-main-before-integration_py_create_pairing_code`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/auth/pairing-codes`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-117] Unauthenticated Sensitive Route Exposure on POST /api/v1/auth/pair
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/auth/pair`
- **Source:** `storage/backups/api-main-before-integration.py:237-268`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/auth/pair` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_pair_device_POST`
1. `fn_storage_backups_api-main-before-integration_py_pair_device`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/auth/pair`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-118] Unauthenticated Sensitive Route Exposure on GET /api/v1/auth/me
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `GET /api/v1/auth/me`
- **Source:** `storage/backups/api-main-before-integration.py:272-278`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `GET /api/v1/auth/me` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_get_current_user_GET`
1. `fn_storage_backups_api-main-before-integration_py_get_current_user`

#### Static AST Evidence
- State-changing: False
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `GET /api/v1/auth/me`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-119] Unauthenticated Sensitive Route Exposure on PATCH /api/v1/devices/me
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PATCH /api/v1/devices/me`
- **Source:** `storage/backups/api-main-before-integration.py:287-295`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PATCH /api/v1/devices/me` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_update_device_me_PATCH`
1. `fn_storage_backups_api-main-before-integration_py_update_device_me`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PATCH /api/v1/devices/me`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-120] Unauthenticated Sensitive Route Exposure on POST /api/v1/ws-tickets
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/ws-tickets`
- **Source:** `storage/backups/api-main-before-integration.py:299-303`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/ws-tickets` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_create_ws_ticket_POST`
1. `fn_storage_backups_api-main-before-integration_py_create_ws_ticket`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/ws-tickets`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-121] Unauthenticated WebSocket Connection on WEBSOCKET /api/v1/ws
- **Category:** AUTHENTICATION
- **Severity:** MEDIUM
- **Confidence:** MEDIUM
- **Endpoint:** `WEBSOCKET /api/v1/ws`
- **Source:** `storage/backups/api-main-before-integration.py:311-347`

#### Root Cause & Exploit Mechanics
The WebSocket route `WEBSOCKET /api/v1/ws` accepts incoming streaming connections and dispatches real-time telemetry without authenticating the client during the handshake, allowing unauthorized eavesdropping or malicious event injection.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_websocket_endpoint_WEBSOCKET`
1. `fn_storage_backups_api-main-before-integration_py_websocket_endpoint`

#### Static AST Evidence
- WebSocket route /api/v1/ws accepts unauthenticated connections
- No token or session check in handshake handler

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Extract and validate authentication credentials (JWT ticket or session cookie) during the WebSocket connection handshake.
2. Reject unauthenticated handshakes before calling `await websocket.accept()` using WebSocket close code 1008 (Policy Violation).
3. Associate the open WebSocket connection strictly with the validated user ID.

---

### [TR-AUTH-122] Unauthenticated Sensitive Route Exposure on POST /api/v1/cameras
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/cameras`
- **Source:** `storage/backups/api-main-before-integration.py:360-373`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/cameras` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_create_camera_POST`
1. `fn_storage_backups_api-main-before-integration_py_create_camera`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: True
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/cameras`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-123] Unauthenticated Sensitive Route Exposure on PATCH /api/v1/cameras/{camera_id}
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `PATCH /api/v1/cameras/{camera_id}`
- **Source:** `storage/backups/api-main-before-integration.py:377-388`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `PATCH /api/v1/cameras/{camera_id}` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_update_camera_PATCH`
1. `fn_storage_backups_api-main-before-integration_py_update_camera`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `PATCH /api/v1/cameras/{camera_id}`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-124] Unauthenticated Sensitive Route Exposure on POST /api/v1/events/{event_id}/verification
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/events/{event_id}/verification`
- **Source:** `storage/backups/api-main-before-integration.py:422-451`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/events/{event_id}/verification` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_human_verify_event_POST`
1. `fn_storage_backups_api-main-before-integration_py_human_verify_event`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/events/{event_id}/verification`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-125] Unauthenticated Stateless ML/Inference Endpoint on POST /api/v1/inference/predict-frame
- **Category:** AUTHENTICATION
- **Severity:** LOW
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/inference/predict-frame`
- **Source:** `storage/backups/api-main-before-integration.py:480-556`

#### Root Cause & Exploit Mechanics
The compute-intensive inference endpoint `POST /api/v1/inference/predict-frame` is exposed to the public internet without authentication or request rate-limiting, allowing unauthorized callers to trigger CPU/GPU exhaustion and denial-of-wallet.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_predict_frame_POST`
1. `fn_storage_backups_api-main-before-integration_py_predict_frame`

#### Static AST Evidence
- Stateless compute endpoint POST /api/v1/inference/predict-frame
- No database access or private user data stored
- Risk limited to compute exhaustion / unmetered access

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Add API key or session token verification to authenticate callers.
2. Implement rate-limiting middleware (e.g. `slowapi` or Redis token bucket) to throttle request frequency per client IP.
3. Enforce maximum payload size limits on input telemetry arrays.

---

### [TR-TRAV-126] Potential Path Traversal on POST /api/v1/inference/predict-frame
- **Category:** PATH_TRAVERSAL
- **Severity:** HIGH
- **Confidence:** MEDIUM
- **Endpoint:** `POST /api/v1/inference/predict-frame`
- **Source:** `storage/backups/api-main-before-integration.py:480-556`

#### Root Cause & Exploit Mechanics
The compute-intensive inference endpoint `POST /api/v1/inference/predict-frame` is exposed to the public internet without authentication or request rate-limiting, allowing unauthorized callers to trigger CPU/GPU exhaustion and denial-of-wallet.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_predict_frame_POST`
1. `fn_storage_backups_api-main-before-integration_py_predict_frame`

#### Static AST Evidence
- File/path parameter names detected: ['file']
- Source location: storage/backups/api-main-before-integration.py:480-556

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Add API key or session token verification to authenticate callers.
2. Implement rate-limiting middleware (e.g. `slowapi` or Redis token bucket) to throttle request frequency per client IP.
3. Enforce maximum payload size limits on input telemetry arrays.

---

### [TR-AUTH-127] Unauthenticated Sensitive Route Exposure on POST /api/v1/chat
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/chat`
- **Source:** `storage/backups/api-main-before-integration.py:564-596`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/chat` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_query_chat_POST`
1. `db_ep_storage_backups_api-main-before-integration_py_query_chat_POST`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/chat`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-128] Unauthenticated Sensitive Route Exposure on POST /api/v1/internal/events
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/internal/events`
- **Source:** `storage/backups/api-main-before-integration.py:604-646`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/internal/events` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_internal_create_event_POST`
1. `fn_storage_backups_api-main-before-integration_py_internal_create_event`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/internal/events`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-129] Unauthenticated Sensitive Route Exposure on POST /api/v1/internal/events/{event_id}/extend
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/internal/events/{event_id}/extend`
- **Source:** `storage/backups/api-main-before-integration.py:650-670`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/internal/events/{event_id}/extend` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_internal_extend_event_POST`
1. `fn_storage_backups_api-main-before-integration_py_internal_extend_event`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/internal/events/{event_id}/extend`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---

### [TR-AUTH-130] Unauthenticated Sensitive Route Exposure on POST /api/v1/internal/events/{event_id}/verification
- **Category:** AUTHENTICATION
- **Severity:** HIGH
- **Confidence:** HIGH
- **Endpoint:** `POST /api/v1/internal/events/{event_id}/verification`
- **Source:** `storage/backups/api-main-before-integration.py:674-704`

#### Root Cause & Exploit Mechanics
Sensitive or state-modifying endpoint `POST /api/v1/internal/events/{event_id}/verification` does not enforce authentication. Unauthorized callers can trigger operations or retrieve private data without providing credentials or session tokens.

#### Attack Path Hops (APM Traversal)
1. `ep_storage_backups_api-main-before-integration_py_internal_verify_event_POST`
1. `fn_storage_backups_api-main-before-integration_py_internal_verify_event`

#### Static AST Evidence
- State-changing: True
- Sensitive data indicator: False
- No auth middleware or dependency detected

#### Runtime Behavioral Evidence
- Static Attack-Path Model verified vulnerable control boundary. Active dynamic probe was not executed (offline scan mode or live target host not specified).

#### Concrete Remediation Plan
1. Mount authentication dependency `Depends(get_current_user)` or security middleware on `POST /api/v1/internal/events/{event_id}/verification`.
2. Reject unauthenticated requests with HTTP 401 Unauthorized.

---
