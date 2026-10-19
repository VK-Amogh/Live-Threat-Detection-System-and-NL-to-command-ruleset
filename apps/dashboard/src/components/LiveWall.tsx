import { useCallback, useEffect, useRef, useState } from 'react';
import { api, post, date, type Camera } from '../api/client';
import { Badge, Empty, ErrorNotice, Icon, Modal } from '../components';

export interface DetectionBox {
  track_id?: number | null;
  class_name: string;
  confidence: number;
  bbox: [number, number, number, number];
  model?: string;
  kind?: 'object' | 'threat';
}

export interface OverlayState {
  seq: number;
  captured_at_ms: number;
  fps_in: number;
  fps_inference: number;
  latency_ms: number;
  profile: string;
  viewer_count: number;
  boxes: DetectionBox[];
  threat?: { detected: boolean; violence?: number | null; inference_ms?: number | null };
}

export interface TimelineSegment {
  id: string;
  camera_id: string;
  started_at: string;
  ended_at?: string | null;
  duration_ms: number;
  stream_url: string;
}

export interface TimelineSnapshot {
  id: string;
  camera_id: string;
  created_at: string;
  width: number;
  height: number;
  url: string;
}

export interface TimelineData {
  camera_id: string;
  from_ts: string;
  to_ts: string;
  segments: TimelineSegment[];
  incidents: { id: string; category: string; severity: string; status: string; first_seen_at: string; peak_confidence: number }[];
  snapshots: TimelineSnapshot[];
}

// SSF1 frame: magic "SSF1" | flags u8 | orientation u8 | width u16 | height u16 | seq u32 | captured_ms u64, then the JPEG.
const SSF1_HEADER = 22;

function parseSsf1Frame(buffer: ArrayBuffer): { header: { w: number; h: number; seq: number; capturedMs: number }; jpegBuffer: ArrayBuffer } | null {
  if (buffer.byteLength <= SSF1_HEADER) return null;
  const view = new DataView(buffer);
  const magic = String.fromCharCode(view.getUint8(0), view.getUint8(1), view.getUint8(2), view.getUint8(3));
  if (magic !== 'SSF1') return null;
  return {
    header: {
      w: view.getUint16(6, false),
      h: view.getUint16(8, false),
      seq: view.getUint32(10, false),
      capturedMs: Number(view.getBigUint64(14, false)),
    },
    jpegBuffer: buffer.slice(SSF1_HEADER),
  };
}

// The server's timeline, reshaped for this component.
interface ServerTimeline {
  camera_id: string; from_ts: number; to_ts: number;
  segments: { segment_id: string; camera_id: string; start_ts: number; end_ts: number; duration_s: number; url: string }[];
  events: { id: string; ts: number; category: string; severity: string; status: string }[];
  snapshots: { snapshot_id: string; camera_id: string; ts: number; width: number; height: number; url: string }[];
}
const iso = (t: number) => new Date(t * 1000).toISOString();
function toTimeline(r: ServerTimeline): TimelineData {
  return {
    camera_id: r.camera_id,
    from_ts: iso(r.from_ts),
    to_ts: iso(r.to_ts),
    segments: r.segments.map((x) => ({ id: x.segment_id, camera_id: x.camera_id, started_at: iso(x.start_ts), ended_at: iso(x.end_ts), duration_ms: x.duration_s * 1000, stream_url: x.url })),
    incidents: r.events.map((e) => ({ id: e.id, category: e.category, severity: e.severity, status: e.status, first_seen_at: iso(e.ts), peak_confidence: 0 })),
    snapshots: r.snapshots.map((x) => ({ id: x.snapshot_id, camera_id: x.camera_id, created_at: iso(x.ts), width: x.width, height: x.height, url: x.url })),
  };
}

