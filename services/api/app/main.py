"""SafeSpace authenticated local server; serves the built dashboard and shared API."""
import asyncio
from datetime import datetime, timezone
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import json
import mimetypes
import re
from pathlib import Path
import secrets
import time
import uuid
import httpx
import psutil
from fastapi import FastAPI, APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from td_contracts import (
    LoginRequest,
    LoginResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    PairingCodeCreateRequest,
    PairingCodeCreateResponse,
    UserOut,
    WsTicketResponse,
    CameraCreate,
    CameraOut,
    CameraUpdate,
    EventOut,
    ChangesResponse,
    HumanVerificationRequest,
    ChatRequest,
    ChatResponse,
    SourceRecord,
    FrameResult,
    PasswordChange,
    RuntimeSettings,
    SystemSnapshot,
    IdentityHealthResponse,
)
from . import database as db, pipeline, chat, review, rule_routes, mobile_camera, settings as app_settings
from .discovery import start_discovery_server
from .llm_gateway import GATEWAY, P2_BACKGROUND
from .media.hub import HUB
from .media.recorder import RECORDER_MANAGER
from .media.sweeper import get_storage_summary
from . import network_policy as net, tickets
from .network_policy import check_request_allowed, check_websocket_allowed, classify_request, client_ip, get_host_wifi_status, require_capability
from .routes import compat as compat_routes, devices as devices_routes, media as media_routes, recordings as recordings_routes, rulesets as rulesets_routes
from .security import (
    authenticated,
    authenticated_any_scope,
    bootstrap,
    extract_token,
    check_password,
    create_session,
    digest,
    now,
    password_hash,
    session_for,
    stable_camera_id,
)
from .settings import (
    ROOT,
    STORAGE,
    INFERENCE_URL,
    INTERNAL_TOKEN,
    OLLAMA_URL,
    COOKIE_SECURE,
    ALLOWED_ORIGINS,
    MAX_UPLOAD,
    SERVER_ID,
    SERVER_NAME,
    PUBLIC_SERVER_URLS,
    DISCOVERY_PORT,
    ADMIN_TOKEN_DAYS,
    DEMO_AUTOFILL_PASSWORD,
)

SOCKETS = {}
TICKETS = tickets.TICKETS
ATTEMPTS = defaultdict(deque)


async def broadcast(envelope):
    async def send(ws, token):
        try:
            if not session_for(token):
                await ws.close(code=4401)
                SOCKETS.pop(ws, None)
                return
            await asyncio.wait_for(ws.send_json(envelope), 2)
        except Exception:
            SOCKETS.pop(ws, None)

    await asyncio.gather(*(send(ws, token) for ws, token in list(SOCKETS.items())))


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    bootstrap()
    pipeline.BROADCAST = broadcast
    rule_routes.BROADCAST = broadcast
    for source in db.all_objects('source'):
        if source['status'] in ('PENDING', 'RUNNING'):
            source.update(status='FAILED', error='Server restarted. Upload again or restart the camera.')
            db.put('source', source)
    for camera in db.all_objects('camera'):
        camera['is_online'] = False
        if camera.get('source_type') == 'PHONE':
            camera['desired_active'] = False
        db.put('camera', camera)
    for recording in db.all_objects('recording'):
        if recording['status'] == 'RECORDING':
            recording.update(status='INTERRUPTED', ended_at=now())
            db.put('recording', recording)
    discovery_transport = await start_discovery_server()
    warm = asyncio.create_task(chat.warmup())
    yield
    warm.cancel()
    if discovery_transport is not None:
        discovery_transport.close()
    await mobile_camera.shutdown()
    await pipeline.shutdown()


app = FastAPI(title='SafeSpace API', version='3.0.0', lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    allow_headers=['Content-Type', 'Authorization', 'X-SafeSpace-Wifi-SSID', 'X-SafeSpace-Wifi-BSSID'],
)
api = APIRouter(prefix='/api/v1', dependencies=[Depends(authenticated)])


@app.middleware('http')
async def security_headers(request: Request, call_next):
    try:
        check_request_allowed(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/api/v1/health/live')
async def health_live():
    return {'status': 'ok'}


@app.get('/api/v1/health/identity', response_model=IdentityHealthResponse)
async def health_identity(request: Request, nonce: str | None = Query(default=None, max_length=128)):
    """Who this server is, how this request reached it, and where else a device can find it.

    With ?nonce= the response carries an HMAC of the nonce under the shared secret, so an app can tell the genuine
    server from any other host that merely answers on the same address. The route list is signed the same way."""
    c = classify_request(request)
    document = net.route_document()
    return IdentityHealthResponse(
        server_id=SERVER_ID,
        server_name=SERVER_NAME,
        version='3.0.0',
        urls=[r['url'] for r in document['routes']],
        discovery_port=DISCOVERY_PORT,
        capabilities=['ssf1', 'mjpeg', 'ws_view', 'rulesets', 'dry_run', 'llm_gateway', 'route_policy', 'tls_pin', 'pairing_link'],
        wifi_lock=get_host_wifi_status(),
        route=c.route,
        route_label=c.label,
        mode=net.policy().mode,
        route_capabilities=c.caps.as_dict() if c.caps else {},
        routes=document['routes'],
        tls_pins=document['pins'],
        routes_json=document['routes_json'],
        routes_sig=document['routes_sig'],
        proof=net.identity_proof(nonce) if nonce else None,
    )


@app.get('/api/v1/auth/seed-accounts')
async def get_seed_accounts(request: Request):
    c = classify_request(request)
    if not (c.caps and c.caps.password_login):
        # Routes without password sign-in (iBus, relay) show no account tiles: pair with a link instead.
        return {'accounts': [], 'password_login': False, 'demo_autofill_password': False, 'route': c.route,
                'route_label': c.label, 'server_id': SERVER_ID, 'server_name': SERVER_NAME}
    with db.connection() as con:
        rows = con.execute('SELECT email, display_name, role FROM users WHERE coalesce(disabled, 0) = 0 ORDER BY email ASC').fetchall()
    return {
        'accounts': [
            {
                'email': r['email'],
                'display_name': r['display_name'] or r['email'].split('@')[0].title(),
                'role': r['role'] or 'admin',
            }
            for r in rows
        ],
        'password_login': True,
        'demo_autofill_password': DEMO_AUTOFILL_PASSWORD,
        'route': c.route,
        'route_label': c.label,
        'wifi_lock': get_host_wifi_status(),
        'server_id': SERVER_ID,
        'server_name': SERVER_NAME,
    }


def throttle(request):
    key = client_ip(request) or 'unknown'
    bucket = ATTEMPTS[key]
    while bucket and bucket[0] < time.time() - 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, 'Too many attempts. Wait one minute.')
    bucket.append(time.time())


