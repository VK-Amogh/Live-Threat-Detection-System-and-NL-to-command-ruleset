"""Evaluate the deployed frame and incident policy on labelled local video clips.

This diagnostic runs the inference service in process, samples frames exactly as
the API's uploaded-video loop does, and records both raw violence scores and
filtered detections. It never writes incidents to the application database.

Examples:
  python scripts/evaluate_video_pipeline.py --set testvideos --output runs/testvideos-before.json
  python scripts/evaluate_video_pipeline.py --set scvd-test --output runs/scvd-test-after.json
"""
import argparse
import hashlib
import io
import json
import sys
from collections import deque
from pathlib import Path

import cv2
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'services/inference'), str(ROOT / 'contracts/src')]
import server  # noqa: E402


def inputs(which):
    manifest = json.loads((ROOT / 'storage/datasets/violence/manifest.json').read_text())
    if which in ('scvd-test', 'scvd-val'):
        split = which.removeprefix('scvd-')
        return [(Path(row['path']), row['label'], row['split']) for row in manifest
                if row['dataset'] == 'SCVD (CCTV)' and row['split'] == split]
    paths = sorted((ROOT / 'TestVideos').glob('*'))
    return [(path, int(path.name.lower().startswith(('v', 'w'))),
             next((r['split'] for r in manifest if Path(r['path']).stem == path.stem.removesuffix(' 3')), 'unknown'))
            for path in paths if path.suffix.lower() in ('.avi', '.mp4', '.mov', '.mkv')]


def evaluate_clip(path, label, split, policy, sample_fps):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f'Cannot open {path}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    stride = max(1, int(fps / sample_fps))
    stream = hashlib.sha256(str(path).encode()).hexdigest()[:32]
    k_hits, n_window, immediate = policy
    hits = {}
    incidents = set()
    raw_scores = []
    frames = []
    original_score = server.VIOLENCE.score if server.VIOLENCE else None

    def capture_score(image, source_id):
        score, count = original_score(image, source_id)
        raw_scores.append((score, count))
        return score, count

    if original_score:
        server.VIOLENCE.score = capture_score
    try:
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % stride == 0:
                ok_jpg, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok_jpg:
                    raise ValueError(f'Cannot encode frame {index} of {path}')
                result = server.predict(jpg.tobytes(), stream)
                categories = {}
                for detection in result.detections:
                    if detection.category:
                        categories[detection.category] = max(categories.get(detection.category, 0), detection.confidence)
                for category in set(hits) | set(categories):
                    window = hits.setdefault(category, deque(maxlen=n_window))
                    conf = categories.get(category, 0)
                    window.append(conf > 0)
                    if conf >= immediate or sum(window) >= k_hits:
                        incidents.add(category)
                frames.append({'offset_ms': round(index / fps * 1000),
                               'detections': [{'class': d.class_name, 'confidence': round(d.confidence, 4)}
                                              for d in result.detections if d.category],
                               'violence_score': round(raw_scores[-1][0], 4) if raw_scores else None,
                               'violence_window': raw_scores[-1][1] if raw_scores else None})
            index += 1
    finally:
        if original_score:
            server.VIOLENCE.score = original_score
        cap.release()
        server.STREAMS.pop(stream, None)
    return {'file': str(path.relative_to(ROOT)), 'label': label, 'original_split': split,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'fps': fps,
            'duration_s': round(total / fps, 2), 'sampled_frames': len(frames),
            'max_violence_score': round(max((s for s, _ in raw_scores), default=0), 4),
            'violence_frame_hits': sum(any(d['class'] == 'violence' for d in f['detections']) for f in frames),
            'incidents': sorted(incidents), 'frames': frames}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--set', choices=('testvideos', 'scvd-val', 'scvd-test'), default='testvideos')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--sample-fps', type=float, default=2.0)
    p.add_argument('--fire-weights', type=Path, help='candidate checkpoint; keeps deployed fire/smoke thresholds for comparison')
    p.add_argument('--violence-head', type=Path, help='candidate violence-head checkpoint and adjacent JSON thresholds')
    args = p.parse_args()
    server.load_models()
    if server.ERRORS:
        raise RuntimeError(f'Model loading errors: {server.ERRORS}')
    if args.fire_weights:
        from ultralytics import YOLO
        if not args.fire_weights.exists():
            raise FileNotFoundError(args.fire_weights)
        candidate = YOLO(str(args.fire_weights))
        candidate.fuse(verbose=False)
        server.MODELS[:] = [(name, candidate if name == 'fire_smoke' else model, mtime, thresholds, imgsz)
                            for name, model, mtime, thresholds, imgsz in server.MODELS]
    if args.violence_head:
        import torch
        if server.VIOLENCE is None:
            raise RuntimeError('Deployed violence encoder is not loaded')
        state = torch.load(args.violence_head, map_location=server.VIOLENCE.device, weights_only=True)
        server.VIOLENCE.head.load_state_dict(state)
        meta = json.loads(args.violence_head.with_suffix('.json').read_text())
        server.VIOLENCE.thresholds = {int(k): v for k, v in meta['thresholds'].items()}
    worker = yaml.safe_load((ROOT / 'config/worker.yaml').read_text())['temporal_filter']
    policy = (int(worker.get('uploaded_video_k_hits', worker['k_hits'])), int(worker['n_window']),
              float(worker['immediate_confidence']))
    clips = []
    for path, label, split in inputs(args.set):
        row = evaluate_clip(path, label, split, policy, args.sample_fps)
        clips.append(row)
        print(f"{path.name}: label={label}, split={split}, frames={row['sampled_frames']}, "
              f"violence_peak={row['max_violence_score']:.3f}, incidents={row['incidents']}", flush=True)
    positive = [r for r in clips if r['label'] == 1]
    negative = [r for r in clips if r['label'] == 0]
    summary = {'positive_clips': len(positive), 'positive_detected': sum(bool(r['incidents']) for r in positive),
               'negative_clips': len(negative), 'negative_alerted': sum(bool(r['incidents']) for r in negative),
               'violence_detected': sum('FIGHT' in r['incidents'] for r in positive)}
    report = {'set': args.set, 'sample_fps': args.sample_fps, 'fire_weights': str(args.fire_weights) if args.fire_weights else None,
              'violence_head': str(args.violence_head) if args.violence_head else None,
              'models': server.coverage(), 'policy': {'k_hits': policy[0], 'n_window': policy[1],
              'immediate_confidence': policy[2]}, 'summary': summary, 'clips': clips}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print('SUMMARY', json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
