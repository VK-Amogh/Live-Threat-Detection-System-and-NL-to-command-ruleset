"""False-alarm check of the crime-type head on real, mostly uneventful footage: storage/recordings (phone/CCTV segments) and TestVideos.

python scripts/crime/eval_recordings.py
Every video is resampled to 5 fps (the live/upload rate of the runtime), cut into 16-frame windows (3.2 s, stride 8 frames) and scored exactly like a
training clip: DINOv2 frame features (224x224 squash) pooled to [mean | std], VideoMAE-K400 clip feature, calibrated temperature and per-type thresholds.
Nothing here was trained on or tuned against. storage/recordings holds the user's own phone footage, mostly with nothing criminal happening: a flagged window
is a false alarm unless the saved frames show otherwise (scripts/crime/inspect_errors.py renders the top-scoring windows). TestVideos are SCVD demo clips of
real violence/weapons, so they are listed per clip and are NOT counted as false alarms.
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'violence'))
from crime_common import CLASSES, NONE, ROOT, TYPES, pool_features, predict_types  # noqa: E402
from score_blind import load_model, probabilities  # noqa: E402
from extract_features import squash  # noqa: E402
from extract_videomae import MEAN, MODEL, STD, prep  # noqa: E402
from vision_features import encode_frames, load_encoder  # noqa: E402

FPS, WINDOW, STRIDE = 5.0, 16, 8


def sampled_frames(path):
    """Frames at ~FPS by timestamp -> (DINOv2 inputs N,224,224,3 RGB uint8, VideoMAE inputs N,224,224,3 RGB uint8, timestamps)."""
    cap = cv2.VideoCapture(str(path))
    native = cap.get(cv2.CAP_PROP_FPS) or 30.0
    dino, mae, times, nxt, i = [], [], [], 0.0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if t <= 0 and i > 0:
            t = i / native
        i += 1
        if t + 1e-6 >= nxt:
            dino.append(squash(frame))
            mae.append(cv2.cvtColor(prep(frame), cv2.COLOR_BGR2RGB))
            times.append(t)
            nxt = max(nxt + 1 / FPS, t + 0.5 / FPS)
    cap.release()
    return (np.stack(dino) if dino else None), (np.stack(mae) if mae else None), times


def windows_of(n):
    if n < 8:
        return []
    if n < WINDOW:
        return [np.linspace(0, n - 1, WINDOW).round().astype(int)]
    starts = list(range(0, n - WINDOW + 1, STRIDE))
    if starts[-1] != n - WINDOW:
        starts.append(n - WINDOW)
    return [np.arange(s, s + WINDOW) for s in starts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', default='crime_type')
    a = ap.parse_args()
    model, side = load_model(a.name)
    taus = side['thresholds']
    encoder = load_encoder('cuda')
    from transformers import VideoMAEForVideoClassification
    vmae = VideoMAEForVideoClassification.from_pretrained(MODEL, dtype=torch.float16).cuda().eval()
    mean, std = torch.tensor(MEAN).view(1, 1, 3, 1, 1).cuda(), torch.tensor(STD).view(1, 1, 3, 1, 1).cuda()

    paths = sorted((ROOT / 'storage/recordings').rglob('*.mp4')) + sorted((ROOT / 'TestVideos').glob('*'))
    records = []
    started = time.time()
    for k, path in enumerate(paths):
        dino, mae, times = sampled_frames(path)
        wins = windows_of(0 if dino is None else len(dino))
        if not wins:
            records.append({'video': str(path.relative_to(ROOT)), 'camera': None, 'windows': 0, 'skipped': 'fewer than 8 sampled frames'})
            continue
        feats = encode_frames(encoder, torch.from_numpy(dino)).cpu().numpy()                              # N,1536
        d = np.stack([feats[w] for w in wins])                                                              # W,16,1536
        clip = torch.from_numpy(np.stack([mae[w] for w in wins])).cuda().permute(0, 1, 4, 2, 3).float() / 255.0   # W,16,3,224,224
        with torch.inference_mode():
            out = vmae(pixel_values=((clip - mean) / std).half(), output_hidden_states=True)
            v = torch.cat([out.hidden_states[-1].mean(1).float(), out.logits.float()], dim=1).cpu().numpy()
        prob = probabilities(model, side, pool_features(d, v))
        pred, p_top = predict_types(prob, taus)
        cam = path.parts[-3] if path.parent.parent.parent.name == 'recordings' else path.parent.name
        records.append({'video': str(path.relative_to(ROOT)), 'camera': cam, 'windows': len(wins), 'start_s': [float(times[w[0]]) for w in wins], 'span_s': float(times[wins[0][-1]] - times[wins[0][0]]),
                        'pred': [CLASSES[int(i)] for i in pred], 'p_top': [float(x) for x in p_top], 'top_type': [TYPES[int(i)] for i in prob[:, :NONE].argmax(1)], 'p_none': [float(x) for x in prob[:, NONE]],
                        'luminance': [float(dino[w].mean()) for w in wins]})
        if k % 10 == 0:
            print(f'{k}/{len(paths)} videos {time.time() - started:.0f}s', flush=True)

    rec = [r for r in records if r['windows'] and r['video'].startswith('storage')]
    demo = [r for r in records if r['windows'] and r['video'].startswith('TestVideos')]
    n_windows = sum(r['windows'] for r in rec)
    hours = sum(r['windows'] * STRIDE / FPS for r in rec) / 3600
    rng = np.random.default_rng(0)
    out = {'generated_at': time.time(), 'fps': FPS, 'window_frames': WINDOW, 'stride_frames': STRIDE, 'recording_videos': len(rec), 'recording_windows': n_windows, 'recording_hours_approx': hours,
           'cameras': dict(Counter(r['camera'] for r in rec)), 'thresholds': taus, 'types': {}, 'any_type': {}}
    seg_flags = {t: np.array([sum(p == t for p in r['pred']) for r in rec]) for t in TYPES}
    seg_wins = np.array([r['windows'] for r in rec])
    for t in TYPES:
        flagged = int(seg_flags[t].sum())
        draws = []
        for _ in range(1000):
            idx = rng.integers(0, len(rec), len(rec))
            draws.append(seg_flags[t][idx].sum() / seg_wins[idx].sum())
        by_cam = defaultdict(lambda: [0, 0])
        for r, f in zip(rec, seg_flags[t]):
            by_cam[r['camera']][0] += int(f)
            by_cam[r['camera']][1] += r['windows']
        out['types'][t] = {'windows_flagged': flagged, 'window_flag_rate': flagged / n_windows, 'window_flag_rate_ci95': [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))],
                           'videos_with_a_flag': int((seg_flags[t] > 0).sum()), 'per_camera': {c: {'flagged': v[0], 'windows': v[1]} for c, v in by_cam.items()}}
    lum = np.array([x for r in rec for x in r['luminance']])
    out['brightness'] = {'dark_windows_lt_25_of_255': int((lum < 25).sum()), 'windows_ge_25': int((lum >= 25).sum()), 'windows_ge_60': int((lum >= 60).sum()),
                         'median_luminance': float(np.median(lum))}
    any_flag = sum(sum(p != 'none' for p in r['pred']) for r in rec)
    out['any_type'] = {'windows_flagged': any_flag, 'window_flag_rate': any_flag / n_windows, 'flags_per_hour': any_flag / max(hours, 1e-9), 'videos_with_a_flag': sum(any(p != 'none' for p in r['pred']) for r in rec)}
    top = sorted(((p, r['video'], r['start_s'][i], r['top_type'][i]) for r in rec for i, p in enumerate(r['p_top'])), reverse=True)[:30]
    out['top_scoring_windows'] = [{'p': p, 'video': v, 'start_s': s, 'type': t} for p, v, s, t in top]
    out['testvideos'] = {r['video']: {'windows': r['windows'], 'flagged': dict(Counter(p for p in r['pred'] if p != 'none')), 'max_p_top_by_type': {t: max((p for p, tt in zip(r['p_top'], r['top_type']) if tt == t), default=None) for t in set(r['top_type'])}} for r in demo}
    out['records'] = records
    (ROOT / 'storage/benchmarks/crime_type_recordings.json').write_text(json.dumps(out, indent=2))
    print(f'{len(rec)} recordings, {n_windows} windows (~{hours:.2f} h of footage); skipped {sum(1 for r in records if not r["windows"])}')
    b = out['brightness']
    print(f'brightness: {b["dark_windows_lt_25_of_255"]} of {n_windows} windows are nearly black (mean luminance < 25/255), {b["windows_ge_60"]} are reasonably lit (>= 60); median {b["median_luminance"]:.0f}')
    print(f'any crime type flagged: {out["any_type"]["window_flag_rate"]:.1%} of windows, {out["any_type"]["videos_with_a_flag"]} of {len(rec)} videos, {out["any_type"]["flags_per_hour"]:.1f} windows/hour')
    for t in TYPES:
        s = out['types'][t]
        print(f'  {t:14s} windows flagged {s["windows_flagged"]:4d} ({s["window_flag_rate"]:.1%}, 95% CI {s["window_flag_rate_ci95"][0]:.1%}-{s["window_flag_rate_ci95"][1]:.1%}) in {s["videos_with_a_flag"]} videos  (threshold {taus[t]})')
    print('TestVideos (real violence/weapons demo clips, not false alarms):')
    for v, s in out['testvideos'].items():
        print(f'  {v}: {s["windows"]} windows, flagged {s["flagged"] or "nothing"}, max type prob {({k: round(x, 2) for k, x in s["max_p_top_by_type"].items()})}')


if __name__ == '__main__':
    main()
