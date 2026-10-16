import { useEffect, useState, type MouseEvent, type SyntheticEvent } from 'react';
import { api } from '../api/client';
import type { CameraGeometry, Point } from '../api/rules';
import { Badge, ErrorNotice } from '../components';

const blank = (): CameraGeometry => ({snapshot_width: 640, snapshot_height: 480, zones: {}, lines: {}, homography: null});

export function GeometryEditor({cameraId, online, onSaved}: {cameraId: string; online: boolean; onSaved: () => void}) {
  const [geometry, setGeometry] = useState<CameraGeometry>(blank);
  const [hasSaved, setHasSaved] = useState(false);
  const [kind, setKind] = useState<'zone' | 'line'>('zone');
  const [name, setName] = useState('');
  const [points, setPoints] = useState<Point[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setPoints([]); setGeometry(blank()); setHasSaved(false); setError(null);
    api<CameraGeometry | null>(`/cameras/${cameraId}/geometry`).then(value => {
      if (!cancelled && value) { setGeometry(value); setHasSaved(true); }
    }).catch(error => { if (!cancelled) setError((error as Error).message); });
    return () => { cancelled = true; };
  }, [cameraId]);

  function onImageLoad(event: SyntheticEvent<HTMLImageElement>) {
    if (hasSaved) return;
    const image = event.currentTarget;
    setGeometry(old => ({...old, snapshot_width: image.naturalWidth, snapshot_height: image.naturalHeight}));
  }

  function addPoint(event: MouseEvent<SVGSVGElement>) {
    if (!name.trim()) { setError('Enter a zone or line name before drawing.'); return; }
    const bounds = event.currentTarget.getBoundingClientRect();
    const point: Point = [Math.round((event.clientX - bounds.left) / bounds.width * geometry.snapshot_width),
                          Math.round((event.clientY - bounds.top) / bounds.height * geometry.snapshot_height)];
    if (kind === 'line') {
      if (points.length === 1) {
        setGeometry(old => ({...old, lines: {...old.lines, [name.trim()]: [points[0], point]}}));
        setPoints([]); setName(''); setNotice('Line added. Save the geometry to activate it.');
      } else setPoints([point]);
    } else setPoints(old => [...old, point]);
    setError(null);
  }

  function finishZone() {
    if (points.length < 3 || !name.trim()) { setError('A zone needs a name and at least three points.'); return; }
    setGeometry(old => ({...old, zones: {...old.zones, [name.trim()]: points}}));
    setPoints([]); setName(''); setNotice('Zone added. Save the geometry to activate it.');
  }

  async function save() {
    setBusy(true); setError(null);
    try {
      await api(`/cameras/${cameraId}/geometry`, {method: 'PUT', body: JSON.stringify(geometry)});
      setHasSaved(true); setNotice('Camera geometry saved.'); onSaved();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  return <section className="panel geometry-editor"><div className="section-head"><h2>Zones and lines</h2><Badge>{online ? 'Camera online' : 'Start camera to draw'}</Badge></div>
    <p className="caption">Draw on a current camera frame. Click each corner of a zone, then finish it. A line needs two points.</p>
    <ErrorNotice message={error}/>{notice && <p role="status" className="notice">{notice}</p>}
    <div className="geometry-controls"><label>Shape<select value={kind} onChange={event => {setKind(event.target.value as 'zone' | 'line');setPoints([]);}}><option value="zone">Zone polygon</option><option value="line">Crossing line</option></select></label>
      <label>Name<input value={name} onChange={event => setName(event.target.value)} placeholder={kind === 'zone' ? 'driveway' : 'front_gate'}/></label>
      {kind === 'zone' && <button disabled={points.length < 3} onClick={finishZone}>Finish zone</button>}
      <button disabled={!points.length} onClick={() => setPoints([])}>Clear points</button></div>
    {online ? <div className="geometry-stage"><img src={`/api/v1/cameras/${cameraId}/frame`} alt="Camera snapshot for drawing zones" onLoad={onImageLoad}/>
      <svg viewBox={`0 0 ${geometry.snapshot_width} ${geometry.snapshot_height}`} preserveAspectRatio="none" onClick={addPoint} aria-label="Draw camera zone or line">
        {Object.entries(geometry.zones).map(([label, polygon]) => <g key={label}><polygon points={polygon.map(point => point.join(',')).join(' ')}/><text x={polygon[0][0]} y={polygon[0][1]}>{label}</text></g>)}
        {Object.entries(geometry.lines).map(([label, [a, b]]) => <g key={label}><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}/><text x={a[0]} y={a[1]}>{label}</text></g>)}
        {points.length > 0 && <g className="geometry-draft"><polyline points={points.map(point => point.join(',')).join(' ')}/>{points.map(([x, y], index) => <circle key={index} cx={x} cy={y} r="5"/>)}</g>}
      </svg></div> : <p className="muted">Start the camera in Analyze, then return here to draw on its snapshot.</p>}
    <div className="geometry-list">{Object.keys(geometry.zones).map(label => <span key={label}><Badge>Zone: {label}</Badge><button aria-label={`Remove ${label}`} onClick={() => setGeometry(old => {const zones = {...old.zones};delete zones[label];return {...old,zones};})}>Remove</button></span>)}
      {Object.keys(geometry.lines).map(label => <span key={label}><Badge>Line: {label}</Badge><button aria-label={`Remove ${label}`} onClick={() => setGeometry(old => {const lines = {...old.lines};delete lines[label];return {...old,lines};})}>Remove</button></span>)}</div>
    <button className="primary" disabled={busy || points.length > 0} onClick={() => void save()}>{busy ? 'Saving…' : 'Save geometry'}</button>
  </section>;
}
