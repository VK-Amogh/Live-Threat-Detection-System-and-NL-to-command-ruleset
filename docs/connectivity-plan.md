# SafeSpace connectivity: one ecosystem on any network
## Implementation plan

| | |
|---|---|
| Status | Proposed, for review |
| Date | 2026-10-17 |
| Question answered | What is the best, scalable way to connect every phone (APK), the dashboard and the laptop server, whether they share iBus Wi-Fi, use your own hotspot, or sit on completely different networks or mobile data? |
| Scope | Network layer, server exposure, authentication per route, app connection logic, media behaviour per route. No changes to detection or rules. |
| Relationship to `plan.md` | Replaces `plan.md` §5.1 (connectivity). In particular it **reverses** its advice to set the Wi-Fi profile to Private: iBus is an open network and must stay Public (§2). |
| Numbers | Latency, bandwidth and cost figures are estimates until measured in Phase 0. Vendor limits are cited in §10 and must be rechecked before relying on them. |

**How this plan reads your request.**
- **"iBus"** is the `iBus Wi-Fi` network the laptop is on now.
- **"Open network of our own internet"** is your own hotspot (today `Nothing Phone (4a)_7495`, `10.11.229.0/24`), **plus** any other internet connection a device happens to have: home Wi-Fi, another Wi-Fi, 4G/5G.

The plan supports all of them at once, with no code change when you move between them.

---

## 1. Recommendation in one page

**Use route-agnostic devices over three routes. The app picks the best route automatically.**

| Route | When it is used | How devices reach the laptop | Encryption | Installs needed |
|---|---|---|---|---|
| **R1. Trusted LAN** | Devices on *your own* network (your hotspot) | `https://<laptop-lan-ip>:8443`, found by UDP discovery | TLS with a certificate pinned in the APK | APK only |
| **R1b. iBus LAN, token-only** (zero-cost iBus option; only if Phase 0 test N1 shows iBus lets devices reach each other) | Devices on iBus with only the APK | `https://<laptop-ibus-ip>:8443`. The address comes from a dashboard QR code (iBus DHCP can change it); no discovery reply on iBus. | Same pinned TLS as R1 | APK only |
| **R2. Private mesh: Tailscale** (recommended default) | Anywhere: iBus, your hotspot, home Wi-Fi, mobile data | One stable name, e.g. `safespace-laptop.<tailnet>.ts.net`, and a `100.x` address | WireGuard end to end | APK + the Tailscale app on each device |
| **R3. Your own relay** (APK only, anywhere) | Anywhere, when a device can't or won't run Tailscale | `https://safespace.<your-domain>`, a small VPS you control; the laptop dials out to it | TLS to the VPS + WireGuard from the VPS to the laptop | APK only |

**Which one to choose depends on one constraint, so here are both answers:**

- **If every phone may install and sign into the Tailscale app: run R2 for everything, with R1 as the offline fallback on your own
  hotspot.**
  - This is the strongest option. Nothing is exposed to the internet.
  - Devices connect directly peer to peer when the network allows it, and through Tailscale's encrypted relays when it doesn't.
    That includes iBus even if it blocks device-to-device traffic.
  - One address works everywhere. The free Personal plan was reported in 2026 as 6 users with unlimited devices (§10).
  - It also solves the "every device on a different network" case with no server to run.
- **If the APK alone must be enough: run R3 as the internet route, plus R1 on your own hotspot.** R3 costs a small monthly VPS and a
  domain (or a free dynamic-DNS name), but it carries live video legitimately. Cloudflare Tunnel's public hostnames and Tailscale
  Funnel don't (§2.4).
- **If you only need iBus, APK only, at no cost: use R1b,** provided test N1 shows iBus lets devices reach each other.
  - Traffic is encrypted with the pinned certificate, so nobody on the open network can read it.
  - Access is device-token only: no password login, no enrollment code and no discovery on iBus. The baked `admin123` is useless
    to strangers who find the port.
  - Devices join by scanning a QR code on the dashboard.
  - If iBus isolates clients, R1b is impossible and iBus devices must use R2 or R3.
- **You can run several at once.** Your own devices use R2, guest or extra phones use R3 or R1b. The app races every route it knows
  and keeps the best (§5).
- **The current hotspot-only behaviour stays available as a mode, not deleted** (§4.0). You choose between "own hotspot only",
  "iBus" and "anywhere".

**What must not happen:** plain HTTP across iBus. It is an open, unencrypted network (§2.1). Anyone nearby can capture the
`admin123` login, every device token and every camera frame.

**Everything else in this plan** is the same whichever route you pick:
- removing the hotspot-only lock that exists in the code today;
- deciding what each route may do (password login, enrollment);
- making the server safe behind a proxy;
- the app's route manager;
- adapting video quality to the route.

---

## 2. Findings that drive the design

