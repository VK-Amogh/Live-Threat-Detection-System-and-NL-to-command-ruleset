'use client'

import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Bot,
  Camera,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  Filter,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  MoreHorizontal,
  Play,
  Plus,
  Radio,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  Users,
  Video,
  X,
  Zap,
} from 'lucide-react'

const navItems = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Live monitoring', icon: Radio },
  { label: 'Incidents', icon: AlertTriangle, count: '08' },
  { label: 'AI investigation', icon: MessageSquareText },
]

const incidents = [
  { time: '10:42:18', category: 'Restricted-zone intrusion', camera: 'CAM-04 · Loading dock', severity: 'High', confidence: '96%', state: 'Open' },
  { time: '10:31:04', category: 'Unusual crowd density', camera: 'CAM-02 · Main entrance', severity: 'Medium', confidence: '88%', state: 'Review' },
  { time: '09:54:27', category: 'Unattended object', camera: 'CAM-07 · East corridor', severity: 'Medium', confidence: '91%', state: 'Open' },
  { time: '09:18:12', category: 'After-hours activity', camera: 'CAM-01 · Reception', severity: 'Low', confidence: '84%', state: 'Resolved' },
]

const trend = [42, 55, 49, 72, 58, 78, 65, 88, 73, 92, 84, 100]

function MetricCard({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: typeof Activity }) {
  return (
    <article className="metric-card">
      <div className="metric-top"><span>{label}</span><Icon size={16} /></div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </article>
  )
}

function Severity({ value }: { value: string }) {
  return <span className={`severity severity-${value.toLowerCase()}`}><span className="severity-dot" />{value}</span>
}

function VideoPanel({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="video-panel">
      <div className="video-toolbar">
        <div className="camera-select"><span className="live-dot" />CAM-04 · Loading dock<ChevronDown size={14} /></div>
        <div className="toolbar-actions"><button aria-label="Video settings"><SlidersHorizontal size={17} /></button><button aria-label="More options"><MoreHorizontal size={18} /></button></div>
      </div>
      <div className="video-stage">
        <div className="stage-grid" />
        <div className="camera-frame frame-one"><span>person · 96%</span></div>
        <div className="camera-frame frame-two"><span>vehicle · 89%</span></div>
        <div className="stage-copy"><Video size={26} /><strong>Live feed connected</strong><span>Object detection is active</span></div>
        <div className="recording-pill"><span className="live-dot" />LIVE · 00:14:32</div>
        <button className="stage-play" aria-label="Pause live feed"><Play size={19} fill="currentColor" /></button>
      </div>
      <div className="video-footer"><span>1920 × 1080 · 24 FPS</span><span><span className="status-dot" />Connection stable</span><button onClick={onUpload}><Upload size={15} />Upload video</button></div>
    </div>
  )
}

