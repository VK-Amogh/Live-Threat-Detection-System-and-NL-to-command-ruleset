"""Render docs/benchmarks.md from storage/benchmarks/*.json — the only source of numbers in the docs.

Inputs (each optional): stack_images.json (scripts/eval/image_eval.py), blind_fresh.json (blind_score.py --json),
fire_smoke.json / weapons.json (benchmark_detector.py), verifier.json, violence_ensemble.json, chat.json, ecosystem.json.
"""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'storage/benchmarks'


def pct(v, digits=1):
    return '—' if v is None else f'{v * 100:.{digits}f}%'


def load(name):
    path = BENCH / f'{name}.json'
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else None


def rate(counts, fam, kind):
    if kind == 'recall':
        return counts.get(f'{fam}_hit', 0) / counts[f'{fam}_pos'] if counts.get(f'{fam}_pos') else None
    return counts.get(f'{fam}_false_alarm', 0) / counts['clean'] if counts.get('clean') else None


def stack_section(stack):
    sources = sorted({k.split('|')[0] for k in stack})
    out = ['## 1. Still images through the whole deployed stack', '',
           'Held-out annotated images (never trained on, near-duplicates of training images removed) and **blind video frames** the system never saw. '
           '"Detector only" = raw YOLO thresholds; "full stack" = YOLO proposals re-scored by the DINOv2 verifier. Recall is per positive image (any alert of the right family); '
           'false alarm = share of threat-free images with an alert of that family.', '',
           '| Source | Images | Mode | Fire/smoke recall | Fire/smoke false alarm | Weapon recall | Weapon false alarm | Fight recall | Fight false alarm |', '|---|---|---|---|---|---|---|---|---|']
    for src in sources:
        for mode in ('detector_only', 'full_stack'):
            c = stack.get(f'{src}|{mode}')
            if not c:
                continue
            cells = [pct(rate(c, fam, kind)) if (rate(c, fam, kind) is not None) else '—' for fam in ('FIRE/SMOKE', 'WEAPON', 'FIGHT') for kind in ('recall', 'false_alarm')]
            out.append(f'| {src} | {c["images"]} | {mode.replace("_", " ")} | ' + ' | '.join(cells) + ' |')
    return out + ['']


def blind_section(blind):
    p = blind['policy']
    out = ['## 2. Blind video: DCSASS (UCF-Crime CCTV, 320x240) fresh sample', '',
           f'Clips from *parent videos never used in training, mining or calibration*, replayed like an upload with the production decision code '
           f'(verifier {"on" if p["verifier"] else "off"}, {p["k_hits"]}-of-{p["n_window"]} persistence). Ground truth is by DCSASS category because sub-clip labels are coarse.', '',
           '| Threat | Positive clips detected | Clean clips with a false alarm |', '|---|---|---|']
    for name in ('FIRE/SMOKE', 'FIGHT', 'WEAPON'):
        r = blind[name]
        rec = f'{pct(r["recall"])} ({r["detected"]}/{r["positive_clips"]})' if r['recall'] is not None else 'not scored (a Shooting/Robbery clip may not show the weapon)'
        out.append(f'| {name} | {rec} | {pct(r["clip_false_alarm_rate"])} ({r["false_alarm_clips"]}/{r["clean_clips"]}) |')
    out += ['', '| Category / label | Clips | Fire/smoke alerts | Weapon alerts | Fight alerts |', '|---|---|---|---|---|']
    for key, v in blind['by_category'].items():
        out.append(f'| {key} | {v["clips"]} | {v.get("FIRE/SMOKE", 0)} | {v.get("WEAPON", 0)} | {v.get("FIGHT", 0)} |')
    out += ['', 'Label 1 = anomalous sub-clip, 0 = "normal" sub-clip of an anomaly video (these can still show the event). The fresh sample contains no Explosion label-1 clips '
            '(all were used in earlier samples), so fire/smoke recall here rests on Arson clips.', '']
    audit = load('blind_fresh_fire_audit')
    if audit:
        out += ['**Fire/smoke audit (`scripts/eval/audit_fire_blind.py`).** Looking at one frame of every Arson/1 clip by eye shows that many of them *do* contain visible flames or a burning vehicle '
                '(at least 15 of the 47 sampled frames, e.g. a burning car and a table fire), so the low recall is a genuine miss, not label noise. '
                f'All {audit["explosion0_alerted"]} fire/smoke alerts on Explosion/0 clips show a real smoke or dust cloud (the dataset calls these sub-clips "normal"); they are not counted as false alarms. '
                'Where the Arson clips are lost, per parent video:', '',
                '| Parent video | Clips | Sampled frames | Frames with any fire/smoke proposal | Best raw detector score | Best verifier score |', '|---|---|---|---|---|---|']
        for parent, r in audit['per_parent'].items():
            out.append(f'| {parent} | {r["clips"]} | {r["frames"]} | {r["frames_with_proposal"]} | {r["best_detector_conf"]} | {r["best_verifier_prob"]} |')
        out += ['', 'Three parents (15 clips) never produce a proposal (the first-stage detector sees nothing at 320x240); on the burning-car parent the best verifier score (0.75) stays below the fire threshold (0.938), '
                'and on Arson005/040 some proposals score 0.99-1.0 with the verifier yet only one clip alerted, so they were not persistent enough for the 3-of-4 rule. Fire and smoke in low-resolution CCTV is the weakest part of the system.', '']
    return out


