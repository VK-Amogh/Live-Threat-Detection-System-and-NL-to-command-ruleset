import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { api, post, date, type Incident, type Source, type Camera, type System } from './api/client';
import { Badge, Empty, ErrorNotice, Icon, Media, Modal } from './components';
import { Analyze } from './screens/Analyze';
import { Investigation } from './screens/Investigation';
import { SystemScreen } from './screens/System';

const tabs = [ ['Overview','grid-01'], ['Analyze','video-on'], ['Incidents','shield-01'], ['Investigation','search-01'], ['System','server-01'] ];

function Login({ done }: { done: () => void }) {
  const [error,setError] = useState<string|null>(null);
  const [busy,setBusy] = useState(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); setBusy(true); setError(null);
    const data = new FormData(e.currentTarget);
    try { await post('/auth/login', { username: data.get('email'), password: data.get('password'), device_name:'Web dashboard', client_type:'web' }); done(); }
    catch(e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <main className="login"><div className="login-story"><div className="brand"><Icon name="shield-check" size={28}/> SafeSpace</div><div><p className="eyebrow">YOUR SPACE. IN FOCUS.</p><h1>Clarity when<br/>it matters.</h1><p>One place for your cameras, incident evidence,<br/>and the decisions that keep your space protected.</p></div><span className="muted">Local vision · Connected response</span></div><section className="login-form"><Badge>Operator workspace</Badge><h2>Welcome back.</h2><p>Sign in to your SafeSpace server.</p><form onSubmit={submit}><label>Email<input name="email" type="email" autoComplete="username" required placeholder="you@example.com" /></label><label>Password<input name="password" type="password" autoComplete="current-password" required /></label><ErrorNotice message={error}/><button className="primary" disabled={busy}>{busy?'Signing in…':'Sign in'}<Icon name="arrow-left" /></button></form><p className="caption">Your session stays on this device. Incident footage stays on your server.</p></section></main>;
}

export default function App() {
  const [user,setUser] = useState<{username:string}|null>(null);
  const [checking,setChecking] = useState(true);
  const [tab,setTab] = useState('Overview');
  const [events,setEvents] = useState<Incident[]>([]);
  const [sources,setSources] = useState<Source[]>([]);
  const [cameras,setCameras] = useState<Camera[]>([]);
  const [system,setSystem] = useState<System|null>(null);
  const [error,setError] = useState<string|null>(null);
  const [connected,setConnected] = useState(false);
  const [selected,setSelected] = useState<Incident|null>(null);
  const [scope,setScope] = useState<string|null>(null);
  const [search,setSearch] = useState('');
  const [filter,setFilter] = useState('');
  const [reviewBusy,setReviewBusy] = useState(false);
  const updating=useRef(false);
  const signIn = useCallback(async () => { try { setUser(await api('/auth/me')); } catch { setUser(null); } finally { setChecking(false); } }, []);
  useEffect(() => { void signIn(); const expired=()=>setUser(null); window.addEventListener('session-expired',expired); return ()=>window.removeEventListener('session-expired',expired); },[signIn]);
  const refresh=useCallback(async () => {
    if(updating.current) return;
    updating.current=true;
    try {
      const [es,ss,cs,sy] = await Promise.all([api<Incident[]>('/events?limit=200'),api<Source[]>('/sources'),api<Camera[]>('/cameras'),api<System>('/system')]);
      setEvents(es); setSources(ss); setCameras(cs); setSystem(sy); setError(null);
      setSelected(old=>old?es.find(e=>e.id===old.id)||old:null);
    } catch(e) { setError((e as Error).message); } finally { updating.current=false; }
  },[]);
  useEffect(()=>{
    if(!user) return;
    void refresh(); const poll=window.setInterval(refresh,5000); let stopped=false; let socket:WebSocket|undefined; let timer:number; let attempt=0;
    async function connect() {
      try {
        const ticket=await post<{ticket:string}>('/ws-tickets'); if(stopped)return;
        socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/ws?ticket=${encodeURIComponent(ticket.ticket)}`);
        socket.onopen=()=>{attempt=0;setConnected(true);void refresh();};
        socket.onmessage=e=>{const message=JSON.parse(e.data); if(message.type==='ping')socket?.send(JSON.stringify({type:'pong'})); if(message.type.startsWith('event.')||message.type==='source.updated')void refresh();};
        socket.onclose=()=>{setConnected(false);if(!stopped)timer=window.setTimeout(connect,Math.min(30000,1000*2**attempt++));};
      }catch{if(!stopped)timer=window.setTimeout(connect,5000);}
    }
    void connect(); return ()=>{stopped=true;clearInterval(poll);clearTimeout(timer);socket?.close();setConnected(false);};
  },[user,refresh]);
  async function review(action:string) {
    if(!selected)return; setReviewBusy(true);
    try { const updated=await post<Incident>(`/events/${selected.id}/verification`,{client_action_id:crypto.randomUUID(),action}); setSelected(updated); await refresh(); }
    catch(e){setError((e as Error).message);}finally{setReviewBusy(false);}
  }
  const investigate=(event:Incident)=>{setScope(event.id);setTab('Investigation');setSelected(null);};
  const filtered=events.filter(e=>(!filter||e.status===filter)&&(!search||`${e.category.label} ${e.camera.name} ${e.id} ${e.summary}`.toLowerCase().includes(search.toLowerCase())));
  function exportEvents() {
    const rows=[['ID','Time','Source','Category','Status','Confidence'],...filtered.map(e=>[e.id,e.created_at,e.camera.name,e.category.label,e.status,String(e.peak_confidence)])];
    const url=URL.createObjectURL(new Blob([rows.map(r=>r.map(c=>'"'+c.replace(/"/g,'""')+'"').join(',')).join('\n')],{type:'text/csv'}));
    const a=document.createElement('a');a.href=url;a.download='safespace-incidents.csv';a.click();URL.revokeObjectURL(url);
  }
  const incidentList=(items:Incident[])=>items.length?<div className="incident-list">{items.map(e=><button className="incident-row" key={e.id} onClick={()=>setSelected(e)}><div className="row-icon"><Icon name="shield-01"/></div><div className="row-main"><strong>{e.category.label}</strong><span>{e.camera.name} · {date(e.created_at)}</span></div><div className="row-meta"><Badge>{e.status.replaceAll('_',' ').toLowerCase()}</Badge><span>{Math.round(e.peak_confidence*100)}% confidence</span></div><Icon name="link-external"/></button>)}</div>:<Empty title={search||filter?'No matching incidents':'A clear incident log'}>{search||filter?'Try a different search or status filter.':'Analyze an image or connect a camera. Actual detections will appear here for review.'}</Empty>;
  if(checking)return <main className="loading"><div className="skeleton"/><p>Connecting to your workspace…</p></main>;
  if(!user)return <Login done={()=>void signIn()}/>;
  return <><a className="skip" href="#main">Skip to content</a><header className="shell-header"><div className="brand"><Icon name="shield-check" size={24}/><span>SafeSpace</span></div><nav aria-label="Sections" className="glass nav-pill">{tabs.map(([name,icon])=><button key={name} title={name} aria-label={name} aria-current={tab===name?'page':undefined} className={tab===name?'active':''} onClick={()=>setTab(name)}><Icon name={icon} size={22}/></button>)}</nav><div className="header-end"><span className="caption">{connected?'Updates connected':'Reconnecting…'}</span><button className="circle" title="Sign out" aria-label="Sign out" onClick={async()=>{try{await post('/auth/logout');setUser(null);}catch(e){setError((e as Error).message);}}}><Icon name="arrow-left"/></button></div></header>
    <main id="main" className="workspace"><div className="page-heading"><div><p className="eyebrow">SAFESPACE / {tab.toUpperCase()}</p><h1>{tab==='Overview'?'Your space, at a glance.':tab==='Analyze'?'See what’s happening.':tab==='Incidents'?'Every detail matters.':tab==='Investigation'?'Ask the evidence.':'Your connected system.'}</h1><p>{tab==='Overview'?'A shared view of your sources, detections, and response.':tab==='Analyze'?'Upload an image or recording, or connect a live camera.':tab==='Incidents'?'Review detections, inspect recordings, and record your decision.':tab==='Investigation'?'Answers grounded in your incident records, with evidence attached.':'Real service status, model coverage, and device access.'}</p></div>{tab==='Overview'&&<button className="primary" onClick={()=>setTab('Analyze')}><Icon name="plus-01"/>Analyze a source</button>}</div><ErrorNotice message={error}/>
    {tab==='Overview'&&<><div className="stats">{[['Awaiting review',system?.counts.needs_review,'Unverified model candidates'],['Recorded incidents',system?.counts.incidents,'All retained detections'],['Frames analyzed',system?.counts.frames_analyzed,'Across uploads and cameras'],['Cameras online',system?.counts.cameras_online,'Receiving real frames']].map(([label,value,detail])=><article className="stat" key={label}><span>{label}</span><h2>{value??'—'}</h2><small>{detail}</small></article>)}</div><div className="overview-grid"><section className="panel"><div className="section-head"><h2>Recent incidents</h2><button className="quiet" onClick={()=>setTab('Incidents')}>View all <Icon name="link-external"/></button></div>{incidentList(events.slice(0,5))}</section><section className="panel"><div className="section-head"><h2>Detection coverage</h2><Icon name="shield-check"/></div><Badge>{system?.inference.ready?'Detector ready':'Detector unavailable'}</Badge><div className="coverage-list">{((system?.inference.models||[]) as {name:string;classes:string[]}[]).map(m=><div key={m.name}><strong>{m.name}</strong><p>{m.classes.join(' · ')}</p></div>)}</div><p className="caption">No threat detected means none of the supported classes crossed their thresholds. Other threats may remain undetected.</p><button onClick={()=>setTab('System')}>Inspect model coverage</button></section></div><section className="panel"><div className="section-head"><h2>Source activity</h2><Badge>{sources.length} retained sources</Badge></div>{sources.length?<div className="source-grid">{sources.slice(0,4).map(s=><button className="source-card" key={s.id} onClick={()=>setTab('Analyze')}><Icon name={s.kind==='image'?'upload-02':'video-on'}/><strong>{s.filename}</strong><small>{s.status.toLowerCase()} · {s.frames_analyzed} frames</small><span>{s.event_ids?.length||0} incident candidates</span></button>)}</div>:<p className="muted">No sources yet. Start with a photo, a recording, or your PC camera.</p>}</section></>}
    {tab==='Analyze'&&<Analyze sources={sources} cameras={cameras} refresh={refresh} onIncident={id=>{const found=events.find(e=>e.id===id);if(found)setSelected(found);}}/>}
    {tab==='Incidents'&&<section className="panel"><div className="filter-toolbar"><label className="search-field"><Icon name="search-01"/><input aria-label="Search incidents" placeholder="Search category, source, or incident…" value={search} onChange={e=>setSearch(e.target.value)}/></label><select aria-label="Filter incident status" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All statuses</option><option value="NEEDS_REVIEW">Needs review</option><option value="CONFIRMED">Confirmed</option><option value="FALSE_POSITIVE">False positive</option></select><button onClick={exportEvents} disabled={!filtered.length}><Icon name="download"/>Export CSV</button></div><p className="caption">Showing {filtered.length} of the latest 200 incidents</p>{incidentList(filtered)}</section>}
    {tab==='Investigation'&&<Investigation events={events} scope={scope} setScope={setScope} onOpen={setSelected} system={system}/>}
    {tab==='System'&&<SystemScreen system={system} refresh={refresh} onPasswordChange={()=>setUser(null)}/>}
    <footer className="page-footer"><span>SafeSpace · Your PC is the server</span><span>{system?`Last synchronized ${new Date(system.timestamp).toLocaleTimeString()}`:'Waiting for server'}</span></footer></main>
    {selected&&<Modal title={selected.category.label} close={()=>setSelected(null)}><div className="incident-detail"><Media incident={selected}/><div className="section-head"><Badge>{selected.status.replaceAll('_',' ').toLowerCase()}</Badge><Badge>{selected.severity.toLowerCase()}</Badge></div><p>{selected.summary}</p><dl><dt>Source</dt><dd>{selected.camera.name}</dd><dt>Detected</dt><dd>{date(selected.first_seen_at)}</dd><dt>Peak confidence</dt><dd>{(selected.peak_confidence*100).toFixed(1)}%</dd><dt>Model</dt><dd>{selected.models?.yolo.name||'Not recorded'}</dd><dt>Incident ID</dt><dd className="mono">{selected.id}</dd></dl><div className="actions"><button disabled={reviewBusy} onClick={()=>void review('MARK_FALSE_POSITIVE')}>False positive</button><button className="primary" disabled={reviewBusy} onClick={()=>void review('CONFIRM')}><Icon name="check-01"/>Confirm incident</button></div><button onClick={()=>investigate(selected)}><Icon name="search-01"/>Ask about this incident</button>{(selected.feedback?.length||0)>0&&<div><h3>Review history</h3>{selected.feedback?.map(f=><p className="caption" key={f.id}>{f.action.replaceAll('_',' ')} · {date(f.created_at)}</p>)}</div>}</div></Modal>}
  </>;
}