@app.post('/api/v1/auth/login', response_model=LoginResponse, dependencies=[Depends(net.requires('password_login'))])
async def login(req: LoginRequest, request: Request, response: Response):
    c = classify_request(request)
    throttle(request)
    with db.connection() as con:
        user = con.execute('SELECT * FROM users WHERE email=?', (req.username.lower().strip(),)).fetchone()
    if not user or user['disabled'] or not await asyncio.to_thread(check_password, req.password, user['password']):
        raise HTTPException(401, 'Incorrect email or password')

    token, device = create_session(
        user['id'],
        req.device_name,
        installation_id=req.installation_id,
        scope='admin',
        role=req.role or 'control',
        days=ADMIN_TOKEN_DAYS,
    )
    cam_id = stable_camera_id(req.installation_id) if req.installation_id else None
    if req.installation_id:
        db.upsert_device(
            {
                'device_id': device,
                'installation_id': req.installation_id,
                'name': req.device_name,
                'role': req.role or 'control',
                'camera_id': cam_id,
                'model': req.model,
                'os_version': req.os_version,
                'app_version': req.app_version,
                'wifi_ssid': req.wifi_ssid,
                'wifi_bssid': req.wifi_bssid,
                'local_ip': client_ip(request),
                'token_scope': 'admin',
                'status': 'online',
                'last_seen': time.time(),
            }
        )
        db.set_device_route(device, c.route, c.client_ip)
    if req.client_type == 'web':
        response.set_cookie(
            'safespace_session',
            token,
            httponly=True,
            secure=COOKIE_SECURE or c.scheme == 'https',
            samesite='strict',
            max_age=ADMIN_TOKEN_DAYS * 86400,
            path='/',
        )
    db.log_audit(
        action='auth.login',
        actor_user=user['email'],
        actor_device=device,
        ip=client_ip(request),
        target_type='user',
        target_id=user['id'],
        detail={'client_type': req.client_type, 'device_name': req.device_name},
    )
    return LoginResponse(
        device_id=device,
        device_name=req.device_name,
        device_token=token if req.client_type == 'mobile' else None,
        camera_id=cam_id,
        scope='admin',
        role=req.role or 'control',
        user={
            'id': user['id'],
            'email': user['email'],
            'display_name': user['display_name'] or user['email'].split('@')[0].title(),
        },
        server_id=SERVER_ID,
        expires_at=time.time() + ADMIN_TOKEN_DAYS * 86400,
    )


@api.get('/auth/me', response_model=UserOut)
async def me(request: Request):
    s = request.state.session
    return UserOut(
        id=s['user_id'],
        username=s['email'],
        role='admin',
        display_name=s.get('display_name') or s['email'].split('@')[0].title(),
        disabled=bool(s.get('disabled', 0)),
        created_at=s['user_created'],
    )


@api.get('/network')
async def network_info():
    """Network policy as the server sees it: mode, routes, listeners, interfaces and warnings (System screens)."""
    return net.network_status()


@api.post('/auth/logout')
async def logout(request: Request, response: Response):
    with db.connection() as con:
        con.execute('DELETE FROM sessions WHERE token=?', (request.state.session['token'],))
    response.delete_cookie('safespace_session', path='/')
    return {'ok': True}


@api.post('/auth/password')
async def change_password(req: PasswordChange, request: Request, response: Response):
    ident = request.state.session['user_id']
    with db.connection() as con:
        user = con.execute('SELECT * FROM users WHERE id=?', (ident,)).fetchone()
    if not await asyncio.to_thread(check_password, req.current_password, user['password']):
        raise HTTPException(400, 'Current password is incorrect')
    hashed = await asyncio.to_thread(password_hash, req.new_password)
    with db.connection() as con:
        con.execute('UPDATE users SET password=? WHERE id=?', (hashed, ident))
        con.execute('DELETE FROM sessions WHERE user_id=?', (ident,))
    response.delete_cookie('safespace_session', path='/')
    return {'ok': True, 'message': 'Password changed. Sign in again on your devices.'}


