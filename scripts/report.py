"""Render docs/benchmarks.md from storage/benchmarks/*.json — the only source of numbers in the docs."""
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'storage/benchmarks'


def pct(v):
    return '—' if v is None else f'{v * 100:.1f}%'


def load(name):
    path = BENCH / f'{name}.json'
    return json.loads(path.read_text()) if path.exists() else None


def detector(name, d):
    lines = [f'### {name.replace("_", " ").title()}', '',
             f'Held-out test images: {d["splits"]["test"]} ({d["clean_test_images"]} contain no labelled threat). mAP50 **{pct(d["overall"]["mAP50"])}**, mAP50-95 {pct(d["overall"]["mAP50_95"])}.',
             f'Latency {d["latency"]["median_ms"]} ms/frame (p95 {d["latency"]["p95_ms"]} ms), peak VRAM {d["latency"]["peak_vram_mb"]} MB.', '',
             '| Class | AP50 | Precision | Recall | F1 | Alert threshold | Test instances |', '|---|---|---|---|---|---|---|']
    for c, r in d['per_class'].items():
        lines.append(f'| {c} | {pct(r.get("ap50"))} | {pct(r["precision"])} | {pct(r["recall"])} | {pct(r["f1"])} | {r["threshold"]:.3f} | {r["test_instances"]} |')
    il = d['image_level']
    lines += ['', f'Image-level alerting: precision {pct(il["precision"])}, recall {pct(il["recall"])}, **false-alarm rate on clean images {pct(il["false_alarm_rate_on_clean_images"])}**.']
    for inc in d.get('incumbents', []):
        i = inc['image_level']
        c = d.get('image_level_comparable') or il
        lines.append(f'Compared on the same test images and classes ({", ".join(c.get("classes", []))}): new weights recall {pct(c["recall"])} / false alarms {pct(c["false_alarm_rate_on_clean_images"])}; previous weights `{Path(inc["weights"]).name}` recall {pct(i["recall"])} / false alarms {pct(i["false_alarm_rate_on_clean_images"])}.')
    return lines + ['']


def main():
    out = ['# Benchmarks', '', f'_Generated {time.strftime("%Y-%m-%d %H:%M")} from `storage/benchmarks/`. Thresholds are chosen on validation data only; every number below is measured on held-out test data._', '']
    for path in sorted(BENCH.glob('*.json')):
        d = json.loads(path.read_text())
        if 'per_class' in d:
            out += detector(path.stem, d)
    v = load('violence')
    if v:
        out += ['### Violence recognition (clip and single-frame)', '', f'{v["train_clips"]} training / {v["val_clips"]} validation / {v["test_clips"]} held-out test clips. Frozen DINOv2-base features + temporal head.', '',
                '| Evaluation | Accuracy | Precision | Recall | F1 | ROC AUC | False-alarm rate |', '|---|---|---|---|---|---|---|']
        for k, m in v['overall'].items():
            out.append(f'| {k.replace("_", " ")} | {pct(m["accuracy"])} | {pct(m["precision"])} | {pct(m["recall"])} | {pct(m["f1"])} | {pct(m["roc_auc"])} | {pct(m["false_alarm_rate"])} |')
        out += ['', '| Dataset (held-out clips) | Clips | Clip accuracy | Single-frame accuracy |', '|---|---|---|---|']
        for n, m in v['by_dataset'].items():
            out.append(f'| {n} | {m["clips"]} | {pct(m["clip_8_frames"]["accuracy"])} | {pct(m["single_frame"]["accuracy"])} |')
        out.append('')
    chat = load('chat')
    if chat:
        out += ['### Assistant latency', '', '| Configuration | First token | Decode tokens/s |', '|---|---|---|']
        for c in chat['configs']:
            out.append(f'| {c["label"]} | {"failed" if c.get("error") else str(c["median_ttft_s"]) + " s"} | {c.get("median_decode_tps") or "—"} |')
        out.append('')
    eco = load('ecosystem')
    if eco:
        out += [f'### End-to-end verification ({eco["passed"]}/{eco["total"]} checks passed)', '', '| Check | Result |', '|---|---|']
        for c in eco['checks']:
            out.append(f'| {c["name"]} | {"pass" if c["passed"] else "**FAIL**"} — {c["detail"]} |')
        out += ['', 'Latency (ms): ' + ', '.join(f'{k}={v}' for k, v in eco['latency_ms'].items()), '']
    (ROOT / 'docs/benchmarks.md').write_text('\n'.join(out))
    print('wrote docs/benchmarks.md')


if __name__ == '__main__':
    main()
