# Part A: Security Findings

Static review of the repository: API (`services/api`), network policy and TLS, media hub, inference and rules workers, dashboard (`apps/dashboard`, `services/Dashboard`), Android app (`apps/mobile`), legacy `Model/` stack, infrastructure scripts and configuration.

Findings are listed by severity. Locations are given as `path:line`. Secret values are intentionally not reproduced.

## Contents

1. Critical / High (1-16)
2. Medium (17-33)
3. Mobile / Android (34-41)
4. Infrastructure, supply chain and repository hygiene (42-51)
5. Low (52-53)
6. Coverage and limitations

---

## 1. Critical / High

1. **Default admin credentials.** `admin1@safespace.com` and `admin2@safespace.com` with password `admin123` are created automatically on first boot if `SEED_ACCOUNTS` is unset (`services/api/app/security.py:40-43`). The same values appear in `.env.example:29` and `README.md:56`, and `scripts/setup.ps1:4` copies `.env.example` to `.env` unchanged.

2. **Password and one-click admin login shipped inside the clients.** The dashboard bundle, served without authentication, hardcodes `admin123` and renders "Continue as Admin 1/2" buttons (`apps/dashboard/src/App.tsx:36`, `apps/dashboard/src/App.tsx:91-114`). The server flag `DEMO_AUTOFILL_PASSWORD` does not control this. The APK bakes in the demo password and account list (`apps/mobile/lib/core/config.dart:20-22`, `scripts/apk_config.py:53-62`).

3. **Unauthenticated user enumeration.** `GET /api/v1/auth/seed-accounts` returns every account email, display name and role (`services/api/app/main.py:189-214`).

4. **Hardcoded shared secret (camera enrollment code).** It is the default in `services/api/app/settings.py:48`, `.env.example:30` and `apps/mobile/lib/core/config.dart:15`, and can be extracted from any APK. It is used for:
   - camera enrollment (`services/api/app/routes/devices.py:134`);
   - the server identity proof, because `SERVER_PROOF_KEY` falls back to it (`settings.py:49`);
   - the signed route list;
   - authentication of UDP discovery.

   Anyone who knows it can enroll a rogue camera, forge the server's identity, or forge route lists.

5. **Plain-HTTP password login and enrollment.** Both are allowed on `loopback`, `trusted_lan` and `tailnet` (`config/network.yaml:43-46`). Passwords, 30-day admin tokens and 365-day camera tokens cross the hotspot in clear. The session cookie is only marked `Secure` over HTTPS (`services/api/app/main.py:270`).

6. **"tailnet" route is the whole `100.64.0.0/10` carrier-grade-NAT range** (`config/network.yaml:32-34`). Every host in that range gets password login and enrollment; nothing verifies the peer is actually on Tailscale.

7. **Camera-token privilege escalation.**
   - A camera-scoped device can rewrite its own `camera_id` through the heartbeat or WebSocket telemetry, because `camera_id` is in the update allow-list (`services/api/app/database.py:513-534`, `services/api/app/routes/devices.py:177-217`, `services/api/app/routes/media.py:146-147`).
   - The publish ownership check only compares against that same field (`media.py:70-75`).
   - Result: a camera token can publish frames to any camera, spoofing or hijacking feeds.

8. **Mobile deep-link pairing hijack.**
   - `safespace://pair?...` links are redeemed with no user confirmation (`apps/mobile/lib/features/pairing/pairing_screen.dart:96-106`, `apps/mobile/android/app/src/main/AndroidManifest.xml:37-43`).
   - The server-id check is skipped when the link omits `s` (`apps/mobile/lib/core/net/pairing_link.dart:26`).
   - Attacker-supplied URLs and TLS pins are persisted (`apps/mobile/lib/core/net/route_manager.dart:105-113`).
   - The route manager prefers the fastest "verified" route, and the proof can be forged with the public secret (`route_manager.dart:166-200`).
   - The Bearer token is then sent to whichever route is active (`apps/mobile/lib/core/api_client.dart:22-30`, `apps/mobile/android/app/src/main/kotlin/com/safespace/safespace_mobile/AlertService.kt:108-115`).
   - A link with `r=camera` can enroll the phone as a camera for an attacker-controlled server.