### 2.1 The network you are on (measured on 2026-10-17)

| Fact | Evidence | Consequence |
|---|---|---|
| The laptop is on **`iBus Wi-Fi`**, `10.12.253.133/16`, gateway `10.12.0.1`, DHCP | `netsh wlan show interfaces`, `Get-NetIPAddress` | The laptop's address can change. A hardcoded IP is brittle on iBus. |
| **iBus is an open network: Authentication `Open`, Cipher `None`** | `netsh wlan show profile name="iBus Wi-Fi"` | Every unencrypted packet is readable by anyone in range: logins, tokens, camera frames, chat. On iBus, traffic must be end-to-end encrypted. |
| Windows classifies iBus as **Public** | `Get-NetConnectionProfile` | Correct for an open network. **Keep it Public.** |
| A phone→laptop request on iBus (`10.12.253.129` → `.133`) **timed out** in the phase-6 test | `tests/phase6_phone_gate.md` | Either a firewall mismatch (next row) or iBus blocks traffic between its clients ("client isolation"). Not yet known; Phase 0 test N1. |
| The Allow rules are for `…\uv\python\cpython-3.11.15-…\python.exe`, but the running server (PID 4060) is `…\uv\python\cpython-3.11-…\python.exe` | `Get-NetFirewallApplicationFilter`, `Get-CimInstance Win32_Process` | Program-path rules may not match the server binary. Port-plus-subnet rules remove that ambiguity (§6). |
| Tailscale, cloudflared, ngrok, ZeroTier, WireGuard and Caddy are all **not installed** | `Get-Command` | Every remote route is new work. |

### 2.2 The code today: a hard lock to one hotspot

Someone has added a network lock that allows **only** the Nothing Phone hotspot. It is enforced on both sides:

| Where | What it does | Effect on iBus and other networks |
|---|---|---|
| `services/api/app/network_guard.py` | `is_client_ip_allowed()` accepts only `10.11.229.0/24` and loopback. `check_request_allowed()` runs on **every HTTP request** (the `security_headers` middleware in `main.py`) and `check_websocket_allowed()` on the event socket (`main.py` ~line 381). `ENFORCE_NOTHING_WIFI` defaults to `true` (`settings.py`). | Every phone on iBus (`10.12.x.x`), mobile data or another Wi-Fi gets **403** |
| `services/api/app/discovery.py` | The UDP responder on `:47800` ignores any sender outside `10.11.229.0/24` | Discovery is silent on iBus |
| `apps/mobile/lib/core/config.dart` `NothingWifiSocketOverrides`, installed globally in `main.dart` | Throws `NETWORK_LOCK_VIOLATION` for any host not starting with `10.11.229.` | The app **cannot** talk to a Tailscale address, a relay domain, or the laptop's iBus address |
| `apps/mobile/lib/core/connection_resolver.dart` | Candidates must start with `http://10.11.229.`; discovery broadcasts only to `10.11.229.255` | Only the hotspot is ever found |
| `AppConfig` strings in about 8 screens (`app.dart`, `pairing_screen.dart`, `status_screen.dart`, `chat_screen.dart`, `rules_screen.dart`, `auth_store.dart`) | UI copy says "locked to Nothing Phone (4a)_7495" | Must become route-neutral |

Three further defects in that lock:
- **The SSID/BSSID headers it checks are supplied by the client** (`X-SafeSpace-Wifi-SSID`/`-BSSID`), so they prove nothing.
- **`get_host_wifi_status()` reports the hotspot SSID as "detected" even when it was not** (`detected_ssid or NOTHING_PHONE_WIFI_SSID`). The System screen can therefore claim the laptop is on the hotspot while it is on iBus.
- **Loopback is always allowed.** That is harmless today, but the moment a local tunnel or proxy forwards internet traffic from `127.0.0.1`, every internet client would pass the guard.

### 2.3 Server behaviour that breaks behind any proxy or tunnel

| Code | Problem behind a proxy | Fix (§6.3) |
|---|---|---|
| `throttle()` keys on `request.client.host` (`main.py` ~line 187) | All internet clients share one bucket: one attacker locks everyone out of login, or the limit stops protecting anything | Use the forwarded client IP from a trusted proxy only |
| Cookie origin check compares `Origin` with `request.base_url` (`security.py` ~line 160) | Behind HTTPS, `base_url` is `http://127.0.0.1:8000`, so dashboard writes from `https://safespace.<domain>` get **403** | Honour `X-Forwarded-Proto/Host` from a trusted proxy; add the public origins to `ALLOWED_ORIGINS` |
| `pairing_code` `qr_payload` uses `request.base_url` (`main.py` ~line 313) | The QR code encodes `http://127.0.0.1:8000` | Encode the route list from config |
| `COOKIE_SECURE` defaults to `false` | Session cookies sent without `Secure` over HTTPS | `true` whenever the request scheme is HTTPS |
| `worker_auth` (`rule_routes.py:43`) checks only the internal token. `/api/v1/internal/*` sits on the public app (`main.py` ~line 1024). | Internal routes become internet-reachable through any tunnel, protected only by one token | A separate loopback-only listener for internal routes (§6.2) |
| Password login and code enrollment are reachable on every route | With credentials baked into the APK (`admin123`, the enrollment code in `config.dart`), anyone who can reach the server and has the APK can sign in | Per-route auth policy (§4.2) |

