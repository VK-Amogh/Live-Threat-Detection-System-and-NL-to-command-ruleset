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
  const stack = bench.stack_images as Record<string, Record<string, number>> | undefined;
  const blind = bench.blind_fresh as Record<string, { positive_clips: number; detected: number; recall: number | null; clean_clips: number; false_alarm_clips: number; clip_false_alarm_rate: number }> | undefined;
  const verifier = bench.verifier as { auc: { test: Record<string, number> }; test: Record<string, { threshold: number; recall_of_correct_detections: number; blind_negative_frame_far: Record<string, number> }> } | undefined;
  const ensemble = bench.violence_ensemble as { combinations: { stack: { threshold: number; test: Record<string, { auc: number; recall: number; false_alarm: number }>; blind_dcsass: { auc: number; recall: number; calm_false_alarm: number } } } } | undefined;
  const rate = (c: Record<string, number>, fam: string, kind: 'recall' | 'false_alarm') => kind === 'recall' ? (c[`${fam}_pos`] ? c[`${fam}_hit`] / c[`${fam}_pos`] : null) : (c.clean ? (c[`${fam}_false_alarm`] || 0) / c.clean : null);
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
      {stack && <div><h3>whole stack on still images</h3><table className="bench-table"><thead><tr><th>Source · mode</th><th>Fire/smoke recall</th><th>false alarm</th><th>Weapon recall</th><th>false alarm</th><th>Fight recall</th><th>false alarm</th></tr></thead><tbody>
        {Object.entries(stack).sort().map(([k, c]) => <tr key={k}><td>{k.replace('|', ' · ').replaceAll('_', ' ')}</td>{(['FIRE/SMOKE', 'WEAPON', 'FIGHT'] as const).flatMap(f => [<td key={f + 'r'}>{pct(rate(c, f, 'recall'))}</td>, <td key={f + 'f'}>{pct(rate(c, f, 'false_alarm'))}</td>])}</tr>)}</tbody></table>
        <p className="caption">Held-out annotated images plus blind frames from video the system never saw. “detector only” = raw YOLO; “full stack” adds the verifier.</p></div>}
      {blind && <div><h3>blind video (DCSASS CCTV, fresh clips)</h3><table className="bench-table"><thead><tr><th>Threat</th><th>Positive clips detected</th><th>Clean clips with a false alarm</th></tr></thead><tbody>
        {(['FIRE/SMOKE', 'FIGHT', 'WEAPON'] as const).map(n => <tr key={n}><td>{n}</td><td>{blind[n].recall === null ? 'not scored' : `${pct(blind[n].recall)} (${blind[n].detected}/${blind[n].positive_clips})`}</td><td>{pct(blind[n].clip_false_alarm_rate)} ({blind[n].false_alarm_clips}/{blind[n].clean_clips})</td></tr>)}</tbody></table></div>}
      {verifier && <div><h3>verifier (second-stage re-scoring)</h3><table className="bench-table"><thead><tr><th>Class</th><th>AUC</th><th>Alert at</th><th>Recall of correct detections</th><th>Blind-frame false alarms</th></tr></thead><tbody>
        {Object.entries(verifier.test).map(([c, r]) => <tr key={c}><td>{c}</td><td>{pct(verifier.auc.test[c])}</td><td>{r.threshold.toFixed(2)}</td><td>{pct(r.recall_of_correct_detections)}</td><td>{Object.entries(r.blind_negative_frame_far).map(([s, x]) => `${s} ${(x * 100).toFixed(2)}%`).join(' · ')}</td></tr>)}</tbody></table></div>}
      {ensemble && <div><h3>violence (scene + motion)</h3><table className="bench-table"><thead><tr><th>Held-out dataset</th><th>AUC</th><th>Recall</th><th>False alarm</th></tr></thead><tbody>
        {Object.entries(ensemble.combinations.stack.test).map(([d, r]) => <tr key={d}><td>{d}</td><td>{pct(r.auc)}</td><td>{pct(r.recall)}</td><td>{pct(r.false_alarm)}</td></tr>)}
        <tr><td>DCSASS blind</td><td>{pct(ensemble.combinations.stack.blind_dcsass.auc)}</td><td>{pct(ensemble.combinations.stack.blind_dcsass.recall)}</td><td>{pct(ensemble.combinations.stack.blind_dcsass.calm_false_alarm)}</td></tr></tbody></table></div>}
      {chat && <div><h3>assistant latency</h3><table className="bench-table"><thead><tr><th>Configuration</th><th>First token</th><th>Tokens / s</th></tr></thead><tbody>
        {chat.configs.map(c => <tr key={c.label}><td>{c.label}</td><td>{c.error ? 'failed' : `${c.median_ttft_s} s`}</td><td>{c.error ? '—' : c.median_decode_tps}</td></tr>)}</tbody></table></div>}
      {ecosystem && <div><h3>end-to-end verification</h3><table className="bench-table"><thead><tr><th>Check</th><th>Result</th></tr></thead><tbody>
        {ecosystem.checks.map(c => <tr key={c.name}><td>{c.name}</td><td>{c.passed ? 'pass' : 'FAIL'} · {c.detail}</td></tr>)}</tbody></table></div>}
      {!detectors.length && !violence && <p className="muted">Benchmarks appear after a model finishes training and evaluation.</p>}
    </div></section>;
}
