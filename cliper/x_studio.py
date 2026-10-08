"""Durable X research/review/schedule queue. Publishing uncertainty is never retried."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import sqlite3
import time
import uuid
from datetime import UTC, datetime

import httpx

from .browser_provider import BrowserBusyError
from .storage import Store
from .x_content import ResearchInput, XSettings, check_text, commons_image, research

log = logging.getLogger(__name__)


def fingerprint(text):
    normalized = re.sub(r"https?://\S+", "", text.lower())
    return hashlib.sha256(re.sub(r"\W+", "", normalized).encode()).hexdigest()


class XStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS x_settings (owner INTEGER PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS x_jobs (
                    id TEXT PRIMARY KEY, owner INTEGER NOT NULL, state TEXT NOT NULL,
                    request TEXT NOT NULL, result TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT '',
                    due REAL NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    fingerprint TEXT, target TEXT NOT NULL DEFAULT '', submitted REAL,
                    post_url TEXT NOT NULL DEFAULT '');
                CREATE UNIQUE INDEX IF NOT EXISTS x_deduplicate ON x_jobs(owner,fingerprint)
                    WHERE fingerprint IS NOT NULL AND state!='rejected';
                CREATE INDEX IF NOT EXISTS x_due ON x_jobs(state,due);
                CREATE TABLE IF NOT EXISTS x_schedules (
                    owner INTEGER NOT NULL, category TEXT NOT NULL, request TEXT NOT NULL,
                    hours INTEGER NOT NULL, enabled INTEGER NOT NULL, next_run REAL NOT NULL,
                    PRIMARY KEY(owner,category));
                CREATE TABLE IF NOT EXISTS x_media (
                    id TEXT PRIMARY KEY, owner INTEGER NOT NULL, category TEXT NOT NULL,
                    metadata TEXT NOT NULL, created REAL NOT NULL);
            """)

    def folder(self, identity):
        if not re.fullmatch(r"[a-f0-9]{12}", identity):
            raise ValueError("Invalid X job ID")
        return self.store.root / "x-studio" / identity

    def settings(self, owner):
        with self.store.connect() as db:
            row = db.execute("SELECT value FROM x_settings WHERE owner=?", (owner,)).fetchone()
        return XSettings.model_validate_json(row[0]) if row else XSettings()

    def save_settings(self, owner, settings):
        if settings.auto_publish and (not settings.handle or not settings.browser_risk_accepted):
            raise ValueError("Set your X username and acknowledge website automation before enabling automatic publishing")
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO x_settings VALUES (?,?)", (owner, settings.model_dump_json()))
            # Disabling auto holds existing automatic posts; account edits invalidate all queued approvals.
            for row in db.execute("SELECT id,result,target FROM x_jobs WHERE owner=? AND state='queued_publish'", (owner,)).fetchall():
                data = json.loads(row["result"])
                if row["target"].lower() != settings.handle.lower() or (data.get("automatic") and not settings.auto_publish):
                    db.execute("UPDATE x_jobs SET state='review',error='Publishing settings changed; review again' WHERE id=?", (row["id"],))

    @staticmethod
    def decode(row):
        return dict(row) | {"request": json.loads(row["request"]), "result": json.loads(row["result"])}

    def get(self, identity, owner):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM x_jobs WHERE id=? AND owner=?", (identity, owner)).fetchone()
        if not row:
            raise ValueError("X project not found")
        return self.decode(row)

    def recent(self, owner):
        with self.store.connect() as db:
            return [self.decode(r) for r in db.execute("SELECT * FROM x_jobs WHERE owner=? ORDER BY created DESC LIMIT 100", (owner,))]

    def create(self, owner, request: ResearchInput):
        identity, now = uuid.uuid4().hex[:12], time.time()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM x_jobs WHERE owner=? AND state IN ('queued','researching','review','queued_publish','preparing','publishing')", (owner,)).fetchone()[0] >= 20:
                raise ValueError("Review or reject existing X drafts before creating more (20 active maximum)")
            db.execute("INSERT INTO x_jobs (id,owner,state,request,due,created,updated) VALUES (?,?,'queued',?,?,?,?)",
                       (identity, owner, request.model_dump_json(), now, now, now))
        self.folder(identity).mkdir(parents=True, exist_ok=True)
        return self.get(identity, owner)

    def update(self, identity, **values):
        if not values.keys() <= {"state", "result", "error", "due", "fingerprint", "target", "submitted", "post_url"}:
            raise ValueError("Invalid X state update")
        if "result" in values:
            values["result"] = json.dumps(values["result"])
        values["updated"] = time.time()
        with self.store.connect() as db:
            db.execute(f"UPDATE x_jobs SET {','.join(k+'=?' for k in values)} WHERE id=? AND state!='rejected'", (*values.values(), identity))

    def save_draft(self, identity, owner, text, media_reviewed):
        check_text(text)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM x_jobs WHERE id=? AND owner=? AND state='review'", (identity, owner)).fetchone()
            if not row:
                raise ValueError("Only drafts awaiting review can be edited")
            result = json.loads(row["result"])
            result["text"] = text
            if result.get("media"):
                result["media"]["reviewed"] = media_reviewed
            result["human_reviewed"] = bool(media_reviewed)
            try:
                db.execute("UPDATE x_jobs SET result=?,fingerprint=?,updated=? WHERE id=?",
                           (json.dumps(result), fingerprint(text), time.time(), identity))
            except sqlite3.IntegrityError:
                raise ValueError("This post duplicates an existing X draft or publication") from None

    def ready(self, job, *, automatic=False):
        settings = self.settings(job["owner"])
        result = job["result"]
        if not settings.handle or not settings.browser_risk_accepted:
            raise ValueError("Configure the X account and acknowledge browser automation first")
        check_text(result.get("text", ""))
        if time.time() - result.get("researched_at", 0) > min(settings.freshness_hours, job["request"]["hours"]) * 3600:
            raise ValueError("Research is stale. Research a new post before publishing")
        event = datetime.fromisoformat(result["research"]["event_at"])
        if event.tzinfo is None or not -300 <= (datetime.now(UTC) - event).total_seconds() <= min(settings.freshness_hours, job["request"]["hours"]) * 3600:
            raise ValueError("The event is stale or has an invalid date. Research a new post before publishing")
        media = result.get("media")
        if not media or not media.get("reviewed"):
            raise ValueError("Attach a real image/video and confirm its rights, relevance and context")
        path = self.folder(media.get("library_id", job["id"])) / media["file"]
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != media["sha256"]:
            raise ValueError("Reviewed media changed or is missing; attach and review it again")
        if automatic and (not settings.auto_publish or result.get("flags")):
            raise ValueError("This draft needs editorial review")
        if not automatic and not result.get("human_reviewed"):
            raise ValueError("Confirm that you reviewed the sources, claims and media")
        return path

    def approve(self, identity, owner, due=None, *, automatic=False):
        job = self.get(identity, owner)
        self.ready(job, automatic=automatic)
        settings = self.settings(owner)
        result = job["result"] | {"automatic": automatic}
        with self.store.connect() as db:
            changed = db.execute("UPDATE x_jobs SET state='queued_publish',result=?,due=?,target=?,updated=? WHERE id=? AND owner=? AND state='review' AND updated=?",
                (json.dumps(result), due or time.time(), settings.handle, time.time(), identity, owner, job["updated"])).rowcount
        if not changed:
            raise ValueError("This post is not awaiting approval")

    def reject(self, identity, owner):
        with self.store.connect() as db:
            if not db.execute("UPDATE x_jobs SET state='rejected',updated=? WHERE id=? AND owner=? AND state IN ('queued','review','queued_publish','failed')",
                              (time.time(), identity, owner)).rowcount:
                raise ValueError("An active or uncertain submission cannot be discarded; inspect X first")

    def recover(self):
        with self.store.connect() as db:
            db.execute("UPDATE x_jobs SET state='queued' WHERE state='researching'")
            db.execute("UPDATE x_jobs SET state='review',error='Preparation interrupted; review again' WHERE state='preparing'")
            db.execute("UPDATE x_jobs SET state='uncertain',error='Submission interrupted. Inspect X; no automatic retry.' WHERE state='publishing'")

    def claim(self):
        now = time.time()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in db.execute("SELECT * FROM x_jobs WHERE state IN ('queued','queued_publish') AND due<=? ORDER BY due", (now,)).fetchall():
                settings_row = db.execute("SELECT value FROM x_settings WHERE owner=?", (row["owner"],)).fetchone()
                settings = XSettings.model_validate_json(settings_row[0]) if settings_row else XSettings()
                if not settings.enabled:
                    continue
                if row["state"] == "queued_publish":
                    submitted = db.execute("SELECT count(*),max(submitted) FROM x_jobs WHERE owner=? AND submitted>?", (row["owner"], now - 86400)).fetchone()
                    if submitted[0] >= settings.daily_limit or (submitted[1] and now - submitted[1] < settings.gap_minutes * 60):
                        continue
                    state = "preparing"
                else:
                    state = "researching"
                db.execute("UPDATE x_jobs SET state=?,updated=? WHERE id=?", (state, now, row["id"]))
                return self.decode(row) | {"state": state}
        return None

    def library(self, owner):
        with self.store.connect() as db:
            return [dict(r) | {"metadata": json.loads(r["metadata"])} for r in db.execute("SELECT * FROM x_media WHERE owner=? ORDER BY created DESC", (owner,))]

    def schedules(self, owner):
        with self.store.connect() as db:
            return [dict(r) | {"request": json.loads(r["request"])} for r in db.execute("SELECT * FROM x_schedules WHERE owner=?", (owner,))]

    def save_schedule(self, owner, request, hours, enabled):
        if not 3 <= hours <= 168:
            raise ValueError("Research cadence must be 3–168 hours")
        with self.store.connect() as db:
            db.execute("INSERT INTO x_schedules VALUES (?,?,?,?,?,?) ON CONFLICT(owner,category) DO UPDATE SET request=excluded.request,hours=excluded.hours,enabled=excluded.enabled,next_run=excluded.next_run",
                       (owner, request.category, request.model_dump_json(), hours, int(enabled), time.time() + hours * 3600))

    def schedule_tick(self):
        # Called by the single X worker under the existing shared engine lock.
        with self.store.connect() as db:
            rows = db.execute("SELECT * FROM x_schedules WHERE enabled=1 AND next_run<=?", (time.time(),)).fetchall()
        for row in rows:
            if not self.settings(row["owner"]).enabled:
                continue
            try:
                self.create(row["owner"], ResearchInput.model_validate_json(row["request"]))
            except ValueError:
                pass
            with self.store.connect() as db:
                db.execute("UPDATE x_schedules SET next_run=? WHERE owner=? AND category=?", (time.time() + row["hours"] * 3600, row["owner"], row["category"]))