9. **TLS pins are trusted globally.** The pin check ignores the hostname (`apps/mobile/lib/core/net/pinned_http.dart:43-48`). A pin learned from any link or route list is accepted for every host the app connects to.

10. **UDP discovery spoofing.** Discovery announcements are signed with the same public secret (`apps/mobile/lib/core/net/route_manager.dart:285-298`). Anyone on the LAN can inject routes and TLS pins.

11. **DNS rebinding and login CSRF.** There is no Host-header validation and no Origin check on `/auth/login` (`services/api/app/main.py:227`). `public_origin` trusts the Host header (`services/api/app/network_policy.py:215-217`). Combined with default credentials, a web page opened on the LAN can take over the plain-HTTP API.

12. **Unauthenticated information disclosure.**
    - `/docs`, `/redoc` and `/openapi.json` are enabled (`services/api/app/main.py:130`).
    - `/api/v1/health/identity` leaks the host Wi-Fi SSID and BSSID, local IPs, allowed subnets, TLS pins and server id (`main.py:161-186`, `network_policy.py:401-412`).

13. **Session token accepted in the URL.** MJPEG, snapshots, recordings and exports accept `?token=` (`services/api/app/routes/media.py:298`, `media.py:365`, `services/api/app/routes/recordings.py:91`). A 30-day admin token can leak through logs, browser history and Referer headers.

14. **Placeholder `INTERNAL_SERVICE_TOKEN=replace_me`** is accepted as a valid token if copied unchanged (`.env.example:27`). It guards the `/internal/*` routes and the detector (`services/api/app/rule_routes.py:44-47`, `services/inference/server.py:161-165`). One shared token is used by the API, detector, workers and reasoner.

15. **Pickle deserialization of model files.**
    - `torch.load(..., weights_only=False)` in `Model/backend/api.py:36` and `Model/backend/api.py:67`.
    - `torch.hub.load` of unpinned GitHub code (`api.py:34`, `api.py:40`).
    - Weights downloaded from Hugging Face with no revision or hash pin (`Model/backend/download_models.py:6`, `download_models.py:42-47`).
    - The main stack loads YOLO `.pt` files from `storage/models` (`services/inference/server.py:112`, `services/api/app/rule_routes.py:41`, `services/api/app/video_digest.py:183`).
    - A tampered weight file results in code execution.

16. **Legacy `Model/` stack has no authentication.** The API and Streamlit apps listen on `0.0.0.0` (`Model/docker-compose.yml:9-10`, `22-23`, `39-40`) with no upload size limit. Containers run as root, requirements are unpinned, and error text leaks internal paths (`Model/backend/api.py:276-283`).

---

## 2. Medium

17. **Path traversal through `camera_id` on Windows.** A backslash in the ID reaches preview, `*_live.jpg`, snapshot and recording paths (`services/api/app/routes/media.py:63`, `services/api/app/media/hub.py:315-320`, `services/api/app/media/recorder.py:165`, `recorder.py:259`). Admin tokens can name any camera, and finding 7 lets camera tokens do the same. Impact: `.jpg`/`.mp4` reads and writes outside `storage`.

18. **Memory DoS from frame metadata.** SSF1 width and height are trusted (`services/api/app/media/hub.py:88-132`), and the recorder resizes every frame to that size, up to 65535x65535 (`recorder.py:46-69`). JPEG decoding has no pixel cap (`hub.py:107`, `services/api/app/mobile_camera.py:265`).

19. **Unvalidated camera `connection_uri`.** `PATCH /cameras/{id}` accepts any URI (`services/api/app/main.py:711-715`, `contracts/src/td_contracts/cameras.py:18`), and `rtsp://` accepts any host. The URI goes straight to OpenCV/FFmpeg (`services/rules/capture.py:12`, `services/api/app/pipeline.py:228`), allowing SSRF, internal port scanning and possible local file reads.

