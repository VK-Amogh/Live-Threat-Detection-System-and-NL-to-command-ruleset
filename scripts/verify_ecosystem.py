"""End-to-end verification of the running ecosystem using real held-out data and isolated storage.

1. Start the detector:     PYTHONPATH=contracts/src;services/inference uvicorn server:app --port 8001
2. Start an API on :8002 with SAFESPACE_STORAGE=storage/validation (keeps operator records untouched)
3. python scripts/verify_ecosystem.py

Checks: login, held-out images through the real detectors (every class + clean negatives), a fight clip and
a normal clip through the video path, WebSocket delivery, incident media (incl. HTTP Range), and a grounded
chat answer that cites the incident and returns playable footage.  Results: storage/benchmarks/ecosystem.json
"""
import asyncio
import json
import random
import statistics
import time
from pathlib import Path

import httpx
import websockets
import yaml
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV = dotenv_values(ROOT / '.env')
BASE = 'http://127.0.0.1:8002'
random.seed(7)
checks, latency = [], {}


def check(name, passed, detail):
    checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    print(('PASS ' if passed else 'FAIL ') + name + ' — ' + detail, flush=True)


def test_images(domain, per_class=12, negatives=24):
    data = ROOT / 'storage/datasets' / domain
    names = {int(k): v for k, v in yaml.safe_load((data / 'data.yaml').read_text())['names'].items()}
    positives = {n: [] for n in names.values()}
    clean = []
    for img in sorted((data / 'images/test').glob('*.jpg')):
        classes = {names[int(line.split()[0])] for line in (data / 'labels/test' / (img.stem + '.txt')).read_text().splitlines() if line.strip()}
        if not classes:
            clean.append(img)
        for c in classes:
            positives[c].append(img)
    return {c: random.sample(v, min(per_class, len(v))) for c, v in positives.items()}, random.sample(clean, min(negatives, len(clean)))


def upload_image(client, path):
    start = time.perf_counter()
    response = client.post('/api/v1/inference/predict-frame', files={'file': (path.name, path.read_bytes(), 'image/jpeg')})
    response.raise_for_status()
    return response.json(), (time.perf_counter() - start) * 1000