### 2.4 Vendor constraints checked on the web (details and sources in §10)

| Option | Constraint | Verdict |
|---|---|---|
| Cloudflare Tunnel (public hostname) | Cloudflare's own docs say public-hostname traffic on Free/Pro/Business plans falls under its video restriction: video only through paid products. The restriction does not apply to private-network routes, which need Cloudflare's WARP client on each device. Request bodies were reported as limited to 100 MB on Free/Pro (community reports, unverified in official docs). | **Not for live video.** Acceptable only for the dashboard and API without video, which is too awkward to be worth it here. |
| Tailscale Funnel | Ports 443, 8443 and 10000 only; "non-configurable bandwidth limits"; traffic goes through Tailscale's relays | **Not for live video.** Possible for alerts and chat only. |
| Tailscale (private tailnet) | Free Personal plan reported in 2026 as 6 users, unlimited devices (third-party sources; verify on Tailscale's pricing page). Android runs only one VPN at a time, so Tailscale can't run alongside another VPN app. | **Recommended for devices you own.** |
| A relay on your own VPS | You choose the bandwidth; no third-party content terms on the traffic; you run a small server | **Recommended for APK-only remote access.** |

---

## 3. Target architecture

```
                 ┌──────────────────────────── Laptop (the only SafeSpace server) ────────────────────────────┐
                 │  API listener  (TLS 8443 on trusted LAN · plain 8000 on loopback/tailnet only)              │
                 │  Internal listener 127.0.0.1:8010  (/internal/* for workers, never exposed)                 │
                 │  Network policy: classify each request → route + allowed actions                            │
                 │  Tailscale node  safespace-laptop (100.x)      WireGuard tunnel → relay VPS (10.66.0.2)     │
                 └───────▲──────────────────────────▲─────────────────────────────────────▲──────────────────┘
                         │ R1 trusted LAN            │ R2 tailnet (direct P2P or relayed)   │ R3 relay
                         │ (your hotspot only)       │                                      │
          ┌──────────────┴───────┐       ┌───────────┴─────────────┐          ┌─────────────┴──────────────┐
          │ Phones on your       │       │ Phones/laptops with the │          │ VPS  safespace.<domain>     │
          │ hotspot              │       │ Tailscale app, any net: │          │ Caddy (Let's Encrypt TLS,   │
          │ (APK only)           │       │ iBus, home, 4G/5G       │          │ WebSocket proxy)            │
          └──────────────────────┘       └─────────────────────────┘          │ → WireGuard → laptop        │
                                                                              └─────────────▲──────────────┘
                                                                                            │ HTTPS/WSS
                                                                              Phones with APK only, any network;
                                                                              browsers on any machine (dashboard)
```

**Invariants**
1. **The application protocol is identical on every route:** REST, the event WebSocket with tickets, the publish/view WebSockets, NDJSON chat. Media URLs stay relative (`/api/v1/...`), as they already are, so any base URL works.
2. **Identity, not network, is the security boundary.** Device tokens, revocation and device approval decide access. The network route only *restricts further* (§4.2).
3. **Nothing on iBus reaches the server in clear text.** On iBus a device uses R1b (pinned TLS), R2 or R3, never plain HTTP.
4. **The laptop never needs an inbound port from the internet.** R2 and R3 are both outbound from the laptop. This matters on iBus and on mobile hotspots, where inbound connections are often impossible.

---

## 4. Network profiles and per-route policy

### 4.0 Network mode: one explicit setting
The hotspot lock was added recently, outside this planning session, and may reflect a deliberate choice. Rather than deleting it,
`NETWORK_MODE` in `.env` makes it one of three selectable modes. The dashboard System screen shows the active mode, and changing it
needs a server restart.

| Mode | Routes accepted | Equivalent today |
|---|---|---|
| `hotspot_only` | loopback + `trusted_lan` (your hotspot) | The current `ENFORCE_NOTHING_WIFI=true` behaviour, minus the spoofable SSID headers |
| `ibus` | `hotspot_only` + `ibus_lan` (R1b, token-only) + `tailnet` | — |
| `anywhere` | everything in `ibus` + `relay` (R3) | — |

### 4.1 Configuration replaces the hardcoded lock

`config/network.yaml` (new; addresses are data, secrets stay in `.env`):

```yaml
profiles:
  trusted_lan:                     # your own hotspot / home router
    cidrs: ["10.11.229.0/24"]      # add your home LAN here; several allowed
    label: "Your network"
  ibus_lan:                        # R1b — only active in NETWORK_MODE=ibus|anywhere, TLS listener only
    cidrs: ["10.12.0.0/16"]
    label: "iBus (encrypted, paired devices only)"
  tailnet:
    cidrs: ["100.64.0.0/10", "fd7a:115c:a1e0::/48"]
    label: "Private mesh (Tailscale)"
  relay:
    proxies: ["10.66.0.1"]          # the VPS's WireGuard address; only it may send X-Forwarded-*
    public_origin: "https://safespace.example.com"
    label: "Relay"
  loopback:
    cidrs: ["127.0.0.0/8", "::1/128"]
    label: "This laptop"
# anything else (iBus 10.12.0.0/16, strangers) = untrusted → rejected by policy and firewall
```

### 4.2 What each route may do

| Capability | loopback (dashboard on the laptop) | trusted_lan | ibus_lan (R1b) | tailnet | relay | untrusted (unknown) |
|---|---|---|---|---|---|---|
| Password login (`/auth/login`) | yes | yes | **no** | yes | **no**: device token or QR pairing only | rejected |
| Camera enrollment with the baked code (`/devices/enroll`) | yes | yes | **no** | yes | **no** | rejected |
| Single-use QR pairing code from the dashboard (existing `/auth/pair`) | yes | yes | yes (the QR carries the current iBus IP + certificate pin) | yes | yes (10-min, single-use) | rejected |
| Everything else with a valid device token | yes | yes | yes, **TLS listener only** | yes | yes | rejected |
| UDP discovery answered | — | yes | **no**: never announce the server on an open network | no (not needed) | no | no |
| Default live-video ladder cap | full | full | full (measure in N3) | full when direct, reduced when relayed | reduced (§7) | — |

**Why this works with baked credentials.** `admin123` and the enrollment code inside the APK only work on networks you control
(your hotspot, your tailnet). From the internet (R3), a new device joins only with a short-lived QR code shown by an
already-signed-in admin, and then holds a revocable device token. Extracting the password from the APK gains an attacker nothing
remotely.

**New-device approval (optional, recommended once more than 2–3 people use the system).** A device that joins by enrollment starts
as *pending*. An admin approves it with one tap on the dashboard or an admin phone, which sees the device name, model, route and
time. Approval is audit-logged.

### 4.3 How the server classifies a request
1. Take the peer address (`request.client.host`). It is a TCP peer, so it can't be spoofed across networks.
2. If it is a configured relay proxy, read `X-Forwarded-For/Proto/Host`. Otherwise, **ignore those headers**.
3. Match the address against the profile CIDRs. The result sets `request.state.route ∈ {loopback, trusted_lan, tailnet, relay}`, or
   the request is rejected as untrusted.
4. Expose the route to clients in `/health/identity` (a "you are connected via …" field) and record it in device telemetry, so the
   Devices screen shows how each device is connected.

Client-supplied SSID/BSSID headers are **removed** as a control. Android needs location permission to read the SSID, and the value
proves nothing.

---

## 5. App: the route manager (replaces the hotspot lock)

**Delete**
- `NothingWifiSocketOverrides` and its global installation in `main.dart`.
- The `10.11.229.` filters in `connection_resolver.dart`.
- The lock wording in every screen.

**Add `RouteManager` (`lib/core/net/route_manager.dart`)**

1. **Known routes.** The bootstrap list is baked at build time from `.env` through `--dart-define-from-file`:
   - trusted LAN: discovered, plus the last-known hotspot IP;
   - Tailscale MagicDNS name;
   - relay URL.

   After the first connection, the server's signed route list from `/health/identity` replaces the baked one. New routes then reach
   devices without rebuilding the APK.
2. **Racing.** Probe every route in parallel: `GET /health/identity?nonce=…` with a 2 s timeout. Accept only the baked `SERVER_ID`
   and a correct `HMAC(server_secret, nonce)`. Rank by measured RTT, then by route preference (trusted LAN > tailnet > relay).
3. **Sticky with hysteresis.** Switch only when the current route fails 2 consecutive probes, or another route has been ≥ 40 % faster
   for 30 s. This prevents flapping between Wi-Fi and the tailnet.
4. **Re-resolve on network change.** The `connectivity_plus` listener fires on Wi-Fi ↔ cellular and on Wi-Fi network changes. On a
   route change, every socket (events, publish, view, chat) reconnects with a fresh ticket. Missed events are recovered by the
   existing change feed (`/changes?after=`).
5. **TLS per route.**
   - Trusted LAN: pinned self-signed certificate. The SHA-256 is baked into the APK; `HttpClient.badCertificateCallback` compares
     it, and pinning failure is a hard error.
   - Tailnet: WireGuard already encrypts, so `http://` is acceptable. If `tailscale cert` is set up, use `https://<name>.ts.net`.
   - Relay: normal public TLS (Let's Encrypt).

   `ws://` vs `wss://` follows the scheme, as `ws_client.dart` already does.

   **The Dart pin does not cover native media.** `video_player` (ExoPlayer) plays clips and recordings through Android's own TLS
   stack, not Dart's `HttpClient`, so a `badCertificateCallback` pin never applies to it. Without the following, clip and recording
   playback fails on R1/R1b:
   - Ship the local CA certificate in `android/app/src/main/res/raw/`.
   - Trust it in `res/xml/network_security_config.xml` with `<trust-anchors>`, scoped to the server, and reference that file from the
     manifest.
   - In the same file, decide cleartext: allow it only for the tailnet range (R2 over `http://100.x`), or use `tailscale cert` HTTPS
     and turn cleartext off everywhere. Today `usesCleartextTraffic="true"` allows it globally.
6. **Diagnostics screen.** For each route: reachable or not, RTT, the server-reported route, the TLS pin state. Plain-language
   causes, for example:
   - "On iBus without Tailscale: install Tailscale or use the relay."
   - "Wi-Fi blocks devices from reaching each other (client isolation)."
7. **No SSID reading** and no location permission.
8. **Camera role on mobile data:**
   - The app shows an estimated data use per hour for the current quality. At 640×360 @ 5 fps that is roughly 0.4–0.5 GB/h;
     measure in Phase 0.
   - A "Stream only on Wi-Fi" switch defaults to **on**.

---

## 6. Server and laptop changes

### 6.1 Remove the lock, keep a policy
- Replace `network_guard.py` with `network_policy.py` (§4).
  - The Nothing-specific constants move into `config/network.yaml` (`trusted_lan`).
  - `ENFORCE_NOTHING_WIFI` becomes `NETWORK_MODE=hotspot_only` (§4.0), so today's behaviour remains one setting away.
  - Remove the SSID/BSSID headers from CORS `allow_headers` and from the checks.
- Fix `get_host_wifi_status()` to report what it actually detects, or remove it.
- `discovery.py`: answer only senders in `trusted_lan` CIDRs. Include the route list and server id, signed with the server secret.

### 6.2 Listeners
| Listener | Bind | Purpose |
|---|---|---|
| Public API (TLS) | `0.0.0.0:8443`, firewall-scoped to trusted-LAN CIDRs | R1 |
| Public API (plain) | `127.0.0.1:8000` and the Tailscale address `100.x:8000` | Dashboard on the laptop, R2, and the R3 WireGuard peer (`10.66.0.2:8000`) |
| Internal API | `127.0.0.1:8010` only | `/api/v1/internal/*` for rule workers, the reasoner and the recorder; never routed by any tunnel |

The event-socket broadcast lives in one process's memory (D-003), so these must **not** be separate processes. A small launcher
(`services/api/serve.py`) builds one `uvicorn.Server` per bind address and runs them together in a single event loop with
`asyncio.gather(...)`:
- the public servers serve `app.main:app`, with `proxy_headers`/`forwarded_allow_ips` set only on the relay-facing one;
- the internal server serves a separate FastAPI app holding only the `/internal/*` routers;
- both share the same process memory.

Simpler interim step: bind `0.0.0.0:8000` and rely on the policy middleware plus the firewall scope. Even then, move internal routes
to their own `127.0.0.1:8010` server.

### 6.3 Proxy safety (needed for R3)
- Start uvicorn with `--proxy-headers --forwarded-allow-ips 10.66.0.1`, so only the relay may forward.
- In code, read the real client IP, scheme and host via the policy. Use them in `throttle()`, the cookie origin check, `qr_payload`,
  device telemetry and audit.
- `COOKIE_SECURE=true` for HTTPS requests. `ALLOWED_ORIGINS` gains the relay origin and the tailnet HTTPS name.
- WebSocket heartbeat ≤ 25 s on every socket (the event socket uses 20 s today; apply the same to publish and view). Proxies and NAT
  mappings drop idle connections.
- Uploads through the relay use **chunked, resumable uploads** (e.g. 8 MB parts with an upload id). `MAX_UPLOAD_MB=500` single-body
  uploads stay for loopback and LAN. Caddy has no body cap by default, but mobile networks fail long single requests.

### 6.4 Windows firewall (you apply these; the plan does not change system settings automatically)
- **Keep iBus on the Public profile.**
- Replace program-path rules with **port rules scoped to remote address**:
  - TCP 8443 from `trusted_lan` CIDRs only, on the profile your hotspot uses.
  - UDP 47800 from `trusted_lan` CIDRs only.
  - TCP 8000 from `100.64.0.0/10` only, on the Tailscale interface.
  - Nothing on iBus, unless R1b is enabled. Then add TCP 8443 (TLS listener) from `10.12.0.0/16` only, and never 8000 or 47800.
- `scripts/network-setup.ps1` (new, run once as administrator) prints each rule before applying it. `scripts/doctor.ps1` shows the
  profile, the listeners, the rule scopes, and a self-test on every route.

### 6.5 R2 setup (Tailscale)
1. Install Tailscale on the laptop and sign in. Set the machine name to `safespace-laptop`. Enable MagicDNS. Optionally run
   `tailscale cert` for HTTPS.
2. Disable key expiry for the laptop node, so the server never silently drops off the tailnet.
3. Phones: install Tailscale and sign in with the same account. Other people can be invited as users (free plan: 6 users, per 2026
   reports) or shared the single laptop node.
4. ACL policy: tagged `tag:safespace-server` accepts TCP 8000 from `autogroup:member`. Nothing else is open.
5. `/health/identity` reports `route=tailnet` and whether the path is direct or relayed. `tailscale status --json` on the laptop
   gives each peer's path, shown on the Devices screen.

### 6.6 R3 setup (your relay)
1. A small Linux VPS in an Indian region (Mumbai/Bengaluru) to keep added latency low, with a domain or a free dynamic-DNS name
   pointing at it.
2. **WireGuard:** the VPS is `10.66.0.1`, the laptop `10.66.0.2`. The laptop runs the official WireGuard Windows client as a service
   with `PersistentKeepalive=25`, so it dials out from any network (iBus, hotspot) and needs no inbound port.
3. **Caddy** on the VPS: `safespace.<domain>` → `reverse_proxy 10.66.0.2:8000`. Automatic Let's Encrypt; WebSocket upgrade works by
   default; access logs off for media paths.
4. Hardening:
   - The VPS firewall opens only 443/tcp and the WireGuard UDP port.
   - Fail2ban or Caddy rate limits on `/auth/*`.
   - `scripts/relay/` contains the Caddyfile, `wg0.conf` templates and a setup README. Keys come from `.env` and are never
     committed.
5. Capacity: relay bandwidth = camera uplinks through the relay + viewer downlinks. One remote camera at about 1 Mbps around the
   clock is roughly 320 GB per month. Pick a VPS plan accordingly (§7).
6. **If UDP is blocked.** WireGuard is UDP-only, and open public Wi-Fi such as iBus often blocks outbound UDP on non-standard
   ports. Unlike Tailscale, WireGuard has no TCP fallback.
   - First try the WireGuard port on 443/udp.
   - If test N5 shows outbound UDP blocked from iBus, replace WireGuard with a **TLS reverse tunnel over TCP 443**: rathole or frp
     with TLS, the laptop as client, Caddy unchanged on the VPS.
   - The app and server don't change; only the laptop↔VPS leg does.

---

## 7. Media behaviour per route

| Route | Camera publish (ladder top) | Live view default | Notes |
|---|---|---|---|
| loopback / trusted LAN | 960×540 @ 10 fps | same | Unchanged from today's design |
| tailnet, direct | 960×540 @ 10 fps | same | `tailscale status` shows "direct" |
| tailnet, relayed (Tailscale relay servers) | 640×360 @ 6 fps | 640×360 @ 5 fps | Relayed paths add latency and have lower throughput |
| relay (R3) | 640×360 @ 6 fps | 640×360 @ 5 fps; grid uses 2-s thumbnails | Each remote viewer uses laptop uplink + VPS bandwidth |
| any route, camera on mobile data | 640×360 @ 5 fps, data counter visible | — | "Stream only on Wi-Fi" defaults on |

- The server picks the starting ladder step from `request.state.route`. The existing flow-control and ladder logic then adapts to
  measured throughput.
- **Recording always happens on the laptop at whatever quality arrives.** A remote camera's recording is only as good as its uplink,
  and the camera tile says so.
- **The laptop's uplink is the real limit for remote viewers.** On iBus that uplink is shared and unknown (Phase 0 test N3). The
  server caps concurrent remote viewer streams (default 3) and serves extra viewers 2-s thumbnails instead of live frames, with a
  plain message.
- Alerts, chat and the change feed are small and unaffected by the route. Notification latency gains roughly one extra network
  round trip on R2-relayed or R3.

---

## 8. Delivery plan

### Phase 0: Measure before building (½–1 day)
| Test | How | Decides |
|---|---|---|
| N1. Does iBus block phone↔laptop traffic (client isolation)? | You temporarily allow inbound TCP 8000 from `10.12.0.0/16`. Run a throwaway `python -m http.server` on the laptop (not SafeSpace) and request it from a phone on iBus. Remove the rule afterwards. | Whether direct LAN is even possible on iBus (it still must not carry plain HTTP) |
| N2. Captive portal on iBus? | Fresh phone joins iBus; check whether a login page appears before internet works | Whether Tailscale/relay work immediately after joining |
| N3. Laptop up/down throughput on iBus and on your hotspot | Any speed test | Remote viewer cap and relay ladder |
| N4. Tailscale path on iBus | Install on laptop + one phone; `tailscale ping` and `tailscale status` show direct vs relayed and RTT | Default quality on iBus |
| N5. WebSocket through the relay, **with the laptop on iBus** | Trial VPS: first check that WireGuard's UDP port gets out of iBus (handshake shown by `wg show`), then run the publish/view sockets for 30 min | R3 viability; WireGuard or the TCP-443 reverse-tunnel fallback (§6.6) |
| N6. Mobile-data usage per hour of camera streaming | Phone data counter at each ladder step | The in-app estimate (§5) |

**Exit:** results written to `tests/phase0_connectivity.md`; R2 and/or R3 chosen.

### Phase 1: Route-agnostic core (2–3 days)

*Server*
- `config/network.yaml` + `network_policy.py`; delete the Nothing lock.
- Per-route auth policy (§4.2).
- Internal listener on `127.0.0.1:8010`.
- Proxy-header handling (`throttle`, cookie origin check, `qr_payload`, secure cookies).
- Signed route list in `/health/identity`.
- Discovery restricted to trusted LAN.
- Device route in telemetry.

*App*
- Delete `NothingWifiSocketOverrides` and the subnet filters.
- `RouteManager`: racing, hysteresis, re-resolve on network change, socket reconnects.
- Diagnostics screen; route-neutral copy.

*Build*
- `scripts/build-apk.ps1` writes the dart-define file from `.env`: server id, routes, TLS pin, enrollment code, accounts.

**Exit:**
- Unit tests for classification (spoofed `X-Forwarded-For` from a non-proxy is ignored; iBus addresses rejected).
- The app connects over loopback (`adb reverse`) and the hotspot with no code change.

### Phase 2: R2 Tailscale (1–2 days)
- Laptop and phone setup (§6.5), the ACL, and the firewall rule for `100.64.0.0/10`.
- Tailnet route in the APK defines.
- Devices screen shows the path (direct or relayed) and RTT.

**Exit:** a phone on iBus and a phone on 4G both stream and view live, get alerts and chat. Measured latencies recorded.

### Phase 3: R1 and R1b TLS on your hotspot and iBus (1–2 days)
- `setup.ps1` generates a local CA and server certificate. The API serves TLS on 8443.
- The certificate pin goes into the APK (Dart), and the CA goes into `network_security_config.xml` (native media).
- The dashboard on another laptop trusts the local CA, or uses the tailnet HTTPS name instead.
- R1b, only if N1 passed:
  - the `ibus_lan` profile, token-only;
  - a QR pairing payload carrying the current iBus IP and the certificate pin;
  - the firewall rule for TCP 8443 from `10.12.0.0/16`, which **you** apply (§6.4).

**Exit:**
- No plain HTTP leaves the laptop on any network interface. Check with `pktmon` on the Wi-Fi adapter for port 8000.
- Clips and recordings play on R1/R1b.
- On R1b, password login and code enrollment return 403.

### Phase 4: R3 relay (2–3 days, if chosen)
- VPS, WireGuard, Caddy, `scripts/relay/` (§6.6).
- Chunked resumable uploads.
- QR pairing flow for relay-only devices; optional new-device approval.

**Exit:** a phone with only the APK, on 4G, pairs with a QR code from the dashboard, then streams, views, gets alerts and chats.
Password login over the relay returns 403.

### Phase 5: Media per route (1–2 days)
- Route-based ladder start, remote-viewer cap with thumbnail fallback, mobile-data estimate and the Wi-Fi-only switch.

**Exit:** §9 performance rows within target.

### Phase 6 (research, optional): Tailscale inside the APK
Embed Tailscale's userspace library (`tsnet`/`libtailscale`, built with gomobile) so the APK joins the tailnet without the Tailscale
app or Android's single VPN slot, using a pre-authorised, tagged, ephemeral key. This gives R2's benefits with APK-only install.
Costs:
- an estimated 20–30 MB larger APK;
- Go build tooling;
- background-lifetime work.

Spike only after Phases 1–5 are done.

---

## 9. Verification (done last)

### 9.1 Network × feature matrix
Run on two phones plus the dashboard. Every cell must pass, or be recorded as failing with the reason.

| Feature | Hotspot (R1) | iBus via R1b | iBus via R2 | iBus via R3 | 4G via R2 | 4G via R3 | Mixed: camera 4G, viewer iBus, dashboard laptop |
|---|---|---|---|---|---|---|---|
| Sign in / enroll (allowed only where §4.2 allows) | | | | | | | |
| Camera publish ≥ 5 fps for 10 min | | | | | | | |
| Live view, latency p95 | | | | | | | |
| Rule alert on a backgrounded phone, p95 from episode start | | | | | | | |
| Chat first token p95 | | | | | | | |
| Incident clip playback in the app (native player, TLS trust) | | | | | | | |
| Recording playback and seek | | | | | | | |
| Screenshot appears on all clients ≤ 2 s | | | | | | | |
| Video upload (chunked) 300 MB | | | | | | | |

### 9.2 Transitions and faults
| Scenario | Expected |
|---|---|
| Camera phone switches Wi-Fi → 4G mid-stream | Reconnects ≤ 10 s on the next route; one recording gap; no duplicate alerts |
| Laptop moves from hotspot to iBus | R1 disappears; R2/R3 devices keep working (the laptop dials out); discovery goes silent on iBus |
| Tailscale stopped on a phone | `RouteManager` falls back to R3 (if configured) ≤ 10 s |
| Relay VPS down | R2 and R1 devices unaffected; R3-only devices show the route as unreachable, with the reason |
| Laptop IP changes on the hotspot | Discovery re-finds it ≤ 15 s |
| Device token revoked | The device is signed out ≤ 5 s on every route |

### 9.3 Security checks
- **From a second device on iBus:** `nmap` against the laptop shows no SafeSpace port open. Capturing on the laptop's Wi-Fi adapter
  shows no plain HTTP to or from port 8000/8443 on iBus.
- **Over R3:**
  - `POST /auth/login` → 403.
  - `POST /devices/enroll` with the baked code → 403.
  - A forged `X-Forwarded-For` from a non-proxy peer is ignored.
  - `/api/v1/internal/*` is unreachable (404 or connection refused).
- **Login throttling** counts per real client IP behind the relay.
- **TLS pin mismatch** on R1 → the app refuses to connect.

### 9.4 Performance targets (to confirm against Phase 0 measurements)
| Metric | R1 / R2 direct | R2 relayed / R3 |
|---|---|---|
| Live view latency p95 | ≤ 700 ms | ≤ 1.5 s |
| Rule alert, episode start → phone notification p95 | ≤ 3.0 s | ≤ 3.5 s |
| Chat first token p95 | ≤ 2 s | ≤ 2.5 s |
| Route failover | ≤ 10 s | ≤ 10 s |

---

## 10. Sources (vendor facts used in §2.4 and §6)

- **Cloudflare video.** Cloudflare, "Delivering Videos with Cloudflare":
  https://developers.cloudflare.com/fundamentals/reference/policies-compliances/delivering-videos-with-cloudflare/
  Says Tunnel public-hostname traffic on Free, Pro and Business plans is subject to its video terms, and that the restriction does
  not apply to private network routes.
- Cloudflare blog, "Goodbye, section 2.8 and hello to Cloudflare's new terms of service": https://blog.cloudflare.com/updated-tos/
- **Cloudflare WebSockets.** "Using Cloudflare with WebSockets":
  https://developers.cloudflare.com/support/network/using-cloudflare-with-websockets/
  Covers the idle-timeout behaviour and recommends a client heartbeat.
- **Cloudflare upload limit.** Body limit on Tunnel/Free/Pro, reported as 100 MB in community threads (not confirmed in official
  docs): https://community.cloudflare.com/t/max-upload-size/630925
- **Cloudflare Access.** Free for up to 50 users: https://www.cloudflare.com/en-gb/products/zero-trust/access
  Service tokens: https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/
- **Tailscale Funnel.** Ports 443/8443/10000 and non-configurable bandwidth limits: https://tailscale.com/kb/1223/tailscale-funnel
- **Tailscale and other VPNs.** Android and iOS run one VPN at a time: https://tailscale.com/kb/1105/other-vpns
- **Tailscale free plan.** 6 users, unlimited devices after the April 2026 change; third-party, so verify on Tailscale's pricing page:
  https://www.ssdnodes.com/learn/is-tailscale-free-plan-limits
  The stale "3 users / 100 devices" figure appears at https://costbench.com/software/business-vpn/tailscale/free-plan

## 11. Open questions

| # | Question | Default if unanswered |
|---|---|---|
| C0 | Which network mode: `hotspot_only` (today's lock), `ibus` or `anywhere`? | `ibus` once Phase 1 lands; `hotspot_only` until then |
| C1 | May every phone install the Tailscale app? | Yes for your own phones (R2); R3 or R1b for anyone else |
| C2 | Are you willing to run a small VPS + domain for APK-only remote access? | Not until Phase 0; R2 first |
| C3 | Which networks count as "yours" (trusted LAN)? | Only the Nothing Phone hotspot `10.11.229.0/24` |
| C4 | Should new devices need one-tap approval by an admin? | Yes once more than 3 devices exist |
| C5 | Allow camera streaming over mobile data? | Off by default, per camera |
