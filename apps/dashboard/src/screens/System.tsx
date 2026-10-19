import { useCallback, useEffect, useState, type FormEvent } from 'react';
import QRCode from 'qrcode';
import { api, post, date, type System, type Settings } from '../api/client';
import { Badge, ErrorNotice, Icon } from '../components';
import { TrainingPanel } from './Benchmarks';

interface FleetDevice {
  device_id: string;
  camera_id?: string;
  device_name: string;
  device_model?: string | null;
  os_version?: string | null;
  app_version?: string | null;
  battery_pct?: number | null;
  is_charging?: boolean | null;
  temp_c?: number | null;
  wifi_rssi_dbm?: number | null;
  ip_address?: string | null;
  fps_out?: number | null;
  dropped_frames?: number | null;
  current_profile?: string | null;
  lens_facing?: string | null;
  torch_on?: boolean | null;
  stealth_mode?: boolean | null;
  status?: string;
  last_heartbeat_at?: string | null;
  id?: string;
  name?: string;
  route?: string | null;
  role?: string | null;
}

interface StorageSummary {
  recordings_bytes: number;
  incidents_bytes: number;
  snapshots_bytes: number;
  exports_bytes: number;
  total_used_gb: number;
  free_disk_gb: number;
  max_total_gb: number;
}

// The server reports raw bytes; the panel shows gigabytes of SafeSpace data against the disk.
interface ServerStorage {
  total_bytes: number; free_bytes: number; used_bytes: number;
  recordings_bytes: number; snapshots_bytes: number; exports_bytes: number;
}
const GB = 1024 ** 3;
function toStorage(r: ServerStorage): StorageSummary {
  const own = r.recordings_bytes + r.snapshots_bytes + r.exports_bytes;
  return { recordings_bytes: r.recordings_bytes, incidents_bytes: 0, snapshots_bytes: r.snapshots_bytes, exports_bytes: r.exports_bytes,
           total_used_gb: own / GB, free_disk_gb: r.free_bytes / GB, max_total_gb: Math.round(r.total_bytes / GB) };
}

interface ServerDevice {
  device_id: string; camera_id?: string | null; name?: string; model?: string | null; os_version?: string | null; app_version?: string | null;
  battery_pct?: number | null; charging?: number | boolean | null; temp_c?: number | null; wifi_rssi?: number | null; local_ip?: string | null;
  fps?: number | null; capture_profile?: string | null; lens_facing?: string | null; torch_enabled?: number | boolean | null;
  stealth_mode?: number | boolean | null; status?: string | null; last_seen?: number | null; route?: string | null; role?: string | null;
}
function toFleet(d: ServerDevice): FleetDevice {
  return {
    device_id: d.device_id, camera_id: d.camera_id || undefined, device_name: d.name || d.device_id, device_model: d.model, os_version: d.os_version,
    app_version: d.app_version, battery_pct: d.battery_pct, is_charging: !!d.charging, temp_c: d.temp_c, wifi_rssi_dbm: d.wifi_rssi, ip_address: d.local_ip,
    fps_out: d.fps, current_profile: d.capture_profile, lens_facing: d.lens_facing, torch_on: !!d.torch_enabled, stealth_mode: !!d.stealth_mode,
    status: (d.status || 'offline').toUpperCase(), last_heartbeat_at: d.last_seen ? new Date(d.last_seen * 1000).toISOString() : null,
    route: d.route, role: d.role,
  };
}

interface PairingInfo {
  code: string;
  link: string;
  role: 'control' | 'camera';
  expires_in: number;
  routes: { route: string; label: string; url: string; tls: boolean }[];
  qr: string; // data URL
}

interface NetworkInfo {
  mode: string;
  modes: string[];
  enabled_routes: string[];
  labels: Record<string, string>;
  capabilities: Record<string, { password_login: boolean; enroll: boolean; require_tls: boolean }>;
  cidrs: Record<string, string[]>;
  listeners: { http: number | null; https: number | null };
  interfaces: { interface: string; ip: string; route: string | null; enabled: boolean }[];
  routes: { route: string; label: string; url: string; tls: boolean }[];
  host_ssid: string | null;
  warnings: string[];
}

interface AuditEntry {
  id: number;
  actor: string;
  action: string;
  target_id?: string | null;
  created_at: string;
}