class XWorker:
    def __init__(self, cfg, store):
        self.cfg, self.db = cfg, XStore(store)

    async def process(self, job):
        identity, owner = job["id"], job["owner"]
        if job["state"] == "researching":
            previous = self.db.recent(owner)
            library = [m for m in self.db.library(owner) if m["category"] == job["request"]["category"]]
            result = await research(self.cfg, ResearchInput.model_validate(job["request"]),
                                    [j["result"].get("research", {}).get("topic", "") for j in previous],
                                    library[0]["metadata"]["alt"] if library else None)
            prior_sources = {s["url"] for j in previous if j["id"] != identity and j["state"] != "rejected"
                             for s in j["result"].get("research", {}).get("sources", []) if s.get("primary")}
            if any(s["url"] in prior_sources for s in result["research"]["sources"] if s["primary"]):
                raise ValueError("This primary source story was already covered; try a different angle or keyword")
            if library:
                result["media"] = library[0]["metadata"] | {"library_id": library[0]["id"]}
            else:
                try:
                    result["media"] = await commons_image(result["research"]["media_query"], self.db.folder(identity))
                except (httpx.HTTPError, ValueError, OSError):
                    result["flags"].append("Automatic photo retrieval unavailable; attach an owned image/video")
            if result.get("media") and result["media"].get("context"):
                result["text"] += "\n" + result["media"]["context"]
            try:
                check_text(result["text"])
            except ValueError as exc:
                result["flags"].append(str(exc))
            self.db.update(identity, state="review", result=result, fingerprint=fingerprint(result["text"]), error="")
            if self.db.settings(owner).auto_publish:
                try:
                    self.db.approve(identity, owner, automatic=True)
                except ValueError:
                    pass
        else:
            from .x_browser import XBrowser
            settings = self.db.settings(owner)
            path = self.db.ready(job, automatic=job["result"].get("automatic", False))
            if settings.handle.lower() != job["target"].lower():
                raise ValueError("The configured X account changed; review again")

            def submitting():
                current = self.db.settings(owner)
                if not current.enabled or not current.browser_risk_accepted or current.handle.lower() != job["target"].lower():
                    raise ValueError("X account settings changed during preparation; nothing submitted")
                self.db.ready(self.db.get(identity, owner), automatic=job["result"].get("automatic", False))
                self.db.update(identity, state="publishing", submitted=time.time())

            async with XBrowser(self.cfg) as browser:
                url = await browser.publish(job["target"], job["result"]["text"], path,
                                            job["result"]["media"].get("alt", ""), submitting)
            self.db.update(identity, state="published", post_url=url, error="")

    async def run(self):
        self.db.recover()
        while True:
            job = None
            try:
                self.db.schedule_tick()
                job = self.db.claim()
                if job:
                    await self.process(job)
                else:
                    await asyncio.sleep(3)
            except asyncio.CancelledError:
                raise
            except BrowserBusyError:
                self.db.update(job["id"], state="queued" if job["state"] == "researching" else "queued_publish", due=time.time() + 30)
                await asyncio.sleep(3)
            except Exception as exc:
                if job:
                    state = self.db.get(job["id"], job["owner"])["state"]
                    # Never expose Playwright call logs, source prompts or credentials through the queue.
                    message = str(exc)[:500] if isinstance(exc, ValueError) else "Research/browser step failed. Check the shared browser session and retry research; inspect X before resubmission."
                    self.db.update(job["id"], state="uncertain" if state == "publishing" else "failed", error=message)
                else:
                    log.warning("X scheduler paused after a storage error")
                await asyncio.sleep(3)
