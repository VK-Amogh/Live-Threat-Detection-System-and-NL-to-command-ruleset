"""Disk-backed, at-least-once delivery of worker events and clip updates."""

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx

from td_contracts import CameraHealthEvent, RuleEvent


class RuleOutbox:
    def __init__(self, db_path: Path, api_url: str, token: str):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.stopped = threading.Event()
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS pending(
                id TEXT PRIMARY KEY, path TEXT NOT NULL, body TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0)""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue_event(self, event: RuleEvent):
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO pending(id,path,body) VALUES(?,?,?)",
                       (event.event_id, "/api/v1/internal/rule-events", event.model_dump_json()))

    def enqueue_clip(self, event_id: str):
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO pending(id,path,body) VALUES(?,?,?)",
                       (f"clip:{event_id}", f"/api/v1/internal/events/{event_id}/clip", "{}"))

    def enqueue_health(self, event: CameraHealthEvent):
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO pending(id,path,body) VALUES(?,?,?)",
                       (event.event_id, "/api/v1/internal/health-events", event.model_dump_json()))

    def pending_count(self) -> int:
        with self._db() as db:
            return db.execute("SELECT count(*) FROM pending").fetchone()[0]

    def flush_once(self, client: httpx.Client):
        with self._db() as db:
            row = db.execute("SELECT id,path,body,attempts FROM pending WHERE next_at<=? ORDER BY rowid LIMIT 1", (time.time(),)).fetchone()
        if row is None:
            return False
        ident, path, body, attempts = row
        headers = {"Authorization": f"Bearer {self.token}"}
        if not ident.startswith("clip:"):
            headers["Idempotency-Key"] = ident
        try:
            response = client.post(self.api_url + path, json=json.loads(body), headers=headers)
            response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            with self._db() as db:
                db.execute("UPDATE pending SET attempts=?,next_at=? WHERE id=?",
                           (attempts + 1, time.time() + min(30, 2 ** min(attempts, 5)), ident))
            return False
        with self._db() as db:
            db.execute("DELETE FROM pending WHERE id=?", (ident,))
        return True

    def run(self):
        with httpx.Client(timeout=10) as client:
            while not self.stopped.is_set():
                self.flush_once(client)
                self.stopped.wait(.5)
