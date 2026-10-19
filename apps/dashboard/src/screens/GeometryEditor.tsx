import { useEffect, useState, type MouseEvent, type SyntheticEvent } from 'react';
import { api } from '../api/client';
import type { CameraGeometry, Point, ZoneRole } from '../api/rules';
import { Badge, ErrorNotice } from '../components';

const blank = (): CameraGeometry => ({snapshot_width: 1280, snapshot_height: 720, zones: {}, lines: {}, homography: null, zone_roles: {}, line_sides: {}, anchors: {}});
const OBJECT_CLASSES = ['chair', 'couch', 'bench', 'bed', 'backpack', 'handbag', 'suitcase', 'laptop', 'bottle', 'cell phone', 'potted plant', 'dining table'];
type Kind = 'zone' | 'line' | 'object';

/** The B side of a line lies along the normal (-dy, dx) of its A->B vector; the arrow shows which way "A to B" is. */
function arrowFor(a: Point, b: Point, width: number): {from: Point; to: Point} {
  const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy) || 1;
  const mid: Point = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], reach = width * 0.06;
  const normal: Point = [-dy / length, dx / length];
  return {from: [mid[0] - normal[0] * reach, mid[1] - normal[1] * reach], to: [mid[0] + normal[0] * reach, mid[1] + normal[1] * reach]};
}

const STEP_HELP: Record<Kind, string[]> = {
  zone: ['Click the first corner of the zone.', 'Click the next corner.', 'Keep clicking corners, then press "Finish zone".'],
  line: ['Click where the line starts.', 'Click where the line ends.'],
  object: ['Click one corner of a box around the object.', 'Click the opposite corner.'],
};

