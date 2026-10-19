import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, post, type Camera } from '../api/client';
import type { CompileResult, RuleRecord } from '../api/rules';
import { Badge, Empty, ErrorNotice, Icon } from '../components';
import { GeometryEditor } from './GeometryEditor';

interface RuleTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  default_text: string;
  default_severity: string;
  requires_zone: boolean;
  requires_line: boolean;
  default_schedule?: {
    days?: string[];
    start_time?: string;
    end_time?: string;
    timezone?: string;
  } | null;
}

interface RulesetItem {
  id: string;
  name: string;
  description?: string | null;
  camera_ids: string[];
  template_id?: string | null;
  mode?: string | null;
  status: string;
  readback_text?: string | null;
  readback_hash?: string | null;
  rule_ids: string[];
  version: number;
}

interface DryRunResult {
  rule_id: string;
  matched: boolean;
  reasons: string[];
  sub_results: { predicate: string; matched: boolean; reason: string }[];
}

const MODES = ['HOME', 'AWAY', 'NIGHT', 'DISARMED'] as const;
const DAYS = [
  ['mon', 'Mon'],
  ['tue', 'Tue'],
  ['wed', 'Wed'],
  ['thu', 'Thu'],
  ['fri', 'Fri'],
  ['sat', 'Sat'],
  ['sun', 'Sun'],
] as const;

