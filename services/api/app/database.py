"""Durable local SQLite store. Every incident update has a monotonic change record."""
import json
import sqlite3
import time
from contextlib import contextmanager
from .settings import DB_PATH


@contextmanager
def connection():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
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
        ''')


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
    with connection() as db:
        db.execute('''INSERT INTO rules(id,camera_id,text,spec_json,readback,readback_hash,can_activate,status,version,updated_at)
            VALUES(:id,:camera_id,:text,:spec_json,:readback,:readback_hash,:can_activate,:status,:version,:updated_at)
            ON CONFLICT(id) DO UPDATE SET spec_json=excluded.spec_json,readback=excluded.readback,
                readback_hash=excluded.readback_hash,can_activate=excluded.can_activate,
                status=excluded.status,version=excluded.version,updated_at=excluded.updated_at''', record)
    return record


def get_rule(ident):
    with connection() as db:
        row = db.execute('SELECT * FROM rules WHERE id=?', (ident,)).fetchone()
    return dict(row) if row else None


def list_rules(camera_id=None):
    with connection() as db:
        rows = db.execute('SELECT * FROM rules WHERE camera_id=? ORDER BY updated_at DESC', (camera_id,)).fetchall() if camera_id else db.execute('SELECT * FROM rules ORDER BY updated_at DESC').fetchall()
    return [dict(row) for row in rows]


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