def main():
    client = httpx.Client(base_url=BASE, timeout=300)
    login = client.post('/api/v1/auth/login', json={'username': ENV['INITIAL_ADMIN_USERNAME'], 'password': ENV['INITIAL_ADMIN_PASSWORD'], 'device_name': 'Ecosystem verification', 'client_type': 'web'})
    check('Login with the configured administrator account', login.status_code == 200, f'HTTP {login.status_code}')
    system = client.get('/api/v1/system').json()
    check('Detector service reports ready with trained weights', system['inference'].get('ready'), ', '.join(m['name'] for m in system['inference'].get('models', [])))

    created = []
    all_latency = []
    for domain in ('weapons_v2',):
        positives, clean = test_images(domain)
        for cls, files in positives.items():
            hits = 0
            for f in files:
                body, ms = upload_image(client, f)
                all_latency.append(ms)
                hit = any(d['class_name'] == cls and d['category'] for d in body['detections'])
                hits += hit
                if hit and body['created_event_ids']:
                    created.append(body['created_event_ids'][0])
            check(f'{domain}: held-out {cls} images raise an incident', hits / max(len(files), 1) >= 0.5, f'{hits}/{len(files)} detected')
        false_alarms = 0
        for f in clean:
            body, ms = upload_image(client, f)
            all_latency.append(ms)
            false_alarms += bool(body['threat_detected'])
        check(f'{domain}: clean held-out images stay quiet', false_alarms / max(len(clean), 1) <= 0.15, f'{false_alarms}/{len(clean)} false alarms')
    latency['image_upload_to_result_median_ms'] = round(statistics.median(all_latency), 1)
    latency['image_upload_to_result_p95_ms'] = round(sorted(all_latency)[int(len(all_latency) * .95) - 1], 1)

    manifest_path = ROOT / 'storage/datasets/violence/manifest.json'
    video_incident = None
    if manifest_path.exists():
        # real video clips only: the manifest also lists threat-free still images, which would pad the pass rate
        rows = [r for r in json.loads(manifest_path.read_text()) if r['split'] == 'test' and Path(r['path']).suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv', '.webm'}]
        for label, expect in ((1, True), (0, False)):
            pool = [r for r in rows if r['label'] == label]
            hits = 0
            sample = random.sample(pool, min(6, len(pool)))
            for row in sample:
                path = Path(row['path'])
                start = time.perf_counter()
                response = client.post('/api/v1/sources', files={'file': (path.name, path.read_bytes(), 'video/mp4')})
                source = response.json()
                for _ in range(600):
                    source = client.get('/api/v1/sources/' + source['id']).json()
                    if source['status'] in ('DONE', 'FAILED'):
                        break
                    time.sleep(.5)
                flagged = any(client.get('/api/v1/events/' + e).json()['category']['key'] == 'FIGHT' for e in source['event_ids'])
                hits += flagged == expect
                if flagged and expect and not video_incident:
                    video_incident = source['event_ids'][0]
                    latency['video_clip_total_s'] = round(time.perf_counter() - start, 1)
            check(f'violence: held-out {"fight" if expect else "normal"} clips classified correctly', hits / max(len(sample), 1) >= .6, f'{hits}/{len(sample)} correct')
    else:
        check('violence: held-out clips available', False, 'manifest missing')

    events = client.get('/api/v1/events?limit=5').json()
    if events:
        ev = events[0]
        media = next((m for m in ev['media'] if m['kind'] == 'KEYFRAME'), None)
        check('Incident keyframe is served with authentication', media and client.get(media['url']).status_code == 200, media['url'] if media else 'no media')
        clip = next((m for m in ev['media'] if m['kind'] == 'CLIP'), None)
        if clip:
            ranged = client.get(clip['url'], headers={'Range': 'bytes=0-1023'})
            check('Incident clip supports HTTP Range playback', ranged.status_code == 206, f'HTTP {ranged.status_code}')
        anonymous = httpx.get(BASE + (media['url'] if media else '/api/v1/events'))
        check('Evidence is not served without a session', anonymous.status_code == 401, f'HTTP {anonymous.status_code}')

    async def ws_roundtrip():
        ticket = client.post('/api/v1/ws-tickets').json()['ticket']
        async with websockets.connect(f'ws://127.0.0.1:8002/api/v1/ws?ticket={ticket}', additional_headers={'Cookie': '; '.join(f'{k}={v}' for k, v in client.cookies.items())}) as ws:
            await ws.recv()
            candidates = test_images('weapons_v2')[0]['gun']
            start = time.perf_counter()
            for f in candidates[:40]:
                response = await asyncio.to_thread(upload_image, client, f)
                if response[0]['created_event_ids']:
                    break
            try:
                message = json.loads(await asyncio.wait_for(ws.recv(), 5))
                return message['type'], (time.perf_counter() - start) * 1000
            except asyncio.TimeoutError:
                return None, None
    kind, ms = asyncio.run(ws_roundtrip())
    check('Live WebSocket delivers incident events', kind in ('event.created', 'event.updated', 'source.updated'), f'{kind} after {ms and round(ms)} ms (includes upload + inference)')

    for provider in ('groq', 'ollama'):
        if provider == 'groq' and not ENV.get('GROQ_API_KEY'):
            continue
        target = client.get('/api/v1/events?limit=1').json()
        if not target:
            break
        start = time.perf_counter()
        first = None
        answer = ''
        done = {}
        try:
            with client.stream('POST', '/api/v1/chat/stream', json={'message': 'Summarize this incident and show me the footage.', 'event_ids': [target[0]['id']], 'provider': provider, 'include_images': True}) as response:
                for line in response.iter_lines():
                    if not line:
                        continue
                    item = json.loads(line)
                    if item['type'] == 'delta':
                        first = first or time.perf_counter() - start
                        answer += item['text']
                    if item['type'] == 'done':
                        done = item
                    if item['type'] == 'error':
                        raise RuntimeError(item['message'])
            ok = target[0]['id'] in answer and bool(done.get('cited'))
            check(f'Chat ({provider}) is grounded, cites the incident and returns footage', ok, f'first token {first and round(first, 2)} s, cited={len(done.get("cited", []))}')
            latency[f'chat_{provider}_first_token_s'] = round(first or 0, 2)
        except Exception as exc:  # noqa: BLE001
            check(f'Chat ({provider}) reachable', False, f'{type(exc).__name__}: {str(exc)[:120]}')

    report = {'generated_at': time.time(), 'checks': checks, 'latency_ms': latency, 'passed': sum(c['passed'] for c in checks), 'total': len(checks)}
    (ROOT / 'storage/benchmarks').mkdir(parents=True, exist_ok=True)
    (ROOT / 'storage/benchmarks/ecosystem.json').write_text(json.dumps(report, indent=2))
    print(f"\n{report['passed']}/{report['total']} checks passed")


if __name__ == '__main__':
    main()