def pairing_link(code: str, role: str) -> str:
    """safespace://pair link for the QR code: the code, the role, the server id and every address + TLS pin to try."""
    from urllib.parse import urlencode
    document = net.route_document()
    secure_first = sorted(document['routes'], key=lambda r: (not r['tls'], r['route']))[:4]
    params = [('c', code), ('r', role), ('s', SERVER_ID)]
    params += [('u', r['url']) for r in secure_first]
    params += [('p', pin) for pin in document['pins']]
    return 'safespace://pair?' + urlencode(params)


@api.post('/auth/pairing-code', response_model=PairingCodeCreateResponse)
async def pairing_code(request: Request, body: PairingCodeCreateRequest | None = None):
    role = (body.role if body else 'control')
    scope = 'camera' if role == 'camera' else 'admin'
    code = secrets.token_hex(4).upper()
    with db.connection() as con:
        con.execute('DELETE FROM pairing WHERE expires<?', (time.time(),))
        con.execute('INSERT INTO pairing(code, user_id, expires, scope, role) VALUES(?,?,?,?,?)',
                    (digest(code), request.state.session['user_id'], time.time() + 600, scope, role))
    link = pairing_link(code, role)
    db.log_audit(action='pairing.code', actor_user=request.state.session.get('email'), actor_device=request.state.session.get('device_id'),
                 ip=client_ip(request), target_type='pairing', target_id=role)
    return PairingCodeCreateResponse(code=code, qr_payload=link, link=link, role=role,
                                     routes=net.route_document()['routes'], expires_in=600)


@app.post('/api/v1/auth/pair', response_model=PairDeviceResponse)
async def pair(req: PairDeviceRequest, request: Request):
    c = classify_request(request)
    throttle(request)
    with db.connection() as con:
        row = con.execute('DELETE FROM pairing WHERE code=? AND expires>? RETURNING user_id, scope, role',
                          (digest(req.code.upper()), time.time())).fetchone()
    if not row:
        raise HTTPException(401, 'Pairing code is invalid or expired')
    if row['scope'] == 'camera':
        # A camera phone receives a camera-scoped token only (publish its own stream), never an admin token.
        if not req.installation_id:
            raise HTTPException(422, 'A camera pairing needs the installation id of the phone')
        reg = devices_routes.register_camera_device(
            installation_id=req.installation_id, device_name=req.device_name, role='camera', model=req.model,
            os_version=req.os_version, app_version=req.app_version, request=request, owner=row['user_id'], audit_action='device.pair')
        return PairDeviceResponse(device_id=reg['device_id'], device_name=req.device_name, device_token=reg['token'], scope='camera',
                                  role='camera', camera_id=reg['camera_id'], server_id=SERVER_ID, expires_at=reg['expires_at'])
    token, device = create_session(row['user_id'], req.device_name, installation_id=req.installation_id, scope='admin', role='control')
    if req.installation_id:
        db.upsert_device({'device_id': device, 'installation_id': req.installation_id, 'name': req.device_name, 'role': 'control',
                          'model': req.model, 'os_version': req.os_version, 'app_version': req.app_version, 'local_ip': c.client_ip,
                          'token_scope': 'admin', 'status': 'online', 'last_seen': time.time()})
        db.set_device_route(device, c.route, c.client_ip)
    db.log_audit(action='device.pair', actor_device=device, ip=c.client_ip, target_type='device', target_id=device,
                 detail={'device_name': req.device_name, 'route': c.route})
    return PairDeviceResponse(device_id=device, device_name=req.device_name, device_token=token, scope='admin', role='control',
                              camera_id=stable_camera_id(req.installation_id) if req.installation_id else None,
                              server_id=SERVER_ID, expires_at=time.time() + ADMIN_TOKEN_DAYS * 86400)


@api.get('/devices')
async def devices(request: Request):
    with db.connection() as con:
        session_devs = [
            dict(r)
            for r in con.execute(
                'SELECT device_id AS id, name, created_at, expires, scope, role FROM sessions WHERE user_id=? AND expires>?',
                (request.state.session['user_id'], time.time()),
            )
        ]
    fleet = {d['device_id']: d for d in db.list_devices_v3()}
    seen_ids = set()
    merged = []
    for sd in session_devs:
        seen_ids.add(sd['id'])
        extra = fleet.get(sd['id']) or {}
        merged.append({**extra, **sd})
    for did, fd in fleet.items():
        if did not in seen_ids:
            merged.append({'id': did, **fd})
    return merged


@api.delete('/devices/{ident}')
async def revoke_device(ident: str, request: Request):
    with db.connection() as con:
        con.execute('DELETE FROM sessions WHERE device_id=?', (ident,))
    db.delete_device_v3(ident)
    db.log_audit(
        action='device.revoke',
        actor_user=request.state.session.get('email'),
        ip=client_ip(request),
        target_type='device',
        target_id=ident,
    )
    return {'ok': True}


@app.post('/api/v1/ws-tickets', response_model=WsTicketResponse)
async def ws_ticket(request: Request):
    """A 30-second single-use ticket for a socket handshake. Any signed-in device may ask; what the ticket opens is
    still decided by that device's own scope when it is redeemed."""
    await authenticated_any_scope(request)
    return WsTicketResponse(ticket=tickets.issue(extract_token(request)))