20. **Untrusted media reaches FFmpeg, OpenCV and YOLO** with only an extension check, no content sniffing and no sandbox (`services/api/app/main.py:581-606`, `services/api/app/pipeline.py:156`). Eight concurrent jobs fill the queue (`main.py:587`), and there is no upload quota or cleanup.

21. **Destructive `/storage/sweep`.** The caller supplies the retention policy, so a single call can delete all recordings (`services/api/app/routes/recordings.py:311-321`, `services/api/app/media/sweeper.py:67-116`). The request body is an unvalidated dict.

22. **No role-based access control.** Every account is admin, and every paired "control" phone receives a full admin token (`services/api/app/main.py:388`). Any admin can change settings, including routing frames to a cloud provider (`main.py:998-1001`).

23. **Weak login and pairing protections.**
    - Throttling is per IP only, with no per-account lockout (`main.py:217-224`).
    - Failed logins are not audited.
    - Pairing codes are 32 bits (`main.py:358`).
    - Unknown users skip scrypt, so response time reveals valid emails (`main.py:233`).

24. **Sessions never expire while in use.** Admin sessions slide 30 days on every use (`services/api/app/security.py:133-137`); camera tokens last 365 days. There is no rotation or absolute lifetime.

25. **Low password-hash cost and no input cap.** scrypt uses N=2^14 (`security.py:23`), and the login password has no `max_length` (`contracts/src/td_contracts/auth.py:9`).

26. **Cloud exfiltration of CCTV data.** `ChatRequest.provider` can switch any request to Groq, which sends incident data and frames to api.groq.com (`services/api/app/chat.py:580`, `chat.py:628-640`, `services/api/app/review.py:42-45`).

27. **Prompt injection into the VLM and chat.**
    - Camera frames reach the VLM verifier, AI review, video digest and chat (`services/api/app/rule_verify.py:107-115`, `review.py:23-27`). Text held in front of a camera could steer or suppress verdicts.
    - Attacker-chosen `device_name` flows into the chat prompt as the camera name (`chat.py:246`).

28. **Threat detection can be blinded silently.**
    - A busy detector returns 429 (`services/inference/server.py:284-285`).
    - The API retries 8 times, then gives up (`services/api/app/pipeline.py:40-46`).
    - `_process_threat` swallows the error with no health event (`mobile_camera.py:244-245`).
    - Heavy uploads or floods can hide weapon/violence detection on live cameras.

29. **Resource exhaustion.**
    - Arbitrary `camera_id` values create hub channels and camera rows (`media.py:78-100`, `media.py:195`).
    - Many string fields have no length limit.
    - `TICKETS` and `APK_TOKENS` are only pruned on issue (`services/api/app/tickets.py:11-18`, `devices.py:42`).
    - No WebSocket or viewer caps, and no rate limits beyond login/pair.
    - Full-table event scans on each request (`main.py:482-491`, `recordings.py:164`, `recorder.py:175`, `chat.py:380`).
    - The unauthenticated `/health/identity` runs psutil and `netsh` on each call (`network_policy.py:293-303`, `347-367`).

30. **Missing hardening headers and a loose CORS list.** No CSP, HSTS or Permissions-Policy (`main.py:141-153`). CORS allows credentials from localhost dev origins (`settings.py:26-30`, `main.py:131-137`).

31. **Keys and data unencrypted at rest.** The CA key, server key, SQLite DB, recordings and pre-migration DB backups (which contain password hashes and sessions) are stored unencrypted (`services/api/app/tls.py:141-153`, `services/api/app/database.py:35-55`). The local CA is valid for 10 years and is unconstrained.

32. **Audit gaps.** Settings, camera, rule and password changes and failed logins are not logged. Several audit rows use `request.client.host` instead of the real client IP.