function Overview({ onNavigate, onUpload }: { onNavigate: (page: string) => void; onUpload: () => void }) {
  return (
    <div className="page-content">
      <div className="page-heading"><div><p className="eyebrow">WEDNESDAY, OCTOBER 15, 2026 · 10:44 AM</p><h1>Good morning, Alex</h1><p className="muted">Here&apos;s what&apos;s happening across your security network.</p></div><button className="button button-inverse" onClick={onUpload}><Upload size={16} />Analyze video</button></div>
      <div className="metrics-grid"><MetricCard label="Active cameras" value="07 / 08" detail="1 camera needs attention" icon={Camera} /><MetricCard label="Incidents today" value="08" detail="2 high priority · +12%" icon={AlertTriangle} /><MetricCard label="Detection uptime" value="99.2%" detail="Across the last 30 days" icon={Activity} /><MetricCard label="Events reviewed" value="84%" detail="6 require your review" icon={ShieldCheck} /></div>
      <div className="overview-grid">
        <section className="panel trend-panel"><div className="panel-header"><div><h2>Anomaly activity</h2><p className="muted">Detected events over the last 12 hours</p></div><button className="select-button">Today <ChevronDown size={14} /></button></div><div className="chart-wrap"><div className="chart-y"><span>100</span><span>75</span><span>50</span><span>25</span><span>0</span></div><div className="chart"><div className="chart-lines"><i /><i /><i /><i /><i /></div><svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-label="Anomaly activity trend"><polyline points="0,108 54,80 109,94 163,50 218,77 272,39 327,63 381,20 436,48 490,8 545,28 600,0" fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke" /></svg><div className="chart-labels"><span>12 AM</span><span>3 AM</span><span>6 AM</span><span>9 AM</span><span>12 PM</span></div></div></div></section>
        <section className="panel status-panel"><div className="panel-header"><div><h2>Camera status</h2><p className="muted">Your connected sources</p></div><button className="icon-button" aria-label="Add camera"><Plus size={17} /></button></div><div className="camera-list"><div className="camera-row"><span className="camera-icon"><Camera size={17} /></span><span><strong>CAM-01</strong><small>Reception</small></span><span className="camera-state"><i />Online</span></div><div className="camera-row"><span className="camera-icon"><Camera size={17} /></span><span><strong>CAM-02</strong><small>Main entrance</small></span><span className="camera-state"><i />Online</span></div><div className="camera-row"><span className="camera-icon"><Camera size={17} /></span><span><strong>CAM-04</strong><small>Loading dock</small></span><span className="camera-state"><i />Online</span></div><div className="camera-row"><span className="camera-icon muted-icon"><Camera size={17} /></span><span><strong>CAM-08</strong><small>Parking lot</small></span><span className="camera-state offline">Offline</span></div></div><button className="text-button" onClick={() => onNavigate('Live monitoring')}>View all cameras <ArrowUpRight size={14} /></button></section>
      </div>
      <section className="panel incidents-panel"><div className="panel-header"><div><h2>Recent incidents</h2><p className="muted">The latest events requiring attention</p></div><button className="text-button" onClick={() => onNavigate('Incidents')}>View all <ArrowUpRight size={14} /></button></div><IncidentTable compact /></section>
    </div>
  )
}

function IncidentTable({ compact = false }: { compact?: boolean }) {
  const rows = compact ? incidents.slice(0, 3) : incidents
  return <div className="incident-table"><div className="incident-head"><span>TIME</span><span>EVENT</span><span>CAMERA</span><span>SEVERITY</span><span>CONFIDENCE</span><span /></div>{rows.map((item) => <div className="incident-row" key={item.time}><span className="time-cell">{item.time}</span><span className="event-cell"><strong>{item.category}</strong><small>{item.state}</small></span><span className="camera-cell">{item.camera}</span><Severity value={item.severity} /><span className="confidence">{item.confidence}</span><ChevronRight size={16} className="row-chevron" /></div>)}</div>
}

function LiveMonitoring({ onUpload }: { onUpload: () => void }) {
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow">REAL-TIME OPERATIONS</p><h1>Live monitoring</h1><p className="muted">Monitor connected sources and review AI detections as they happen.</p></div><button className="button button-inverse" onClick={onUpload}><Upload size={16} />Analyze video</button></div><div className="live-layout"><div><VideoPanel onUpload={onUpload} /><div className="detection-row"><div className="detection-card"><span className="detection-icon"><Sparkles size={17} /></span><div><strong>AI scene explanation</strong><p>Person detected entering the marked loading zone. Vehicle remains stationary.</p></div><span className="confidence">96%</span></div><div className="detection-card"><span className="detection-icon"><Clock3 size={17} /></span><div><strong>Last event · 10:42:18</strong><p>Restricted-zone intrusion detected and added to incident queue.</p></div><ChevronRight size={16} /></div></div></div><aside className="panel live-side"><div className="panel-header"><div><h2>Active alerts</h2><p className="muted">Events from this session</p></div><span className="count-badge">3</span></div><div className="alert-list"><div className="alert-item"><span className="alert-mark"><AlertTriangle size={16} /></span><div><strong>Restricted-zone intrusion</strong><p>Loading dock · 2 min ago</p></div><Severity value="High" /></div><div className="alert-item"><span className="alert-mark"><Users size={16} /></span><div><strong>Unusual crowd density</strong><p>Main entrance · 14 min ago</p></div><Severity value="Medium" /></div><div className="alert-item"><span className="alert-mark"><Zap size={16} /></span><div><strong>After-hours activity</strong><p>Reception · 1 hr ago</p></div><Severity value="Low" /></div></div><button className="text-button">Open event timeline <ArrowUpRight size={14} /></button></aside></div><section className="panel event-panel"><div className="panel-header"><div><h2>Session timeline</h2><p className="muted">Timestamped events detected in this feed</p></div><button className="select-button">All events <ChevronDown size={14} /></button></div><div className="timeline"><div><time>10:42:18</time><i /><span><strong>Restricted-zone intrusion</strong><small>Person crossed the loading dock boundary</small></span><b>96%</b></div><div><time>10:37:02</time><i /><span><strong>Vehicle detected</strong><small>Delivery van entered the field of view</small></span><b>89%</b></div><div><time>10:31:04</time><i /><span><strong>Unusual crowd density</strong><small>8 people gathered near the entrance</small></span><b>88%</b></div></div></section></div>
}