def detector_section(title, d):
    out = [f'### {title}', '', f'Test images: {d["splits"]["test"]} ({d["clean_test_images"]} threat-free). mAP50 **{pct(d["overall"]["mAP50"])}**, mAP50-95 {pct(d["overall"]["mAP50_95"])}. '
           f'Latency {d["latency"]["median_ms"]} ms/frame (p95 {d["latency"]["p95_ms"]} ms) at {d.get("imgsz", "?")} px.', '',
           '| Class | AP50 | Precision | Recall | F1 | Raw-detector alert threshold | Test instances |', '|---|---|---|---|---|---|---|']
    for c, r in d['per_class'].items():
        out.append(f'| {c} | {pct(r.get("ap50"))} | {pct(r["precision"])} | {pct(r["recall"])} | {pct(r["f1"])} | {r["threshold"]:.3f} | {r["test_instances"]} |')
    out += ['', '| Source | Images | Clean | New weights recall | New false alarm | Previous recall | Previous false alarm |', '|---|---|---|---|---|---|---|']
    prev = (d.get('incumbents') or [{}])[0].get('by_source', {})
    for src, v in d.get('by_source', {}).items():
        p = prev.get(src, {})
        out.append(f'| {src} | {sum(v["images"].values())} | {v["clean_images"]} | {pct(v["recall"]) if sum(v["images"][k] for k in ("tp", "fn")) else "—"} | {pct(v["false_alarm_rate_on_clean_images"]) if v["clean_images"] else "—"} | '
                   f'{pct(p.get("recall")) if p and sum(p["images"][k] for k in ("tp", "fn")) else "—"} | {pct(p.get("false_alarm_rate_on_clean_images")) if p and p.get("clean_images") else "—"} |')
    return out + ['']


