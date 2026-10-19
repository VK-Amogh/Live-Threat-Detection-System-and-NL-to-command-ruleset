"""Durable local SQLite store. Every incident update has a monotonic change record."""
import json
import shutil
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from . import settings
from .settings import DB_PATH

SCHEMA_TARGET_VERSION = 3


def _active_db_path() -> Path:
    return Path(DB_PATH)


@contextmanager
def connection():
    db = sqlite3.connect(_active_db_path(), timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def _ensure_column(db, table: str, column: str, definition: str):
    cols = {row['name'] for row in db.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in cols:
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def _backup_before_migration():
    db_path = _active_db_path()
    if not db_path.exists() or db_path.stat().st_size == 0:
        return
    try:
        with sqlite3.connect(db_path, timeout=5) as tmp:
            has_ver = tmp.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            ).fetchone()
            current_ver = 0
            if has_ver:
                row = tmp.execute('SELECT coalesce(max(version), 0) FROM schema_version').fetchone()
                current_ver = row[0] if row else 0
            if current_ver >= SCHEMA_TARGET_VERSION:
                return
        backup_dir = db_path.parent / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / f'safespace-pre-v{SCHEMA_TARGET_VERSION}-{int(time.time())}.db'
        shutil.copy2(db_path, backup_file)
    except Exception:
        pass


def initialize():
    _backup_before_migration()
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE, password TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id TEXT, device_id TEXT, name TEXT, expires REAL, created_at TEXT);
        CREATE TABLE IF NOT EXISTS pairing(code TEXT PRIMARY KEY, user_id TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS objects(kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id));
        CREATE TABLE IF NOT EXISTS changes(seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS feedback(action_id TEXT PRIMARY KEY, event_id TEXT);
        CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, user_id TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS rules(id TEXT PRIMARY KEY, camera_id TEXT NOT NULL, text TEXT NOT NULL,
            spec_json TEXT NOT NULL, readback TEXT, readback_hash TEXT, can_activate INTEGER NOT NULL,
            status TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS rules_camera ON rules(camera_id, status);
        CREATE TABLE IF NOT EXISTS camera_geometry(camera_id TEXT PRIMARY KEY, body TEXT NOT NULL,
            version INTEGER NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS review_jobs(event_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS camera_health(camera_id TEXT PRIMARY KEY, last_frame_ts REAL,
            fps REAL, gpu_ok INTEGER, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS changes_event ON changes(event_id);

        CREATE TABLE IF NOT EXISTS devices (
          device_id       TEXT PRIMARY KEY,
          installation_id TEXT NOT NULL UNIQUE,
          name            TEXT NOT NULL,
          role            TEXT NOT NULL,
          camera_id       TEXT,
          model           TEXT,
          os_version      TEXT,
          app_version     TEXT,
          token_hash      TEXT,
          token_scope     TEXT,
          token_expires   REAL,
          battery_pct     INTEGER,
          charging        INTEGER,
          temp_c          REAL,
          wifi_rssi       INTEGER,
          wifi_ssid       TEXT,
          wifi_bssid      TEXT,
          local_ip        TEXT,
          fps             REAL,
          dropped_frames  INTEGER DEFAULT 0,
          queue_depth     INTEGER DEFAULT 0,
          capture_profile TEXT DEFAULT 'normal',
          stealth_mode    INTEGER DEFAULT 0,
          torch_enabled   INTEGER DEFAULT 0,
          lens_facing     TEXT DEFAULT 'back',
          status          TEXT NOT NULL DEFAULT 'offline',
          last_seen       REAL,
          created_at      REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recording_segments (
          segment_id  TEXT PRIMARY KEY,
          camera_id   TEXT NOT NULL,
          start_ts    REAL NOT NULL,
          end_ts      REAL NOT NULL,
          duration_s  REAL NOT NULL,
          path        TEXT NOT NULL,
          size_bytes  INTEGER NOT NULL,
          width       INTEGER NOT NULL,
          height      INTEGER NOT NULL,
          fps         REAL NOT NULL,
          codec       TEXT NOT NULL DEFAULT 'h264',
          has_events  INTEGER NOT NULL DEFAULT 0,
          event_count INTEGER NOT NULL DEFAULT 0,
          created_at  REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_segments_cam_ts ON recording_segments(camera_id, start_ts, end_ts);

        CREATE TABLE IF NOT EXISTS snapshots (
          snapshot_id     TEXT PRIMARY KEY,
          camera_id       TEXT NOT NULL,
          ts              REAL NOT NULL,
          kind            TEXT NOT NULL,
          path            TEXT NOT NULL,
          width           INTEGER NOT NULL,
          height          INTEGER NOT NULL,
          size_bytes      INTEGER NOT NULL,
          source_event_id TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_cam_ts ON snapshots(camera_id, ts);

        CREATE TABLE IF NOT EXISTS exports (
          export_id   TEXT PRIMARY KEY,
          camera_id   TEXT NOT NULL,
          start_ts    REAL NOT NULL,
          end_ts      REAL NOT NULL,
          duration_s  REAL NOT NULL,
          path        TEXT NOT NULL,
          size_bytes  INTEGER NOT NULL,
          created_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rulesets (
          ruleset_id    TEXT PRIMARY KEY,
          name          TEXT NOT NULL,
          source_type   TEXT NOT NULL,
          spec_json     TEXT NOT NULL,
          readback      TEXT NOT NULL,
          readback_hash TEXT NOT NULL,
          support_level TEXT NOT NULL DEFAULT 'SUPPORTED',
          camera_ids    TEXT NOT NULL,
          rule_ids      TEXT NOT NULL DEFAULT '[]',
          schedule_json TEXT,
          modes_json    TEXT,
          status        TEXT NOT NULL DEFAULT 'draft',
          version       INTEGER NOT NULL DEFAULT 1,
          problems_json TEXT NOT NULL DEFAULT '[]',
          can_activate  INTEGER NOT NULL DEFAULT 1,
          created_at    REAL NOT NULL,
          updated_at    REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
          id           INTEGER PRIMARY KEY AUTOINCREMENT,
          ts           REAL NOT NULL,
          actor_user   TEXT,
          actor_device TEXT,
          ip           TEXT,
          action       TEXT NOT NULL,
          target_type  TEXT,
          target_id    TEXT,
          detail_json  TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);

        CREATE TABLE IF NOT EXISTS moments (
          moment_id     TEXT PRIMARY KEY,
          camera_id     TEXT NOT NULL,
          ts            REAL NOT NULL,
          kind          TEXT NOT NULL,
          label         TEXT NOT NULL,
          summary       TEXT NOT NULL,
          media_url     TEXT,
          segment_id    TEXT,
          snapshot_id   TEXT,
          event_id      TEXT,
          metadata_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_moments_cam_ts ON moments(camera_id, ts DESC);
        ''')
        _ensure_column(db, 'users', 'display_name', "TEXT DEFAULT ''")
        _ensure_column(db, 'users', 'disabled', 'INTEGER NOT NULL DEFAULT 0')
        _ensure_column(db, 'users', 'role', "TEXT NOT NULL DEFAULT 'admin'")
        _ensure_column(db, 'sessions', 'scope', "TEXT NOT NULL DEFAULT 'admin'")
        _ensure_column(db, 'sessions', 'role', "TEXT NOT NULL DEFAULT 'control'")
        _ensure_column(db, 'rules', 'ruleset_id', 'TEXT')
        # A pairing code carries the scope/role the new device will receive (a camera phone never gets an admin token).
        _ensure_column(db, 'pairing', 'scope', "TEXT NOT NULL DEFAULT 'admin'")
        _ensure_column(db, 'pairing', 'role', "TEXT NOT NULL DEFAULT 'control'")
        # Which route (loopback / trusted_lan / ibus_lan / tailnet / relay) a device last connected through.
        _ensure_column(db, 'devices', 'route', 'TEXT')
        db.execute(
            'INSERT OR REPLACE INTO schema_version(version, applied_at) VALUES(?, ?)',
            (SCHEMA_TARGET_VERSION, time.time()),
        )


def get(kind, ident):
    with connection() as db:
        row = db.execute('SELECT body FROM objects WHERE kind=? AND id=?', (kind, ident)).fetchone()
        return json.loads(row['body']) if row else None


def all_objects(kind):
    with connection() as db:
        return [json.loads(r['body']) for r in db.execute('SELECT body FROM objects WHERE kind=?', (kind,))]


def put(kind, body):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO objects VALUES(?,?,?)', (kind, body['id'], json.dumps(body)))
    return body


def delete_object(kind, ident):
    with connection() as db:
        cur = db.execute('DELETE FROM objects WHERE kind=? AND id=?', (kind, ident))
        return cur.rowcount > 0


def save_event(event):
    with connection() as db:
        seq = db.execute('INSERT INTO changes(event_id,body) VALUES(?,?)', (event['id'], '{}')).lastrowid
        event['change_seq'] = seq
        payload = json.dumps(event)
        db.execute('UPDATE changes SET body=? WHERE seq=?', (payload, seq))
        db.execute('INSERT OR REPLACE INTO objects VALUES(?,?,?)', ('event', event['id'], payload))
    return event


def insert_event_once(event):
    """Atomically persist a new event and its change before anyone broadcasts."""
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT body FROM objects WHERE kind=? AND id=?', ('event', event['id'])).fetchone()
        if old:
            return json.loads(old['body']), False
        seq = db.execute('INSERT INTO changes(event_id,body) VALUES(?,?)', (event['id'], '{}')).lastrowid
        event['change_seq'] = seq
        payload = json.dumps(event)
        db.execute('UPDATE changes SET body=? WHERE seq=?', (payload, seq))
        db.execute('INSERT INTO objects VALUES(?,?,?)', ('event', event['id'], payload))
        if event.get('needs_visual_review'):
            db.execute('INSERT INTO review_jobs(event_id,status,updated_at) VALUES(?,?,?)',
                       (event['id'], 'PENDING', event['created_at']))
    return event, True


def put_rule(record):
    record = dict(record)
    record.setdefault('ruleset_id', None)
    with connection() as db:
        db.execute('''INSERT INTO rules(id,camera_id,text,spec_json,readback,readback_hash,can_activate,status,version,updated_at,ruleset_id)
            VALUES(:id,:camera_id,:text,:spec_json,:readback,:readback_hash,:can_activate,:status,:version,:updated_at,:ruleset_id)
            ON CONFLICT(id) DO UPDATE SET spec_json=excluded.spec_json,readback=excluded.readback,
                readback_hash=excluded.readback_hash,can_activate=excluded.can_activate,
                status=excluded.status,version=excluded.version,updated_at=excluded.updated_at,
                ruleset_id=coalesce(excluded.ruleset_id, rules.ruleset_id)''', record)
    return record


def get_rule(ident):
    with connection() as db:
        row = db.execute('SELECT * FROM rules WHERE id=?', (ident,)).fetchone()
    return dict(row) if row else None


def list_rules(camera_id=None):
    with connection() as db:
        rows = (
            db.execute('SELECT * FROM rules WHERE camera_id=? ORDER BY updated_at DESC', (camera_id,)).fetchall()
            if camera_id
            else db.execute('SELECT * FROM rules ORDER BY updated_at DESC').fetchall()
        )
    return [dict(row) for row in rows]


def delete_rule(ident):
    with connection() as db:
        cur = db.execute('DELETE FROM rules WHERE id=?', (ident,))
        return cur.rowcount > 0


def put_geometry(camera_id, body, updated_at):
    with connection() as db:
        row = db.execute('SELECT version FROM camera_geometry WHERE camera_id=?', (camera_id,)).fetchone()
        version = (row['version'] + 1) if row else 1
        db.execute('''INSERT INTO camera_geometry(camera_id,body,version,updated_at) VALUES(?,?,?,?)
            ON CONFLICT(camera_id) DO UPDATE SET body=excluded.body,version=excluded.version,updated_at=excluded.updated_at''',
                   (camera_id, json.dumps(body), version, updated_at))
    return version


def get_geometry(camera_id):
    with connection() as db:
        row = db.execute('SELECT body,version FROM camera_geometry WHERE camera_id=?', (camera_id,)).fetchone()
    return (json.loads(row['body']), row['version']) if row else (None, 0)


def head():
    with connection() as db:
        return db.execute('SELECT coalesce(max(seq),0) FROM changes').fetchone()[0]


def _write_event_locked(db, event):
    seq = db.execute('INSERT INTO changes(event_id,body) VALUES(?,?)', (event['id'], '{}')).lastrowid
    event['change_seq'] = seq
    payload = json.dumps(event)
    db.execute('UPDATE changes SET body=? WHERE seq=?', (payload, seq))
    db.execute('UPDATE objects SET body=? WHERE kind=? AND id=?', (payload, 'event', event['id']))
    return event


def claim_review_job(stamp):
    """Lease one event whose clip has been attached; expired leases can be reclaimed."""
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute('''SELECT j.event_id,j.lease_until,o.body FROM review_jobs j
            JOIN objects o ON o.kind='event' AND o.id=j.event_id
            WHERE (j.status IN ('PENDING','RETRY') AND coalesce(j.lease_until,0)<=?)
               OR (j.status='VERIFYING' AND j.lease_until<=?)
            ORDER BY j.updated_at''', (time.time(), time.time())).fetchall()
        for row in rows:
            event = json.loads(row['body'])
            if event['status'] in ('CONFIRMED', 'FALSE_POSITIVE'):
                db.execute("UPDATE review_jobs SET status='DONE',lease_until=NULL,updated_at=? WHERE event_id=?",
                           (stamp, row['event_id']))
                continue
            if not any(item['kind'] == 'CLIP' for item in event['media']):
                continue
            lease = time.time() + 300
            db.execute("UPDATE review_jobs SET status='VERIFYING',attempts=attempts+1,lease_until=?,updated_at=? WHERE event_id=?",
                       (lease, stamp, row['event_id']))
            event.update(status='VERIFYING', status_reason='Visual summary in progress', updated_at=stamp)
            _write_event_locked(db, event)
            return event, lease
    return None


def finish_review_job(event_id, claim_token, result, stamp):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute('SELECT * FROM review_jobs WHERE event_id=?', (event_id,)).fetchone()
        if job is None or job['status'] != 'VERIFYING' or job['lease_until'] != claim_token:
            return None
        row = db.execute('SELECT body FROM objects WHERE kind=? AND id=?', ('event', event_id)).fetchone()
        if row is None:
            return None
        event = json.loads(row['body'])
        event.update(summary=result['visible_evidence'], uncertainty=result['uncertainty'],
                     review_possible_false_positive=result['possible_false_positive'], updated_at=stamp)
        if event['status'] == 'VERIFYING':
            event.update(status='NEEDS_REVIEW', status_reason='Visual summary ready for human review')
        _write_event_locked(db, event)
        db.execute("UPDATE review_jobs SET status='DONE',lease_until=NULL,updated_at=? WHERE event_id=?", (stamp, event_id))
    return event


def retry_review_job(event_id, claim_token, reason, stamp):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute('SELECT * FROM review_jobs WHERE event_id=?', (event_id,)).fetchone()
        if job is None or job['status'] != 'VERIFYING' or job['lease_until'] != claim_token:
            return None
        row = db.execute('SELECT body FROM objects WHERE kind=? AND id=?', ('event', event_id)).fetchone()
        if row is None:
            return None
        event = json.loads(row['body'])
        if event['status'] == 'VERIFYING':
            event.update(status='DETECTED', status_reason='Visual review unavailable',
                         summary='Visual review unavailable; detection is unaffected', updated_at=stamp)
            _write_event_locked(db, event)
        backoff = min(300, 2 ** min(job['attempts'], 8))
        db.execute("UPDATE review_jobs SET status='RETRY',lease_until=?,updated_at=? WHERE event_id=?",
                   (time.time() + backoff, stamp, event_id))
    return event


# --- v3 Device Registry Helpers ---

def upsert_device(record: dict) -> dict:
    now_ts = time.time()
    data = {
        'device_id': record['device_id'],
        'installation_id': record['installation_id'],
        'name': record.get('name', 'Mobile Device'),
        'role': record.get('role', 'camera'),
        'camera_id': record.get('camera_id'),
        'model': record.get('model'),
        'os_version': record.get('os_version'),
        'app_version': record.get('app_version'),
        'token_hash': record.get('token_hash'),
        'token_scope': record.get('token_scope', 'camera'),
        'token_expires': record.get('token_expires'),
        'battery_pct': record.get('battery_pct'),
        'charging': 1 if record.get('charging') else (0 if record.get('charging') is not None else None),
        'temp_c': record.get('temp_c'),
        'wifi_rssi': record.get('wifi_rssi'),
        'wifi_ssid': record.get('wifi_ssid'),
        'wifi_bssid': record.get('wifi_bssid'),
        'local_ip': record.get('local_ip'),
        'fps': record.get('fps', 0.0),
        'dropped_frames': record.get('dropped_frames', 0),
        'queue_depth': record.get('queue_depth', 0),
        'capture_profile': record.get('capture_profile', 'normal'),
        'stealth_mode': 1 if record.get('stealth_mode') else 0,
        'torch_enabled': 1 if record.get('torch_enabled') else 0,
        'lens_facing': record.get('lens_facing', 'back'),
        'status': record.get('status', 'online'),
        'last_seen': record.get('last_seen', now_ts),
        'created_at': record.get('created_at', now_ts),
    }
    with connection() as db:
        db.execute('''
        INSERT INTO devices (
          device_id, installation_id, name, role, camera_id, model, os_version, app_version,
          token_hash, token_scope, token_expires, battery_pct, charging, temp_c, wifi_rssi,
          wifi_ssid, wifi_bssid, local_ip, fps, dropped_frames, queue_depth, capture_profile,
          stealth_mode, torch_enabled, lens_facing, status, last_seen, created_at
        ) VALUES (
          :device_id, :installation_id, :name, :role, :camera_id, :model, :os_version, :app_version,
          :token_hash, :token_scope, :token_expires, :battery_pct, :charging, :temp_c, :wifi_rssi,
          :wifi_ssid, :wifi_bssid, :local_ip, :fps, :dropped_frames, :queue_depth, :capture_profile,
          :stealth_mode, :torch_enabled, :lens_facing, :status, :last_seen, :created_at
        )
        ON CONFLICT(device_id) DO UPDATE SET
          name=excluded.name,
          role=excluded.role,
          camera_id=coalesce(excluded.camera_id, devices.camera_id),
          model=coalesce(excluded.model, devices.model),
          os_version=coalesce(excluded.os_version, devices.os_version),
          app_version=coalesce(excluded.app_version, devices.app_version),
          token_hash=coalesce(excluded.token_hash, devices.token_hash),
          token_scope=coalesce(excluded.token_scope, devices.token_scope),
          token_expires=coalesce(excluded.token_expires, devices.token_expires),
          battery_pct=coalesce(excluded.battery_pct, devices.battery_pct),
          charging=coalesce(excluded.charging, devices.charging),
          temp_c=coalesce(excluded.temp_c, devices.temp_c),
          wifi_rssi=coalesce(excluded.wifi_rssi, devices.wifi_rssi),
          wifi_ssid=coalesce(excluded.wifi_ssid, devices.wifi_ssid),
          wifi_bssid=coalesce(excluded.wifi_bssid, devices.wifi_bssid),
          local_ip=coalesce(excluded.local_ip, devices.local_ip),
          fps=coalesce(excluded.fps, devices.fps),
          dropped_frames=coalesce(excluded.dropped_frames, devices.dropped_frames),
          queue_depth=coalesce(excluded.queue_depth, devices.queue_depth),
          capture_profile=coalesce(excluded.capture_profile, devices.capture_profile),
          stealth_mode=coalesce(excluded.stealth_mode, devices.stealth_mode),
          torch_enabled=coalesce(excluded.torch_enabled, devices.torch_enabled),
          lens_facing=coalesce(excluded.lens_facing, devices.lens_facing),
          status=excluded.status,
          last_seen=excluded.last_seen
        ''', data)
    return get_device(data['device_id'])


def _format_device_row(row) -> dict:
    if not row:
        return None
    d = dict(row)
    d['charging'] = bool(d['charging']) if d.get('charging') is not None else None
    d['stealth_mode'] = bool(d.get('stealth_mode'))
    d['torch_enabled'] = bool(d.get('torch_enabled'))
    d.pop('token_hash', None)
    return d


def set_device_route(device_id: str, route: str | None, client_ip: str | None = None) -> None:
    with connection() as db:
        db.execute('UPDATE devices SET route=?, local_ip=coalesce(?, local_ip) WHERE device_id=?', (route, client_ip, device_id))


def get_device(device_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM devices WHERE device_id=?', (device_id,)).fetchone()
    return _format_device_row(row)


def get_device_by_camera(camera_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM devices WHERE camera_id=? ORDER BY last_seen DESC LIMIT 1', (camera_id,)).fetchone()
    return _format_device_row(row)


def list_devices_v3() -> list[dict]:
    with connection() as db:
        rows = db.execute('SELECT * FROM devices ORDER BY coalesce(last_seen, created_at) DESC').fetchall()
    return [_format_device_row(r) for r in rows]


def update_device_telemetry(device_id: str, fields: dict) -> dict | None:
    allowed = {
        'name', 'role', 'camera_id', 'model', 'os_version', 'app_version',
        'battery_pct', 'charging', 'temp_c', 'wifi_rssi', 'wifi_ssid', 'wifi_bssid',
        'local_ip', 'fps', 'dropped_frames', 'queue_depth', 'capture_profile',
        'stealth_mode', 'torch_enabled', 'lens_facing', 'status', 'last_seen'
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_device(device_id)
    if 'charging' in updates and updates['charging'] is not None:
        updates['charging'] = 1 if updates['charging'] else 0
    if 'stealth_mode' in updates and updates['stealth_mode'] is not None:
        updates['stealth_mode'] = 1 if updates['stealth_mode'] else 0
    if 'torch_enabled' in updates and updates['torch_enabled'] is not None:
        updates['torch_enabled'] = 1 if updates['torch_enabled'] else 0
    updates['last_seen'] = updates.get('last_seen', time.time())
    set_clause = ', '.join(f'{k}=:{k}' for k in updates)
    updates['device_id'] = device_id
    with connection() as db:
        db.execute(f'UPDATE devices SET {set_clause} WHERE device_id=:device_id', updates)
    return get_device(device_id)


def delete_device_v3(device_id: str) -> bool:
    with connection() as db:
        db.execute('DELETE FROM sessions WHERE device_id=?', (device_id,))
        cur = db.execute('DELETE FROM devices WHERE device_id=?', (device_id,))
        return cur.rowcount > 0


# --- v3 Recording Segments, Snapshots & Exports Helpers ---

def insert_recording_segment(seg: dict) -> dict:
    with connection() as db:
        db.execute('''
        INSERT OR REPLACE INTO recording_segments (
          segment_id, camera_id, start_ts, end_ts, duration_s, path, size_bytes,
          width, height, fps, codec, has_events, event_count, created_at
        ) VALUES (
          :segment_id, :camera_id, :start_ts, :end_ts, :duration_s, :path, :size_bytes,
          :width, :height, :fps, :codec, :has_events, :event_count, :created_at
        )
        ''', seg)
    return seg


def get_recording_segment(segment_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM recording_segments WHERE segment_id=?', (segment_id,)).fetchone()
    return dict(row) if row else None


def list_recording_segments(camera_id: str | None = None, from_ts: float | None = None, to_ts: float | None = None, limit: int = 500) -> list[dict]:
    clauses = []
    params = []
    if camera_id:
        clauses.append('camera_id=?')
        params.append(camera_id)
    if from_ts is not None:
        clauses.append('end_ts>=?')
        params.append(float(from_ts))
    if to_ts is not None:
        clauses.append('start_ts<=?')
        params.append(float(to_ts))
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    params.append(limit)
    with connection() as db:
        rows = db.execute(
            f'SELECT * FROM recording_segments {where} ORDER BY start_ts ASC LIMIT ?',
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_recording_segment(segment_id: str) -> dict | None:
    seg = get_recording_segment(segment_id)
    if not seg:
        return None
    with connection() as db:
        db.execute('DELETE FROM recording_segments WHERE segment_id=?', (segment_id,))
    return seg


def insert_snapshot(snap: dict) -> dict:
    with connection() as db:
        db.execute('''
        INSERT OR REPLACE INTO snapshots (
          snapshot_id, camera_id, ts, kind, path, width, height, size_bytes, source_event_id
        ) VALUES (
          :snapshot_id, :camera_id, :ts, :kind, :path, :width, :height, :size_bytes, :source_event_id
        )
        ''', snap)
    return snap


def get_snapshot(snapshot_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM snapshots WHERE snapshot_id=?', (snapshot_id,)).fetchone()
    return dict(row) if row else None


def list_snapshots(camera_id: str | None = None, from_ts: float | None = None, to_ts: float | None = None, limit: int = 200) -> list[dict]:
    clauses = []
    params = []
    if camera_id:
        clauses.append('camera_id=?')
        params.append(camera_id)
    if from_ts is not None:
        clauses.append('ts>=?')
        params.append(float(from_ts))
    if to_ts is not None:
        clauses.append('ts<=?')
        params.append(float(to_ts))
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    params.append(limit)
    with connection() as db:
        rows = db.execute(
            f'SELECT * FROM snapshots {where} ORDER BY ts DESC LIMIT ?',
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_snapshot(snapshot_id: str) -> dict | None:
    snap = get_snapshot(snapshot_id)
    if not snap:
        return None
    with connection() as db:
        db.execute('DELETE FROM snapshots WHERE snapshot_id=?', (snapshot_id,))
    return snap


def insert_export(exp: dict) -> dict:
    with connection() as db:
        db.execute('''
        INSERT OR REPLACE INTO exports (
          export_id, camera_id, start_ts, end_ts, duration_s, path, size_bytes, created_at
        ) VALUES (
          :export_id, :camera_id, :start_ts, :end_ts, :duration_s, :path, :size_bytes, :created_at
        )
        ''', exp)
    return exp


def get_export(export_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM exports WHERE export_id=?', (export_id,)).fetchone()
    return dict(row) if row else None


def list_exports(camera_id: str | None = None, limit: int = 100) -> list[dict]:
    with connection() as db:
        if camera_id:
            rows = db.execute('SELECT * FROM exports WHERE camera_id=? ORDER BY created_at DESC LIMIT ?', (camera_id, limit)).fetchall()
        else:
            rows = db.execute('SELECT * FROM exports ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
    return [dict(r) for r in rows]


# --- v3 Rulesets Helpers ---

def put_ruleset(record: dict) -> dict:
    with connection() as db:
        db.execute('''
        INSERT INTO rulesets (
          ruleset_id, name, source_type, spec_json, readback, readback_hash,
          support_level, camera_ids, rule_ids, schedule_json, modes_json,
          status, version, problems_json, can_activate, created_at, updated_at
        ) VALUES (
          :ruleset_id, :name, :source_type, :spec_json, :readback, :readback_hash,
          :support_level, :camera_ids, :rule_ids, :schedule_json, :modes_json,
          :status, :version, :problems_json, :can_activate, :created_at, :updated_at
        )
        ON CONFLICT(ruleset_id) DO UPDATE SET
          name=excluded.name,
          source_type=excluded.source_type,
          spec_json=excluded.spec_json,
          readback=excluded.readback,
          readback_hash=excluded.readback_hash,
          support_level=excluded.support_level,
          camera_ids=excluded.camera_ids,
          rule_ids=excluded.rule_ids,
          schedule_json=excluded.schedule_json,
          modes_json=excluded.modes_json,
          status=excluded.status,
          version=excluded.version,
          problems_json=excluded.problems_json,
          can_activate=excluded.can_activate,
          updated_at=excluded.updated_at
        ''', record)
    return get_ruleset(record['ruleset_id'])


def _format_ruleset_row(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    spec = json.loads(d['spec_json'] or '{}')
    modes = json.loads(d['modes_json'] or '[]') if d.get('modes_json') else []
    return {
        'ruleset_id': d['ruleset_id'],
        'id': d['ruleset_id'],
        'description': spec.get('description'),
        'template_id': spec.get('template_id'),
        'mode': '/'.join(modes) if modes else None,
        'readback_text': d['readback'],
        'name': d['name'],
        'source_type': d['source_type'],
        'spec': spec,
        'readback': d['readback'],
        'readback_hash': d['readback_hash'],
        'support_level': d.get('support_level', 'SUPPORTED'),
        'camera_ids': json.loads(d['camera_ids'] or '[]'),
        'rule_ids': json.loads(d.get('rule_ids') or '[]'),
        'schedule': json.loads(d['schedule_json']) if d.get('schedule_json') else None,
        'modes': json.loads(d['modes_json'] or '[]') if d.get('modes_json') else [],
        'status': d['status'],
        'version': d['version'],
        'problems': json.loads(d.get('problems_json') or '[]'),
        'can_activate': bool(d.get('can_activate', 1)),
        'created_at': d['created_at'],
        'updated_at': d['updated_at'],
    }


def get_ruleset(ruleset_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT * FROM rulesets WHERE ruleset_id=?', (ruleset_id,)).fetchone()
    return _format_ruleset_row(row)


def list_rulesets() -> list[dict]:
    with connection() as db:
        rows = db.execute('SELECT * FROM rulesets ORDER BY updated_at DESC').fetchall()
    return [_format_ruleset_row(r) for r in rows]


def delete_ruleset(ruleset_id: str) -> bool:
    rs = get_ruleset(ruleset_id)
    if not rs:
        return False
    with connection() as db:
        db.execute('DELETE FROM rules WHERE ruleset_id=?', (ruleset_id,))
        for rid in rs.get('rule_ids', []):
            db.execute('DELETE FROM rules WHERE id=?', (rid,))
        cur = db.execute('DELETE FROM rulesets WHERE ruleset_id=?', (ruleset_id,))
        return cur.rowcount > 0


# --- v3 Audit Log & Moments Helpers ---

def log_audit(action: str, actor_user: str | None = None, actor_device: str | None = None,
              ip: str | None = None, target_type: str | None = None, target_id: str | None = None,
              detail: dict | None = None) -> int:
    with connection() as db:
        cur = db.execute('''
        INSERT INTO audit_log(ts, actor_user, actor_device, ip, action, target_type, target_id, detail_json)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), actor_user, actor_device, ip, action, target_type, target_id, json.dumps(detail or {})))
        return cur.lastrowid


def list_audit_log(limit: int = 100) -> list[dict]:
    with connection() as db:
        rows = db.execute('SELECT * FROM audit_log ORDER BY ts DESC, id DESC LIMIT ?', (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        out.append({
            'id': d['id'],
            'ts': d['ts'],
            'actor_user': d.get('actor_user'),
            'actor_device': d.get('actor_device'),
            'ip': d.get('ip'),
            'action': d['action'],
            'target_type': d.get('target_type'),
            'target_id': d.get('target_id'),
            'detail': json.loads(d.get('detail_json') or '{}'),
        })
    return out


def insert_moment(moment: dict) -> dict:
    data = {
        'moment_id': moment['moment_id'],
        'camera_id': moment['camera_id'],
        'ts': float(moment.get('ts', time.time())),
        'kind': moment.get('kind', 'observation'),
        'label': moment.get('label', ''),
        'summary': moment.get('summary', ''),
        'media_url': moment.get('media_url'),
        'segment_id': moment.get('segment_id'),
        'snapshot_id': moment.get('snapshot_id'),
        'event_id': moment.get('event_id'),
        'metadata_json': json.dumps(moment.get('metadata', {})),
    }
    with connection() as db:
        db.execute('''
        INSERT OR REPLACE INTO moments(
          moment_id, camera_id, ts, kind, label, summary, media_url, segment_id, snapshot_id, event_id, metadata_json
        ) VALUES(
          :moment_id, :camera_id, :ts, :kind, :label, :summary, :media_url, :segment_id, :snapshot_id, :event_id, :metadata_json
        )
        ''', data)
    return data


def list_moments(camera_id: str | None = None, from_ts: float | None = None, to_ts: float | None = None, limit: int = 50) -> list[dict]:
    clauses = []
    params = []
    if camera_id:
        clauses.append('camera_id=?')
        params.append(camera_id)
    if from_ts is not None:
        clauses.append('ts>=?')
        params.append(float(from_ts))
    if to_ts is not None:
        clauses.append('ts<=?')
        params.append(float(to_ts))
    where = ('WHERE ' + ' AND '.join(clauses)) if clauses else ''
    params.append(limit)
    with connection() as db:
        rows = db.execute(f'SELECT * FROM moments {where} ORDER BY ts DESC LIMIT ?', tuple(params)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d['metadata'] = json.loads(d.pop('metadata_json', '{}') or '{}')
        out.append(d)
    return out
