import { Badge } from '../components';

type Num = number | null | undefined;
const pct = (v: Num) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—');
type ClassRow = { threshold: number; precision: number; recall: number; f1: number; ap50?: number; ap50_95?: number; test_instances?: number };
type Detector = { name: string; overall: Record<string, number>; per_class: Record<string, ClassRow>; image_level: { precision: number; recall: number; false_alarm_rate_on_clean_images: number };
  latency: { median_ms: number; p95_ms: number; peak_vram_mb: number }; splits: Record<string, number>; clean_test_images: number; incumbents?: { weights: string; image_level: { recall: number; precision: number; false_alarm_rate_on_clean_images: number } }[]; image_level_comparable?: { classes: string[]; recall: number; false_alarm_rate_on_clean_images: number } };
type Metrics = { accuracy: number; precision: number; recall: number; f1: number; roc_auc: number | null; false_alarm_rate: number; n: number; threshold: number };
type Violence = { train_clips: number; val_clips: number; test_clips: number; overall: Record<string, Metrics>; by_dataset: Record<string, { clips: number; clip_8_frames: Metrics; single_frame: Metrics }> };
type Chat = { configs: { label: string; median_ttft_s?: number | null; median_decode_tps?: number | null; error?: string }[] };
type Ecosystem = { checks: { name: string; passed: boolean; detail: string }[]; latency_ms: Record<string, number> };
type Run = { status?: string; epoch?: number; epochs?: number; model?: string; elapsed_s?: number; metrics?: Record<string, number>; error?: string };

export function TrainingPanel({ training }: { training?: Record<string, unknown> }) {
  const runs = (training?.runs || {}) as Record<string, Run>;
  const bench = (training?.benchmarks || {}) as Record<string, unknown>;
  const detectors = Object.entries(bench).filter(([, v]) => Boolean((v as Detector).per_class)) as [string, Detector][];
  const chat = bench.chat as Chat | undefined;
  const ecosystem = bench.ecosystem as Ecosystem | undefined;
  const violence = bench.violence as Violence | undefined;
  return <section className="panel wide"><div className="section-head"><h2>Model training and benchmarks</h2><Badge>{String(training?.status || 'Not started')}</Badge></div>
    {Object.entries(runs).map(([name, run]) => <div key={name}><div className="setting-row"><strong>{name.replaceAll('_', ' ')}</strong><span>{run.status}{run.epoch !== undefined ? ` · epoch ${run.epoch}/${run.epochs}` : ''}</span></div>
      {run.status === 'training' && run.epochs ? <div className="progress" role="progressbar" aria-valuenow={run.epoch || 0} aria-valuemax={run.epochs}><div style={{ width: `${((run.epoch || 0) / run.epochs) * 100}%` }} /></div> : null}
      {run.error && <p className="caption">{run.error}</p>}
      {run.status === 'training' && run.metrics && <p className="caption">mAP50 {pct(run.metrics['metrics/mAP50(B)'])} · precision {pct(run.metrics['metrics/precision(B)'])} · recall {pct(run.metrics['metrics/recall(B)'])} (validation, live)</p>}</div>)}
    <div className="bench">
      {detectors.map(([name, d]) => <div key={name}><h3>{name.replaceAll('_', ' ')}</h3>
        <div className="bench-meta"><Badge>mAP50 {pct(d.overall.mAP50)}</Badge><Badge>mAP50-95 {pct(d.overall.mAP50_95)}</Badge><Badge>{d.latency.median_ms} ms / frame</Badge><Badge>{d.latency.peak_vram_mb} MB VRAM</Badge><Badge>{d.splits.test} held-out test images</Badge></div>
        <table className="bench-table"><thead><tr><th>Class</th><th>AP50</th><th>Precision</th><th>Recall</th><th>F1</th><th>Alert at</th></tr></thead><tbody>
          {Object.entries(d.per_class).map(([c, r]) => <tr key={c}><td>{c}</td><td>{pct(r.ap50)}</td><td>{pct(r.precision)}</td><td>{pct(r.recall)}</td><td>{pct(r.f1)}</td><td>{r.threshold.toFixed(2)}</td></tr>)}</tbody></table>
        <p className="caption">Clean-image false alarms: {pct(d.image_level.false_alarm_rate_on_clean_images)} of {d.clean_test_images} threat-free test images · image-level recall {pct(d.image_level.recall)}. Thresholds were chosen on validation data, never on the test split.
          {d.incumbents?.map(i => ` Same-class comparison (${(d.image_level_comparable?.classes || []).join(', ')}): new recall ${pct(d.image_level_comparable?.recall)} / false alarms ${pct(d.image_level_comparable?.false_alarm_rate_on_clean_images)} vs previous weights recall ${pct(i.image_level.recall)} / false alarms ${pct(i.image_level.false_alarm_rate_on_clean_images)}.`)}</p></div>)}
      {violence && <div><h3>violence (video)</h3>
        <div className="bench-meta"><Badge>{violence.test_clips} held-out clips</Badge><Badge>{violence.train_clips} training clips</Badge></div>
        <table className="bench-table"><thead><tr><th>Evaluation</th><th>Accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC AUC</th><th>False alarms</th></tr></thead><tbody>
          {Object.entries(violence.overall).map(([k, m]) => <tr key={k}><td>{k.replaceAll('_', ' ')}</td><td>{pct(m.accuracy)}</td><td>{pct(m.precision)}</td><td>{pct(m.recall)}</td><td>{pct(m.f1)}</td><td>{pct(m.roc_auc)}</td><td>{pct(m.false_alarm_rate)}</td></tr>)}</tbody></table>
        <p className="caption">Per-dataset results are on clips from sources never seen in training: {Object.entries(violence.by_dataset).map(([n, v]) => `${n} ${pct(v.clip_8_frames.accuracy)} (${v.clips})`).join(' · ')}.</p></div>}
      {chat && <div><h3>assistant latency</h3><table className="bench-table"><thead><tr><th>Configuration</th><th>First token</th><th>Tokens / s</th></tr></thead><tbody>
        {chat.configs.map(c => <tr key={c.label}><td>{c.label}</td><td>{c.error ? 'failed' : `${c.median_ttft_s} s`}</td><td>{c.error ? '—' : c.median_decode_tps}</td></tr>)}</tbody></table></div>}
      {ecosystem && <div><h3>end-to-end verification</h3><table className="bench-table"><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>
        {ecosystem.checks.map(c => <tr key={c.name}><td>{c.name}</td><td>{c.passed ? 'pass' : 'FAIL'} · {c.detail}</td></tr>)}</tbody></table></div>}
      {!detectors.length && !violence && <p className="muted">Benchmarks appear after a model finishes training and evaluation.</p>}
    </div></section>;
}
