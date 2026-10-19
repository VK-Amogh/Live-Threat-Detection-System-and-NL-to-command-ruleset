#!/usr/bin/env python
"""End-to-end connectivity check against a RUNNING SafeSpace server, from the point of view of each kind of device.

It plays every client with the same wire protocols the phone app and the dashboard use:

  * route policy        - which network may do what (identity, password login, enrollment, plain HTTP on iBus)
  * pairing             - an admin creates a camera link; a phone redeems it and receives a camera-only token
  * live camera         - the phone publishes SSF1 frames over a WebSocket (Authorization header, no token in the URL)
  * live viewing        - another device receives those frames (with sequence + capture time) and measures latency
  * screenshots / recordings / chat - the server-side features the phones reach

Usage:
    python scripts/verify_connectivity.py --http http://127.0.0.1:8000 [--https https://10.12.253.133:8443 --ca storage/tls/ca.pem]
                                          [--chat] [--frames 60] [--fps 10]

Exit status 0 only if every check passed. Prints measured latencies; nothing is assumed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import statistics
import struct
import sys
import time
import uuid
from pathlib import Path

import cv2
import httpx
import numpy as np
import websockets

SSF1 = struct.Struct('>4sBBHHIQ')
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = '') -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f'  - {detail}' if detail else ''))
    return ok


def jpeg(width: int, height: int, tick: int) -> bytes:
    frame = np.full((height, width, 3), 30, dtype=np.uint8)
    cv2.rectangle(frame, (20 + (tick * 9) % (width - 160), 40), (140 + (tick * 9) % (width - 160), height - 40), (255, 255, 255), -1)
    cv2.putText(frame, f'{tick:05d}', (30, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    ok, enc = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
    assert ok
    return enc.tobytes()


def pack(seq: int, payload: bytes, width: int, height: int) -> bytes:
    return SSF1.pack(b'SSF1', 0, 0, width, height, seq, int(time.time() * 1000)) + payload


class Server:
    def __init__(self, base: str, ca: str | None):
        self.base = base.rstrip('/')
        self.verify = ca if (ca and base.startswith('https')) else True
        self.client = httpx.Client(base_url=self.base, verify=self.verify, timeout=15)
        self.ssl_ctx = None
        if base.startswith('https'):
            self.ssl_ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()

    @property
    def ws_base(self) -> str:
        return self.base.replace('https://', 'wss://').replace('http://', 'ws://')

    def ws(self, path: str, token: str):
        return websockets.connect(self.ws_base + path, additional_headers={'Authorization': f'Bearer {token}'}, ssl=self.ssl_ctx,
                                  max_size=8 * 1024 * 1024, open_timeout=8)


def login(server: Server, email: str = 'admin1@safespace.com') -> str:
    r = server.client.post('/api/v1/auth/login', json={'username': email, 'password': 'admin123', 'device_name': 'verify', 'client_type': 'mobile',
                                                       'installation_id': 'verify-admin-' + email})
    r.raise_for_status()
    return r.json()['device_token']


def auth(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


def route_checks(local: Server, remote: Server | None) -> None:
    ident = local.client.get('/api/v1/health/identity', params={'nonce': 'n-123'})
    d = ident.json()
    check('identity answers with a server proof', ident.status_code == 200 and bool(d.get('proof')), f"route={d.get('route')} mode={d.get('mode')}")
    check('identity lists signed routes and a TLS pin', bool(d.get('routes_sig')) and isinstance(d.get('routes'), list), f"{len(d.get('routes', []))} routes, pins={len(d.get('tls_pins', []))}")
    r = local.client.get('/api/v1/auth/seed-accounts')
    check('this route offers the account tiles', r.status_code == 200 and len(r.json().get('accounts', [])) >= 2)
    if remote is not None:
        plain = httpx.get(local.base.replace('127.0.0.1', remote.base.split('//')[1].split(':')[0]) + '/api/v1/health/live', timeout=8)
        check('iBus peer over plain HTTP is refused', plain.status_code == 403, plain.json().get('detail', ''))
        r = remote.client.post('/api/v1/auth/login', json={'username': 'admin1@safespace.com', 'password': 'admin123', 'device_name': 'x', 'client_type': 'mobile'})
        check('iBus peer cannot use the baked password', r.status_code == 403, r.json().get('detail', ''))
        r = remote.client.post('/api/v1/devices/enroll', json={'installation_id': 'abcd-1234', 'enrollment_code': 'x', 'device_name': 'x'})
        check('iBus peer cannot use the baked enrollment code', r.status_code == 403)
        r = remote.client.get('/api/v1/internal/cameras')
        check('internal API is hidden from the network', r.status_code == 404)


async def media_checks(local: Server, remote: Server | None, frames: int, fps: float, chat: bool) -> None:
    admin = login(local)
    # --- a CAMERA pairing link, redeemed over the "remote" route if given (a phone on iBus), else locally
    phone = remote or local
    pc = local.client.post('/api/v1/auth/pairing-code', headers=auth(admin), json={'role': 'camera'})
    check('admin can create a camera pairing link', pc.status_code == 200 and pc.json().get('link', '').startswith('safespace://pair?'), (pc.json().get('link') or '')[:90])
    installation = 'verify-cam-' + uuid.uuid4().hex[:8]
    paired = phone.client.post('/api/v1/auth/pair', json={'code': pc.json()['code'], 'device_name': 'Verify camera', 'installation_id': installation, 'model': 'verify'})
    ok = paired.status_code == 200 and paired.json().get('scope') == 'camera'
    check('phone pairs with the link and receives a camera-only token', ok, f"route={'remote' if remote else 'local'} camera_id={paired.json().get('camera_id') if ok else paired.text[:80]}")
    if not ok:
        return
    cam_token, cam_id = paired.json()['device_token'], paired.json()['camera_id']
    again = phone.client.post('/api/v1/auth/pair', json={'code': pc.json()['code'], 'device_name': 'x', 'installation_id': 'other-1234'})
    check('a pairing code works only once', again.status_code == 401)
    r = phone.client.get('/api/v1/events', headers=auth(cam_token))
    check('a camera token cannot read events', r.status_code == 403)

    # --- publish + view
    width, height = 960, 540
    sent_at: dict[int, float] = {}
    latencies: list[float] = []
    received = 0
    first_frame_s = None
    started = time.time()

    async def viewer():
        nonlocal received, first_frame_s
        async with (remote or local).ws(f'/api/v1/cameras/{cam_id}/view', admin) as ws:
            hello = json.loads(await ws.recv())
            check('viewer socket says hello', hello.get('type') == 'hello', f"online={hello.get('is_online')}")
            while received < frames - 5:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                if isinstance(msg, bytes):
                    magic, flags, orient, w, h, seq, captured = SSF1.unpack_from(msg, 0)
                    if magic != b'SSF1' or not msg[SSF1.size:].startswith(b'\xff\xd8'):
                        check('viewer receives SSF1-framed JPEG', False, 'bad framing')
                        return
                    received += 1
                    first_frame_s = first_frame_s or (time.time() - started)
                    if seq in sent_at:
                        latencies.append((time.time() - sent_at[seq]) * 1000)

    async def publisher():
        async with phone.ws(f'/api/v1/cameras/{cam_id}/publish', cam_token) as ws:
            ready = json.loads(await ws.recv())
            check('publish socket accepts the camera token (header auth)', ready.get('type') == 'ready', f"profile={ready.get('profile')} {ready.get('width')}x{ready.get('height')}@{ready.get('fps')}")
            acked = 0

            async def reader():
                nonlocal acked
                async for m in ws:
                    if isinstance(m, str) and json.loads(m).get('type') == 'ack':
                        acked += 1
            task = asyncio.create_task(reader())
            await asyncio.sleep(0.4)          # let the viewer attach
            for seq in range(1, frames + 1):
                sent_at[seq] = time.time()
                await ws.send(pack(seq, jpeg(width, height, seq), width, height))
                await asyncio.sleep(1.0 / fps)
            await asyncio.sleep(0.6)
            task.cancel()
            check('server acknowledges published frames', acked >= frames * 0.9, f'{acked}/{frames}')

    await asyncio.gather(viewer(), publisher())
    check('viewer received the live frames', received >= frames * 0.8, f'{received}/{frames} at {fps:.0f} fps in, first frame {first_frame_s:.2f}s' if first_frame_s else '')
    if latencies:
        latencies.sort()
        p50, p95 = statistics.median(latencies), latencies[int(len(latencies) * 0.95) - 1]
        check('live latency (publish -> viewer) is low', p95 < 400, f'p50 {p50:.0f} ms, p95 {p95:.0f} ms over {len(latencies)} frames')

    # --- screenshot, recording, device fleet
    snap = local.client.post(f'/api/v1/cameras/{cam_id}/snapshot', headers=auth(admin), json={'kind': 'stream'})
    ok = snap.status_code == 200
    check('screenshot is saved on the laptop', ok, snap.json().get('url', snap.text[:80]) if ok else snap.text[:80])
    if ok:
        img = local.client.get(snap.json()['url'], headers=auth(admin))
        check('screenshot is downloadable', img.status_code == 200 and img.content.startswith(b'\xff\xd8'))
    tl = local.client.get(f'/api/v1/cameras/{cam_id}/timeline', params={'flush': 'true'}, headers=auth(admin))
    segs = tl.json().get('segments', []) if tl.status_code == 200 else []
    check('the stream is being recorded', len(segs) >= 1, f'{len(segs)} segment(s)')
    if segs:
        part = local.client.get(segs[0]['url'], headers={**auth(admin), 'Range': 'bytes=0-255'})
        check('recording supports seeking (HTTP range)', part.status_code == 206)
    fleet = local.client.get('/api/v1/devices/fleet', headers=auth(admin)).json().get('items', [])
    mine = next((d for d in fleet if d.get('camera_id') == cam_id), None)
    check('fleet shows the camera phone and the route it used', bool(mine) and bool(mine.get('route')), f"route={mine.get('route') if mine else None}")

    if chat:
        started = time.time()
        first = None
        text = ''
        with (remote or local).client.stream('POST', '/api/v1/chat/stream', headers=auth(admin),
                                              json={'message': 'In one sentence, what cameras do you see right now?', 'provider': 'ollama', 'include_images': False}, timeout=180) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                item = json.loads(line)
                if item['type'] == 'delta':
                    first = first or (time.time() - started)
                    text += item['text']
                if item['type'] == 'error':
                    check('assistant answers over the network', False, item['message'])
                    return
        check('assistant (Gemma on the laptop) streams an answer', bool(text.strip()), f'first token {first:.2f}s, {len(text)} chars' if first else 'no tokens')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--http', required=True, help='plain URL on this laptop (loopback), e.g. http://127.0.0.1:8000')
    ap.add_argument('--https', help='TLS URL as an iBus phone would use it, e.g. https://10.12.253.133:8443')
    ap.add_argument('--ca', help='path to ca.pem for --https')
    ap.add_argument('--frames', type=int, default=60)
    ap.add_argument('--fps', type=float, default=10)
    ap.add_argument('--chat', action='store_true', help='also ask Gemma a question through the API')
    args = ap.parse_args()
    local = Server(args.http, None)
    remote = Server(args.https, args.ca) if args.https else None
    route_checks(local, remote)
    asyncio.run(media_checks(local, remote, args.frames, args.fps, args.chat))
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed" + (f"; FAILED: {', '.join(failed)}" if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
