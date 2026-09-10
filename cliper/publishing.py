"""Durable approval/scheduling and official Instagram Graph API publishing."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .storage import Store


def asset_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def caption_text(caption: str, hashtags: list[str]) -> str:
    text = re.sub(r"#[\w]+", "", caption).strip()
    tags = list(dict.fromkeys(re.sub(r"\W", "", t) for t in hashtags))
    suffix = " ".join("#" + t for t in tags if t)[:500]
    suffix = " ".join(suffix.split()[:5])
    return (text[:max(0, 2198 - len(suffix))] + "\n\n" + suffix).strip()


class PublishStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS publications (
                    id TEXT PRIMARY KEY, owner INTEGER NOT NULL, chat INTEGER NOT NULL,
                    origin TEXT NOT NULL, feature TEXT NOT NULL, account TEXT NOT NULL,
                    state TEXT NOT NULL, due REAL NOT NULL, predecessor TEXT, gap REAL NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL, container TEXT, target_id TEXT, media_id TEXT,
                    error TEXT NOT NULL DEFAULT '', published_at REAL, created REAL NOT NULL,
                    UNIQUE(owner,origin));
                CREATE INDEX IF NOT EXISTS publish_due ON publications(state,due);
            ''')

    def add(self, owner, chat, origin, feature, account, paths, caption, hashtags, *, auto=False,
            predecessor=None, gap=0, due=None, niche=None, review_note=""):
        identity = uuid.uuid4().hex[:12]
        payload = json.dumps({"paths": [str(Path(p).resolve()) for p in paths],
                              "caption": caption_text(caption, hashtags), "automatic": auto, "niche": niche,
                              "review_note": review_note,
                              "asset_hashes": [asset_hash(p) if Path(p).is_file() else None for p in paths]})
        with self.store.connect() as db:
            db.execute("INSERT OR IGNORE INTO publications (id,owner,chat,origin,feature,account,state,due,"
                       "predecessor,gap,payload,created) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (identity, owner, chat, origin, feature, account, "queued" if auto else "approval",
                        due if due is not None else time.time(), predecessor, gap, payload, time.time()))
            row = db.execute("SELECT id FROM publications WHERE owner=? AND origin=?", (owner, origin)).fetchone()
        return self.get(row[0], owner)

    def get(self, identity, owner=None):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM publications WHERE id=?", (identity,)).fetchone()
        if row is None or (owner is not None and owner != row["owner"]):
            raise ValueError("Publication not found")
        return dict(row)

    def recent(self, owner):
        with self.store.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM publications WHERE owner=? ORDER BY created DESC LIMIT 20", (owner,))]

    def update(self, identity, **values):
        if not values.keys() <= {"state", "container", "target_id", "media_id", "error", "published_at", "payload"}:
            raise ValueError("Invalid publication update")
        with self.store.connect() as db:
            db.execute(f"UPDATE publications SET {','.join(k + '=?' for k in values)} WHERE id=?",
                       (*values.values(), identity))

    def decide(self, identity, owner, approved):
        post = self.get(identity, owner)
        payload = json.loads(post["payload"])
        payload["automatic"] = False
        with self.store.connect() as db:
            result = db.execute("UPDATE publications SET state=?,due=?,predecessor=CASE WHEN ? THEN NULL ELSE predecessor END,"
                                "gap=CASE WHEN ? THEN 0 ELSE gap END,error='',payload=? "
                                "WHERE id=? AND owner=? AND state IN ('approval','failed','queued')",
                                ("queued" if approved else "rejected", time.time(), approved, approved, json.dumps(payload), identity, owner))
            if not result.rowcount:
                raise ValueError("Already publishing/published, or outcome uncertain; inspect Instagram before retrying")

    def hold_auto(self, owner, feature):
        with self.store.connect() as db:
            db.execute("UPDATE publications SET state='approval' WHERE owner=? AND feature=? AND state='queued' "
                       "AND json_extract(payload,'$.automatic')=1",
                       (owner, feature))

    def claim(self):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM publications WHERE state='queued' AND due<=? ORDER BY due,created",
                              (time.time(),)).fetchall()
            for row in rows:
                if row["predecessor"]:
                    identity, visited, ready = row["predecessor"], {row["id"]}, False
                    while identity and identity not in visited:
                        visited.add(identity)
                        prev = db.execute("SELECT state,published_at,predecessor FROM publications WHERE id=?", (identity,)).fetchone()
                        if not prev:
                            break
                        if prev["state"] == "rejected":
                            identity = prev["predecessor"]
                            if not identity:
                                ready = True
                            continue
                        ready = (prev["state"] == "published" and prev["published_at"] is not None
                                 and prev["published_at"] + row["gap"] <= time.time())
                        break
                    if not ready:
                        continue
                db.execute("UPDATE publications SET state='preparing' WHERE id=?", (row["id"],))
                return dict(row) | {"state": "preparing"}
        return None

    def recover(self):
        with self.store.connect() as db:
            db.execute("UPDATE publications SET state='queued' WHERE state='preparing'")
            db.execute("UPDATE publications SET state='uncertain',error='Interrupted during publish; inspect Instagram' "
                       "WHERE state='publishing'")


def account_config(key: str, owner: int):
    path = Path(os.getenv("INSTAGRAM_ACCOUNTS_FILE", "config/instagram.json"))
    if not path.is_file():
        raise ValueError("Configure config/instagram.json and the referenced token in .env before publishing")
    account = json.loads(path.read_text("utf-8")).get(key)
    if not account or owner not in account.get("owners", []):
        raise ValueError(f"Instagram account '{key}' is not configured for this Telegram owner")
    if not re.fullmatch(r"\d+", str(account.get("ig_user_id", ""))):
        raise ValueError("Configure the numeric Instagram professional account ID")
    token = os.getenv(account.get("token_env", ""), "")
    if not token:
        raise ValueError("The Instagram token environment variable is empty")
    host = {"instagram": "graph.instagram.com", "facebook": "graph.facebook.com"}.get(account.get("login", "instagram"))
    version = os.getenv("INSTAGRAM_GRAPH_VERSION", "v23.0")
    if not host or not re.fullmatch(r"v\d+\.\d+", version):
        raise ValueError("Invalid Instagram API login type or graph version")
    return account, token, f"https://{host}/{version}"


def stage_assets(paths: list[str], identity: str, expected_hashes=None) -> list[str]:
    if not re.fullmatch(r"[0-9a-f]{12}", identity):
        raise ValueError("Invalid publication identity")
    base = os.getenv("PUBLIC_MEDIA_BASE_URL", "").rstrip("/")
    url = urlsplit(base)
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("Set PUBLIC_MEDIA_BASE_URL to your public HTTPS media directory")
    root = Path(os.getenv("PUBLIC_MEDIA_DIR", "data/public-media")).resolve()
    folder = root / identity
    folder.mkdir(parents=True, exist_ok=True)
    if folder.is_symlink() or folder.resolve().parent != root:
        raise ValueError("Publication directory must stay inside the media root")
    urls = []
    for n, name in enumerate(paths):
        path = Path(name)
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".jpg", ".jpeg"}:
            raise ValueError("Publication asset is missing or has an unsupported format")
        target = folder / f"{n + 1}{path.suffix.lower()}"
        current_hash = asset_hash(path)
        if expected_hashes and n < len(expected_hashes) and expected_hashes[n] and expected_hashes[n] != current_hash:
            raise ValueError("A publication asset changed after review; generate a new publication")
        if target.is_symlink() or target.exists() and asset_hash(target) != current_hash:
            raise ValueError("Staged media differs from the approved asset; refusing a stale publication")
        if not target.exists():
            temporary = target.with_suffix(target.suffix + ".tmp")
            shutil.copy2(path, temporary)
            temporary.replace(target)
        urls.append(f"{base}/{identity}/{target.name}")
    return urls


class InstagramPublisher:
    def __init__(self, store: PublishStore, client=None):
        self.store, self.client = store, client

    async def process(self, post):
        account, token, base = account_config(post["account"], post["owner"])
        target = str(account["ig_user_id"])
        if post["target_id"] and post["target_id"] != target:
            raise ValueError("Instagram account mapping changed after preparation; refusing to publish to a different account")
        self.store.update(post["id"], target_id=target)
        payload = json.loads(post["payload"])
        urls = await asyncio.to_thread(stage_assets, payload["paths"], post["id"], payload.get("asset_hashes"))
        client = self.client or httpx.AsyncClient(timeout=60, follow_redirects=False)

        async def request(method, path, **params):
            response = await client.request(method, base + "/" + path,
                                            headers={"Authorization": "Bearer " + token},
                                            **({"data": params} if method == "POST" else {"params": params}))
            try:
                value = response.json()
            except ValueError:
                raise ValueError("Instagram returned a non-JSON response") from None
            if response.is_error or "error" in value:
                code = value.get("error", {}).get("code", response.status_code)
                raise ValueError(f"Instagram API error {code}. Check permissions, token, account limits and public media URLs.")
            return value

        async def wait_ready(identity):
            for _ in range(60):
                value = await request("GET", identity, fields="status_code")
                if value.get("status_code") == "FINISHED":
                    return
                status = value.get("status_code")
                if status in {"ERROR", "EXPIRED"}:
                    payload.pop("children", None)
                    self.store.update(post["id"], container=None, payload=json.dumps(payload))
                    raise ValueError(f"Instagram container {status.lower()}; retry will prepare fresh media")
                if status == "PUBLISHED":
                    self.store.update(post["id"], state="uncertain",
                                      error="Instagram reports this container already published; inspect Instagram")
                    raise ValueError("Container already published; inspect Instagram before any further action")
                await asyncio.sleep(3)
            raise ValueError("Instagram media processing timed out")

        try:
            container = post["container"]
            if not container:
                if len(urls) == 1 and payload["paths"][0].lower().endswith(".mp4"):
                    result = await request("POST", target + "/media", media_type="REELS", video_url=urls[0],
                                           caption=payload["caption"], share_to_feed="true")
                else:
                    if not 4 <= len(urls) <= 7:
                        raise ValueError("A Feature 2 carousel needs 4–7 slides")
                    children = payload.get("children", [])
                    for url in urls[len(children):]:
                        child = await request("POST", target + "/media", image_url=url, is_carousel_item="true")
                        children.append(child["id"])
                        payload["children"] = children
                        self.store.update(post["id"], payload=json.dumps(payload))
                    for child in children:
                        await wait_ready(child)
                    result = await request("POST", target + "/media", media_type="CAROUSEL",
                                           children=",".join(children), caption=payload["caption"])
                container = result["id"]
                self.store.update(post["id"], container=container)
            await wait_ready(container)
            if payload.get("automatic"):
                current = self.store.store.prefs(post["owner"])
                allowed = (current.f1_enabled and current.auto_publish) if post["feature"] == "f1" else (
                    current.f2_enabled and current.f2_auto_publish and payload.get("niche") in current.enabled_niches)
                if not allowed:
                    self.store.update(post["id"], state="approval", error="Automatic publishing was paused before publish")
                    raise ValueError("Automatic publishing is paused; approve this item manually when ready")
            # Persist before the external side effect. An ambiguous outcome is never blindly resent.
            self.store.update(post["id"], state="publishing")
            try:
                published = await request("POST", target + "/media_publish", creation_id=container)
                if not published.get("id"):
                    raise ValueError("Publish response has no media ID")
            except BaseException:
                self.store.update(post["id"], state="uncertain", error="Publish outcome uncertain. Inspect Instagram; do not blindly retry.")
                raise
            self.store.update(post["id"], state="published", media_id=published["id"], published_at=time.time(), error="")
            return published["id"]
        finally:
            if self.client is None:
                await client.aclose()

    async def run(self, notify):
        self.store.recover()
        while True:
            post = self.store.claim()
            if not post:
                await asyncio.sleep(2)
                continue
            try:
                media_id = await self.process(post)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self.store.get(post["id"])["state"] not in {"uncertain", "approval"}:
                    self.store.update(post["id"], state="failed", error=str(exc)[:500] if isinstance(exc, ValueError)
                                      else "Instagram connection failed; inspect settings and retry")
                message = f"Instagram {post['id']}: {self.store.get(post['id'])['error']}"
            else:
                message = f"Published to Instagram · {post['id']} · media {media_id}"
            try:
                await notify(post, message)
            except Exception:
                pass  # Publication state must not depend on Telegram notification delivery.
