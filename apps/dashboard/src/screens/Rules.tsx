import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, post, type Camera } from '../api/client';
import type { CompileResult, RuleRecord } from '../api/rules';
import { Badge, Empty, ErrorNotice } from '../components';
import { GeometryEditor } from './GeometryEditor';

export function Rules({cameras}: {cameras: Camera[]}) {
  const [cameraId, setCameraId] = useState('');
  const [rules, setRules] = useState<RuleRecord[]>([]);
  const [text, setText] = useState('');
  const [visual, setVisual] = useState(false);
  const [preview, setPreview] = useState<CompileResult | null>(null);
  const [acknowledge, setAcknowledge] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const camera = cameras.find(item => item.id === cameraId);
  useEffect(() => { if (!cameraId && cameras.length) setCameraId(cameras[0].id); }, [cameraId, cameras]);
  const refresh = useCallback(async () => {
    if (!cameraId) return;
    try { setRules(await api<RuleRecord[]>(`/rules?camera_id=${encodeURIComponent(cameraId)}`)); }
    catch (error) { setError((error as Error).message); }
  }, [cameraId]);
  useEffect(() => { setPreview(null); void refresh(); }, [refresh]);

  async function compile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null); setPreview(null);
    try {
      const result = await post<CompileResult>('/rules/compile', {camera_id: cameraId, text, needs_visual_review: visual});
      setPreview(result); setAcknowledge(false); await refresh();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  async function activate(record: RuleRecord | CompileResult) {
    const spec = record.spec;
    const hash = record.readback_hash;
    if (!hash) return;
    if (spec.support_level === 'EXPERIMENTAL' && !acknowledge) {
      setError('Acknowledge the experimental limitation before activation.'); return;
    }
    setBusy(true); setError(null);
    try {
      await post(`/rules/${spec.rule_id}/activate`, {expected_version: spec.version,
        confirmed_readback_hash: hash, acknowledge_experimental: acknowledge});
      setPreview(null); setNotice('The confirmed rule is active.'); await refresh();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  async function disable(record: RuleRecord) {
    setBusy(true); setError(null);
    try {
      await api(`/rules/${record.id}`, {method: 'PATCH', body: JSON.stringify({status: 'disabled', expected_version: record.version})});
      setNotice('Rule disabled.'); await refresh();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="rules-layout"><ErrorNotice message={error}/>{notice && <p role="status" className="notice">{notice}</p>}
    {!cameras.length ? <Empty title="Add a camera first">Connect a server camera in Analyze, then draw its zones and create rules.</Empty> : <>
      <section className="panel"><div className="section-head"><h2>Camera rules</h2><Badge>{rules.filter(rule => rule.status === 'active').length} active</Badge></div>
        <label>Camera<select value={cameraId} onChange={event => setCameraId(event.target.value)}>{cameras.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <form onSubmit={event => void compile(event)} className="rule-compose"><label>Monitoring request<textarea rows={3} value={text} onChange={event => setText(event.target.value)} placeholder="Alert me when a person stays in the driveway for 3 seconds between midnight and 5 a.m." required/></label>
          <label className="checkbox"><input type="checkbox" checked={visual} onChange={event => setVisual(event.target.checked)}/>Add a later visual summary</label>
          <p className="caption">A visual summary describes sampled frames; it does not decide whether the rule fires. Use exact hours for time rules.</p>
          <button className="primary" disabled={busy || !cameraId}>{busy ? 'Working…' : 'Compile rule'}</button></form>
        {preview && <div className="rule-readback"><div className="section-head"><h3>Review before activation</h3><Badge>{preview.support_level.toLowerCase()}</Badge></div>
          {preview.readback && <p>{preview.readback}</p>}
          {preview.problems.map(problem => <p className="caption" key={problem}>{problem}</p>)}
          {preview.support_level === 'EXPERIMENTAL' && <label className="checkbox"><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)}/>I understand the experimental limitation</label>}
          {preview.can_activate && <button className="primary" disabled={busy} onClick={() => void activate(preview)}>Confirm this readback and activate</button>}
          {!preview.can_activate && <p className="caption">Saved as a draft. It cannot run with the current camera capabilities.</p>}</div>}
      </section>
      {cameraId && <GeometryEditor cameraId={cameraId} online={Boolean(camera?.is_online)} onSaved={() => void refresh()}/>}
      <section className="panel rules-list"><div className="section-head"><h2>Saved rules</h2><Badge>{rules.length}</Badge></div>
        {rules.length ? rules.map(record => <article className="rule-card" key={record.id}><div className="section-head"><strong>{record.spec.name}</strong><Badge>{record.status} · {record.spec.support_level.toLowerCase()}</Badge></div>
          <p>{record.readback || record.text}</p>{record.spec.unsupported_reason && <p className="caption">{record.spec.unsupported_reason}</p>}
          <small>Version {record.version}{record.spec.needs_visual_review ? ' · visual summary' : ''}</small>
          {record.status !== 'active' && record.spec.support_level === 'EXPERIMENTAL' && <label className="checkbox"><input type="checkbox" checked={acknowledge} onChange={event => setAcknowledge(event.target.checked)}/>I understand this experimental rule</label>}
          <div className="actions">{record.status === 'active' ? <button disabled={busy} onClick={() => void disable(record)}>Disable</button>
            : record.can_activate && record.readback_hash && <button disabled={busy} onClick={() => void activate(record)}>Confirm readback and activate</button>}</div></article>) : <Empty title="No rules saved">Type a monitoring request to create a draft.</Empty>}
      </section>
    </>}</div>;
}