export function Rules({ cameras, selectedCameraId }: { cameras: Camera[]; selectedCameraId?: string }) {
  const [cameraId, setCameraId] = useState('');
  const [selectedCameras, setSelectedCameras] = useState<string[]>([]);
  const [rules, setRules] = useState<RuleRecord[]>([]);
  const [templates, setTemplates] = useState<RuleTemplate[]>([]);
  const [rulesets, setRulesets] = useState<RulesetItem[]>([]);
  const [systemMode, setSystemMode] = useState<string>('HOME');
  const [text, setText] = useState('');
  const [rulesetName, setRulesetName] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [ruleMode, setRuleMode] = useState<string>('');
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleDays, setScheduleDays] = useState<string[]>(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']);
  const [startTime, setStartTime] = useState('22:00');
  const [endTime, setEndTime] = useState('06:00');
  const [visual, setVisual] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showGeometry, setShowGeometry] = useState(false);
  const [preview, setPreview] = useState<CompileResult | null>(null);
  const [acknowledge, setAcknowledge] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const camera = cameras.find((item) => item.id === cameraId);

  useEffect(() => {
    if (!cameraId && cameras.length) {
      setCameraId(cameras[0].id);
      setSelectedCameras([cameras[0].id]);
    }
  }, [cameraId, cameras]);

  useEffect(() => {
    if (selectedCameraId && cameras.some((c) => c.id === selectedCameraId)) {
      setCameraId(selectedCameraId);
      setSelectedCameras([selectedCameraId]);
    }
  }, [selectedCameraId, cameras]);

  const refreshAll = useCallback(async () => {
    try {
      const [tmpls, rsets, modeRes] = await Promise.all([
        api<RuleTemplate[]>('/rules/templates').catch(() => []),
        api<{ items: RulesetItem[] } | RulesetItem[]>('/rulesets').then((r) => (Array.isArray(r) ? r : r.items)).catch(() => [] as RulesetItem[]),
        api<{ mode: string }>('/system/mode').catch(() => ({ mode: 'HOME' })),
      ]);
      setTemplates(tmpls);
      setRulesets(rsets);
      setSystemMode(modeRes.mode || 'HOME');
      if (cameraId) {
        setRules(await api<RuleRecord[]>(`/rules?camera_id=${encodeURIComponent(cameraId)}`));
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, [cameraId]);

  useEffect(() => {
    setPreview(null);
    void refreshAll();
  }, [refreshAll]);

  async function changeSystemMode(newMode: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ mode: string }>('/system/mode', {
        method: 'PUT',
        body: JSON.stringify({ mode: newMode }),
      });
      setSystemMode(res.mode);
      setNotice(`System mode switched to ${res.mode}.`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function applyTemplate(t: RuleTemplate) {
    setSelectedTemplateId(t.id);
    setRulesetName(t.name);
    setText(t.default_text);
    setRuleMode('');
    if (t.default_schedule) {
      setScheduleEnabled(true);
      setScheduleDays(t.default_schedule.days || ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']);
      setStartTime(t.default_schedule.start_time || '22:00');
      setEndTime(t.default_schedule.end_time || '06:00');
    } else {
      setScheduleEnabled(false);
    }
    setNotice(`“${t.name}” is ready. Check the camera and wording, then set the rule.`);
    requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('#rule-builder textarea')?.focus());
  }

  async function compile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedTemplateId) {
      await createMultiCameraRuleset();
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    setPreview(null);
    setDryRunResult(null);
    try {
      const result = await post<CompileResult>('/rules/compile', {
        camera_id: cameraId,
        text,
        needs_visual_review: visual,
      });
      setPreview(result);
      setAcknowledge(false);
      await refreshAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function createMultiCameraRuleset() {
    const targets = selectedCameras.length ? selectedCameras : cameraId ? [cameraId] : [];
    if (scheduleEnabled && !scheduleDays.length) {
      setError('Choose at least one day for the schedule.');
      return;
    }
    if (!targets.length || !text.trim()) {
      setError('Select at least one camera and enter a monitoring rule.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await post<RulesetItem>('/rulesets', {
        name: rulesetName.trim() || text.trim().slice(0, 48),
        description: text.trim(),
        camera_ids: targets,
        template_id: selectedTemplateId || null,
        text: text.trim(),
        mode: ruleMode || null,
        schedule: scheduleEnabled
          ? {
              days: scheduleDays,
              start_time: startTime,
              end_time: endTime,
              timezone: 'local',
            }
          : null,
        needs_visual_review: visual,
      });
      setNotice(`Multi-camera ruleset "${created.name}" compiled for ${targets.length} camera(s). Confirm readback below to activate.`);
      await refreshAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function activateRuleset(rs: RulesetItem) {
    if (!rs.readback_hash) return;
    setBusy(true);
    setError(null);
    try {
      await post(`/rulesets/${rs.id}/activate`, {
        confirmed_readback_hash: rs.readback_hash,
        acknowledge_experimental: true,
      });
      setNotice(`Ruleset "${rs.name}" is now active across ${rs.camera_ids.length} camera(s).`);
      await refreshAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function activate(record: RuleRecord | CompileResult) {
    const spec = record.spec;
    const hash = record.readback_hash;
    if (!hash) return;
    if (spec.support_level === 'EXPERIMENTAL' && !acknowledge) {
      setError('Acknowledge the experimental limitation before activation.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await post(`/rules/${spec.rule_id}/activate`, {
        expected_version: spec.version,
        confirmed_readback_hash: hash,
        acknowledge_experimental: acknowledge,
      });
      setPreview(null);
      setNotice('The confirmed rule is active.');
      await refreshAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function disable(record: RuleRecord) {
    setBusy(true);
    setError(null);
    try {
      await api(`/rules/${record.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'disabled', expected_version: record.version }),
      });
      setNotice('Rule disabled.');
      await refreshAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function runDryRun(ruleId: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await post<DryRunResult>(`/rules/${ruleId}/dry-run`, {
        synthetic_tracks: [
          {
            track_id: 1,
            class_name: 'person',
            confidence: 0.92,
            bbox: [120, 120, 260, 380],
            dwell_seconds: 12.0,
          },
        ],
      });
      setDryRunResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function toggleCameraTarget(id: string) {
    setSelectedCameras((old) => (old.includes(id) ? old.filter((x) => x !== id) : [...old, id]));
  }

  function toggleDay(day: string) {
    setScheduleDays((old) => (old.includes(day) ? old.filter((d) => d !== day) : [...old, day]));
  }

  return (
    <div className="rules-layout">
      <ErrorNotice message={error} />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}

      {!cameras.length ? (
        <Empty title="Add a camera first">
          Connect a Nothing Phone camera station or server camera in Analyze, then draw its zones and create rules.
        </Empty>
      ) : (
        <>
          <section className="panel rule-builder-panel" id="rule-builder">
            <div className="section-head">
              <h2>Create a rule</h2>
              <Badge>{rules.filter((rule) => rule.status === 'active').length} active on camera</Badge>
            </div>

            <div className="rule-camera-step"><label>
              1. Choose a camera
              <select value={cameraId} onChange={(event) => { setCameraId(event.target.value); setSelectedCameras([event.target.value]); }}>
                {cameras.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            {showAdvanced && <div style={{ marginTop: 12 }}>
              <span className="caption">Also watch these cameras ({selectedCameras.length} selected)</span>
              <div className="actions" style={{ marginTop: 8 }}>
                {cameras.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={selectedCameras.includes(item.id)}
                    onClick={() => toggleCameraTarget(item.id)}
                  >
                    {item.name}
                  </button>
                ))}
              </div>
            </div>}</div>

            <form onSubmit={(event) => void compile(event)} className="rule-compose">
              {showAdvanced && <label>
                Name for a group of cameras (optional)
                <input
                  value={rulesetName}
                  onChange={(e) => setRulesetName(e.target.value)}
                  placeholder="e.g. Night Perimeter Watch"
                />
              </label>}

              <label>
                2. Describe what should trigger an alert
                <textarea
                  rows={3}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Alert me when a person stays in the driveway for 3 seconds between midnight and 5 a.m."
                  required
                />
              </label>

              {showAdvanced && <div className="geometry-controls">
                <label>
                  Only in this mode
                  <select value={ruleMode} onChange={(e) => setRuleMode(e.target.value)}>
                    <option value="">All Armed Modes (HOME, AWAY, NIGHT)</option>
                    <option value="HOME">HOME Only</option>
                    <option value="AWAY">AWAY Only</option>
                    <option value="NIGHT">NIGHT Only</option>
                  </select>
                </label>
              </div>}

              {showAdvanced && <label className="checkbox">
                <input
                  type="checkbox"
                  checked={scheduleEnabled}
                  onChange={(e) => setScheduleEnabled(e.target.checked)}
                />
                Use a schedule
              </label>}

              {showAdvanced && scheduleEnabled && (
                <div className="rule-readback">
                  <div className="actions">
                    {DAYS.map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        aria-pressed={scheduleDays.includes(key)}
                        onClick={() => toggleDay(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="geometry-controls">
                    <label>
                      Start Time (24h)
                      <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
                    </label>
                    <label>
                      End Time (24h)
                      <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
                    </label>
                  </div>
                </div>
              )}

              {showAdvanced && <label className="checkbox">
                <input type="checkbox" checked={visual} onChange={(event) => setVisual(event.target.checked)} />
                Add a visual summary after an alert
              </label>}

              <button type="button" className="rule-more" aria-expanded={showAdvanced} onClick={() => setShowAdvanced(!showAdvanced)}>
                {showAdvanced ? 'Hide extra options' : 'Schedule, multiple cameras and other options'}
              </button>
              <p className="caption">3. Set the rule. Check the preview before it starts watching.</p>

              <div className="actions">
                <button className="primary" disabled={busy || !cameraId}>
                  {busy ? 'Setting up…' : selectedTemplateId ? 'Create template ruleset' : 'Set rule'}
                </button>
                {showAdvanced && !selectedTemplateId && <button type="button" disabled={busy || !text.trim()} onClick={() => void createMultiCameraRuleset()}>
                  Preview for {selectedCameras.length || 1} cameras
                </button>}
              </div>
            </form>

            {preview && (
              <div className="rule-readback">
                <div className="section-head">
                  <h3>Check what this rule will do</h3>
                  <Badge>{preview.support_level.toLowerCase()}</Badge>
                </div>
                {preview.readback && <p>{preview.readback}</p>}
                {!!preview.needs_setup?.length && (
                  <div>
                    <strong>To make this rule work, first:</strong>
                    <ul className="rule-setup">
                      {preview.needs_setup.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {preview.problems.filter((problem) => !preview.needs_setup?.includes(problem)).map((problem) => (
                  <p className="caption" key={problem}>
                    {problem}
                  </p>
                ))}
                {preview.support_level === 'EXPERIMENTAL' && (
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={acknowledge}
                      onChange={(event) => setAcknowledge(event.target.checked)}
                    />
                    I understand the experimental limitation
                  </label>
                )}
                <div className="actions">
                  {preview.can_activate && (
                    <button className="primary" disabled={busy} onClick={() => void activate(preview)}>
                      Turn on this rule
                    </button>
                  )}
                  <button type="button" disabled={busy} onClick={() => void runDryRun(preview.spec.rule_id)}>
                    Test with example data
                  </button>
                </div>
                {!preview.can_activate && (
                  <div><p className="caption">Saved as a draft. Add the required area or line before turning it on.</p><button type="button" onClick={() => setShowGeometry(true)}>Draw camera area or line</button></div>
                )}
              </div>
            )}

            {dryRunResult && (
              <div className="rule-readback">
                <div className="section-head">
                  <h3>Dry-Run Evaluation Result</h3>
                  <Badge>{dryRunResult.matched ? 'MATCHED' : 'NO MATCH'}</Badge>
                </div>
                {dryRunResult.reasons.map((r, i) => (
                  <p className="caption" key={i}>
                    {r}
                  </p>
                ))}
                {dryRunResult.sub_results.map((sr, i) => (
                  <div className="setting-row" key={i}>
                    <strong>{sr.predicate}</strong>
                    <span>
                      {sr.matched ? 'PASS' : 'FAIL'} · {sr.reason}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {templates.length > 0 && <section className="panel rules-wide rule-examples">
            <div className="section-head"><div><p className="eyebrow">QUICK START</p><h2>Ready to use examples</h2><p className="caption">Choose a rule to fill in the form above. You can change the wording before setting it.</p></div><Badge>{templates.length} examples</Badge></div>
            <div className="rule-template-grid">
              {templates.map((template) => <button
                key={template.id}
                type="button"
                className={`source-card ${selectedTemplateId === template.id ? 'selected' : ''}`}
                aria-pressed={selectedTemplateId === template.id}
                onClick={() => applyTemplate(template)}
              >
                <div className="section-head" style={{ width: '100%', marginBottom: 4 }}><strong>{template.name}</strong><Badge>{template.default_severity.toLowerCase()}</Badge></div>
                <small>{template.description}</small>
                <span>Choose template <Icon name="chevron-right" size={16} /></span>
              </button>)}
            </div>
          </section>}

          <div className="rules-utilities">
            {cameraId && <section className="rules-geometry">
              <button type="button" className="rule-more" aria-expanded={showGeometry} onClick={() => setShowGeometry(!showGeometry)}>
                {showGeometry ? 'Hide camera areas' : 'Draw an area or crossing line on the camera'}
                <Icon name="chevron-right" size={18} />
              </button>
              {showGeometry && <GeometryEditor cameraId={cameraId} online={Boolean(camera?.is_online)} onSaved={() => void refreshAll()} />}
            </section>}

            <details className="panel rule-mode-details">
              <summary><span><strong>Monitoring mode</strong><small>{systemMode === 'DISARMED' ? 'Alerts are paused' : `${systemMode.charAt(0) + systemMode.slice(1).toLowerCase()} is active`}</small></span><Icon name="chevron-down" size={18} /></summary>
              <p className="caption">Home watches the perimeter. Away watches all areas. Night uses overnight rules. Disarmed pauses alerts while cameras keep recording.</p>
              <div className="actions">{MODES.map((mode) => <button key={mode} type="button" className={systemMode === mode ? 'primary' : ''} aria-pressed={systemMode === mode} disabled={busy} onClick={() => void changeSystemMode(mode)}>{mode.charAt(0) + mode.slice(1).toLowerCase()}</button>)}</div>
            </details>
          </div>

          {rulesets.length > 0 && (
            <section className="panel rules-list">
              <div className="section-head">
                <h2>Rules for multiple cameras</h2>
                <Badge>{rulesets.length}</Badge>
              </div>
              {rulesets.map((rs) => (
                <article className="rule-card" key={rs.id}>
                  <div className="section-head">
                    <strong>{rs.name}</strong>
                    <Badge>{rs.status}</Badge>
                  </div>
                  <p>{rs.readback_text || rs.description}</p>
                  <small>
                    Cameras: {rs.camera_ids.join(', ')} {rs.mode ? `· Mode: ${rs.mode}` : ''}
                  </small>
                  {rs.status !== 'active' && rs.readback_hash && (
                    <div className="actions">
                      <button className="primary" disabled={busy} onClick={() => void activateRuleset(rs)}>
                        Turn on for these cameras
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </section>
          )}

          <section className="panel rules-list active-rules-panel">
            <div className="section-head">
              <h2>Your rules</h2>
              <Badge>{rules.filter((rule) => rule.status === 'active').length} active · {rules.length} total</Badge>
            </div>
            {rules.length ? (
              [...rules].sort((a, b) => Number(b.status === 'active') - Number(a.status === 'active')).map((record) => (
                <article className="rule-card" key={record.id}>
                  <div className="section-head">
                    <strong>{record.spec.name}</strong>
                    <Badge>
                      {record.status} · {record.spec.support_level.toLowerCase()}
                    </Badge>
                  </div>
                  <p>{record.readback || record.text}</p>
                  {record.spec.unsupported_reason && <p className="caption">{record.spec.unsupported_reason}</p>}
                  <small>
                    Version {record.version}
                    {record.spec.needs_visual_review ? ' · visual summary' : ''}
                  </small>
                  {record.status !== 'active' && record.spec.support_level === 'EXPERIMENTAL' && (
                    <label className="checkbox">
                      <input
                        type="checkbox"
                        checked={acknowledge}
                        onChange={(event) => setAcknowledge(event.target.checked)}
                      />
                      I understand this experimental rule
                    </label>
                  )}
                  <div className="actions">
                    {record.status === 'active' ? (
                      <button disabled={busy} onClick={() => void disable(record)}>
                        Disable
                      </button>
                    ) : (
                      record.can_activate &&
                      record.readback_hash && (
                        <button className="primary" disabled={busy} onClick={() => void activate(record)}>
                          Turn on rule
                        </button>
                      )
                    )}
                    <button type="button" disabled={busy} onClick={() => void runDryRun(record.id)}>
                      Test with example data
                    </button>
                  </div>
                </article>
              ))
            ) : (
              <Empty title="No rules yet">Choose an example or describe what you want this camera to watch.</Empty>
            )}
          </section>
        </>
      )}
    </div>
  );
}