def main():
    out = ['# Benchmarks', '', f'_Generated {time.strftime("%Y-%m-%d %H:%M")} from `storage/benchmarks/`. Method, data and caveats: [ml-pipeline.md](ml-pipeline.md). '
           'Thresholds are chosen on validation data only. Earlier blind samples shaped design decisions; section 2 uses a fresh sample taken after the configuration was frozen._', '']
    for fn, section in (('stack_images', stack_section), ('blind_fresh', blind_section)):
        d = load(fn)
        if d:
            out += section(d)
    out += ['## 3. Components', '', "Component benchmarks use each detector's benchmark resolution. In production the gun/knife detector runs at 640 px (the verifier was trained on proposals made at that size); the stack numbers in sections 1 and 2 use the deployed configuration.", '']
    for name, title in (('fire_smoke', 'Fire / smoke detector (stage 1)'), ('weapons', 'Gun / knife detector (stage 1)')):
        d = load(name)
        if d:
            out += detector_section(title, d)
    v = load('verifier')
    if v:
        out += ['### Verifier (stage 2)', '', f'Trained on {v["train_records"]} crops. ROC AUC on held-out *actual detector proposals*: ' + ', '.join(f'{k.replace("yolo_confidence_only", "YOLO confidence alone (baseline)")} {pct(x)}' for k, x in v['auc']['test'].items()) +
                '. Frame-level false-alarm rate on blind video frames at the validation-chosen thresholds:', '',
                '| Class | Threshold | Recall of correct detections | ' + ' | '.join(sorted(next(iter(v['test'].values()))['blind_negative_frame_far'])) + ' |', '|---|---|---|' + '---|' * len(next(iter(v['test'].values()))['blind_negative_frame_far'])]
        for c, r in v['test'].items():
            out.append(f'| {c} | {r["threshold"]:.3f} | {pct(r["recall_of_correct_detections"])} | ' + ' | '.join(pct(x, 2) for _, x in sorted(r['blind_negative_frame_far'].items())) + ' |')
        out.append('')
    e = load('violence_ensemble')
    if e:
        s = e['combinations']['stack']
        out += ['### Violence (scene head + motion head, logistic stack)', '', f'Threshold {s["threshold"]:.3f} (validation false-alarm target {pct(s["val_far"], 0)}). Held-out clips per dataset (the in-domain test splits; RWF-2000 `val` is the official test set):', '',
                '| Dataset | AUC | Recall | False alarm |', '|---|---|---|---|']
        for d, r in s['test'].items():
            out.append(f'| {d} | {pct(r["auc"])} | {pct(r["recall"])} | {pct(r["false_alarm"])} |')
        b = s['blind_dcsass']
        out += [f'| DCSASS blind (Fighting/Assault/Abuse vs calm categories) | {pct(b["auc"])} | {pct(b["recall"])} | {pct(b["calm_false_alarm"])} |', '',
                'How the stack compares with its parts on the **blind DCSASS clips** (each at its own validation-chosen threshold, and at a common 5 % calm-clip false-alarm budget). '
                'The stack has the best AUC and a low false-alarm rate; at a fixed false-alarm budget it is not better than the best single head, so it was chosen for its false-alarm behaviour, not for recall.', '',
                '| Method | Blind AUC | Recall at its threshold | Calm-clip false alarm | Recall at 5 % calm false alarm |', '|---|---|---|---|---|']
        names = {'dinov2': 'DINOv2 scene head', 'videomae': 'VideoMAE motion head', 'mean': 'Mean of both', 'max': 'Max of both', 'stack': 'Logistic stack (deployed)'}
        for key, label in names.items():
            r = (e['combinations'].get(key) or {}).get('blind_dcsass')
            if r:
                out.append(f'| {label} | {pct(r["auc"])} | {pct(r["recall"])} | {pct(r["calm_false_alarm"])} | {pct(r["recall_at_calm_far_5pct"])} |')
        out.append('')
    chat = load('chat')
    if chat:
        out += ['## 4. Assistant latency (local Gemma 4 E2B vs Groq)', '',
                'Streaming requests with a realistic incident dossier. **Every timed request carries a different incident id and question**, so first-token times are not served from '
                f"the KV prefix cache. \"GPU layers\" is Ollama's `num_gpu` (0 = CPU only, 99 = everything on the RTX 4050). "
                "Decode speed is the model's own `eval_count / eval_duration`."
                ' The "without the MTP drafter" rows use the same weights with the multi-token-prediction drafter removed, '
                'which isolates what speculative decoding contributes.', '',
                '| Configuration | First token | Decode tokens/s |', '|---|---|---|']
        for c in chat['configs']:
            out.append(f'| {c["label"]} | {"failed" if c.get("error") else str(c["median_ttft_s"]) + " s"} | {c.get("median_decode_tps") or "—"} |')
        out.append('')
    eco = load('ecosystem')
    if eco:
        out += [f'## 5. End-to-end verification ({eco["passed"]}/{eco["total"]} checks passed)', '', '| Check | Result |', '|---|---|']
        for c in eco['checks']:
            out.append(f'| {c["name"]} | {"pass" if c["passed"] else "**FAIL**"} — {c["detail"]} |')
        out += ['', 'Latency (ms): ' + ', '.join(f'{k}={x}' for k, x in eco['latency_ms'].items()), '']
    (ROOT / 'docs/benchmarks.md').write_text('\n'.join(out))
    print('wrote docs/benchmarks.md')


if __name__ == '__main__':
    main()