export function SystemScreen({
  system,
  refresh,
  onPasswordChange,
}: {
  system: System | null;
  refresh: () => Promise<void>;
  onPasswordChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const [pairing, setPairing] = useState<PairingInfo | null>(null);
  const [apk, setApk] = useState<{ url: string; qr: string; ready: boolean } | null>(null);
  const [network, setNetwork] = useState<NetworkInfo | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [devices, setDevices] = useState<FleetDevice[]>([]);
  const [storage, setStorage] = useState<StorageSummary | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);

  const loadAll = useCallback(async () => {
    try {
      const [s, d, st, au, net] = await Promise.all([
        api<Settings>('/settings').catch(() => null),
        api<{ items: ServerDevice[] }>('/devices/fleet').then((r) => r.items.map(toFleet)).catch(() => [] as FleetDevice[]),
        api<ServerStorage>('/storage/summary').then(toStorage).catch(() => null),
        api<AuditEntry[]>('/system/audit?limit=15').catch(() => [] as AuditEntry[]),
        api<NetworkInfo>('/network').catch(() => null),
      ]);
      if (net) setNetwork(net);
      if (s) setSettings(s);
      setDevices(d);
      if (st) setStorage(st);
      setAudit(au);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function action(fn: () => Promise<unknown>, message = 'Saved') {
    setError(null);
    try {
      await fn();
      setNotice(message);
      await refresh();
      await loadAll();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function sendDeviceCommand(deviceId: string, command: string, params: Record<string, unknown> = {}) {
    await action(
      () => post(`/devices/${encodeURIComponent(deviceId)}/command`, { command, params }),
      `Sent "${command}" to ${deviceId}`,
    );
  }

  async function createPairing(role: 'control' | 'camera') {
    await action(async () => {
      const r = await post<{ code: string; link: string; role: 'control' | 'camera'; expires_in: number; routes: PairingInfo['routes'] }>('/auth/pairing-code', { role });
      const qr = await QRCode.toDataURL(r.link, { margin: 1, width: 280, errorCorrectionLevel: 'M', color: { dark: '#000000', light: '#ffffff' } });
      setPairing({ ...r, qr });
      setApk(null);
    }, role === 'camera' ? 'Camera pairing link ready' : 'Control phone pairing link ready');
  }

  async function createApkLink() {
    await action(async () => {
      const r = await post<{ url: string; apk_ready: boolean }>('/devices/apk-token', {});
      setApk({ url: r.url, ready: r.apk_ready, qr: await QRCode.toDataURL(r.url, { margin: 1, width: 280, color: { dark: '#000000', light: '#ffffff' } }) });
      setPairing(null);
    }, 'APK download link ready');
  }

  async function password(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    await action(async () => {
      await post('/auth/password', { current_password: f.get('current'), new_password: f.get('next') });
      onPasswordChange();
    });
  }

  const inf = system?.inference;
  const train = system?.training;

  return (
    <>
      <ErrorNotice message={error} />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="system-grid">
        <section className="panel wide">
          <div className="section-head">
            <div>
              <p className="eyebrow">CONNECTION</p>
              <h2>{network ? 'How phones connect' : 'Checking connection…'}</h2>
            </div>
            <Badge>{network ? (network.mode === 'hotspot_only' ? 'Hotspot only' : network.mode === 'ibus' ? 'Wi-Fi + mesh' : 'Anywhere') : '—'}</Badge>
          </div>
          {network && (
            <>
              <p>{network.host_ssid ? `Laptop connected to ${network.host_ssid}.` : 'Connect this laptop and your phones to an allowed network.'}</p>
              {network.warnings.map((w) => (
                <p className="caption" role="status" key={w}>{w}</p>
              ))}
              <details className="system-advanced"><summary>Show network details</summary>
              <dl>
                <dt>This laptop is on</dt>
                <dd className="mono">{network.host_ssid || 'unknown Wi-Fi'}</dd>
                {network.interfaces.map((i) => (
                  <div key={i.ip} style={{ display: 'contents' }}>
                    <dt>{i.interface}</dt>
                    <dd className="mono">{i.ip} · {i.route ? (network.labels[i.route] || i.route) : 'not an allowed network'}{i.enabled ? '' : ' (off)'}</dd>
                  </div>
                ))}
                <dt>Addresses phones use</dt>
                <dd className="mono">{network.routes.length ? network.routes.map((r) => r.url).join('   ') : 'none yet: join the Nothing Phone hotspot'}</dd>
                <dt>Listening</dt>
                <dd className="mono">HTTP :{network.listeners.http ?? 'off'} · HTTPS :{network.listeners.https ?? 'off'}</dd>
              </dl>
              </details>
            </>
          )}
        </section>

        <section className="panel wide">
          <div className="section-head">
            <h2>Connected phones</h2>
            <div className="actions">
              <Badge>{devices.length} enrolled</Badge>
              <button type="button" onClick={() => void createPairing('camera')}>
                <Icon name="plus-01" />
                Add a camera phone
              </button>
              <button type="button" onClick={() => void createPairing('control')}>
                <Icon name="plus-01" />
                Add a control phone
              </button>
              <button type="button" onClick={() => void createApkLink()}>
                <Icon name="download" />
                Install app
              </button>
            </div>
          </div>

          {pairing && (
            <div className="pairing-code" style={{ textAlign: 'left', marginBottom: 20, display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
              <img src={pairing.qr} width={220} height={220} alt="Pairing QR code" style={{ borderRadius: 12, background: '#fff' }} />
              <div style={{ flex: 1, minWidth: 240 }}>
                <h3>{pairing.role === 'camera' ? 'Pair a camera phone' : 'Pair a control phone'}</h3>
                <p>Scan with the phone's camera app. SafeSpace opens and connects with nothing to type. Or enter this code in the app:</p>
                <h2 className="mono">{pairing.code}</h2>
                <span className="caption">Single use · expires in {Math.round(pairing.expires_in / 60)} minutes</span>
                <dl>
                  <dt>Addresses in the link</dt>
                  <dd className="mono">{pairing.routes.map((r) => r.url).join('  ') || 'none (is the laptop on the hotspot?)'}</dd>
                </dl>
              </div>
            </div>
          )}

          {apk && (
            <div className="pairing-code" style={{ textAlign: 'left', marginBottom: 20, display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
              <img src={apk.qr} width={220} height={220} alt="APK download QR code" style={{ borderRadius: 12, background: '#fff' }} />
              <div style={{ flex: 1, minWidth: 240 }}>
                <h3>Install SafeSpace</h3>
                <p>Scan to download the app (single use, 10 minutes). Your phone must be on the same network as this laptop.</p>
                <a className="mono" href={apk.url} target="_blank" rel="noreferrer">{apk.url}</a>
                {!apk.ready && <p className="caption">No APK has been built yet. Run scripts/build-apk.ps1.</p>}
              </div>
            </div>
          )}

          {devices.length === 0 ? (
            <p className="muted">No phones enrolled yet. Use Add a camera phone or Add a control phone above.</p>
          ) : (
            <div className="source-grid">
              {devices.map((d) => {
                const devId = d.device_id || d.id || 'unknown';
                const devName = d.device_name || d.name || devId;
                return (
                  <article className="source-card" key={devId}>
                    <div className="section-head" style={{ width: '100%' }}>
                      <strong>{devName}</strong>
                      <Badge>{d.status || 'ONLINE'}</Badge>
                    </div>
                    <small className="mono">
                      {devId} {d.camera_id ? `→ ${d.camera_id}` : ''}
                    </small>
                    <span className="caption">
                      {d.device_model || 'Android phone'} · {d.ip_address || 'no address yet'}{d.route && network ? ` · via ${network.labels[d.route] || d.route}` : ''} ·{' '}
                      {d.battery_pct != null ? `${d.battery_pct}%${d.is_charging ? ' ⚡' : ''}` : 'Battery —'} ·{' '}
                      {d.temp_c != null ? `${d.temp_c.toFixed(1)}°C` : 'Temp —'} ·{' '}
                      {d.fps_out != null ? `${d.fps_out.toFixed(1)} FPS` : 'Idle'} ({d.current_profile || 'BALANCED'})
                    </span>
                    <div className="actions" style={{ marginTop: 8 }}>
                      <button type="button" onClick={() => void sendDeviceCommand(devId, 'toggle_torch')}>
                        Torch
                      </button>
                      <button type="button" onClick={() => void sendDeviceCommand(devId, 'flip_lens')}>
                        Flip Lens
                      </button>
                      <button type="button" onClick={() => void sendDeviceCommand(devId, 'toggle_stealth')}>
                        Stealth
                      </button>
                      <button type="button" onClick={() => void sendDeviceCommand(devId, 'take_snapshot')}>
                        Snapshot
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          void action(async () => {
                            await api(`/devices/${encodeURIComponent(devId)}`, { method: 'DELETE' });
                          }, `Revoked ${devName}`)
                        }
                      >
                        Revoke
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className="panel">
          <div className="section-head">
            <h2>System status</h2>
            <Badge>{system?.status || 'Connecting'}</Badge>
          </div>
          <dl>
            <dt>Detector</dt>
            <dd>{inf?.ready ? 'Ready' : 'Unavailable'}</dd>
            <dt>Compute device</dt>
            <dd>{inf?.device === '0' ? 'NVIDIA CUDA' : String(inf?.device || 'Unknown')}</dd>
            <dt>Local chat</dt>
            <dd>{system?.chat.local_available ? 'Ollama connected' : 'Ollama unavailable'}</dd>
            <dt>RAM in use</dt>
            <dd>
              {String(system?.resources.ram_used_gb ?? '—')} / {String(system?.resources.ram_total_gb ?? '—')} GB
            </dd>
            <dt>Disk available</dt>
            <dd>{String(system?.resources.disk_free_gb ?? '—')} GB</dd>
          </dl>
          {((inf?.errors || []) as string[]).map((e) => (
            <p className="caption" key={e}>
              {e}
            </p>
          ))}
          <button onClick={() => void action(() => post('/models/reload'), 'Model registry reloaded')}>
            <Icon name="refresh-01" />
            Reload installed weights
          </button>
        </section>

        <section className="panel">
          <div className="section-head">
            <h2>Recording storage</h2>
            <Badge>{storage ? `${storage.total_used_gb.toFixed(2)} / ${storage.max_total_gb} GB` : 'Active'}</Badge>
          </div>
          {storage && (
            <dl>
              <dt>Continuous Recordings</dt>
              <dd>{(storage.recordings_bytes / (1024 * 1024)).toFixed(1)} MB</dd>
              <dt>Incident Evidence</dt>
              <dd>{(storage.incidents_bytes / (1024 * 1024)).toFixed(1)} MB</dd>
              <dt>Snapshots</dt>
              <dd>{(storage.snapshots_bytes / (1024 * 1024)).toFixed(1)} MB</dd>
              <dt>Exported Clips</dt>
              <dd>{(storage.exports_bytes / (1024 * 1024)).toFixed(1)} MB</dd>
              <dt>Free Disk Space</dt>
              <dd>{storage.free_disk_gb.toFixed(1)} GB</dd>
            </dl>
          )}
          <button
            type="button"
            onClick={() => void action(() => post('/storage/sweep', {}), 'Retention sweep completed')}
          >
            <Icon name="refresh-01" />
            Apply storage limits
          </button>
        </section>

        <TrainingPanel training={train} />

        <section className="panel">
          <h2>What the system can detect</h2>
          {((inf?.models || []) as { name: string; classes: string[] }[]).map((m) => (
            <div className="setting-row" key={m.name}>
              <strong>{m.name}</strong>
              <span>{m.classes.join(', ')}</span>
            </div>
          ))}
          <h3>Outside current coverage</h3>
          <ul className="muted">
            {((inf?.unsupported || []) as string[]).map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <p className="caption">
            Behavior, intent, and unseen hazards cannot be reliably inferred from object detection alone.
          </p>
        </section>

        <section className="panel">
          <h2>Incident assistant</h2>
          {settings && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(() => post('/settings', settings), 'Assistant settings saved');
              }}
            >
              <label>
                Default provider
                <select
                  value={settings.chat_provider}
                  onChange={(e) =>
                    setSettings({ ...settings, chat_provider: e.target.value as Settings['chat_provider'] })
                  }
                >
                  <option value="ollama">Local Ollama</option>
                  <option value="groq">Groq cloud</option>
                </select>
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={settings.ai_review}
                  onChange={(e) => setSettings({ ...settings, ai_review: e.target.checked })}
                />
                Automatically ask the AI to double-check every new incident
              </label>
              <label>
                Ollama model
                <input
                  value={settings.ollama_model}
                  onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                />
              </label>
              <label>
                Groq model
                <input
                  value={settings.groq_model}
                  onChange={(e) => setSettings({ ...settings, groq_model: e.target.value })}
                />
              </label>
              <p className="caption">
                Installed locally: {((system?.chat.installed_models || []) as string[]).join(', ') || 'None detected'}.
                Groq credentials are stored only on the server.
              </p>
              <button className="primary">Save settings</button>
            </form>
          )}
        </section>


        <section className="panel">
          <h2>Change your password</h2>
          <p>Changing your password signs out every connected device.</p>
          <form onSubmit={password}>
            <label>
              Current password
              <input name="current" type="password" required autoComplete="current-password" />
            </label>
            <label>
              New password
              <input name="next" type="password" required minLength={10} autoComplete="new-password" />
            </label>
            <button className="primary">Change password</button>
          </form>
        </section>

        {audit.length > 0 && (
          <section className="panel wide">
            <div className="section-head">
              <h2>Security Audit Log</h2>
              <Badge>{audit.length} recent events</Badge>
            </div>
            {audit.map((entry) => (
              <div className="setting-row" key={entry.id}>
                <strong>
                  {entry.action} · <span className="mono">{entry.actor}</span>
                </strong>
                <span>
                  {entry.target_id ? `${entry.target_id} · ` : ''}
                  {date(entry.created_at)}
                </span>
              </div>
            ))}
          </section>
        )}
      </div>
    </>
  );
}
