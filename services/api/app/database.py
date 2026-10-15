"""Durable local SQLite store. Every incident update has a monotonic change record."""
import json
import sqlite3
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


def head():
    with connection() as db:
        return db.execute('SELECT coalesce(max(seq),0) FROM changes').fetchone()[0]
