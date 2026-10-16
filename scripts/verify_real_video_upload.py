"""Exercise real model inference through the upload API in isolated local storage."""
import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ['SAFESPACE_STORAGE'] = str(ROOT / 'runs/e2e-upload-storage' / secrets.token_hex(8))
os.environ['INITIAL_ADMIN_USERNAME'] = 'validation@example.invalid'
password = secrets.token_urlsafe(24)
os.environ['INITIAL_ADMIN_PASSWORD'] = password
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'services/api'), str(ROOT / 'contracts/src')]

import server  # noqa: E402
from app import main, pipeline  # noqa: E402


async def local_detector(data, stream_id=None):
    return await asyncio.to_thread(server.predict, data, stream_id)


def main_run():
    server.load_models()
    if server.ERRORS:
        raise RuntimeError(server.ERRORS)
    pipeline.detector = local_detector
    checks = []
    with TestClient(main.app) as client:
        login = client.post('/api/v1/auth/login', json={'username': 'validation@example.invalid',
            'password': password, 'device_name': 'isolated model check', 'client_type': 'web'})
        login.raise_for_status()
        for name in ('v011_converted 3.avi', 'v006_converted 3.avi', 'w001_converted 3.avi'):
            path = ROOT / 'TestVideos' / name
            response = client.post('/api/v1/sources', files={'file': (name, path.read_bytes(), 'video/x-msvideo')})
            response.raise_for_status()
            ident = response.json()['id']
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                source = client.get('/api/v1/sources/' + ident).json()
                if source['status'] in ('DONE', 'FAILED'):
                    break
                time.sleep(0.2)
            else:
                raise TimeoutError(f'Upload did not finish: {name}')
            events = [client.get('/api/v1/events/' + event_id).json() for event_id in source['event_ids']]
            row = {'file': name, 'status': source['status'], 'error': source['error'],
                   'frames_analyzed': source['frames_analyzed'],
                   'categories': sorted({event['category']['key'] for event in events})}
            checks.append(row)
            print(json.dumps(row), flush=True)
            if source['status'] != 'DONE':
                raise AssertionError(row)
    server.STREAMS.clear()
    (ROOT / 'runs/e2e-upload-report.json').write_text(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main_run()