function IncidentsPage() {
  const [filter, setFilter] = useState('All incidents')
  const filtered = useMemo(() => filter === 'All incidents' ? incidents : incidents.filter((item) => item.severity === filter), [filter])
  return <div className="page-content"><div className="page-heading"><div><p className="eyebrow">EVENT REVIEW</p><h1>Incidents</h1><p className="muted">Review, investigate, and resolve detected events.</p></div><button className="button button-inverse"><Filter size={16} />Create report</button></div><div className="filter-bar"><div className="search-box"><Search size={16} /><input aria-label="Search incidents" placeholder="Search incidents" /></div><div className="filter-pills">{['All incidents', 'High', 'Medium', 'Low'].map((item) => <button key={item} onClick={() => setFilter(item)} className={filter === item ? 'active' : ''}>{item}</button>)}</div><button className="icon-button" aria-label="More filters"><SlidersHorizontal size={17} /></button></div><section className="panel incidents-panel"><div className="panel-header"><div><h2>{filtered.length} incidents</h2><p className="muted">Showing events from the last 24 hours</p></div><button className="select-button">Newest first <ChevronDown size={14} /></button></div><IncidentTable /></section><div className="incident-dna"><div><p className="eyebrow">SELECTED INCIDENT</p><h2>Incident DNA</h2><p className="muted">Restricted-zone intrusion · CAM-04</p></div><div className="dna-flow"><div><span>BEFORE</span><strong>10:41:52</strong><p>Loading dock clear</p></div><i /><div className="dna-active"><span>DURING</span><strong>10:42:18</strong><p>Boundary crossed</p></div><i /><div><span>AFTER</span><strong>10:42:36</strong><p>Alert acknowledged</p></div></div></div></div>
}

