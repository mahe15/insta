from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .models import Preferences

TERMINAL = {"complete", "failed", "cancelled"}


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "jobs.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner INTEGER NOT NULL, chat INTEGER NOT NULL,
                    source TEXT NOT NULL, state TEXT NOT NULL, stage TEXT NOT NULL,
                    prefs TEXT NOT NULL, selected TEXT NOT NULL DEFAULT '[]',
                    delivered TEXT NOT NULL DEFAULT '[]', error TEXT NOT NULL DEFAULT '',
                    created REAL NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (owner INTEGER PRIMARY KEY, prefs TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def directory(self, job_id: str) -> Path:
        if len(job_id) != 12 or any(c not in "0123456789abcdef" for c in job_id):
            raise ValueError("Invalid job ID")
        return self.root / "jobs" / job_id

    def create(self, owner: int, chat: int, source: str, prefs: Preferences, limit: int = 3,
               state: str = "queued_analysis") -> dict:
        job_id = uuid.uuid4().hex[:12]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','failed','cancelled')")
            if count.fetchone()[0] >= limit:
                raise ValueError("The queue is full. Finish or cancel an existing job first.")
            now = time.time()
            db.execute("INSERT INTO jobs (id,owner,chat,source,state,stage,prefs,created,updated) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (job_id, owner, chat, source, state,
                                                     "Waiting in queue", prefs.model_dump_json(), now, now))
        self.directory(job_id).mkdir(parents=True)
        return self.get(job_id)

    def get(self, job_id: str, owner: int | None = None) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or (owner is not None and row["owner"] != owner):
            raise ValueError("Job not found")
        return dict(row)

    def update(self, job_id: str, **values):
        if not values.keys() <= {"state", "stage", "selected", "delivered", "error", "source"}:
            raise ValueError("Invalid update")
        values["updated"] = time.time()
        with self.connect() as db:
            # Cancellation wins races with running workers.
            db.execute(f"UPDATE jobs SET {','.join(f'{k}=?' for k in values)} "
                       "WHERE id=? AND state != 'cancelled'", (*values.values(), job_id))

    def recent(self, owner: int) -> list[dict]:
        with self.connect() as db:
            return [dict(x) for x in db.execute(
                "SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 10", (owner,))]

    def claim(self) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE state IN ('queued_analysis','queued_render') "
                             "ORDER BY updated LIMIT 1").fetchone()
            if not row:
                return None
            state = "analyzing" if row["state"] == "queued_analysis" else "rendering"
            db.execute("UPDATE jobs SET state=?,updated=? WHERE id=?", (state, time.time(), row["id"]))
            return dict(row) | {"state": state}

    def select(self, job_id: str, owner: int, ids: list[int]):
        self.get(job_id, owner)
        with self.connect() as db:
            result = db.execute("UPDATE jobs SET selected=?,state='queued_render',stage='Waiting to render',"
                                "updated=? WHERE id=? AND state='awaiting_selection'",
                                (json.dumps(ids), time.time(), job_id))
            if not result.rowcount:
                raise ValueError("This job is not awaiting selection. Use /status to see its state.")

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state='queued_analysis',stage='Resuming analysis' WHERE state='analyzing'")
            db.execute("UPDATE jobs SET state='queued_render',stage='Resuming render' WHERE state='rendering'")
            db.execute("UPDATE jobs SET state='failed',error='Upload interrupted; please send it again' "
                       "WHERE state='uploading'")

    def update_job_prefs(self, job_id: str, owner: int, prefs: Preferences):
        self.get(job_id, owner)
        with self.connect() as db:
            db.execute("UPDATE jobs SET prefs=?, updated=? WHERE id=?",
                       (prefs.model_dump_json(), time.time(), job_id))

    def retry(self, job_id: str, owner: int, limit: int, prefs: Preferences | None = None):
        self.get(job_id, owner)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None or job["state"] != "failed":
                raise ValueError("Only failed jobs can be retried. Submit a new job to re-edit completed clips.")
            active = db.execute("SELECT count(*) FROM jobs WHERE state NOT IN ('complete','failed','cancelled')").fetchone()[0]
            if active >= limit:
                raise ValueError("The queue is full. Finish or cancel another job before retrying.")
            if job["source"] == "telegram-upload":
                raise ValueError("The upload was interrupted. Please send the video again.")
            has_analysis = (self.directory(job_id) / "analysis.json").exists()
            state = "queued_render" if has_analysis and json.loads(job["selected"]) else "queued_analysis"
            new_prefs = prefs.model_dump_json() if prefs else job["prefs"]
            db.execute("UPDATE jobs SET state=?,stage='Queued for retry',error='',prefs=?,updated=? WHERE id=?",
                       (state, new_prefs, time.time(), job_id))

    def prefs(self, owner: int) -> Preferences:
        with self.connect() as db:
            row = db.execute("SELECT prefs FROM settings WHERE owner=?", (owner,)).fetchone()
        return Preferences.model_validate_json(row[0]) if row else Preferences()

    def save_prefs(self, owner: int, prefs: Preferences):
        with self.connect() as db:
            db.execute("INSERT INTO settings VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET prefs=excluded.prefs",
                       (owner, prefs.model_dump_json()))


def write_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
