"""Authenticated X Studio endpoints, mounted inside the existing Studio boundary."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

from fastapi import Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field

from .models import Model
from .x_content import CATEGORIES, ResearchInput, XSettings
from .x_studio import XStore


class Edit(Model):
    text: str = Field(min_length=1, max_length=1000)
    reviewed: bool = False


class Approval(Model):
    due: float | None = Field(default=None, ge=0)


class Schedule(Model):
    request: ResearchInput
    hours: int = Field(default=12, ge=3, le=168)
    enabled: bool = True


class Resolve(Model):
    post_url: str


def install_routes(app, cfg, store, owner, save_upload):
    db = XStore(store)
    app.state.x_store = db

    def media_path(job):
        media = job["result"].get("media") or {}
        folder = db.folder(media.get("library_id", job["id"]))
        path = folder / media.get("file", "missing")
        if not path.is_file() or path.is_symlink() or path.resolve().parent != folder.resolve():
            raise HTTPException(404, "Media not found")
        return path

    @app.get("/api/x")
    def overview():
        return {"categories": CATEGORIES, "settings": db.settings(owner).model_dump(), "jobs": db.recent(owner),
                "schedules": db.schedules(owner), "library": db.library(owner)}

    @app.put("/api/x/settings")
    def settings(body: XSettings):
        db.save_settings(owner, body)
        return body.model_dump()

    @app.post("/api/x/research")
    def start(body: ResearchInput):
        return db.create(owner, body)

    @app.put("/api/x/schedule")
    def schedule(body: Schedule):
        db.save_schedule(owner, body.request, body.hours, body.enabled)
        return {"ok": True}

    @app.put("/api/x/jobs/{identity}")
    def edit(identity: str, body: Edit):
        db.save_draft(identity, owner, body.text, body.reviewed)
        return db.get(identity, owner)

    @app.post("/api/x/jobs/{identity}/approve")
    def approve(identity: str, body: Approval):
        if body.due and body.due > time.time() + 72 * 3600:
            raise ValueError("Schedule at most 72 hours ahead; research freshness is checked again before posting")
        db.approve(identity, owner, body.due)
        return db.get(identity, owner)

    @app.post("/api/x/jobs/{identity}/reject")
    def reject(identity: str):
        db.reject(identity, owner)
        return {"ok": True}

    @app.post("/api/x/jobs/{identity}/resolve")
    def resolve(identity: str, body: Resolve):
        job = db.get(identity, owner)
        if job["state"] != "uncertain":
            raise ValueError("Only uncertain submissions can be reconciled")
        if not re.fullmatch(r"https://x\.com/" + re.escape(job["target"]) + r"/status/\d+", body.post_url, re.I):
            raise ValueError("Provide the actual post URL from the target account after inspecting X")
        db.update(identity, state="published", post_url=body.post_url, error="Manually reconciled by owner")
        return db.get(identity, owner)

    @app.get("/api/x/jobs/{identity}/media")
    def media(identity: str):
        return FileResponse(media_path(db.get(identity, owner)))

    @app.get("/api/x/library/{identity}/media")
    def library_media(identity: str):
        item = next((m for m in db.library(owner) if m["id"] == identity), None)
        if not item:
            raise HTTPException(404, "Media not found")
        return FileResponse(media_path({"id": identity, "result": {"media": item["metadata"]}}))

    @app.delete("/api/x/library/{identity}")
    def remove_library(identity: str):
        # Retain the immutable file for already approved jobs; remove only future library selection.
        with store.connect() as conn:
            conn.execute("DELETE FROM x_media WHERE id=? AND owner=?", (identity, owner))
        return {"ok": True}

    async def receive(file, identity, alt, rights):
        if not rights or not 5 <= len(alt.strip()) <= 500:
            raise ValueError("Confirm media rights and describe the real image/video in 5–500 characters")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".mp4"}:
            raise ValueError("Use a real JPG/PNG image (5 MB) or MP4 video (80 MB, 140 seconds maximum)")
        folder = db.folder(identity)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (uuid.uuid4().hex[:12] + suffix)
        await save_upload(file, path, (80 if suffix == ".mp4" else 5) * 1024**2)
        try:
            if suffix == ".mp4":
                from .media import dimensions
                from .process import run
                info = await asyncio.to_thread(dimensions, path)
                if not .5 <= info["duration"] <= 140 or max(info["width"], info["height"]) > 1920:
                    raise ValueError("Use an MP4 up to 140 seconds and 1920 pixels on the longest side")
                output = await run([cfg.ffmpeg(), "-hide_banner", "-nostdin", "-xerror", "-i", str(path), "-f", "null", "-"], timeout=180)
                if not re.search(r"Video: h264", output):
                    raise ValueError("Upload an H.264 MP4; CLIPER's clip exports use this format")
            else:
                from PIL import Image
                with Image.open(path) as image:
                    if image.width * image.height > 30_000_000 or min(image.size) < 200:
                        raise ValueError("Use an image at least 200 pixels wide/high and under 30 megapixels")
                    image.verify()
        except Exception:
            path.unlink(missing_ok=True)
            raise ValueError("Media validation failed. Use a decodable JPG/PNG or H.264 MP4 within the upload limits") from None
        return {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "kind": "video" if suffix == ".mp4" else "image",
                "license": "Owner-confirmed rights", "source_url": "", "creator": "Account owner", "alt": alt.strip(),
                "context": "Illustrative media", "reviewed": True}

    @app.post("/api/x/library")
    async def add_library(file: UploadFile, category: str = Form(...), alt: str = Form(...), rights: bool = Form(False)):
        if category not in CATEGORIES:
            raise ValueError("Choose one of the six X categories")
        identity = uuid.uuid4().hex[:12]
        media = await receive(file, identity, alt, rights)
        with store.connect() as conn:
            conn.execute("INSERT INTO x_media VALUES (?,?,?,?,?)", (identity, owner, category, json.dumps(media), time.time()))
        return {"id": identity, "metadata": media}

    @app.post("/api/x/jobs/{identity}/media")
    async def attach(identity: str, file: UploadFile, alt: str = Form(...), rights: bool = Form(False)):
        job = db.get(identity, owner)
        if job["state"] != "review":
            raise ValueError("Only drafts awaiting review can receive media")
        media = await receive(file, identity, alt, rights)
        with store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT result FROM x_jobs WHERE id=? AND owner=? AND state='review'", (identity, owner)).fetchone()
            if not current:
                raise ValueError("The draft changed while uploading; open it again")
            result = json.loads(current[0]) | {"media": media, "human_reviewed": False}
            result["text"] = re.sub(r"(?m)^Illustrative file photo$", "Illustrative media", result.get("text", ""))
            conn.execute("UPDATE x_jobs SET result=?,updated=? WHERE id=?", (json.dumps(result), time.time(), identity))
        return db.get(identity, owner)