export function GeometryEditor({cameraId, online, onSaved}: {cameraId: string; online: boolean; onSaved: () => void}) {
  const [geometry, setGeometry] = useState<CameraGeometry>(blank);
  const [hasSaved, setHasSaved] = useState(false);
  const [kind, setKind] = useState<Kind>('zone');
  const [name, setName] = useState('');
  const [role, setRole] = useState<ZoneRole>('area');
  const [sideA, setSideA] = useState('outside');
  const [sideB, setSideB] = useState('inside');
  const [objectClass, setObjectClass] = useState('chair');
  const [objectLabel, setObjectLabel] = useState('');
  const [points, setPoints] = useState<Point[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    setPoints([]); setGeometry(blank()); setHasSaved(false); setError(null);
    api<CameraGeometry | null>(`/cameras/${cameraId}/geometry`).then(value => {
      if (!cancelled && value) { setGeometry({...blank(), ...value}); setHasSaved(true); }
    }).catch(error => { if (!cancelled) setError((error as Error).message); });
    return () => { cancelled = true; };
  }, [cameraId]);

  function onImageLoad(event: SyntheticEvent<HTMLImageElement>) {
    if (hasSaved) return;
    const image = event.currentTarget;
    setGeometry(old => ({...old, snapshot_width: image.naturalWidth || 1280, snapshot_height: image.naturalHeight || 720}));
  }

  /** A blank name is fine: shapes get zone_1, line_1, object_1... (the placeholder shows which). */
  function defaultName(shape: Kind): string {
    const taken = Object.keys(shape === 'zone' ? geometry.zones : shape === 'line' ? geometry.lines : (geometry.anchors ?? {}));
    let number = taken.length + 1;
    while (taken.includes(`${shape}_${number}`)) number += 1;
    return `${shape}_${number}`;
  }

  function addPoint(event: MouseEvent<SVGSVGElement>) {
    const label = name.trim() || defaultName(kind);
    const bounds = event.currentTarget.getBoundingClientRect();
    const point: Point = [Math.round((event.clientX - bounds.left) / bounds.width * geometry.snapshot_width),
                          Math.round((event.clientY - bounds.top) / bounds.height * geometry.snapshot_height)];
    if (kind === 'line') {
      if (points.length === 1) {
        setGeometry(old => ({...old, lines: {...old.lines, [label]: [points[0], point]}, line_sides: {...old.line_sides, [label]: {a: sideA.trim() || 'A', b: sideB.trim() || 'B'}}}));
        setPoints([]); setName(''); setNotice('Line added. The arrow points from side A to side B; use Flip if it points the wrong way. Save to activate it.');
      } else setPoints([point]);
    } else if (kind === 'object') {
      if (points.length === 1) {
        const [first] = points;
        const bbox: [number, number, number, number] = [Math.min(first[0], point[0]), Math.min(first[1], point[1]), Math.max(first[0], point[0]), Math.max(first[1], point[1])];
        if (bbox[2] - bbox[0] < 8 || bbox[3] - bbox[1] < 8) { setError('Drag a box around the object: click one corner, then the opposite corner.'); setPoints([]); return; }
        setGeometry(old => ({...old, anchors: {...old.anchors, [label]: {cls: objectClass, bbox, label: objectLabel.trim() || null}}}));
        setPoints([]); setName(''); setObjectLabel(''); setNotice('Object marked. Rules can now say exactly which one you mean. Save to activate it.');
      } else setPoints([point]);
    } else setPoints(old => [...old, point]);
    setError(null);
  }

  function finishZone() {
    const label = name.trim() || defaultName('zone');
    if (points.length < 3) { setError('A zone needs at least three points.'); return; }
    setGeometry(old => ({...old, zones: {...old.zones, [label]: points}, zone_roles: {...old.zone_roles, [label]: role}}));
    setPoints([]); setName(''); setNotice('Zone added. Save the geometry to activate it.');
  }

  function remove(what: 'zones' | 'lines' | 'anchors', label: string) {
    setGeometry(old => {
      const next = {...old, [what]: {...(old[what] ?? {})}} as CameraGeometry;
      delete (next[what] as Record<string, unknown>)[label];
      if (what === 'zones') { next.zone_roles = {...old.zone_roles}; delete next.zone_roles[label]; }
      if (what === 'lines') { next.line_sides = {...old.line_sides}; delete next.line_sides[label]; }
      return next;
    });
  }

  function flip(label: string) {
    setGeometry(old => ({...old, lines: {...old.lines, [label]: [old.lines[label][1], old.lines[label][0]]}}));
  }

  async function save() {
    setBusy(true); setError(null);
    try {
      await api(`/cameras/${cameraId}/geometry`, {method: 'PUT', body: JSON.stringify(geometry)});
      setHasSaved(true); setNotice('Camera geometry saved. Rules that were waiting for this setup do not re-check by themselves: set them again to compile them with it.'); onSaved();
    } catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  const ratio = `${geometry.snapshot_width} / ${geometry.snapshot_height}`;
  const zoneRoles = geometry.zone_roles ?? {}, lineSides = geometry.line_sides ?? {}, anchors = geometry.anchors ?? {};
  return <section className="panel geometry-editor"><div className="section-head"><h2>Zones, lines and objects</h2><Badge>{online ? 'Camera online' : 'Start camera to draw'}</Badge></div>
    <p className="caption">Draw on a current camera frame, with the camera fixed in place: zones, lines and objects pause while the view is moving. A zone is clicked corner by corner, a line needs two points, and an object is marked by two opposite corners of a box.</p>
    <ErrorNotice message={error}/>{notice && <p role="status" className="notice">{notice}</p>}
    <p className="caption" aria-live="polite"><strong>{STEP_HELP[kind][Math.min(points.length, STEP_HELP[kind].length - 1)]}</strong> {kind === 'line' && 'To let a rule say "enters the front door", name the line with the word door, for example front_door.'}{kind === 'zone' && role === 'door' && 'A door zone fires when someone walks into this area, including walking past it. To detect going through the door, and which way, draw a line across the doorway instead.'}</p>
    <div className="geometry-controls"><label>Shape<select value={kind} onChange={event => {setKind(event.target.value as Kind);setPoints([]);}}><option value="zone">Zone polygon</option><option value="line">Crossing line or door</option><option value="object">Mark an object (chair, bag…)</option></select></label>
      <label>Name (optional)<input value={name} onChange={event => setName(event.target.value)} placeholder={defaultName(kind)}/></label>
      {kind === 'zone' && <label>Role<select value={role} onChange={event => setRole(event.target.value as ZoneRole)}><option value="area">Area</option><option value="door">Door</option><option value="restricted">Restricted</option><option value="seat">Seating</option></select></label>}
      {kind === 'line' && <><label>Side A (before crossing)<input value={sideA} onChange={event => setSideA(event.target.value)}/></label><label>Side B (after crossing)<input value={sideB} onChange={event => setSideB(event.target.value)}/></label></>}
      {kind === 'object' && <><label>Object type<input list="geometry-object-classes" value={objectClass} onChange={event => setObjectClass(event.target.value)}/></label><datalist id="geometry-object-classes">{OBJECT_CLASSES.map(item => <option key={item} value={item}/>)}</datalist>
        <label>Describe it<input value={objectLabel} onChange={event => setObjectLabel(event.target.value)} placeholder="chair by the window"/></label></>}
      {kind === 'zone' && <button disabled={points.length < 3} onClick={finishZone}>Finish zone</button>}
      <button disabled={!points.length} onClick={() => setPoints([])}>Clear points</button></div>
    {online ? <div className="geometry-stage" style={{['--snap-ratio' as string]: ratio, aspectRatio: ratio, width: '100%'}}><img src={`/api/v1/cameras/${cameraId}/frame`} alt="Camera snapshot for drawing zones" onLoad={onImageLoad}/>
      <svg viewBox={`0 0 ${geometry.snapshot_width} ${geometry.snapshot_height}`} preserveAspectRatio="none" onClick={addPoint} aria-label="Draw camera zone, line or object">
        {Object.entries(geometry.zones).map(([label, polygon]) => <g key={label}><polygon points={polygon.map(point => point.join(',')).join(' ')}/><text x={polygon[0][0]} y={polygon[0][1]}>{label}{zoneRoles[label] && zoneRoles[label] !== 'area' ? ` (${zoneRoles[label]})` : ''}</text></g>)}
        {Object.entries(geometry.lines).map(([label, [a, b]]) => {
          const arrow = arrowFor(a, b, geometry.snapshot_width), sides = lineSides[label];
          return <g key={label}><line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}/><text x={a[0]} y={a[1]}>{label}</text>
            <line className="geometry-arrow" x1={arrow.from[0]} y1={arrow.from[1]} x2={arrow.to[0]} y2={arrow.to[1]}/><circle className="geometry-arrow-tip" cx={arrow.to[0]} cy={arrow.to[1]} r="9"/>
            {sides && <><text x={arrow.from[0]} y={arrow.from[1]}>{sides.a}</text><text x={arrow.to[0]} y={arrow.to[1]}>{sides.b}</text></>}</g>;
        })}
        {Object.entries(anchors).map(([label, anchor]) => <g key={label}><rect className="geometry-anchor" x={anchor.bbox[0]} y={anchor.bbox[1]} width={anchor.bbox[2] - anchor.bbox[0]} height={anchor.bbox[3] - anchor.bbox[1]}/><text x={anchor.bbox[0]} y={anchor.bbox[1]}>{anchor.label || label} ({anchor.cls})</text></g>)}
        {points.length > 0 && <g className="geometry-draft"><polyline points={points.map(point => point.join(',')).join(' ')}/>{points.map(([x, y], index) => <circle key={index} cx={x} cy={y} r="5"/>)}</g>}
      </svg></div> : <p className="muted">Start the camera in Analyze, then return here to draw on its snapshot.</p>}
    <div className="geometry-list">{Object.keys(geometry.zones).map(label => <span key={label}><Badge>Zone: {label}{zoneRoles[label] ? ` · ${zoneRoles[label]}` : ''}</Badge><button aria-label={`Remove ${label}`} onClick={() => remove('zones', label)}>Remove</button></span>)}
      {Object.keys(geometry.lines).map(label => <span key={label}><Badge>Line: {label}{lineSides[label] ? ` · ${lineSides[label].a} → ${lineSides[label].b}` : ''}</Badge><button aria-label={`Flip direction of ${label}`} onClick={() => flip(label)}>Flip</button><button aria-label={`Remove ${label}`} onClick={() => remove('lines', label)}>Remove</button></span>)}
      {Object.entries(anchors).map(([label, anchor]) => <span key={label}><Badge>Object: {label} · {anchor.cls}</Badge><button aria-label={`Remove ${label}`} onClick={() => remove('anchors', label)}>Remove</button></span>)}</div>
    <button className="primary" disabled={busy || points.length > 0} onClick={() => void save()}>{busy ? 'Saving…' : 'Save geometry'}</button>
  </section>;
}
