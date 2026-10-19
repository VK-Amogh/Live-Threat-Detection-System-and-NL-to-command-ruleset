#!/usr/bin/env python
"""Stream a video file into SafeSpace exactly like a phone camera does (SSF1 frames over the publish WebSocket).

Useful to demo or test the whole pipeline - live view, recording, YOLO rules, weapon/violence detection, alerts -
without a phone. It pairs as a camera (admin account -> pairing code -> camera-scoped token), then loops the clip.

    python scripts/fake_camera.py --clip "TestVideos/v001_converted 3.avi" --base http://127.0.0.1:8000 --fps 10 --seconds 60
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import struct
import sys
import time
import uuid
from pathlib import Path

import cv2
import httpx
import websockets

SSF1 = struct.Struct('>4sBBHHIQ')


async def run(args) -> int:
    verify = args.ca if args.ca and args.base.startswith('https') else True
    http = httpx.Client(base_url=args.base.rstrip('/'), verify=verify, timeout=20)
    login = http.post('/api/v1/auth/login', json={'username': args.user, 'password': args.password, 'device_name': 'fake-camera', 'client_type': 'mobile'})
    login.raise_for_status()
    admin = {'Authorization': f"Bearer {login.json()['device_token']}"}
    installation = args.installation or f'fake-cam-{uuid.uuid4().hex[:8]}'
    code = http.post('/api/v1/auth/pairing-code', headers=admin, json={'role': 'camera'}).json()['code']
    paired = http.post('/api/v1/auth/pair', json={'code': code, 'device_name': args.name, 'installation_id': installation, 'model': 'fake-camera'})
    paired.raise_for_status()
    token, camera_id = paired.json()['device_token'], paired.json()['camera_id']
    print(f'camera paired: {camera_id} ({args.name})')

    capture = cv2.VideoCapture(args.clip)
    if not capture.isOpened():
        print(f'cannot open {args.clip}')
        return 2
    ws_url = args.base.replace('https://', 'wss://').replace('http://', 'ws://').rstrip('/') + f'/api/v1/cameras/{camera_id}/publish'
    ctx = ssl.create_default_context(cafile=args.ca) if args.base.startswith('https') and args.ca else None
    sent = acked = 0
    started = time.time()
    async with websockets.connect(ws_url, additional_headers={'Authorization': f'Bearer {token}'}, ssl=ctx, max_size=8 * 1024 * 1024) as ws:
        ready = json.loads(await ws.recv())
        print(f"publishing: server profile {ready.get('profile')} {ready.get('width')}x{ready.get('height')}@{ready.get('fps')}")

        async def reader():
            nonlocal acked
            async for message in ws:
                if isinstance(message, str) and json.loads(message).get('type') == 'ack':
                    acked += 1
        task = asyncio.create_task(reader())
        interval = 1.0 / args.fps
        seq = 0
        while time.time() - started < args.seconds:
            ok, frame = capture.read()
            if not ok:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)      # loop the clip
                continue
            if args.width and frame.shape[1] != args.width:
                frame = cv2.resize(frame, (args.width, int(frame.shape[0] * args.width / frame.shape[1])))
            ok, jpg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
            seq += 1
            h, w = frame.shape[:2]
            await ws.send(SSF1.pack(b'SSF1', 0, 0, w, h, seq, int(time.time() * 1000)) + jpg.tobytes())
            sent += 1
            await asyncio.sleep(interval)
        await asyncio.sleep(0.5)
        task.cancel()
    print(f'sent {sent} frames, {acked} acknowledged, over {time.time() - started:.1f}s')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--clip', required=True)
    ap.add_argument('--base', default='http://127.0.0.1:8000')
    ap.add_argument('--ca', help='ca.pem when --base is https')
    ap.add_argument('--user', default='admin1@safespace.com')
    ap.add_argument('--password', default='admin123')
    ap.add_argument('--name', default='Fake camera')
    ap.add_argument('--installation', help='keep the same id between runs to reuse the same camera')
    ap.add_argument('--fps', type=float, default=10)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--width', type=int, default=0, help='resize frames to this width (0 = keep)')
    return asyncio.run(run(ap.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
