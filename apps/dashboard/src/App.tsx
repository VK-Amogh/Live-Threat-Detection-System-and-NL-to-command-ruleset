import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { api, post, date, type Incident, type Source, type Camera, type System } from './api/client';
import { useChangeFeed } from './api/changeFeed';
import { Badge, Empty, ErrorNotice, Icon, Media, Modal } from './components';
import { LiveWall } from './components/LiveWall';
import { Analyze } from './screens/Analyze';
import { Investigation } from './screens/Investigation';
import { Rules } from './screens/Rules';
import { SystemScreen } from './screens/System';

const tabs = [
  ['Overview', 'grid-01'],
  ['Live Wall', 'video-on'],
  ['Analyze', 'upload-02'],
  ['Rules', 'shield-check'],
  ['Incidents', 'shield-01'],
  ['Investigation', 'search-01'],
  ['System', 'server-01'],
];

function mergeEvents(current: Incident[], incoming: Incident[]) {
  const byId = new Map(current.map((event) => [event.id, event]));
  for (const event of incoming) {
    const old = byId.get(event.id);
    if (!old || event.change_seq >= old.change_seq) byId.set(event.id, event);
  }
  return [...byId.values()].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 200);
}

function readableCategory(value: string) {
  return value.replaceAll('_', ' ').replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

function Login({ done }: { done: () => void }) {
  const [email, setEmail] = useState('admin1@safespace.com');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signInWith(userEmail: string, userPass: string) {
    setBusy(true);
    setError(null);
    try {
      await post('/auth/login', {
        username: userEmail,
        password: userPass,
        device_name: 'Web dashboard (Nothing Phone Wi-Fi)',
        client_type: 'web',
      });
      done();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await signInWith(email, password);
  }

  return (
    <main className="login">
      <div className="login-story">
        <div className="brand">
          <Icon name="shield-check" size={28} /> SafeSpace v3
        </div>
        <div>
          <p className="eyebrow">SAFESPACE</p>
          <h1>
            Clarity when
            <br />
            it matters.
          </h1>
          <p>
            Watch your cameras, review alerts, and set simple rules
            <br />
            for what matters in your space.
          </p>
        </div>
        <span className="muted">Your cameras and recordings stay on your local server.</span>
      </div>
      <section className="login-form">
        <div className="actions">
          <Badge>Your workspace</Badge>
        </div>
        <h2>Welcome back.</h2>
        <p>Choose an account or sign in with your email.</p>
        <div className="actions" style={{ marginTop: 16 }}>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setEmail('admin1@safespace.com');
              setPassword('admin123');
              void signInWith('admin1@safespace.com', 'admin123');
            }}
          >
            <Icon name="shield-check" size={18} />
            Continue as Admin 1
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setEmail('admin2@safespace.com');
              setPassword('admin123');
              void signInWith('admin2@safespace.com', 'admin123');
            }}
          >
            <Icon name="shield-01" size={18} />
            Continue as Admin 2
          </button>
        </div>
        <form onSubmit={(e) => void submit(e)}>
          <label>
            Email
            <input
              name="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin1@safespace.com"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <ErrorNotice message={error} />
          <button className="primary" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
            <Icon name="chevron-right" />
          </button>
        </form>
        <p className="caption">
          Your session stays on this device. Camera recordings stay on your local server.
        </p>
      </section>
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState<{ username: string; display_name?: string } | null>(null);
  const [checking, setChecking] = useState(true);
  const [tab, setTab] = useState('Overview');
  const [events, setEvents] = useState<Incident[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [ruleCameraId, setRuleCameraId] = useState<string | undefined>();
  const [system, setSystem] = useState<System | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Incident | null>(null);
  const [scope, setScope] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('');
  const [reviewBusy, setReviewBusy] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const [showAllRecordings, setShowAllRecordings] = useState(false);
  const updating = useRef(false);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' });
  }, [tab]);

  const signIn = useCallback(async () => {
    try {
      setUser(await api('/auth/me'));
    } catch {
      setUser(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void signIn();
    const expired = () => setUser(null);
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, [signIn]);

  const refresh = useCallback(async () => {
    if (updating.current) return;
    updating.current = true;
    try {
      const [es, ss, cs, sy] = await Promise.all([
        api<Incident[]>('/events?limit=200'),
        api<Source[]>('/sources'),
        api<Camera[]>('/cameras'),
        api<System>('/system'),
      ]);
      setEvents((old) => mergeEvents(old, es));
      setSources(ss);
      setCameras(cs);
      setSystem(sy);
      setError(null);
      setSelected((old) => {
        const next = old && es.find((e) => e.id === old.id);
        return next && old && next.change_seq >= old.change_seq ? next : old;
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      updating.current = false;
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void refresh();
    const poll = window.setInterval(refresh, 15000);
    return () => clearInterval(poll);
  }, [user, refresh]);

  const onChange = useCallback((event: Incident) => {
    setEvents((old) => mergeEvents(old, [event]));
    setSelected((old) => (old?.id === event.id && event.change_seq > old.change_seq ? event : old));
  }, []);

  const connected = useChangeFeed(Boolean(user), onChange, refresh);

  async function review(action: string) {
    if (!selected) return;
    setReviewBusy(true);
    try {
      const updated = await post<Incident>(`/events/${selected.id}/verification`, {
        client_action_id: crypto.randomUUID(),
        action,
      });
      setSelected(updated);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setReviewBusy(false);
    }
  }

  async function askAi() {
    if (!selected) return;
    setAiBusy(true);
    try {
      const updated = await post<Incident>(`/events/${selected.id}/ai-review`);
      setSelected(updated);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAiBusy(false);
    }
  }

  const investigate = (event: Incident) => {
    setScope(event.id);
    setTab('Investigation');
    setSelected(null);
  };

  const filtered = events.filter(
    (e) =>
      (!filter || e.status === filter) &&
      (!search ||
        `${e.category.label} ${e.camera.name} ${e.id} ${e.summary}`.toLowerCase().includes(search.toLowerCase())),
  );
  const recordedEvents = events.filter((event) => event.media?.some((item) => item.kind === 'CLIP'));

  function exportEvents() {
    const rows = [
      ['ID', 'Time', 'Source', 'Category', 'Status', 'Confidence'],
      ...filtered.map((e) => [
        e.id,
        e.created_at,
        e.camera.name,
        e.category.label,
        e.status,
        String(e.peak_confidence),
      ]),
    ];
    const url = URL.createObjectURL(
      new Blob([rows.map((r) => r.map((c) => '"' + c.replace(/"/g, '""') + '"').join(',')).join('\n')], {
        type: 'text/csv',
      }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = 'safespace-incidents.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  const incidentList = (items: Incident[]) =>
    items.length ? (
      <div className="incident-list">
        {items.map((e) => (
          <button className="incident-row" key={e.id} onClick={() => setSelected(e)}>
            <div className="row-icon">
              <Icon name="shield-01" />
            </div>
            <div className="row-main">
              <strong>{readableCategory(e.category.label)}</strong>
              <span>
                {e.camera.name} · {date(e.created_at)}
              </span>
            </div>
            <div className="row-meta">
              <Badge>{e.severity === 'CRITICAL' ? 'Critical' : e.status.replaceAll('_', ' ').toLowerCase()}</Badge>
            </div>
            <Icon name="chevron-right" />
          </button>
        ))}
      </div>
    ) : (
      <Empty title={search || filter ? 'No matching incidents' : 'A clear incident log'}>
        {search || filter
          ? 'Try a different search or status filter.'
          : 'Analyze an image or connect a camera. Actual detections will appear here for review.'}
      </Empty>
    );

  if (checking)
    return (
      <main className="loading">
        <div className="skeleton" />
        <p>Connecting to your workspace…</p>
      </main>
    );
  if (!user) return <Login done={() => void signIn()} />;

  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="shell-header">
        <div className="brand">
          <Icon name="shield-check" size={24} />
          <span>SafeSpace</span>
          <Badge>Nothing Phone (4a)_7495</Badge>
        </div>
        <nav aria-label="Sections" className="glass nav-pill">
          {tabs.map(([name, icon]) => (
            <button
              key={name}
              title={name}
              aria-label={name}
              aria-current={tab === name ? 'page' : undefined}
              className={tab === name ? 'active' : ''}
              onClick={() => setTab(name)}
            >
              <Icon name={icon} size={22} />
              <span>{name === 'Live Wall' ? 'Cameras' : name === 'Investigation' ? 'Ask' : name === 'System' ? 'Settings' : name}</span>
            </button>
          ))}
        </nav>
        <div className="header-end">
          <span className="caption">
            {user.display_name || user.username} · {connected ? 'Live feed connected' : 'Reconnecting…'}
          </span>
          <button
            className="circle"
            title="Sign out"
            aria-label="Sign out"
            onClick={async () => {
              try {
                await post('/auth/logout');
                setUser(null);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <Icon name="arrow-left" />
          </button>
        </div>
      </header>
      <main id="main" className={`workspace page-${tab.toLowerCase().replaceAll(' ', '-')}`}>
        <div className="page-heading">
          <div>
            <p className="eyebrow">SAFESPACE / {tab.toUpperCase()}</p>
            <h1>
              {tab === 'Overview'
                ? 'Overview'
                : tab === 'Live Wall'
                  ? 'Cameras'
                  : tab === 'Analyze'
                    ? 'Analyze video'
                    : tab === 'Rules'
                      ? 'Rules'
                      : tab === 'Incidents'
                        ? 'Incidents'
                        : tab === 'Investigation'
                          ? 'Ask SafeSpace'
                          : 'Settings'}
            </h1>
            <p>
              {tab === 'Overview'
                ? 'The alerts that need you and the recordings behind them.'
                : tab === 'Live Wall'
                  ? 'See live cameras, look back at recordings, and save a snapshot.'
                  : tab === 'Analyze'
                    ? 'Upload a new video or open one you already analyzed.'
                    : tab === 'Rules'
                      ? 'Choose a camera, describe what to watch, and review the rule before turning it on.'
                      : tab === 'Incidents'
                        ? 'Search alerts, watch their clips, and record your decision.'
                        : tab === 'Investigation'
                          ? 'Ask questions about alerts, rules, and camera footage.'
                          : 'See connection and service status.'}
            </p>
          </div>
          {tab === 'Overview' && (
            <div className="actions">
              <button type="button" onClick={() => setTab('Live Wall')}>
                <Icon name="video-on" />
                View cameras
              </button>
              <button className="primary" onClick={() => setTab('Analyze')}>
                <Icon name="plus-01" />
                Analyze video
              </button>
            </div>
          )}
        </div>
        <ErrorNotice message={error} />

        {tab === 'Overview' && (
          <>
            <div className="stats overview-stats">
              {[
                ['Awaiting review', system?.counts.needs_review, 'Incidents that need your decision'],
                ['Recorded incidents', system?.counts.incidents, 'All incidents saved on this server'],
              ].map(([label, value, detail]) => (
                <article className="stat" key={label}>
                  <span>{label}</span>
                  <h2>{value ?? '—'}</h2>
                  <small>{detail}</small>
                </article>
              ))}
            </div>

            <section className="panel recordings-panel">
              <div className="section-head">
                <div><p className="eyebrow">RECENT FOOTAGE</p><h2>Recordings</h2><p className="caption">Watch the clip, then open an incident for the full timeline and review.</p></div>
                <Badge>{recordedEvents.length} clips</Badge>
              </div>
              {recordedEvents.length ? <>
                <div className="recordings-grid">
                  {recordedEvents.slice(0, showAllRecordings ? undefined : 6).map((event) => (
                    <article className="recording-card" key={event.id}>
                      <div className="recording-media"><Media incident={event} /></div>
                      <div className="recording-content">
                        <div className="recording-badges"><Badge>{event.severity === 'CRITICAL' ? 'Critical' : 'Not critical'}</Badge><Badge>{event.status.replaceAll('_', ' ').toLowerCase()}</Badge></div>
                        <h3>{readableCategory(event.category.label)}</h3>
                        <p>{event.summary || `Recorded on ${event.camera.name}`}</p>
                        <div className="recording-footer"><span>{event.camera.name} · {date(event.created_at)}</span><button type="button" onClick={() => setSelected(event)}>View more <Icon name="chevron-right" size={16} /></button></div>
                      </div>
                    </article>
                  ))}
                </div>
                {recordedEvents.length > 6 && <button className="recordings-more" type="button" onClick={() => setShowAllRecordings(!showAllRecordings)}>{showAllRecordings ? 'Show fewer recordings' : `Show all ${recordedEvents.length} recordings`}</button>}
              </> : <Empty title="No recordings yet" icon="video-on">Clips attached to incidents will appear here. Connect an Android camera or analyze a video to get started.</Empty>}
            </section>

          </>
        )}

        {tab === 'Live Wall' && (
          <LiveWall
            cameras={cameras}
            onCreateRule={(id) => {
              setRuleCameraId(id);
              setTab('Rules');
            }}
            refresh={refresh}
          />
        )}

        {tab === 'Analyze' && (
          <Analyze
            sources={sources}
            cameras={cameras}
            refresh={refresh}
            onIncident={(id) => {
              const found = events.find((e) => e.id === id);
              if (found) setSelected(found);
            }}
            onCreateRule={(id) => {
              setRuleCameraId(id);
              setTab('Rules');
            }}
          />
        )}
        {tab === 'Rules' && <Rules cameras={cameras} selectedCameraId={ruleCameraId} />}
        {tab === 'Incidents' && (
          <section className="panel">
            <div className="filter-toolbar">
              <label className="search-field">
                <Icon name="search-01" />
                <input
                  aria-label="Search incidents"
                  placeholder="Search category, source, or incident…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <select aria-label="Filter incident status" value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="">All statuses</option>
                <option value="NEEDS_REVIEW">Needs review</option>
                <option value="CONFIRMED">Confirmed</option>
                <option value="FALSE_POSITIVE">False positive</option>
              </select>
              <button onClick={exportEvents} disabled={!filtered.length}>
                <Icon name="download" />
                Export CSV
              </button>
            </div>
            <p className="caption">Showing {filtered.length} of the latest 200 incidents</p>
            {incidentList(filtered)}
          </section>
        )}
        {tab === 'Investigation' && (
          <Investigation events={events} scope={scope} setScope={setScope} onOpen={setSelected} system={system} />
        )}
        {tab === 'System' && (
          <SystemScreen system={system} refresh={refresh} onPasswordChange={() => setUser(null)} />
        )}
        <footer className="page-footer">
          <span>SafeSpace · Your camera footage stays on your local server</span>
          <span>
            {system ? `Last synchronized ${new Date(system.timestamp).toLocaleTimeString()}` : 'Waiting for server'}
          </span>
        </footer>
      </main>
      {selected && (
        <Modal title={readableCategory(selected.category.label)} close={() => setSelected(null)}>
          <div className="incident-detail">
            <Media incident={selected} />
            <div className="section-head">
              <Badge>{selected.status.replaceAll('_', ' ').toLowerCase()}</Badge>
              <Badge>{selected.severity === 'CRITICAL' ? 'Critical' : 'Not critical'}</Badge>
            </div>
            <p>{selected.summary}</p>
            <dl>
              <dt>Source</dt>
              <dd>{selected.camera.name}</dd>
              <dt>Recorded</dt>
              <dd>{date(selected.created_at)}</dd>
              <dt>Detected</dt>
              <dd>{date(selected.first_seen_at)}</dd>
              <dt>Last seen</dt>
              <dd>{date(selected.last_seen_at)}</dd>
              <dt>Review status</dt>
              <dd>{selected.status.replaceAll('_', ' ').toLowerCase()}</dd>
              <dt>Severity</dt>
              <dd>{selected.severity.toLowerCase()}</dd>
              <dt>Peak confidence</dt>
              <dd>{(selected.peak_confidence * 100).toFixed(1)}%</dd>
            </dl>
            <details className="incident-technical"><summary>Technical details</summary><dl>
              {selected.rule_id && <><dt>Rule</dt><dd className="mono">{selected.rule_id} · version {selected.rule_version}</dd></>}
              <dt>Detector</dt><dd>{selected.models?.yolo.name || 'Not recorded'}</dd>
              <dt>Incident ID</dt><dd className="mono">{selected.id}</dd>
            </dl>{selected.uncertainty && <p className="caption">{selected.uncertainty}</p>}</details>
            <section className="ai-review" aria-label="AI second opinion">
              <div className="section-head">
                <h3>AI second opinion</h3>
                {selected.ai_disagrees ? (
                  <Badge>Disagrees with detector</Badge>
                ) : selected.reasoning ? (
                  <Badge>{selected.reasoning.evidence_insufficient ? 'Inconclusive' : 'Consistent'}</Badge>
                ) : null}
              </div>
              {selected.reasoning ? (
                <>
                  <p>{selected.reasoning.uncertainty}</p>
                  {(selected.reasoning.visible_facts || []).length > 0 && (
                    <ul>
                      {(selected.reasoning.visible_facts || []).map((f) => (
                        <li key={f}>{f}</li>
                      ))}
                    </ul>
                  )}
                  <p className="caption">
                    Model: {selected.models?.vlm?.name || 'unknown'} · confidence{' '}
                    {Math.round(selected.reasoning.confidence * 100)}%. The AI only advises; you decide.
                  </p>
                </>
              ) : (
                <p className="caption">
                  An open-weights vision model can double-check the evidence frames. It never confirms or dismisses an incident for you.
                </p>
              )}
              <button disabled={aiBusy} onClick={() => void askAi()}>
                <Icon name="search-01" />
                {aiBusy ? 'Looking at the footage…' : selected.reasoning ? 'Ask again' : 'Ask the AI to double-check'}
              </button>
            </section>
            <div className="actions">
              <button disabled={reviewBusy} onClick={() => void review('MARK_FALSE_POSITIVE')}>
                False positive
              </button>
              <button className="primary" disabled={reviewBusy} onClick={() => void review('CONFIRM')}>
                <Icon name="check-01" />
                Confirm incident
              </button>
            </div>
            <button onClick={() => investigate(selected)}>
              <Icon name="search-01" />
              Ask about this incident
            </button>
            {(selected.feedback?.length || 0) > 0 && (
              <div>
                <h3>Review history</h3>
                {selected.feedback?.map((f) => (
                  <p className="caption" key={f.id}>
                    {f.action.replaceAll('_', ' ')} · {date(f.created_at)}
                  </p>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </>
  );
}