export function LiveTile({
  camera,
  focused,
  onFocus,
  onCreateRule,
  onOpenTimeline,
}: {
  camera: Camera;
  focused: boolean;
  onFocus: () => void;
  onCreateRule: (cameraId: string) => void;
  onOpenTimeline: (camera: Camera) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [overlay, setOverlay] = useState<OverlayState | null>(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);
  const [fallbackTick, setFallbackTick] = useState(Date.now());
  const [frameDims, setFrameDims] = useState<{ w: number; h: number }>({ w: 1280, h: 720 });
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!camera.is_online) {
      setWsConnected(false);
      return;
    }
    let closed = false;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/api/v1/cameras/${encodeURIComponent(camera.id)}/view`;
    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      if (!closed) setWsConnected(true);
    };

    ws.onmessage = async (ev) => {
      if (closed) return;
      if (typeof ev.data === 'string') {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'overlay') {
            setOverlay(msg as OverlayState);
          }
        } catch {
          // ignore malformed overlay
        }
      } else if (ev.data instanceof ArrayBuffer) {
        const parsed = parseSsf1Frame(ev.data);
        if (!parsed) return;
        try {
          const blob = new Blob([parsed.jpegBuffer], { type: 'image/jpeg' });
          const bmp = await createImageBitmap(blob);
          const srcW = bmp.width || parsed.header.w || 1280;
          const srcH = bmp.height || parsed.header.h || 720;
          let sx = 0;
          let sy = 0;
          let sw = srcW;
          let sh = srcH;
          if (srcW * 9 > srcH * 16) {
            sw = Math.floor((srcH * 16) / 9);
            sx = Math.floor((srcW - sw) / 2);
          } else if (srcW * 9 < srcH * 16) {
            sh = Math.floor((srcW * 9) / 16);
            sy = Math.floor((srcH - sh) / 2);
          }
          setFrameDims({ w: sw, h: sh });
          const canvas = canvasRef.current;
          if (canvas) {
            if (canvas.width !== sw) canvas.width = sw;
            if (canvas.height !== sh) canvas.height = sh;
            const ctx = canvas.getContext('2d');
            ctx?.drawImage(bmp, sx, sy, sw, sh, 0, 0, sw, sh);
          }
          bmp.close();
        } catch {
          // fallback if createImageBitmap fails
        }
      }
    };

    ws.onclose = () => {
      if (!closed) setWsConnected(false);
    };
    ws.onerror = () => {
      if (!closed) setWsConnected(false);
    };

    return () => {
      closed = true;
      ws.close();
    };
  }, [camera.id, camera.is_online]);

  useEffect(() => {
    if (!camera.is_online || wsConnected) return;
    const t = window.setInterval(() => setFallbackTick(Date.now()), 650);
    return () => clearInterval(t);
  }, [camera.is_online, wsConnected]);

  async function takeSnapshot() {
    try {
      await post(`/cameras/${camera.id}/snapshots`, {});
      setToast('Snapshot saved');
      window.setTimeout(() => setToast(null), 2200);
    } catch (e) {
      setToast((e as Error).message);
      window.setTimeout(() => setToast(null), 3000);
    }
  }

  return (
    <article className={`live-tile ${focused ? 'focused' : ''}`}>
      <div
        className="live-stage"
        style={{ aspectRatio: '16 / 9', width: '100%', height: 'auto' }}
        onDoubleClick={onFocus}
      >
        {camera.is_online ? (
          <>
            <canvas
              ref={canvasRef}
              className="live-canvas"
              style={{
                display: wsConnected ? 'block' : 'none',
                width: '100%',
                height: '100%',
                aspectRatio: '16 / 9',
                objectFit: 'cover',
              }}
            />
            {!wsConnected && (
              <img
                className="live-canvas"
                src={`/api/v1/cameras/${camera.id}/frame?t=${fallbackTick}`}
                alt={`${camera.name} live stream`}
                style={{
                  width: '100%',
                  height: '100%',
                  aspectRatio: '16 / 9',
                  objectFit: 'cover',
                  display: 'block',
                }}
              />
            )}
            {overlay?.threat?.violence != null && overlay.threat.violence >= 0.5 && (
              <div className="glass live-pill live-threat-banner">
                <Icon name="shield-01" size={16} />
                <strong>Possible violence {Math.round(overlay.threat.violence * 100)}%</strong>
              </div>
            )}
            {showBoxes && overlay && overlay.boxes.length > 0 && (
              <svg
                className="live-overlay-svg"
                viewBox={`0 0 ${frameDims.w} ${frameDims.h}`}
                preserveAspectRatio="none"
                aria-label="Live detections"
              >
                {overlay.boxes.map((b, idx) => {
                  const [x1, y1, x2, y2] = b.bbox;
                  const bw = Math.max(4, x2 - x1);
                  const bh = Math.max(4, y2 - y1);
                  return (
                    <g key={`${b.track_id ?? idx}-${idx}`} className={b.kind === 'threat' ? 'threat' : undefined}>
                      <rect x={x1} y={y1} width={bw} height={bh} />
                      <text x={x1 + 6} y={Math.max(20, y1 - 6)}>
                        {b.class_name} {Math.round(b.confidence * 100)}%
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </>
        ) : (
          <div className="live-offline">
            <div className="empty-icon">
              <Icon name="video-on" size={32} />
            </div>
            <strong>{camera.name}</strong>
            <span className="caption">Waiting for this camera's stream</span>
          </div>
        )}

        <div className="live-top-bar">
          <div className="glass live-pill">
            <span className={`status-dot ${camera.is_online ? 'online' : ''}`} />
            <strong>{camera.name}</strong>
            <span className="caption">{camera.is_online ? 'Live' : 'Offline'}</span>
          </div>
          <div className="glass live-pill">
            <span className="caption">{camera.source_type === 'PHONE' ? 'Android camera' : camera.source_type.toLowerCase()}</span>
          </div>
        </div>

        {toast && <div className="glass live-toast">{toast}</div>}

        <div className="live-bottom-bar">
          <div className="glass live-controls">
            {camera.is_online && <button type="button" className="quiet" title="Take snapshot (S)" onClick={() => void takeSnapshot()}>
              <Icon name="video-on" size={18} />
              <span>Snapshot</span>
            </button>}
            {camera.is_online && <button
              type="button"
              className="quiet"
              aria-pressed={showBoxes}
              title="Toggle detection boxes"
              onClick={() => setShowBoxes((v) => !v)}
            >
              <Icon name="shield-01" size={18} />
              <span>{showBoxes ? 'Boxes On' : 'Boxes Off'}</span>
            </button>}
            <button type="button" className="quiet" title="24h Timeline & Recordings" onClick={() => onOpenTimeline(camera)}>
              <Icon name="play-01" size={18} />
              <span>Timeline</span>
            </button>
            <button type="button" className="quiet" title="Create rule for camera" onClick={() => onCreateRule(camera.id)}>
              <Icon name="shield-check" size={18} />
              <span>Rule</span>
            </button>
            <button type="button" className="quiet" title={focused ? 'Exit focus' : 'Focus tile'} onClick={onFocus}>
              <Icon name="grid-01" size={18} />
              <span>{focused ? 'Grid' : 'Focus'}</span>
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export function LiveWall({
  cameras,
  onCreateRule,
  refresh,
}: {
  cameras: Camera[];
  onCreateRule: (cameraId: string) => void;
  refresh: () => Promise<void>;
}) {
  const [gridSize, setGridSize] = useState<1 | 4 | 9>(4);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [timelineCam, setTimelineCam] = useState<Camera | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [activeSeg, setActiveSeg] = useState<TimelineSegment | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openTimeline = useCallback(async (cam: Camera) => {
    setTimelineCam(cam);
    setExportNotice(null);
    try {
      const data = toTimeline(await api<ServerTimeline>(`/cameras/${cam.id}/timeline`));
      setTimeline(data);
      if (data.segments.length > 0) {
        setActiveSeg(data.segments[data.segments.length - 1]);
      } else {
        setActiveSeg(null);
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    const handler = (ev: KeyboardEvent) => {
      if (ev.target instanceof HTMLInputElement || ev.target instanceof HTMLTextAreaElement) return;
      if (ev.key >= '1' && ev.key <= '9') {
        const idx = Number(ev.key) - 1;
        const numberedCameras = [...cameras].sort((a, b) => Number(b.source_type === 'PHONE') - Number(a.source_type === 'PHONE'));
        if (numberedCameras[idx]) {
          setFocusedId((old) => (old === numberedCameras[idx].id ? null : numberedCameras[idx].id));
        }
      } else if (ev.key === 'Escape') {
        setFocusedId(null);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [cameras]);

  async function exportClip(cam: Camera) {
    if (!timeline || timeline.segments.length === 0) return;
    const first = timeline.segments[0];
    const last = timeline.segments[timeline.segments.length - 1];
    try {
      const res = await post<{ url: string; duration_s: number }>(`/cameras/${cam.id}/exports`, {
        from_ts: Date.parse(first.started_at) / 1000,
        to_ts: Date.parse(last.ended_at || new Date().toISOString()) / 1000,
      });
      setExportNotice(`Export ready (${Math.round(res.duration_s)}s): ${res.url}`);
    } catch (e) {
      setExportNotice(`Export notice: ${(e as Error).message}`);
    }
  }

  const orderedCameras = [...cameras].sort((a, b) => Number(b.source_type === 'PHONE') - Number(a.source_type === 'PHONE'));
  const visibleCameras = focusedId
    ? orderedCameras.filter((c) => c.id === focusedId)
    : orderedCameras.slice(0, gridSize);

  return (
    <div className="live-wall-container">
      <ErrorNotice message={error} />
      <div className="section-head">
        <div className="actions">
          <Badge>{cameras.filter((c) => c.is_online).length} / {cameras.length} online</Badge>
          <Badge>{cameras.filter((c) => c.source_type === 'PHONE').length} Android cameras</Badge>
        </div>
        <div className="actions">
          {cameras.length > 1 && ([1, 4, 9] as const).map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={!focusedId && gridSize === n}
              onClick={() => {
                setFocusedId(null);
                setGridSize(n);
              }}
            >
              {n === 1 ? 'One' : n === 4 ? 'Four' : 'Nine'}
            </button>
          ))}
          <button type="button" onClick={() => void refresh()}>
            <Icon name="refresh-01" />
            Refresh
          </button>
        </div>
      </div>

      {cameras.length === 0 ? (
        <Empty title="No live cameras yet" icon="video-on">
          Open SafeSpace on your Android phone and choose Camera Station. Its live feed will appear here when connected.
        </Empty>
      ) : (
        <div className={`live-wall-grid cols-${focusedId || cameras.length === 1 || gridSize === 1 ? 1 : gridSize === 4 ? 2 : 3}`}>
          {visibleCameras.map((cam) => (
            <LiveTile
              key={cam.id}
              camera={cam}
              focused={focusedId === cam.id}
              onFocus={() => setFocusedId((old) => (old === cam.id ? null : cam.id))}
              onCreateRule={onCreateRule}
              onOpenTimeline={(c) => void openTimeline(c)}
            />
          ))}
        </div>
      )}

      {timelineCam && (
        <Modal title={`${timelineCam.name} · 24h Timeline & Recordings`} close={() => { setTimelineCam(null); setTimeline(null); }}>
          <div className="incident-detail">
            {activeSeg ? (
              <video key={activeSeg.id} controls autoPlay src={activeSeg.stream_url} style={{ width: '100%', aspectRatio: '16 / 9', objectFit: 'contain', background: '#000', borderRadius: 16 }} />
            ) : (
              <Empty title="No recording segments in window" icon="play-01">
                10-second MP4 segments are recorded automatically while {timelineCam.name} streams live.
              </Empty>
            )}

            {timeline && (
              <>
                <div className="section-head">
                  <h3>Timeline Scrubber ({timeline.segments.length} segments · {timeline.snapshots.length} snapshots)</h3>
                  <button type="button" disabled={timeline.segments.length === 0} onClick={() => void exportClip(timelineCam)}>
                    <Icon name="download" />
                    Export Clip Range
                  </button>
                </div>
                {exportNotice && <p className="notice">{exportNotice}</p>}
                <div className="timeline-strip">
                  {timeline.segments.map((seg) => (
                    <button
                      key={seg.id}
                      type="button"
                      className={`timeline-seg ${activeSeg?.id === seg.id ? 'active' : ''}`}
                      onClick={() => setActiveSeg(seg)}
                    >
                      <strong>{new Date(seg.started_at).toLocaleTimeString()}</strong>
                      <span className="caption">{Math.round(seg.duration_ms / 1000)}s</span>
                    </button>
                  ))}
                </div>
                {timeline.snapshots.length > 0 && (
                  <>
                    <h3>Saved Snapshots</h3>
                    <div className="source-grid">
                      {timeline.snapshots.slice(0, 6).map((snap) => (
                        <a key={snap.id} href={snap.url} target="_blank" rel="noreferrer" className="source-card">
                          <img src={snap.url} alt="Snapshot" style={{ width: '100%', aspectRatio: '16 / 9', objectFit: 'cover', borderRadius: 12 }} />
                          <span className="caption">{date(snap.created_at)}</span>
                        </a>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