@app.websocket('/api/v1/ws')
async def websocket(ws: WebSocket, ticket: str = ''):
    if not await check_websocket_allowed(ws):
        return
    token = tickets.redeem(ticket)
    sess = session_for(token) if token else None
    if not sess or (sess.get('scope') or 'admin') != 'admin':
        await ws.close(code=4401)
        return
    await ws.accept()
    SOCKETS[ws] = token
    await ws.send_json({'v': 1, 'type': 'hello', 'sent_at': now(), 'data': {'head_seq': db.head(), 'heartbeat_s': 20}})
    try:
        while session_for(token):
            try:
                await asyncio.wait_for(ws.receive_text(), 20)
                await ws.send_json({'v': 1, 'type': 'pong', 'sent_at': now(), 'data': {}})
            except asyncio.TimeoutError:
                await ws.send_json({'v': 1, 'type': 'ping', 'sent_at': now(), 'data': {}})
        await ws.close(code=4401)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        SOCKETS.pop(ws, None)


@api.get('/events', response_model=list[EventOut])
async def events(
    camera_id: str | None = None,
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = db.all_objects('event')
    if camera_id:
        rows = [e for e in rows if e['camera']['id'] == camera_id]
    if category:
        rows = [e for e in rows if e['category']['key'] == category]
    if status:
        rows = [e for e in rows if e['status'] == status]
    if q:
        rows = [e for e in rows if q.lower() in json.dumps(e).lower()]
    return sorted(rows, key=lambda e: e['created_at'], reverse=True)[offset : offset + limit]


def required(kind, ident):
    item = db.get(kind, ident)
    if not item:
        raise HTTPException(404, f'{kind.title()} not found')
    return item


@api.get('/events/{ident}', response_model=EventOut)
async def event(ident: str):
    return required('event', ident)


@api.post('/events/{ident}/verification', response_model=EventOut)
async def verify(ident: str, req: HumanVerificationRequest, request: Request):
    event = required('event', ident)
    with db.connection() as con:
        old = con.execute('SELECT event_id FROM feedback WHERE action_id=?', (req.client_action_id,)).fetchone()
        if old:
            if old['event_id'] != ident:
                raise HTTPException(409, 'Action id already used')
            return event
        con.execute('INSERT INTO feedback VALUES(?,?)', (req.client_action_id, ident))
    event.update(
        status={'CONFIRM': 'CONFIRMED', 'MARK_FALSE_POSITIVE': 'FALSE_POSITIVE', 'REOPEN': 'NEEDS_REVIEW'}[req.action.value],
        verified_by='HUMAN',
        status_reason=req.note,
        updated_at=now(),
    )
    event['feedback'].append(
        {
            'id': uuid.uuid4().hex,
            'client_action_id': req.client_action_id,
            'action': req.action.value,
            'note': req.note,
            'created_at': now(),
            'user_id': request.state.session['user_id'],
        }
    )
    db.save_event(event)
    await broadcast({'v': 1, 'type': 'event.updated', 'sent_at': now(), 'data': {'event': EventOut.model_validate(event).model_dump(mode='json', by_alias=True)}})
    return event


@api.post('/events/{ident}/ai-review', response_model=EventOut)
async def ai_review(ident: str):
    required('event', ident)
    try:
        updated = await review.review(ident, pipeline.publish)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(503, 'The assistant could not review this incident. Check System and try again.') from exc
    if not updated:
        raise HTTPException(404, 'Event not found')
    return updated


@api.get('/changes', response_model=ChangesResponse)
async def changes(after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    with db.connection() as con:
        rows = con.execute('SELECT seq,body FROM changes WHERE seq>? ORDER BY seq LIMIT ?', (after, limit + 1)).fetchall()
    return ChangesResponse(
        items=[EventOut.model_validate_json(r['body']) for r in rows[:limit]],
        next_after=rows[min(limit, len(rows)) - 1]['seq'] if rows else after,
        has_more=len(rows) > limit,
        head_seq=db.head(),
    )


@api.get('/events/{ident}/media/{filename}')
async def media(ident: str, filename: str):
    required('event', ident)
    if filename not in ('frame.jpg', 'clip.mp4', 'detections.json'):
        raise HTTPException(404, 'Media not found')
    path = STORAGE / 'media' / ident / filename
    if not path.is_file():
        raise HTTPException(404, 'Media not found')
    return FileResponse(path, media_type=mimetypes.guess_type(filename)[0])


@api.get('/categories')
async def categories():
    import yaml

    mappings = yaml.safe_load((ROOT / 'config/class_map.yaml').read_text())['mappings']
    return [{'key': key, 'label': key.replace('_', ' ').title()} for key in sorted({m['category'] for m in mappings.values() if m.get('category')})]


@api.post('/sources', response_model=SourceRecord, status_code=202)
async def upload(file: UploadFile = File(...), camera_id: str | None = Form(None)):
    if camera_id:
        required('camera', camera_id)
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.webm', '.mov', '.avi', '.mkv'):
        raise HTTPException(415, 'Choose a JPG, PNG, WebP, MP4, WebM, MOV, AVI or MKV file')
    if len(pipeline.TASKS) >= 8:
        raise HTTPException(429, 'Processing queue is full. Try again shortly.')
    ident = uuid.uuid4().hex
    folder = STORAGE / 'uploads' / ident
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ('original' + ext)
    size = 0
    with path.open('wb') as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD:
                out.close()
                path.unlink(missing_ok=True)
                folder.rmdir()
                raise HTTPException(413, f'Upload exceeds {MAX_UPLOAD // 1024 // 1024} MB')
            out.write(chunk)
    if size == 0:
        path.unlink()
        folder.rmdir()
        raise HTTPException(422, 'Empty file')
    kind = 'image' if ext in ('.jpg', '.jpeg', '.png', '.webp') else 'video'
    source = SourceRecord(
        id=ident,
        filename=Path(file.filename).name,
        kind=kind,
        camera_id=camera_id,
        status='PENDING',
        created_at=now(),
        media_url=f'/api/v1/sources/{ident}/media' if kind == 'image' else None,
    ).model_dump()
    db.put('source', source)
    pipeline.start_source(source, path)
    return source


@api.get('/sources', response_model=list[SourceRecord])
async def sources():
    return sorted(db.all_objects('source'), key=lambda s: s['created_at'], reverse=True)[:100]


@api.get('/sources/{ident}', response_model=SourceRecord)
async def source(ident: str):
    return required('source', ident)


@api.get('/sources/{ident}/media')
async def source_media(ident: str):
    source = required('source', ident)
    folder = STORAGE / 'uploads' / ident
    path = folder / 'playback.mp4' if source['kind'] == 'video' else next(folder.glob('original.*'), None)
    if not path or not path.is_file():
        raise HTTPException(404, 'Media is not ready')
    return FileResponse(path, media_type=mimetypes.guess_type(str(path))[0])


@api.get('/sources/{ident}/keyframes/{name}')
async def source_keyframe(ident: str, name: str):
    required('source', ident)
    path = STORAGE / 'uploads' / ident / 'keyframes' / name
    if not re.fullmatch(r'[1-9]\.jpg', name) or not path.is_file():
        raise HTTPException(404, 'Key frame not found')
    return FileResponse(path, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600'})


@api.post('/inference/predict-frame', response_model=FrameResult)
async def predict_frame(file: UploadFile = File(...)):
    source = await upload(file, None)
    if source['kind'] != 'image':
        raise HTTPException(415, 'Use /sources for video')
    await pipeline.TASKS[source['id']]
    result = required('source', source['id'])
    if result['status'] != 'DONE':
        raise HTTPException(503, result['error'])
    return result['result']


@api.get('/cameras', response_model=list[CameraOut])
async def cameras():
    rows = db.all_objects('camera')
    with db.connection() as con:
        recent = {row['camera_id']: row['last_frame_ts'] for row in con.execute('SELECT camera_id,last_frame_ts FROM camera_health')}
    for camera in rows:
        cid = camera['id']
        if camera.get('source_type') == 'MOBILE':
            camera['source_type'] = 'PHONE'     # rows written before the type was corrected
        ch = HUB.channel(cid)
        dev = db.get_device_by_camera(cid)
        legacy_online = bool(camera.get('desired_active') and time.time() - (recent.get(cid) or 0) <= 5)
        is_online = ch.is_online or legacy_online
        camera['is_online'] = is_online
        camera['status'] = 'LIVE' if is_online else 'OFFLINE'
        camera['fps'] = ch.fps if ch.is_online else (4.0 if legacy_online else 0.0)
        camera['viewer_count'] = ch.viewer_count
        camera['width'] = ch.latest_frame.width if ch.latest_frame else camera.get('width', 640)
        camera['height'] = ch.latest_frame.height if ch.latest_frame else camera.get('height', 360)
        camera['recording_active'] = is_online
        camera['stealth_mode'] = ch.stealth_mode or bool((dev or {}).get('stealth_mode'))
        camera['torch_enabled'] = ch.torch_enabled or bool((dev or {}).get('torch_enabled'))
        camera['lens_facing'] = ch.lens_facing or (dev or {}).get('lens_facing', 'back')
        camera['capture_profile'] = ch.profile or (dev or {}).get('capture_profile', 'normal')
        camera['battery_pct'] = ch.battery_pct if ch.battery_pct is not None else (dev or {}).get('battery_pct')
        camera['charging'] = ch.charging if ch.charging is not None else (dev or {}).get('charging')
        camera['temp_c'] = ch.temp_c if ch.temp_c is not None else (dev or {}).get('temp_c')
        camera['wifi_rssi'] = ch.wifi_rssi if ch.wifi_rssi is not None else (dev or {}).get('wifi_rssi')
        camera['device_id'] = ch.device_id or (dev or {}).get('device_id') or camera.get('device_id')
        camera['active_rules_count'] = sum(1 for r in db.list_rules(cid) if r.get('status') == 'active')
        geom, _ = db.get_geometry(cid)
        camera['geometry'] = geom
    return rows


@api.post('/cameras', response_model=CameraOut, status_code=201)
async def add_camera(req: CameraCreate):
    uri = req.connection_uri or '0'
    if req.source_type.value == 'RTSP' and not uri.startswith('rtsp://'):
        raise HTTPException(422, 'RTSP camera address must begin with rtsp://')
    if req.source_type.value == 'WEBCAM' and not uri.isdigit():
        raise HTTPException(422, 'Webcam source must be a numeric device index')
    if req.source_type.value == 'FILE':
        raise HTTPException(422, 'Use file upload to add recorded footage')
    cam = CameraOut(id='cam_' + uuid.uuid4().hex, name=req.name, source_type=req.source_type, connection_uri=uri, created_at=now()).model_dump(mode='json')
    return db.put('camera', cam)


@api.patch('/cameras/{ident}', response_model=CameraOut)
async def update_camera(ident: str, req: CameraUpdate):
    cam = required('camera', ident)
    cam.update(req.model_dump(exclude_none=True))
    return db.put('camera', cam)


@api.delete('/cameras/{ident}')
async def delete_camera(ident: str, request: Request):
    required('camera', ident)
    sess = mobile_camera.SESSIONS.pop(ident, None)
    if sess:
        await sess.stop()
    db.delete_object('camera', ident)
    db.log_audit(
        action='camera.delete',
        actor_user=request.state.session.get('email'),
        ip=client_ip(request),
        target_type='camera',
        target_id=ident,
    )
    return {'ok': True}


@api.post('/cameras/{ident}/start', response_model=SourceRecord)
async def start_camera(ident: str):
    cam = required('camera', ident)
    if cam.get('source_type') == 'PHONE':
        raise HTTPException(409, 'Start this camera from its paired phone')
    if cam.get('desired_active'):
        raise HTTPException(409, 'Camera already running')
    if not cam['enabled']:
        raise HTTPException(409, 'Camera is disabled')
    source = SourceRecord(id=uuid.uuid4().hex, filename=cam['name'], kind='live', camera_id=ident, status='RUNNING', created_at=now()).model_dump()
    source['_started_epoch'] = time.time()
    db.put('source', source)
    cam['desired_active'] = True
    cam['_active_source_id'] = source['id']
    db.put('camera', cam)
    return source


@api.post('/cameras/{ident}/stop')
async def stop_camera(ident: str):
    cam = required('camera', ident)
    if cam.get('source_type') == 'PHONE':
        session = mobile_camera.SESSIONS.pop(ident, None)
        if session:
            await session.stop()
    cam['desired_active'] = False
    cam['is_online'] = False
    db.put('camera', cam)
    RECORDER_MANAGER.flush(ident)       # close the open recording segment so it is playable straight away
    source = db.get('source', cam.get('_active_source_id'))
    if source and source['status'] == 'RUNNING':
        source['status'] = 'CANCELED'
        db.put('source', source)
    return {'ok': True}


@api.get('/cameras/{ident}/live')
async def camera_live(ident: str):
    """Latest detector output for a running camera, for drawing boxes over the live preview."""
    required('camera', ident)
    camera = required('camera', ident)
    ch = HUB.channel(ident)
    if ch.is_online:
        return {
            'running': True,
            'frames_analyzed': ch.seq_counter,
            'result': ch.latest_overlay,
            'event_ids': [],
        }
    source = db.get('source', camera.get('_active_source_id'))
    if not source or source['status'] != 'RUNNING' or not camera.get('desired_active') or camera.get('source_type') == 'PHONE' and not camera_recent(ident):
        return {'running': False}
    return {'running': True, 'frames_analyzed': source['frames_analyzed'], 'result': source.get('result'), 'event_ids': source['event_ids']}


@api.get('/cameras/{ident}/frame')
async def camera_frame(ident: str):
    camera = required('camera', ident)
    ch = HUB.channel(ident)
    if ch.latest_frame is not None and ch.is_online:
        return Response(content=ch.latest_frame.jpeg_bytes, media_type='image/jpeg')
    if not camera.get('desired_active') or not camera_recent(ident):
        raise HTTPException(409, 'Camera is not running')
    preview = STORAGE / 'previews' / f'{ident}.jpg'
    if not preview.is_file():
        raise HTTPException(409, 'Camera is not running')
    return FileResponse(preview, media_type='image/jpeg')


def camera_recent(ident: str) -> bool:
    if HUB.channel(ident).is_online:
        return True
    with db.connection() as con:
        row = con.execute('SELECT last_frame_ts FROM camera_health WHERE camera_id=?', (ident,)).fetchone()
    return bool(row and row['last_frame_ts'] and time.time() - row['last_frame_ts'] <= 5)


@api.post('/phone-cameras/register', response_model=CameraOut)
async def register_phone_camera(request: Request):
    session = request.state.session
    ident = 'cam_phone_' + session['device_id']
    cam = db.get('camera', ident)
    if cam is None:
        if sum(c.get('desired_active', False) and c.get('source_type') == 'PHONE' for c in db.all_objects('camera')) >= mobile_camera.MAX_CAMERAS:
            raise HTTPException(429, 'Laptop camera capacity is full')
        cam = CameraOut(id=ident, name=f"{session['name']} camera", source_type='PHONE', connection_uri=None, created_at=now()).model_dump(mode='json')
        cam['_owner_device_id'] = session['device_id']
    if cam.get('_owner_device_id') != session['device_id']:
        raise HTTPException(403, 'Only the paired camera phone can publish this feed')
    if not cam.get('enabled', True):
        raise HTTPException(409, 'This camera is disabled')
    if not cam.get('desired_active'):
        source = SourceRecord(id=uuid.uuid4().hex, filename=cam['name'], kind='live', camera_id=ident, status='RUNNING', created_at=now()).model_dump()
        source['_started_epoch'] = time.time()
        db.put('source', source)
        cam['_active_source_id'] = source['id']
    cam['desired_active'] = True
    db.put('camera', cam)
    if ident not in mobile_camera.SESSIONS:
        mobile_camera.SESSIONS[ident] = mobile_camera.PhoneCameraSession(ident)
    mobile_camera.SESSIONS[ident].start()
    return cam


@api.post('/phone-cameras/{ident}/frames', status_code=202)
async def phone_camera_frame(ident: str, request: Request):
    camera = required('camera', ident)
    if camera.get('source_type') != 'PHONE' or camera.get('_owner_device_id') != request.state.session['device_id']:
        raise HTTPException(403, 'Only the paired camera phone can publish this feed')
    if not camera.get('desired_active') or ident not in mobile_camera.SESSIONS:
        raise HTTPException(409, 'Start the phone camera before sending frames')
    length = request.headers.get('content-length', '0')
    if not length.isdigit() or int(length) > mobile_camera.MAX_FRAME_BYTES:
        raise HTTPException(413, 'Camera frame is too large')
    data = await request.body()
    if len(data) > mobile_camera.MAX_FRAME_BYTES or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise HTTPException(415, 'Send one complete JPEG frame under 2 MB')
    await mobile_camera.SESSIONS[ident].submit(data, request.headers.get('x-capture-ts'))
    try:
        await HUB.publish_frame(ident, data, forward_to_session=False)
    except Exception:
        pass
    return {'accepted': True}


@api.post('/phone-cameras/{ident}/stop')
async def stop_phone_camera(ident: str, request: Request):
    camera = required('camera', ident)
    if camera.get('source_type') != 'PHONE' or camera.get('_owner_device_id') != request.state.session['device_id']:
        raise HTTPException(403, 'Only the paired camera phone can stop this feed')
    return await stop_camera(ident)


@api.get('/phone-cameras/{ident}/status')
async def phone_camera_status(ident: str):
    camera = required('camera', ident)
    if camera.get('source_type') != 'PHONE':
        raise HTTPException(404, 'Phone camera not found')
    session = mobile_camera.SESSIONS.get(ident)
    age = time.time() - session.last_frame_ts if session and session.last_frame_ts else None
    return {
        'camera_id': ident,
        'streaming': bool(camera.get('desired_active') and age is not None and age < 5),
        'recording_id': session.recording_id if session else None,
        'last_frame_age_s': round(age, 1) if age is not None else None,
        'frames_processed': session.frame_id if session else 0,
        'error': session.last_error if session else None,
    }


@api.post('/cameras/{ident}/snapshots')
async def camera_snapshot(ident: str):
    camera = required('camera', ident)
    if not camera.get('desired_active') and not HUB.channel(ident).is_online or not camera_recent(ident):
        raise HTTPException(409, 'Camera is not currently sending frames')
    preview = STORAGE / 'previews' / f'{ident}.jpg'
    if not preview.is_file():
        raise HTTPException(409, 'No current camera frame is available')
    snapshot_id = uuid.uuid4().hex
    folder = STORAGE / 'snapshots' / ident
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{snapshot_id}.jpg').write_bytes(preview.read_bytes())
    item = {'id': snapshot_id, 'camera_id': ident, 'created_at': now(), 'url': f'/api/v1/cameras/{ident}/snapshots/{snapshot_id}.jpg'}
    db.put('snapshot', item)
    return item


@api.get('/cameras/{ident}/snapshots')
async def camera_snapshots(ident: str):
    required('camera', ident)
    return sorted((s for s in db.all_objects('snapshot') if s['camera_id'] == ident), key=lambda s: s['created_at'], reverse=True)[:100]


@api.get('/cameras/{ident}/snapshots/{snapshot_id}.jpg')
async def camera_snapshot_file(ident: str, snapshot_id: str):
    item = required('snapshot', snapshot_id)
    if item['camera_id'] != ident:
        raise HTTPException(404, 'Snapshot not found')
    path = STORAGE / 'snapshots' / ident / f'{snapshot_id}.jpg'
    if not path.is_file():
        raise HTTPException(404, 'Snapshot file not found')
    return FileResponse(path, media_type='image/jpeg')


@api.get('/cameras/{ident}/recordings')
async def camera_recordings(ident: str):
    """Recordings of one camera, newest first: the media hub's seekable segments plus any older single-file recordings."""
    required('camera', ident)
    legacy = [{**r, 'url': f"/api/v1/cameras/{ident}/recordings/{r['id']}.mp4"} for r in db.all_objects('recording') if r['camera_id'] == ident]
    segments = [{
        'id': seg['segment_id'], 'camera_id': ident, 'status': 'READY', 'duration_s': seg.get('duration_s'),
        'started_at': datetime.fromtimestamp(seg['start_ts'], timezone.utc).isoformat(),
        'ended_at': datetime.fromtimestamp(seg['end_ts'], timezone.utc).isoformat(),
        'url': f"/api/v1/recordings/{seg['segment_id']}.mp4",
    } for seg in db.list_recording_segments(ident, limit=200)]
    return sorted(legacy + segments, key=lambda r: r['started_at'], reverse=True)[:100]


@api.get('/cameras/{ident}/recordings/{recording_id}.mp4')
async def camera_recording_file(ident: str, recording_id: str):
    item = required('recording', recording_id)
    if item['camera_id'] != ident:
        raise HTTPException(404, 'Recording not found')
    path = STORAGE / 'recordings' / ident / f'{recording_id}.mp4'
    if not path.is_file():
        raise HTTPException(404, 'Recording file not found')
    return FileResponse(path, media_type='video/mp4')


@api.get('/chat/conversations')
async def get_chat_conversations(request: Request):
    return {'items': chat.list_conversations(request.state.session['user_id'])}


@api.get('/chat/conversations/{conversation_id}')
async def get_chat_conversation(conversation_id: str, request: Request):
    return chat.get_conversation_messages(conversation_id, request.state.session['user_id'])


@api.delete('/chat/conversations/{conversation_id}')
async def remove_chat_conversation(conversation_id: str, request: Request):
    chat.delete_conversation(conversation_id, request.state.session['user_id'])
    return {'ok': True}


@api.post('/chat/stream')
async def stream_chat(req: ChatRequest, request: Request):
    chat.context(req, request.state.session)

    async def lines():
        async for item in chat.stream(req, request.state.session):
            yield json.dumps(item) + '\n'

    return StreamingResponse(lines(), media_type='application/x-ndjson')


@api.post('/chat', response_model=ChatResponse)
async def ask_chat(req: ChatRequest, request: Request):
    async for item in chat.stream(req, request.state.session):
        if item['type'] == 'done':
            item.pop('type')
            return ChatResponse(**item)
        if item['type'] == 'error':
            raise HTTPException(503, item['message'])


@rule_routes.worker_router.post('/llm/describe', dependencies=[Depends(rule_routes.worker_auth)])
async def internal_llm_describe(payload: dict):
    out = await GATEWAY.describe(
        images_b64=payload.get('images', []),
        system_prompt=payload.get('system', ''),
        user_prompt=payload.get('prompt', ''),
        json_schema=payload.get('schema'),
        priority=int(payload.get('priority', P2_BACKGROUND)),
    )
    return {'content': out}


@api.get('/settings', response_model=RuntimeSettings)
async def get_settings():
    return {k: v for k, v in chat.settings().items() if k != 'id'}


@api.post('/settings', response_model=RuntimeSettings)
async def set_settings(req: RuntimeSettings):
    db.put('setting', {'id': 'runtime', **req.model_dump()})
    return req


@api.get('/system', response_model=SystemSnapshot)
@api.get('/health', response_model=SystemSnapshot)
async def system():
    async with httpx.AsyncClient(timeout=3) as client:
        async def inspect(url, headers=None):
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError):
                return None

        inference, local = await asyncio.gather(
            inspect(f'{INFERENCE_URL}/health', {'Authorization': f'Bearer {INTERNAL_TOKEN}'}),
            inspect(f'{OLLAMA_URL}/api/tags'),
        )
    records = db.all_objects('event')
    all_sources = db.all_objects('source')
    training_path = STORAGE / 'training.json'
    try:
        training = json.loads(training_path.read_text()) if training_path.exists() else {'status': 'not_started'}
    except (ValueError, OSError):
        training = {'status': 'unavailable'}
    import os
    import yaml as _yaml

    try:
        deployed = {m['name'] for m in _yaml.safe_load((ROOT / 'config/models.yaml').read_text())['models']}
    except (OSError, ValueError, KeyError):
        deployed = set()
    shown = deployed | {'verifier', 'violence_ensemble', 'stack_images', 'blind_fresh', 'chat', 'ecosystem'}
    benchmarks = {}
    for path in sorted((STORAGE / 'benchmarks').glob('*.json')):
        if path.stem not in shown:
            continue
        try:
            benchmarks[path.stem] = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
    training['benchmarks'] = benchmarks
    if isinstance(training.get('runs'), dict):
        training['runs'] = {k: v for k, v in training['runs'].items() if k in deployed or v.get('status') in ('training', 'preparing', 'failed')}
    memory = psutil.virtual_memory()
    setup_path = STORAGE / 'local-chat-setup.json'
    try:
        local_setup = json.loads(setup_path.read_text()) if setup_path.exists() else {'status': 'not_started'}
    except (ValueError, OSError):
        local_setup = {'status': 'unavailable'}

    all_cams = db.all_objects('camera')
    online_count = sum(1 for c in all_cams if HUB.channel(c['id']).is_online or c.get('is_online'))
    storage_info = get_storage_summary()
    wifi_status = get_host_wifi_status()

    return SystemSnapshot(
        timestamp=now(),
        status='ok' if inference and inference.get('ready') else 'degraded',
        counts={
            'incidents': len(records),
            'needs_review': sum(e['status'] == 'NEEDS_REVIEW' for e in records),
            'confirmed': sum(e['status'] == 'CONFIRMED' for e in records),
            'sources': len(all_sources),
            'frames_analyzed': sum(s['frames_analyzed'] for s in all_sources),
            'cameras_online': online_count,
            'rulesets_active': sum(1 for r in db.list_rulesets() if r['status'] == 'active'),
            'devices_enrolled': len(db.list_devices_v3()),
        },
        inference=inference or {'ready': False, 'errors': ['Detector service unavailable']},
        chat={
            'setup': local_setup,
            'local_available': local is not None,
            'installed_models': [m['name'] for m in (local or {}).get('models', [])],
            'groq_configured': bool(os.getenv('GROQ_API_KEY')),
            'gateway_stats': GATEWAY.stats,
            **{k: v for k, v in chat.settings().items() if k != 'id'},
        },
        training={
            **training,
            'wifi_lock': wifi_status,
            'storage_summary': storage_info,
            'server_id': SERVER_ID,
            'server_name': SERVER_NAME,
        },
        resources={
            'ram_used_gb': round(memory.used / 1024**3, 1),
            'ram_total_gb': round(memory.total / 1024**3, 1),
            'cpu_percent': psutil.cpu_percent(),
            'disk_free_gb': round(psutil.disk_usage(str(STORAGE)).free / 1024**3, 1),
        },
    )


@api.post('/models/reload')
async def reload_models():
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            result = await client.post(f'{INFERENCE_URL}/reload', headers={'Authorization': f'Bearer {INTERNAL_TOKEN}'})
            result.raise_for_status()
            return result.json()
        except httpx.HTTPError:
            raise HTTPException(503, 'Detector service is unavailable')


app.include_router(devices_routes.router)
app.include_router(media_routes.router)
app.include_router(recordings_routes.router)
app.include_router(rulesets_routes.router)
app.include_router(compat_routes.router)
app.include_router(api)
app.include_router(rule_routes.router)
app.include_router(rule_routes.worker_router)
dashboard = ROOT / 'apps/dashboard/dist'
if dashboard.exists():
    app.mount('/', StaticFiles(directory=dashboard, html=True), name='dashboard')