33. **Device identity and exposure.**
    - Device and camera IDs are `sha256(installation_id)[:12]` (`security.py:31-36`).
    - Re-enrolling with a known installation ID reissues a token and overwrites the camera row (`devices.py:104-119`).
    - `/devices` and `/devices/fleet` return `SELECT *`, exposing `installation_id`, SSID, BSSID and IP to every admin (`database.py:507-510`).

---

## 3. Mobile / Android

34. Cleartext traffic is allowed app-wide (`apps/mobile/android/app/src/main/AndroidManifest.xml:19`, `apps/mobile/android/app/src/main/res/xml/network_security_config.xml`).

35. The private CA is trusted for all domains in Android's native stack (same config), so a leaked `ca.key` enables MITM of the app.

36. The release build is signed with the debug key (`apps/mobile/android/app/build.gradle.kts:31-35`).

37. The APK is distributed over HTTP via a token in the URL, with no integrity or signature check (`services/api/app/routes/devices.py:282`, `devices.py:303-337`).

38. `AlertService` sends the Bearer token to every listed URL, including `http://`, using plain `HttpURLConnection` with no pinning (`AlertService.kt:44`, `AlertService.kt:108-115`). The token also persists in the redelivered intent (`AlertService.kt:66`).

39. Alert text is shown on the lock screen (`AlertService.kt:154-162`).

40. No `FLAG_SECURE`, and `allowBackup` is left at its default.

41. Event metadata is logged via `debugPrint` (`apps/mobile/lib/core/ws_client.dart:135-136`).

---

## 4. Infrastructure, supply chain and repository hygiene

42. `apps/mobile/.dart_defines.json` holds the enrollment code and demo password. It is untracked and not in `.gitignore`, so one `git add .` would commit it. `.trace/` is also untracked and unignored.

43. A Supabase URL and publishable key are hardcoded in `services/Dashboard/lib/supabase.ts:3-4`, and `ignoreBuildErrors: true` is set in `services/Dashboard/next.config.mjs:4`.

44. `docker-compose.yml:13` falls back to a default Postgres password.

45. `scripts/install-local-chat.py:24-41` downloads the latest Ollama release from GitHub with no checksum or signature check, then pulls an unpinned model.

46. Dependencies are unpinned or ranged with no lockfile or hashes (`requirements.txt`, `Model/*/requirements.txt`).

47. `infra/windows/firewall.ps1:4-9` opens port 8000 to any remote address on the Private profile.

48. `infra/systemd/td-api.service:9` binds `0.0.0.0` and references paths that do not exist (`app.main:app`, `services/inference/worker/main.py`). It has no sandboxing directives.

49. Security-critical files are untracked, so they have no history or review: `tls.py`, `network_policy.py`, `serve.py`, `discovery.py`, `routes/*`, `media/*`, `mobile_camera.py`, `llm_gateway.py`, `rule_verify.py`.

50. Trained weights (`.pt`) are committed under `Model/Notebooks/runs/**`, despite `*.pt` in `.gitignore`.

51. `services/api/app/network_policy.py:75-76` maps the peer name `testclient` to `127.0.0.1` in production code.

---

## 5. Low

52. UDP discovery replies are larger than the queries. They can only be reflected within allowed subnets, but the per-source reply bucket map has no size cap (`services/api/app/discovery.py:49-58`).

53. Detector stream state (`STREAMS`) is retained until its TTL expires, so many distinct `source_id` values grow memory in the interim (`services/inference/server.py:66-72`).

---

## 6. Coverage and limitations

- Static review only. No dynamic testing, fuzzing or dependency vulnerability scans (`pip-audit`, `npm audit`, Gradle) were performed.
- `.env` was not inspected, so it is unknown whether real secrets in use differ from the defaults documented above.
- Not reviewed in depth: `services/rules` engine/grammar internals, Flutter UI screens, notebooks, and the data/training scripts under `scripts/`.
- An earlier automated report under `.trace/` lists many routes as unauthenticated. Those were excluded because they are protected by the router-level dependency `APIRouter(dependencies=[Depends(authenticated)])` (`services/api/app/main.py:138`, `services/api/app/rule_routes.py:28`).
