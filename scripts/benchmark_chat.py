"""Measure real chat latency (time-to-first-token, decode tokens/s) for each configured provider/setting.

python scripts/benchmark_chat.py [--prompt-file ...] [--repeat 3]
Runs against local Ollama (various GPU-offload settings, optional MTP draft model) and Groq when a key is set.
Results are written to storage/benchmarks/chat.json; the dashboard shows them under System.  No synthetic
numbers: every row is a timed streaming request with a realistic incident-dossier prompt.
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV = {**dotenv_values(ROOT / '.env'), **os.environ}
OLLAMA = ENV.get('OLLAMA_URL', 'http://127.0.0.1:11434')
QUESTIONS = ['Summarize what happened, how reliable the detection is, and what an operator should check first.',
             'Is this a real weapon or could it be a false alarm? Explain using the confidences.',
             'Which camera saw this, how severe is it, and has anyone reviewed it yet?',
             'List the detections in the keyframe and where in the frame each one is.']


def dossier(n):
    """A different incident id (and question) for every request, so Ollama cannot answer from its KV prefix cache."""
    return json.dumps({
        'id': f'evt_bench{n:04d}', 'category': 'WEAPON_DETECTED', 'severity': 'CRITICAL', 'status': 'NEEDS_REVIEW', 'verified_by': 'NONE', 'camera_or_source': 'Warehouse north camera',
        'peak_confidence': round(0.8 + (n % 19) / 100, 2), 'detections_in_keyframe': [{'class': 'gun', 'confidence': 0.91, 'location': 'middle-left', 'frame_area_pct': 1.4}, {'class': 'knife', 'confidence': 0.72, 'location': 'top-left', 'frame_area_pct': 0.6}],
        'other_incidents_same_source': [{'id': f'evt_b{n:04d}', 'category': 'WEAPON_DETECTED', 'offset_ms': 2500}],
    })


COUNTER = [0]


def next_prompt():
    COUNTER[0] += 1
    n = COUNTER[0]
    return f'Detailed dossiers (JSON):\n{dossier(n)}\n\nQuestion: {QUESTIONS[n % len(QUESTIONS)]}'


SYSTEM = 'You are SafeSpace\'s incident assistant. Answer only from the supplied dossiers. Cite incident IDs. Be concise.'


def stream_ollama(model, options, extra=None, images=None):
    user = {'role': 'user', 'content': next_prompt(), **({'images': images} if images else {})}
    body = {'model': model, 'stream': True, 'think': False, 'keep_alive': '10m', 'messages': [{'role': 'system', 'content': SYSTEM}, user], 'options': {'num_ctx': 6144, 'num_predict': 160, 'temperature': 0.2, **options}, **(extra or {})}
    start = time.perf_counter()
    first, tokens, final = None, 0, {}
    with httpx.stream('POST', f'{OLLAMA}/api/chat', json=body, timeout=300) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            item = json.loads(line)
            if item.get('message', {}).get('content'):
                first = first or time.perf_counter() - start
                tokens += 1
            if item.get('done'):
                final = item
    total = time.perf_counter() - start
    eval_s = (final.get('eval_duration') or 0) / 1e9
    return {'ttft_s': round(first or total, 3), 'tokens': final.get('eval_count', tokens), 'decode_tps': round(final.get('eval_count', tokens) / eval_s, 2) if eval_s else None, 'total_s': round(total, 3)}


def stream_groq(model):
    key = ENV.get('GROQ_API_KEY')
    body = {'model': model, 'stream': True, 'max_completion_tokens': 160, 'temperature': 0.2, 'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': next_prompt()}]}
    start = time.perf_counter()
    first, chunks = None, 0
    with httpx.stream('POST', 'https://api.groq.com/openai/v1/chat/completions', json=body, headers={'Authorization': f'Bearer {key}'}, timeout=120) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith('data: ') and line != 'data: [DONE]':
                delta = (json.loads(line[6:]).get('choices') or [{}])[0].get('delta', {}).get('content')
                if delta:
                    first = first or time.perf_counter() - start
                    chunks += 1
    total = time.perf_counter() - start
    return {'ttft_s': round(first or total, 3), 'tokens': chunks, 'decode_tps': round(chunks / max(total - (first or 0), 1e-6), 2), 'total_s': round(total, 3)}


def median(rows, key):
    values = [r[key] for r in rows if r.get(key) is not None]
    return round(statistics.median(values), 3) if values else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeat', type=int, default=3)
    ap.add_argument('--model', default=ENV.get('OLLAMA_MODEL', 'gemma4:e2b'))
    ap.add_argument('--gpu-layers', default='0,12,99', help='comma list of num_gpu values to test')
    ap.add_argument('--models', default=None, help='comma list of Ollama models to compare, e.g. gemma4:e2b,gemma4-e2b-nodraft')
    ap.add_argument('--image', default=None, help='also time each config with one evidence frame attached')
    ap.add_argument('--draft-model', default=None, help='(legacy) extra Ollama model measured at 99 GPU layers')
    a = ap.parse_args()
    results = []
    label = {'gemma4:e2b': 'gemma4:e2b (stock build, MTP drafter)', 'gemma4-e2b-nodraft': 'gemma4:e2b without the MTP drafter'}
    models = a.models.split(',') if a.models else [a.model]
    configs = [(f'{label.get(m, m)} · {n} GPU layers', m, {'num_gpu': int(n)}) for m in models for n in a.gpu_layers.split(',')]
    image_b64 = None
    if a.image:
        import base64
        image_b64 = [base64.b64encode(Path(a.image).read_bytes()).decode()]
    if a.draft_model:
        configs += [(f'{a.draft_model} (MTP speculative) · 99 GPU layers', a.draft_model, {'num_gpu': 99})]
    for label, model, options in configs:
        try:
            stream_ollama(model, options)  # warm: load weights (not timed)
            rows = [stream_ollama(model, options) for _ in range(a.repeat)]
            results.append({'label': label, 'provider': 'ollama', 'model': model, 'options': options, 'runs': rows, 'median_ttft_s': median(rows, 'ttft_s'), 'median_decode_tps': median(rows, 'decode_tps')})
            if image_b64:
                stream_ollama(model, options, images=image_b64)
                rows = [stream_ollama(model, options, images=image_b64) for _ in range(max(1, a.repeat - 1))]
                results.append({'label': label + ' + 1 evidence frame', 'provider': 'ollama', 'model': model, 'options': options, 'runs': rows, 'median_ttft_s': median(rows, 'ttft_s'), 'median_decode_tps': median(rows, 'decode_tps')})
        except Exception as exc:  # noqa: BLE001
            results.append({'label': label, 'provider': 'ollama', 'model': model, 'options': options, 'error': f'{type(exc).__name__}: {str(exc)[:160]}'})
        print(results[-1]['label'], results[-1].get('median_ttft_s'), results[-1].get('median_decode_tps'), results[-1].get('error', ''), flush=True)
    if ENV.get('GROQ_API_KEY'):
        model = ENV.get('GROQ_MODEL', 'qwen/qwen3.8-27b')
        try:
            stream_groq(model)
            rows = [stream_groq(model) for _ in range(a.repeat)]
            results.append({'label': f'Groq · {model}', 'provider': 'groq', 'model': model, 'runs': rows, 'median_ttft_s': median(rows, 'ttft_s'), 'median_decode_tps': median(rows, 'decode_tps')})
        except Exception as exc:  # noqa: BLE001
            results.append({'label': f'Groq · {model}', 'provider': 'groq', 'model': model, 'error': f'{type(exc).__name__}: {str(exc)[:160]}'})
        print(results[-1]['label'], results[-1].get('median_ttft_s'), results[-1].get('median_decode_tps'), results[-1].get('error', ''), flush=True)
    out = ROOT / 'storage/benchmarks'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'chat.json').write_text(json.dumps({'generated_at': time.time(), 'prompt_chars': len(next_prompt()), 'note': 'every timed request carries a different incident id and question, so first-token times are not served from the KV prefix cache', 'configs': results}, indent=2))


if __name__ == '__main__':
    main()