function Investigation() {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([{ role: 'assistant', text: 'Ask me about your monitoring sessions, uploaded videos, or stored incidents. I can link answers to the relevant timestamps and evidence.' }])
  const send = () => { if (!query.trim()) return; setMessages([...messages, { role: 'user', text: query }, { role: 'assistant', text: 'I found 3 relevant events in the current workspace. The closest match is the restricted-zone intrusion at 10:42:18 on CAM-04.' }]); setQuery('') }
  return <div className="page-content investigation-page"><div className="page-heading"><div><p className="eyebrow">AI-ASSISTED REVIEW</p><h1>AI investigation</h1><p className="muted">Ask questions across your live sessions and incident history.</p></div><span className="privacy-note"><ShieldCheck size={15} />Your footage stays in your workspace</span></div><div className="investigation-layout"><section className="panel chat-panel"><div className="chat-head"><div className="bot-avatar"><Bot size={20} /></div><div><strong>Security intelligence</strong><p>Context-aware incident analysis</p></div><span className="online-label"><span className="status-dot" />Ready</span></div><div className="chat-messages">{messages.map((message, i) => <div key={i} className={`message ${message.role}`}><div className={message.role === 'assistant' ? 'bot-avatar small' : 'user-avatar'}>{message.role === 'assistant' ? <Bot size={15} /> : 'A'}</div><div><p>{message.text}</p>{message.role === 'assistant' && i > 0 && <button className="evidence-link"><Clock3 size={14} />Jump to 10:42:18 · CAM-04 <ArrowUpRight size={13} /></button>}</div></div>)}</div><div className="prompt-box"><textarea value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) { e.preventDefault(); send() } }} placeholder="Ask about an incident, camera, or time range..." rows={1} /><button onClick={send} aria-label="Send question"><ArrowUpRight size={17} /></button></div><div className="prompt-hints"><button onClick={() => setQuery('What happened at the loading dock today?')}>What happened at the loading dock?</button><button onClick={() => setQuery('Show all high severity incidents')}>Show high severity incidents</button></div></section><aside className="panel sources-panel"><div className="panel-header"><div><h2>Evidence sources</h2><p className="muted">3 sources in context</p></div><button className="icon-button"><Plus size={17} /></button></div><div className="source-item"><Video size={17} /><span><strong>Live session · CAM-04</strong><small>Today · 10:00 AM — now</small></span><ChevronRight size={15} /></div><div className="source-item"><AlertTriangle size={17} /><span><strong>Incident history</strong><small>8 events · Last 24 hours</small></span><ChevronRight size={15} /></div><div className="source-item"><Upload size={17} /><span><strong>Uploaded videos</strong><small>No uploads in this session</small></span><ChevronRight size={15} /></div></aside></div></div>
}

export default function Page() {
  const [page, setPage] = useState('Overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const renderPage = page === 'Live monitoring' ? <LiveMonitoring onUpload={() => setUploadOpen(true)} /> : page === 'Incidents' ? <IncidentsPage /> : page === 'AI investigation' ? <Investigation /> : <Overview onNavigate={setPage} onUpload={() => setUploadOpen(true)} />
  return <main className="app-shell"><aside className={`sidebar ${mobileOpen ? 'open' : ''}`}><div className="brand"><span className="brand-mark"><ShieldCheck size={17} /></span><span>Sentinel<span className="brand-dot">.</span></span><button className="mobile-close" onClick={() => setMobileOpen(false)}><X size={18} /></button></div><div className="workspace-switcher"><span className="workspace-avatar">AC</span><span><strong>Acme Corporation</strong><small>Security workspace</small></span><ChevronDown size={14} /></div><nav><p className="nav-label">WORKSPACE</p>{navItems.map(({ label, icon: Icon, count }) => <button key={label} className={page === label ? 'nav-item active' : 'nav-item'} onClick={() => { setPage(label); setMobileOpen(false) }}><Icon size={18} /><span>{label}</span>{count && <b>{count}</b>}</button>)}</nav><div className="sidebar-bottom"><button className="nav-item"><Settings2 size={18} /><span>Settings</span></button><button className="nav-item"><CircleHelp size={18} /><span>Help center</span></button><div className="profile"><span className="user-avatar">AR</span><span><strong>Alex Rivera</strong><small>Administrator</small></span><MoreHorizontal size={16} /></div></div></aside><section className="main-area"><header className="topbar"><button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{page}</strong></div><div className="topbar-actions"><button className="top-icon" aria-label="Notifications"><Bell size={18} /><i /></button><button className="top-avatar">AR</button></div></header>{renderPage}</section>{uploadOpen && <div className="modal-backdrop" onClick={() => setUploadOpen(false)}><div className="upload-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setUploadOpen(false)}><X size={18} /></button><div className="upload-icon"><Upload size={22} /></div><h2>Analyze a video</h2><p>Upload a recording to generate incidents, timestamps, and evidence keyframes.</p><label className="drop-zone"><input type="file" accept="video/*" /> <Upload size={18} /><strong>Choose a video file</strong><span>MP4, MOV, or WebM up to 2 GB</span></label><button className="button button-inverse full" onClick={() => setUploadOpen(false)}>Continue</button><span className="modal-note">Nothing uploads until you continue.</span></div></div>}</main>
}
