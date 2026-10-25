"""Authenticated loopback control plane for the existing CLIPER engine."""
from __future__ import annotations

import asyncio
import hashlib
import httpx
import ipaddress
import json
import os
import re
import secrets
import shutil
import logging
import socket
import time
from contextlib import asynccontextmanager

log = logging.getLogger("cliper.web")
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field, ValidationError

from .config import PROVIDERS, Config
from .controls import NICHES
from .faceless import FacelessStore
from .maintenance import export_metadata
from .media import validate_url
from .models import Analysis, Model, Preferences, Transcript
from .music import CATEGORIES, get_categories, resolve_category_folder, resolve_track
from .pipeline import safe_error
from .platforms import PLATFORMS
from .publishing import PublishStore
from .storage import Store, write_json
from .web_runtime import WebRuntime

ROOT = Path(__file__).resolve().parent.parent
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


class NewJob(Model):
    source: str = Field(min_length=8, max_length=4000)
    preferences: dict = Field(default_factory=dict)


class ClipEdit(Model):
    title: str = Field(min_length=1, max_length=90)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    caption: str = Field(default="", max_length=1800)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    music_category: str


class Selection(Model):
    ids: list[int] = Field(min_length=1, max_length=10)


class Generate(Model):
    niche: str
    count: int = Field(default=1, ge=1, le=20)
    prompt: str = Field(default="", max_length=4000)


class PromptUpdate(Model):
    value: str = Field(min_length=1, max_length=15000)


class BatchPromptUpdate(Model):
    prompts: dict[str, str]



class Schedule(Model):
    hours: int = 24
    daily_time: str | None = None
    zone: str = "Asia/Kolkata"
    enabled: bool = True
    weekdays: list[int] = Field(default_factory=list, max_length=7)


class PostEdit(Model):
    caption: str = Field(max_length=2200)
    due: float | None = Field(default=None, ge=0)


class ClipPublish(Model):
    platform: str = "youtube"
    account: str = "main"
    title: str = Field(default="", max_length=100)
    caption: str = Field(default="", max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=15)
    privacy: str = "public"
    publish_now: bool = True


class ScheduleAllClips(Model):
    platform: str = "youtube"
    account: str = "main"
    gap_hours: float = Field(default=2.0, ge=0.05, le=168.0)
    start_time: float | None = None
    publish_first_now: bool = True
    privacy: str = "public"
    clip_ids: list[int] | None = None
    schedule_on_youtube: bool = True


def read_json(path, default=None):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def is_allowed_host(host: str | None, custom_allowed: set[str] | None = None) -> bool:
    if not host:
        return False
    host_lower = host.lower()
    if custom_allowed and host_lower in custom_allowed:
        return True
    if host_lower in {"localhost", "testserver"} or host_lower == socket.gethostname().lower() or host_lower.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback or ip.is_private
    except ValueError:
        return False


def contained(path, root):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or path.is_symlink():
        raise HTTPException(404, "Asset not found")
    if not resolved.is_file():
        raise HTTPException(404, "Asset not found")
    return resolved


def create_app(cfg: Config | None = None, *, start_engine=True, token=None, project_root=None, static_root=None, allowed_hosts=None):
    cfg = cfg or Config.load()
    root = Path(project_root or ROOT)
    store = Store(cfg.data_dir)
    publications, carousels = PublishStore(store), FacelessStore(store)
    runtime = WebRuntime(cfg, store)
    owner = min(cfg.owners) if cfg.owners else 0
    allowed = cfg.owners | {0}
    key_path = cfg.data_dir / "web" / "access-key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if token is None:
        if not key_path.exists():
            key_path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        token = key_path.read_text("utf-8").strip()
    sessions = {}
    thumbnail_slots = asyncio.Semaphore(2)

    @asynccontextmanager
    async def lifespan(app):
        if start_engine:
            await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(title="CLIPER Studio", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.runtime = store, runtime
    app.state.launch_token = token

    @app.middleware("http")
    async def boundary(request, call_next):
        host = urlsplit("http://" + request.headers.get("host", "")).hostname
        if not is_allowed_host(host, allowed_hosts):
            return JSONResponse({"detail": "Use the local Studio address"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "Cross-origin requests are not accepted"}, status_code=403)
        if request.url.path.startswith("/api/"):
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
            x_upload = request.method == "POST" and bool(re.fullmatch(r"/api/x/(library|jobs/[a-f0-9]{12}/media)", request.url.path))
            is_upload = "/upload" in request.url.path or x_upload
            limit = (81 * 1024**2 if x_upload else cfg.max_download_mb * 1024**2 + 1024**2) if is_upload else 1024**2
            try:
                length = int(request.headers.get("content-length", 0))
            except ValueError:
                return JSONResponse({"detail": "Invalid content length"}, status_code=400)
            if length > limit:
                return JSONResponse({"detail": "Upload exceeds the configured size limit"}, status_code=413)
            if is_upload and request.method == "POST" and not length:
                return JSONResponse({"detail": "Upload requires Content-Length"}, status_code=411)
            if not (request.url.path == "/api/session" and request.method == "POST"):
                session = sessions.get(request.cookies.get("cliper_session"))
                if not session or session["expires"] < time.time():
                    return JSONResponse({"detail": "Open Studio from its launcher or enter your local access key"}, status_code=401)
                request.state.session = session
                if request.method not in {"GET", "HEAD"} and not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session["csrf"]):
                    return JSONResponse({"detail": "Session changed. Refresh Studio and retry."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        message = "Invalid settings: " + "; ".join(str(e["msg"]) for e in exc.errors()[:4]) if isinstance(exc, ValidationError) else safe_error(exc, cfg)
        return JSONResponse({"detail": message}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": "; ".join(f"{'.'.join(map(str, e['loc'][1:]))}: {e['msg']}" for e in exc.errors()[:4])}, status_code=422)

    @app.post("/api/session")
    async def login(request: Request):
        body = await request.json()
        supplied = body.get("key", "") if isinstance(body, dict) else ""
        active_token = token
        if key_path.exists():
            try:
                active_token = key_path.read_text("utf-8").strip()
            except OSError:
                active_token = token
        if not isinstance(supplied, str) or not secrets.compare_digest(supplied, active_token or ""):
            raise HTTPException(401, "That access key is not valid")
        identity, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        expired = [k for k, v in sessions.items() if v["expires"] < time.time()]
        for old in expired:
            sessions.pop(old, None)
        if len(sessions) >= 100:
            sessions.pop(next(iter(sessions)))
        sessions[identity] = {"csrf": csrf, "expires": time.time() + 86400}
        response = JSONResponse({"csrf": csrf})
        response.set_cookie("cliper_session", identity, httponly=True, samesite="lax", max_age=86400)
        return response

    @app.delete("/api/session")
    async def logout(request: Request):
        sessions.pop(request.cookies.get("cliper_session"), None)
        response = JSONResponse({"ok": True})
        response.delete_cookie("cliper_session")
        return response

    def owned(identity, kind="job"):
        getter = {"job": store.get, "carousel": carousels.get, "post": publications.get}[kind]
        row = getter(identity)
        if row["owner"] not in allowed:
            raise HTTPException(404, "Item not found")
        return row

    def rows(table, count=250):
        assert table in {"jobs", "publications", "faceless_jobs", "content_schedules"}
        with store.connect() as db:
            return [dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE owner IN ({','.join('?' for _ in allowed)}) "
                    + ("ORDER BY created DESC " if table != "content_schedules" else "") + "LIMIT ?", (*sorted(allowed), count))]

    def job_data(job):
        directory = store.directory(job["id"])
        analysis = read_json(directory / "analysis.json", {})
        source = read_json(directory / "source.json", {})
        clips = analysis.get("clips", [])
        cover = next(iter(sorted((directory / "clips").glob("*.cover.jpg"))), None)
        video_exists = any((directory / "clips").glob("*.mp4"))
        source_url = urlsplit(job["source"])
        fallback_title = ((source_url.hostname or "Video") + " · " + (source_url.path.rstrip("/").split("/")[-1] or "Source")) if source_url.scheme == "https" else Path(job["source"]).name
        return {k: job[k] for k in ("id", "state", "stage", "created", "updated", "source", "owner", "chat")} | {
            "title": source.get("media", {}).get("title") or analysis.get("title") or fallback_title,
            "error": safe_error(Exception(job["error"]), cfg) if job["error"] else "", "clip_count": len(clips),
            "rendered": len(list((directory / "clips").glob("*.mp4"))),
            "duration": analysis.get("duration") or source.get("media", {}).get("duration"),
            "cover": f"/api/jobs/{job['id']}/files/{cover.name}" if cover else f"/api/jobs/{job['id']}/thumbnail" if video_exists else None,
            "editorial_profile": json.loads(job["prefs"]).get("editorial_profile", "standard"),
            "coverage": analysis.get("coverage", {}), "provider": json.loads(job["prefs"]).get("ai_provider") or cfg.provider}

    def status():
        disk = shutil.disk_usage(cfg.data_dir)
        return {"engine": runtime.status(), "device": cfg.whisper_device, "encoder": cfg.video_encoder,
                "whisper_model": cfg.whisper_model, "compute_type": cfg.whisper_compute,
                "free_gb": round(disk.free / 1024**3, 1), "total_gb": round(disk.total / 1024**3, 1),
                "face_model": cfg.face_model_path.is_file(), "max_source_minutes": cfg.max_source_minutes,
                "long_source_minutes": cfg.long_source_minutes, "max_active_jobs": cfg.max_active_jobs,
                "max_download_mb": cfg.max_download_mb, "scan_download_workers": cfg.scan_download_workers,
                "retention_days": cfg.retention_days, "browser_profile": "Shared project Chromium"}

    @app.get("/api/bootstrap")
    def bootstrap(request: Request):
        return {"csrf": request.state.session["csrf"], "owner": owner, "default_provider": cfg.provider, "preferences": store.prefs(owner).model_dump(),
                "schema": Preferences.model_json_schema(), "platforms": PLATFORMS, "niches": NICHES,
                "providers": [{"id": p, "model": cfg.ai(p).model, "configured": p in {"chatgpt_browser", "heuristic"} or bool(cfg.ai(p).key)} for p in PROVIDERS],
                "system": status()}

    @app.get("/api/status")
    def system_status():
        return status()

    @app.post("/api/engine/{action}")
    async def engine(action: str):
        if action == "start":
            await runtime.start()
        elif action == "stop":
            if runtime.mode == "attached":
                raise ValueError("The Telegram worker owns the engine. Pause the feature switches or stop its terminal.")
            await runtime.stop()
        else:
            raise ValueError("Unknown engine action")
        return runtime.status()

    @app.put("/api/preferences")
    def preferences(body: dict):
        current = store.prefs(owner)
        updated = Preferences.model_validate(current.model_dump() | body)
        if updated.selected_niche not in NICHES or not set(updated.enabled_niches) <= NICHES.keys():
            raise ValueError("Unknown niche")
        if current.auto_publish and not updated.auto_publish:
            publications.hold_auto(owner, "f1")
        if current.f2_auto_publish and not updated.f2_auto_publish:
            publications.hold_auto(owner, "f2")
        store.save_prefs(owner, updated)
        return updated.model_dump()

    @app.get("/api/jobs")
    def jobs():
        return [job_data(j) for j in rows("jobs")]

    def create_job(source, overrides):
        prefs = Preferences.model_validate(store.prefs(owner).model_dump() | overrides)
        if not prefs.f1_enabled:
            raise ValueError("Enable clipping in Settings before creating a project")
        if prefs.clipping_mode == "audio_first":
            cfg.check_ai(prefs.ai_provider, prefs.ai_model)
        cfg.check_disk()
        if prefs.clipping_mode == "gemini_browser":
            from .gemini_clipping import youtube_url
            source = youtube_url(source)
        else:
            validate_url(source, cfg)
        return store.create(owner, 0, source, cfg.snapshot_ai(prefs), cfg.max_active_jobs)

    @app.post("/api/jobs", status_code=201)
    def new_job(body: NewJob):
        return job_data(create_job(body.source.strip(), body.preferences))

    @app.post("/api/speed/jobs", status_code=201)
    def new_speed_job(body: NewJob):
        from .gemini_clipping import youtube_url
        from .speed_profile import preset
        prefs = preset(store.prefs(owner), **body.preferences)
        if prefs.editorial_profile != "ishowspeed":
            raise ValueError("Use the normal project endpoint for other editorial profiles")
        return job_data(create_job(youtube_url(body.source.strip()), prefs.model_dump()))

    @app.get("/api/speed/sounds")
    def speed_sounds():
        from .speed_edit import ASSETS
        manifest = read_json(ASSETS / "manifest.json", {})
        return {"license": manifest.get("license"), "creator": manifest.get("creator"),
                "files": [{"name": name, "url": f"/api/speed/sounds/{name}"} for name in manifest.get("files", {})]}

    @app.get("/api/speed/sounds/{name}")
    def speed_sound(name: str):
        from .speed_edit import ASSETS
        if name not in {"reaction.wav", "reveal.wav", "transition.wav"}:
            raise HTTPException(404, "Sound not found")
        return FileResponse(ASSETS / name)

    async def save_upload(file, target, max_bytes):
        total = 0
        partial = target.with_suffix(target.suffix + ".upload")
        try:
            with partial.open("wb") as stream:
                while chunk := await file.read(1024**2):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(413, "File exceeds the upload limit")
                    cfg.check_disk()
                    stream.write(chunk)
            if not total:
                raise ValueError("The uploaded file is empty")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
            await file.close()

    @app.post("/api/jobs/upload", status_code=201)
    async def upload_video(file: UploadFile, preferences: str = Form("{}")):
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
            raise ValueError("Upload MP4, MOV, MKV or WebM video")
        try:
            overrides = json.loads(preferences)
        except ValueError:
            raise ValueError("Upload preferences must be valid JSON")
        if not isinstance(overrides, dict):
            raise ValueError("Upload preferences must be an object")
        prefs = Preferences.model_validate(store.prefs(owner).model_dump() | overrides | {"clipping_mode": "audio_first"})
        if not prefs.f1_enabled:
            raise ValueError("Enable clipping first")
        cfg.check_ai(prefs.ai_provider, prefs.ai_model)
        job = store.create(owner, 0, "web-upload", cfg.snapshot_ai(prefs), cfg.max_active_jobs, state="uploading")
        target = store.directory(job["id"]) / ("uploaded-source" + suffix)
        try:
            await save_upload(file, target, cfg.max_download_mb * 1024**2)
            store.update(job["id"], source=str(target.resolve()), state="queued_analysis", stage="Waiting in queue")
        except BaseException:
            store.update(job["id"], state="failed", error="Upload did not complete; upload the file again")
            raise
        return job_data(store.get(job["id"]))

    @app.get("/api/jobs/{identity}")
    def job_detail(identity: str):
        job = owned(identity)
        directory = store.directory(identity)
        analysis = read_json(directory / "analysis.json")
        if analysis:
            pubs_by_clip = {}
            try:
                with store.connect() as db:
                    pub_rows = db.execute(
                        "SELECT id, origin, feature, account, state, platform, media_id, error, published_at, due, gap, created "
                        "FROM publications WHERE origin LIKE ? ORDER BY created DESC",
                        (f"{identity}:%",)
                    ).fetchall()
                for prow in pub_rows:
                    parts = prow["origin"].split(":")
                    if len(parts) >= 2 and parts[1].isdigit():
                        cid = int(parts[1])
                        pubs_by_clip.setdefault(cid, []).append(dict(prow))
            except Exception:
                pass

            for clip in analysis["clips"]:
                from .project_rules import description
                clip["caption"], clip["hashtags"] = description(clip.get("caption") or clip["title"],
                    clip.get("hashtags", []), Preferences.model_validate_json(job["prefs"]))
                stem = f"clip_{clip['id']:02}"
                clip["video"] = f"/api/jobs/{identity}/files/{stem}.mp4" if (directory / "clips" / f"{stem}.mp4").is_file() else None
                clip["cover"] = f"/api/jobs/{identity}/files/{stem}.cover.jpg" if (directory / "clips" / f"{stem}.cover.jpg").is_file() else None
                clip["qa"] = read_json(directory / "clips" / f"{stem}.json", {}).get("quality")
                clip["publications"] = pubs_by_clip.get(clip["id"], [])
        return job_data(job) | {"analysis": analysis, "preferences": Preferences.model_validate_json(job["prefs"]).model_dump(), "selected": json.loads(job["selected"])}

    @app.get("/api/jobs/{identity}/transcript")
    def transcript(identity: str, q: str = "", offset: int = 0):
        owned(identity)
        data = read_json(store.directory(identity) / "transcript.json", {"segments": []})
        segments = [s for s in data["segments"] if not q or q.casefold() in s["text"].casefold()]
        return {"segments": segments[max(0, offset):max(0, offset) + 200], "total": len(segments)}

    @app.post("/api/jobs/{identity}/actions/{action}")
    def job_action(identity: str, action: str):
        job = owned(identity)
        if action == "cancel":
            with store.connect() as db:
                db.execute("UPDATE jobs SET state='cancelled',stage='Cancelled from Studio',updated=? WHERE id=? AND state NOT IN ('complete','cancelled')", (time.time(), identity))
        elif action == "retry":
            if job["source"] == "web-upload":
                raise ValueError("Upload the video again")
            store.retry(identity, job["owner"], cfg.max_active_jobs)
        elif action == "duplicate":
            source = job["source"]
            previous = Preferences.model_validate_json(job["prefs"])
            prefs = cfg.snapshot_ai(previous if previous.editorial_profile == "ishowspeed" else store.prefs(owner))
            prefs = prefs.model_copy(update={key: getattr(previous, key) for key in
                ("project_rules", "description_suffix", "overlay_text")})
            if not source.startswith("https://") and not Path(source).is_file():
                raise ValueError("The original file is no longer available")
            duplicate = store.create(owner, 0, source, prefs, cfg.max_active_jobs)
            return job_data(duplicate)
        else:
            raise ValueError("Unknown job action")
        return job_data(store.get(identity))

    @app.post("/api/jobs/{identity}/render")
    def render(identity: str, body: Selection):
        job = owned(identity)
        analysis = Analysis.model_validate_json((store.directory(identity) / "analysis.json").read_text("utf-8"))
        if not set(body.ids) <= {c.id for c in analysis.clips} or len(set(body.ids)) != len(body.ids):
            raise ValueError("Choose valid, distinct clips")
        store.select(identity, job["owner"], body.ids)
        return {"ok": True}

    @app.put("/api/jobs/{identity}/clips/{clip_id}")
    def edit_clip(identity: str, clip_id: int, body: ClipEdit):
        job = owned(identity)
        if job["state"] != "awaiting_selection":
            raise ValueError("Only clips awaiting selection can be edited. Duplicate a finished project to re-edit it.")
        directory = store.directory(identity)
        analysis = Analysis.model_validate_json((directory / "analysis.json").read_text("utf-8"))
        prefs = Preferences.model_validate_json(job["prefs"])
        if not prefs.min_seconds <= body.end - body.start <= prefs.max_seconds or body.end > analysis.duration:
            raise ValueError(f"Choose a complete interval within the source, {prefs.min_seconds}–{prefs.max_seconds} seconds long")
        ranges = analysis.coverage.get("ranges", [])
        if ranges and not any(body.start >= r["start"] and body.end <= r["end"] for r in ranges):
            raise ValueError("Keep edits inside one analyzed range")
        if not resolve_category_folder(cfg.music_dir, body.music_category):
            raise ValueError("Unknown music category")
        clip = next((c for c in analysis.clips if c.id == clip_id), None)
        if not clip:
            raise ValueError("Clip not found")
        data = body.model_dump()
        transcript_data = Transcript.model_validate_json((directory / "transcript.json").read_text("utf-8"))
        data["text"] = " ".join(s.text for s in transcript_data.segments if s.end > body.start and s.start < body.end)
        data["editorial"] = clip.editorial | {"manually_edited": True, "automatic_ready": False,
                                               "flags": ["Manually edited; review the rendered result"]}
        analysis.clips = [c.model_copy(update=data) if c.id == clip_id else c for c in analysis.clips]
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT state,prefs FROM jobs WHERE id=?", (identity,)).fetchone()
            if current["state"] != "awaiting_selection" or current["prefs"] != job["prefs"]:
                raise ValueError("The project changed while editing. Refresh before saving.")
            write_json(directory / "analysis.json", analysis.model_dump())
            db.execute("UPDATE jobs SET updated=? WHERE id=?", (time.time(), identity))
        return {"ok": True}

    @app.post("/api/jobs/{identity}/clips/{clip_id}/publish")
    async def publish_clip(identity: str, clip_id: int, body: ClipPublish):
        job = owned(identity)
        directory = store.directory(identity)
        analysis = read_json(directory / "analysis.json")
        if not analysis:
            raise HTTPException(404, "Project analysis not found")
        clip = next((c for c in analysis.get("clips", []) if c.get("id") == clip_id), None)
        if not clip:
            raise HTTPException(404, "Clip not found")

        stem = f"clip_{clip_id:02}"
        video_path = directory / "clips" / f"{stem}.mp4"
        if not video_path.is_file():
            for cand in [directory / f"{stem}.mp4", directory / "clips" / f"clip_{clip_id}.mp4"]:
                if cand.is_file():
                    video_path = cand
                    break
        if not video_path.is_file():
            raise ValueError("Clip video is not ready. Please render the clip first.")

        title = (body.title or clip.get("title") or f"Clip {clip_id}").strip()
        caption = (body.caption or clip.get("caption") or title).strip()
        tags = [t.lstrip("#") for t in (body.hashtags or clip.get("hashtags") or []) if t.strip()]
        from .project_rules import description
        caption, tags = description(caption, tags, Preferences.model_validate_json(job["prefs"]))

        if body.platform == "youtube":
            from .youtube_publishing import get_youtube_config, get_token_path, upload_to_youtube
            yt_cfg = get_youtube_config(root)
            account_key = body.account or "main"
            acc_info = yt_cfg.get("accounts", {}).get(account_key)
            if not acc_info:
                raise ValueError(f"YouTube account '{account_key}' is not configured.")
            token_path = get_token_path(account_key, cfg.data_dir)
            if not token_path.is_file():
                raise ValueError(f"YouTube channel '{acc_info.get('title', account_key)}' is not authorized yet. Authorize it in Settings.")

            clean_tags = list(tags)
            if len(clean_tags) < 5 and "shorts" not in [t.lower() for t in clean_tags]:
                clean_tags.append("shorts")
            desc_text = caption
            if clean_tags and not any(f"#{t}" in desc_text for t in clean_tags):
                desc_text = f"{desc_text}\n\n{' '.join('#' + t for t in clean_tags[:5])}".strip()

            origin = f"{identity}:{clip_id}:yt:{account_key}:{secrets.token_hex(4)}"
            post = publications.add(
                owner=0, chat=0, origin=origin, feature="f1", account=account_key,
                paths=[video_path], caption=desc_text, hashtags=clean_tags,
                auto=False, platform="youtube"
            )

            if body.publish_now:
                try:
                    publications.update(post["id"], state="publishing")
                    result = await asyncio.to_thread(
                        upload_to_youtube,
                        account_key=account_key,
                        video_path=video_path,
                        title=title,
                        description=desc_text,
                        tags=clean_tags,
                        privacy=body.privacy or acc_info.get("privacy", "public"),
                        made_for_kids=False,
                        is_short=True,
                        project_root=root,
                        data_dir=cfg.data_dir,
                    )
                    video_id = result["id"]
                    publications.update(post["id"], state="published", media_id=video_id, published_at=time.time())
                    return {
                        "ok": True,
                        "state": "published",
                        "platform": "youtube",
                        "media_id": video_id,
                        "url": f"https://www.youtube.com/shorts/{video_id}",
                        "publication_id": post["id"],
                        "title": title,
                        "account": account_key,
                        "channel_title": acc_info.get("title", account_key),
                        "message": f"Successfully published to YouTube Shorts!"
                    }
                except Exception as exc:
                    err_msg = str(exc)
                    publications.update(post["id"], state="failed", error=err_msg[:500])
                    raise ValueError(f"YouTube upload failed: {err_msg}")
            else:
                publications.update(post["id"], state="queued")
                return {
                    "ok": True,
                    "state": "queued",
                    "platform": "youtube",
                    "publication_id": post["id"],
                    "account": account_key,
                    "channel_title": acc_info.get("title", account_key),
                    "message": "Queued for YouTube Shorts publishing."
                }

        elif body.platform == "instagram":
            account_key = body.account or "clips"
            origin = f"{identity}:{clip_id}:ig:{account_key}:{secrets.token_hex(4)}"
            post = publications.add(
                owner=0, chat=0, origin=origin, feature="f1", account=account_key,
                paths=[video_path], caption=caption, hashtags=tags,
                auto=body.publish_now, platform="instagram"
            )
            return {
                "ok": True,
                "state": "queued" if body.publish_now else "approval",
                "platform": "instagram",
                "publication_id": post["id"],
                "account": account_key,
                "message": "Queued for Instagram publishing."
            }
        else:
            raise ValueError(f"Unsupported platform: {body.platform}")

    @app.post("/api/jobs/{identity}/schedule-all")
    async def schedule_all_clips(identity: str, body: ScheduleAllClips):
        job = owned(identity)
        directory = store.directory(identity)
        analysis = read_json(directory / "analysis.json")
        if not analysis:
            raise HTTPException(404, "Project analysis not found")
        clips = analysis.get("clips", [])
        if not clips:
            raise HTTPException(404, "No clips found in project")

        selected_ids = set(body.clip_ids) if body.clip_ids else None

        rendered_clips = []
        for clip in clips:
            cid = clip.get("id")
            if selected_ids is not None and cid not in selected_ids:
                continue
            stem = f"clip_{cid:02}"
            vpath = directory / "clips" / f"{stem}.mp4"
            if not vpath.is_file():
                for cand in [directory / f"{stem}.mp4", directory / "clips" / f"clip_{cid}.mp4"]:
                    if cand.is_file():
                        vpath = cand
                        break
            if vpath.is_file():
                rendered_clips.append((clip, vpath))

        if not rendered_clips:
            raise ValueError("No rendered clips found to schedule. Please render your clips before scheduling.")

        rendered_clips.sort(key=lambda item: item[0].get("id", 0))

        # Check which clips are already live on YouTube / target platform
        with store.connect() as db:
            live_rows = db.execute(
                "SELECT origin, platform FROM publications WHERE origin LIKE ? AND state='published'",
                (f"{identity}:%",)
            ).fetchall()

        live_clip_ids = set()
        target_plat = (body.platform or "youtube").strip().lower()
        for r in live_rows:
            plat = (r["platform"] or "").strip().lower()
            is_match = False
            if target_plat == "youtube" and plat in ("youtube", "yt"):
                is_match = True
            elif target_plat == "instagram" and plat in ("instagram", "ig"):
                is_match = True
            elif plat == target_plat:
                is_match = True

            if is_match:
                parts = r["origin"].split(":")
                if len(parts) >= 2 and parts[1].isdigit():
                    live_clip_ids.add(int(parts[1]))

        # Filter out clips that are already live
        skipped_live_clips = []
        to_schedule = []
        for clip, vpath in rendered_clips:
            cid = clip.get("id")
            if cid in live_clip_ids:
                skipped_live_clips.append(clip)
            else:
                to_schedule.append((clip, vpath))

        if not to_schedule:
            if skipped_live_clips:
                raise ValueError(
                    f"All {len(skipped_live_clips)} rendered clip(s) are already live on {body.platform.title()}. No remaining clips to schedule."
                )
            raise ValueError("No rendered clips found to schedule. Please render your clips before scheduling.")

        account_key = body.account or ("main" if body.platform == "youtube" else "clips")
        channel_title = account_key
        if body.platform == "youtube":
            from .youtube_publishing import get_youtube_config, get_token_path
            yt_cfg = get_youtube_config(root)
            acc_info = yt_cfg.get("accounts", {}).get(account_key)
            if not acc_info:
                raise ValueError(f"YouTube account '{account_key}' is not configured.")
            token_path = get_token_path(account_key, cfg.data_dir)
            if not token_path.is_file():
                raise ValueError(f"YouTube channel '{acc_info.get('title', account_key)}' is not authorized yet. Authorize it in Settings.")
            channel_title = acc_info.get("title", account_key)
        elif body.platform == "instagram":
            from .publishing import account_config
            try:
                acc, _, _ = account_config(account_key, job["owner"])
                channel_title = str(acc.get("ig_user_id", account_key))
            except Exception:
                pass
        else:
            raise ValueError(f"Unsupported platform: {body.platform}")

        gap_seconds = int(round(body.gap_hours * 3600))
        now = time.time()
        if body.start_time and body.start_time > 0:
            first_due = float(body.start_time)
        else:
            first_due = now if body.publish_first_now else now + gap_seconds

        from .project_rules import description
        prefs = Preferences.model_validate_json(job["prefs"])

        with store.connect() as db:
            for clip, _ in to_schedule:
                cid = clip["id"]
                db.execute(
                    "UPDATE publications SET state='rejected' WHERE origin LIKE ? AND state='queued'",
                    (f"{identity}:{cid}:%",)
                )

        scheduled_items = []
        prev_pub_id = None

        for idx, (clip, video_path) in enumerate(to_schedule):
            cid = clip["id"]
            clip_due = first_due + (idx * gap_seconds)
            title = (clip.get("title") or f"Clip {cid}").strip()
            caption = (clip.get("caption") or clip.get("text") or title).strip()
            tags = [t.lstrip("#") for t in (clip.get("hashtags") or []) if t.strip()]
            caption, tags = description(caption, tags, prefs)

            clean_tags = list(tags)
            desc_text = caption
            if body.platform == "youtube":
                if len(clean_tags) < 5 and "shorts" not in [t.lower() for t in clean_tags]:
                    clean_tags.append("shorts")
                if clean_tags and not any(f"#{t}" in desc_text for t in clean_tags):
                    desc_text = f"{desc_text}\n\n{' '.join('#' + t for t in clean_tags[:5])}".strip()

            origin = f"{identity}:{cid}:{body.platform[:2]}:{account_key}:{secrets.token_hex(4)}"
            post = publications.add(
                owner=0,
                chat=0,
                origin=origin,
                feature="f1",
                account=account_key,
                paths=[video_path],
                caption=desc_text,
                hashtags=clean_tags,
                auto=True,
                due=clip_due,
                predecessor=prev_pub_id,
                gap=gap_seconds if prev_pub_id else 0,
                platform=body.platform,
                extra_payload={
                    "title": title,
                    "description": desc_text,
                    "tags": clean_tags,
                    "privacy": body.privacy or "public",
                }
            )
            prev_pub_id = post["id"]

            video_id = None
            shorts_url = None
            is_scheduled_on_yt = False
            upload_err = None

            # If platform is YouTube and schedule_on_youtube is enabled,
            # upload directly to YouTube with publishAt for native YouTube-side scheduling!
            if body.platform == "youtube" and getattr(body, "schedule_on_youtube", True):
                from .youtube_publishing import upload_to_youtube
                if idx == 0 and body.publish_first_now:
                    clip_publish_at = None
                    clip_privacy = body.privacy or "public"
                else:
                    clip_publish_at = clip_due
                    clip_privacy = "private"

                try:
                    publications.update(post["id"], state="publishing")
                    yt_res = await asyncio.to_thread(
                        upload_to_youtube,
                        account_key=account_key,
                        video_path=video_path,
                        title=title,
                        description=desc_text,
                        tags=clean_tags,
                        privacy=clip_privacy,
                        made_for_kids=False,
                        is_short=True,
                        publish_at=clip_publish_at,
                        project_root=root,
                        data_dir=cfg.data_dir,
                    )
                    video_id = yt_res.get("id")
                    shorts_url = yt_res.get("shorts_url") or (f"https://www.youtube.com/shorts/{video_id}" if video_id else None)
                    is_scheduled_on_yt = bool(clip_publish_at)
                    publications.update(
                        post["id"],
                        state="published",
                        media_id=video_id,
                        published_at=time.time(),
                        due=clip_due,
                    )
                except Exception as exc:
                    upload_err = str(exc)[:500]
                    log.warning("YouTube direct schedule upload failed for clip %s: %s", cid, exc)
                    publications.update(post["id"], state="failed", error=upload_err)

            state = "published" if video_id else ("failed" if upload_err else "queued")
            scheduled_items.append({
                "clip_id": cid,
                "title": title,
                "publication_id": post["id"],
                "media_id": video_id,
                "url": shorts_url,
                "due": clip_due,
                "gap_seconds": gap_seconds if idx > 0 else 0,
                "platform": body.platform,
                "state": state,
                "error": upload_err,
                "scheduled_on_youtube": is_scheduled_on_yt,
            })

        skip_note = f" ({len(skipped_live_clips)} live clip{'s' if len(skipped_live_clips) != 1 else ''} skipped)" if skipped_live_clips else ""
        failed_count = sum(1 for item in scheduled_items if item.get("state") == "failed")
        if failed_count > 0:
            msg = f"Scheduled {len(scheduled_items) - failed_count} clips successfully ({failed_count} failed to upload). Inspect Settings or quota.{skip_note}"
        elif any(item.get("scheduled_on_youtube") for item in scheduled_items):
            msg = f"Successfully uploaded and scheduled {len(scheduled_items)} clips directly on YouTube Shorts with {body.gap_hours:g}-hour intervals. YouTube will publish each Short on schedule.{skip_note}"
        else:
            msg = f"Successfully scheduled {len(scheduled_items)} clips with a {body.gap_hours:g}-hour interval.{skip_note}"

        return {
            "ok": True,
            "count": len(scheduled_items),
            "skipped_live_count": len(skipped_live_clips),
            "skipped_clip_ids": [c.get("id") for c in skipped_live_clips],
            "gap_hours": body.gap_hours,
            "platform": body.platform,
            "account": account_key,
            "channel_title": channel_title,
            "items": scheduled_items,
            "message": msg,
        }

    @app.post("/api/jobs/{identity}/publications/{pub_id}/cancel")
    def cancel_publication(identity: str, pub_id: str):
        job = owned(identity)
        cancelled = publications.cancel(pub_id, owner=job["owner"])
        if not cancelled:
            with store.connect() as db:
                res = db.execute(
                    "UPDATE publications SET state='rejected' WHERE id=? AND owner=? AND origin LIKE ?",
                    (pub_id, job["owner"], f"{identity}:%")
                )
                if res.rowcount > 0:
                    return {"ok": True, "message": "Publication cancelled successfully"}
            raise HTTPException(404, "Publication not found or not in cancellable state")
        return {"ok": True, "message": "Publication cancelled successfully"}

    @app.post("/api/jobs/{identity}/schedule/cancel-all")
    def cancel_all_job_publications(identity: str):
        owned(identity)
        with store.connect() as db:
            result = db.execute(
                "UPDATE publications SET state='rejected' WHERE origin LIKE ? AND state IN ('queued', 'approval')",
                (f"{identity}:%",)
            )
        return {"ok": True, "cancelled": result.rowcount, "message": f"Cancelled {result.rowcount} scheduled publications"}


    @app.put("/api/jobs/{identity}/preferences")
    def project_preferences(identity: str, body: dict):
        job = owned(identity)
        allowed_fields = {"style", "captions", "reframe", "width", "layout", "music", "music_gain",
                          "music_override", "music_folder", "music_track",
                          "fps", "color_grade", "export_quality", "description_suffix", "overlay_text",
                          "music_normalize", "music_ducking", "smart_crop", "preserve_wide_groups", "trim_edges",
                          "text_mode", "sound_effects", "sfx_gain", "reaction_zoom"}
        if not body.keys() <= allowed_fields:
            raise ValueError("Only editing settings can be changed after discovery")
        updated = Preferences.model_validate(json.loads(job["prefs"]) | body)
        with store.connect() as db:
            changed = db.execute("UPDATE jobs SET prefs=?,updated=? WHERE id=? AND state='awaiting_selection'",
                                 (updated.model_dump_json(), time.time(), identity))
            if not changed.rowcount:
                raise ValueError("Editing settings can only change while awaiting selection")
        return updated.model_dump()

    @app.get("/api/jobs/{identity}/files/{name}")
    def job_file(identity: str, name: str):
        owned(identity)
        directory = store.directory(identity)
        if name == "captions-and-edit-plans.zip":
            path = export_metadata(directory)
        elif re.fullmatch(r"clip_\d{2}\.(mp4|cover\.jpg|srt|ass)", name):
            path = directory / "clips" / name
        else:
            raise HTTPException(404, "Asset not found")
        return FileResponse(contained(path, cfg.data_dir), filename=name if name.endswith((".zip", ".srt", ".ass")) else None)

    @app.get("/api/jobs/{identity}/thumbnail")
    async def thumbnail(identity: str):
        from .process import run
        owned(identity)
        directory = store.directory(identity)
        source = next(iter(sorted((directory / "clips").glob("*.mp4"))), None)
        if source is None:
            raise HTTPException(404, "No rendered media yet")
        source = contained(source, cfg.data_dir)
        stat = source.stat()
        signature = hashlib.sha256(f"{source.name}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:12]
        path = directory / f"studio-cover-{signature}.jpg"
        async with thumbnail_slots:
            if not path.is_file():
                partial = directory / f"studio-cover-{secrets.token_hex(6)}.jpg"
                try:
                    await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-ss", "2", "-i", str(source),
                               "-frames:v", "1", "-vf", "scale=640:360:force_original_aspect_ratio=increase,crop=640:360",
                               "-q:v", "3", str(partial)], timeout=30)
                    partial.replace(path)
                finally:
                    partial.unlink(missing_ok=True)
        return FileResponse(contained(path, cfg.data_dir))

    @app.get("/api/carousels")
    def carousel_jobs():
        result = []
        for job in rows("faceless_jobs"):
            items = []
            folder = cfg.data_dir / "carousels" / job["id"]
            for post in sorted(folder.glob("post_*")):
                plan = read_json(post / "plan.json", {})
                images = [f"/api/carousels/{job['id']}/files/{post.name}/{p.name}" for p in sorted(post.glob("slide_*.jpg"))]
                items.append({"name": post.name, "plan": plan, "images": images,
                              "cover": f"/api/carousels/{job['id']}/files/{post.name}/contact-sheet.jpg" if (post / "contact-sheet.jpg").exists() else None})
            result.append({k: job[k] for k in ("id", "niche", "count", "state", "stage", "created", "error")} | {
                "prompt": job.get("prompt", "") or "",
                "items": items,
            })
        return result

    @app.post("/api/carousels", status_code=201)
    def generate(body: Generate):
        prefs = cfg.snapshot_ai(store.prefs(owner))
        cfg.check_ai(prefs.ai_provider, prefs.ai_model)
        identity = carousels.create(owner, 0, body.niche, body.count, prefs, prompt=body.prompt)
        return {"id": identity}

    @app.get("/api/prompts")
    def get_prompts():
        from .prompts import list_prompts
        return list_prompts(cfg.data_dir)

    @app.get("/api/prompts/{key}")
    def get_one_prompt(key: str):
        from .prompts import get_prompt_info
        return get_prompt_info(key, cfg.data_dir)

    @app.put("/api/prompts/{key}")
    def update_one_prompt(key: str, body: PromptUpdate):
        from .prompts import set_prompt
        return set_prompt(key, body.value, cfg.data_dir)

    @app.put("/api/prompts")
    def update_prompts(body: BatchPromptUpdate):
        from .prompts import list_prompts, set_prompt
        for k, v in body.prompts.items():
            set_prompt(k, v, cfg.data_dir)
        return list_prompts(cfg.data_dir)

    @app.post("/api/prompts/{key}/reset")
    def reset_one_prompt(key: str):
        from .prompts import reset_prompt
        return reset_prompt(key, cfg.data_dir)

    @app.post("/api/prompts/reset")
    def reset_all_prompts_route():
        from .prompts import reset_all_prompts
        return reset_all_prompts(cfg.data_dir)


    @app.post("/api/carousels/{identity}/{action}")
    def carousel_action(identity: str, action: str):
        job = owned(identity, "carousel")
        if action == "retry":
            carousels.retry(identity, job["owner"])
        elif action == "cancel":
            carousels.cancel(identity, job["owner"])
        else:
            raise ValueError("Unknown carousel action")
        return {"ok": True}

    @app.get("/api/carousels/{identity}/files/{item}/{name}")
    def carousel_file(identity: str, item: str, name: str):
        owned(identity, "carousel")
        if not re.fullmatch(r"post_\d{3}", item) or not re.fullmatch(r"(slide_\d+|contact-sheet)\.jpg", name):
            raise HTTPException(404, "Asset not found")
        return FileResponse(contained(cfg.data_dir / "carousels" / identity / item / name, cfg.data_dir))

    def niche_path():
        return Path(os.getenv("NICHES_CONFIG_FILE", str(root / "config" / "niches.json")))

    @app.get("/api/niches")
    def niches():
        config = read_json(niche_path(), {})
        return [{"key": key, "label": label, "config": config.get(key, {}),
                 "reference_ready": bool(config.get(key, {}).get("character_path") and Path(config[key]["character_path"]).is_file())} for key, label in NICHES.items()]

    @app.put("/api/niches/{key}")
    def update_niche(key: str, body: dict):
        if key not in NICHES:
            raise ValueError("Unknown niche")
        allowed_fields = {"name", "brand", "character_path", "instagram_account", "threshold", "pillars", "banned_topics", "research_feeds"}
        if not body.keys() <= allowed_fields:
            raise ValueError("Unsupported niche field")
        if "threshold" in body and (type(body["threshold"]) is not int or not 70 <= body["threshold"] <= 100):
            raise ValueError("Threshold must be 70–100")
        for field in ("pillars", "banned_topics", "research_feeds"):
            if field in body and (not isinstance(body[field], list) or len(body[field]) > 30 or any(not isinstance(x, str) or len(x) > 2000 for x in body[field])):
                raise ValueError(f"Invalid {field}")
        for field in ("name", "brand", "character_path", "instagram_account"):
            if field in body and (not isinstance(body[field], str) or len(body[field]) > 5000):
                raise ValueError(f"Invalid {field}")
        if any(not u.startswith("https://") for u in body.get("research_feeds", [])):
            raise ValueError("Research feeds must use HTTPS")
        path = niche_path()
        data = read_json(path, {})
        data[key] = data.get(key, {}) | body
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, data)
        return {"ok": True}

    @app.post("/api/niches/{key}/upload")
    async def upload_reference(key: str, file: UploadFile):
        if key not in NICHES or Path(file.filename or "").suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("Choose a niche and a PNG, JPEG or WebP reference")
        folder = cfg.data_dir / "references"
        folder.mkdir(exist_ok=True)
        path = folder / (key + "-" + secrets.token_hex(4) + Path(file.filename).suffix.lower())
        await save_upload(file, path, 20 * 1024**2)
        import cv2
        try:
            image = cv2.imread(str(path))
            if image is None or image.size == 0:
                raise ValueError("Unreadable image")
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise ValueError("The file is not a readable image") from exc
        update_niche(key, {"character_path": str(path.resolve())})
        return {"ok": True, "character_path": str(path.resolve())}

    @app.get("/api/schedules")
    def schedules():
        return rows("content_schedules")

    @app.put("/api/schedules/{key}")
    def schedule(key: str, body: Schedule):
        if body.daily_time and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", body.daily_time):
            raise ValueError("Use a 24-hour time, HH:MM")
        carousels.schedule(owner, 0, key, **body.model_dump())
        return {"ok": True}

    @app.get("/api/publications")
    def posts():
        result = []
        for post in rows("publications"):
            payload = json.loads(post["payload"])
            result.append({k: post[k] for k in ("id", "origin", "feature", "account", "state", "due", "created", "error", "published_at", "media_id", "predecessor", "gap")} | {
                "caption": payload["caption"], "automatic": payload.get("automatic"), "review_note": payload.get("review_note", ""),
                "platform": post.get("platform") or payload.get("platform", "instagram"),
                "media": [{"url": f"/api/publications/{post['id']}/media/{i}", "video": Path(p).suffix == ".mp4"} for i, p in enumerate(payload["paths"])]})
        return result

    @app.get("/api/publications/{identity}/media/{index}")
    def post_media(identity: str, index: int):
        post = owned(identity, "post")
        paths = json.loads(post["payload"])["paths"]
        if not 0 <= index < len(paths):
            raise HTTPException(404, "Asset not found")
        path = Path(paths[index])
        if path.suffix.lower() not in {".mp4", ".jpg", ".jpeg"}:
            raise HTTPException(404, "Asset not found")
        return FileResponse(contained(path, cfg.data_dir))

    @app.put("/api/publications/{identity}")
    def edit_post(identity: str, body: PostEdit):
        owned(identity, "post")
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            post = db.execute("SELECT * FROM publications WHERE id=?", (identity,)).fetchone()
            if post["state"] not in {"approval", "queued", "failed"} or post["container"]:
                raise ValueError("This publication can no longer be edited safely")
            if len(re.findall(r"#[\w]+", body.caption)) > 5:
                raise ValueError("Use at most five hashtags")
            payload = json.loads(post["payload"])
            payload["caption"] = body.caption
            db.execute("UPDATE publications SET payload=?,due=? WHERE id=?", (json.dumps(payload), body.due or post["due"], identity))
        return {"ok": True}

    @app.post("/api/publications/{identity}/{action}")
    def post_action(identity: str, action: str):
        post = owned(identity, "post")
        if action not in {"approve", "reject", "schedule"}:
            raise ValueError("Unknown publication action")
        if action == "schedule":
            with store.connect() as db:
                changed = db.execute("UPDATE publications SET state='queued',error='' WHERE id=? AND state IN ('approval','failed') AND due>?", (identity, time.time()))
                if not changed.rowcount:
                    raise ValueError("Save a future posting time before scheduling")
        else:
            publications.decide(identity, post["owner"], action == "approve")
        return {"ok": True}

    @app.get("/api/music")
    def music():
        result = []
        all_cats = get_categories(cfg.music_dir)
        for category, name in all_cats.items():
            folder = resolve_category_folder(cfg.music_dir, category) or (cfg.music_dir / name)
            tracks = [{"name": p.name, "bytes": p.stat().st_size, "url": f"/api/music/{category}/file/{quote(p.name)}"} for p in sorted(folder.glob("*")) if p.is_file() and not p.is_symlink() and p.suffix.lower() in AUDIO]
            result.append({"id": category, "name": name, "tracks": tracks})
        return result

    @app.get("/api/music/{category}/file/{name}")
    def music_file(category: str, name: str):
        if Path(name).name != name or Path(name).suffix.lower() not in AUDIO:
            raise HTTPException(404, "Track not found")
        folder = resolve_category_folder(cfg.music_dir, category)
        if not folder or not (folder / name).is_file():
            raise HTTPException(404, "Track not found")
        return FileResponse(contained(folder / name, cfg.music_dir))

    @app.post("/api/music/{category}/upload")
    async def upload_music(category: str, file: UploadFile):
        suffix = Path(file.filename or "").suffix.lower()
        folder = resolve_category_folder(cfg.music_dir, category)
        if not folder or suffix not in AUDIO:
            raise ValueError("Choose a music category and supported audio file")
        folder.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w .-]", "_", Path(file.filename).stem)[:80] + "-" + secrets.token_hex(3) + suffix
        await save_upload(file, folder / name, 100 * 1024**2)
        return {"ok": True}

    @app.get("/api/connections")
    def connections():
        accounts = read_json(Path(os.getenv("INSTAGRAM_ACCOUNTS_FILE", str(root / "config" / "instagram.json"))), {})
        return {"telegram_configured": bool(cfg.token), "media_host_configured": bool(os.getenv("PUBLIC_MEDIA_BASE_URL")),
                "accounts": [{"key": k, "ig_user_id": str(v.get("ig_user_id", "")), "login": v.get("login", "instagram"),
                              "token_configured": bool(os.getenv(v.get("token_env", ""))), "owner_allowed": owner in v.get("owners", [])} for k, v in accounts.items()]}

    @app.put("/api/connections/{key}")
    def update_connection(key: str, body: dict):
        from dotenv import set_key
        if not re.fullmatch(r"[a-z0-9_]{1,40}", key) or not body.keys() <= {"ig_user_id", "login", "token", "media_base_url"}:
            raise ValueError("Invalid account mapping")
        if not re.fullmatch(r"\d{1,40}", str(body.get("ig_user_id", ""))) or body.get("login") not in {"instagram", "facebook"}:
            raise ValueError("Supply a numeric professional account ID and valid login flow")
        for field in ("token", "media_base_url"):
            if field in body and (not isinstance(body[field], str) or len(body[field]) > 4000 or any(c in body[field] for c in "\r\n")):
                raise ValueError("Invalid connection value")
        media_url = body.get("media_base_url")
        if media_url:
            parsed = urlsplit(media_url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Media hosting requires a public HTTPS base URL without credentials or query parameters")
        path = Path(os.getenv("INSTAGRAM_ACCOUNTS_FILE", str(root / "config" / "instagram.json")))
        data = read_json(path, {})
        existing = data.get(key, {})
        token_env = existing.get("token_env") or "IG_" + key.upper() + "_TOKEN"
        if not re.fullmatch(r"IG_[A-Z0-9_]+_TOKEN", token_env):
            raise ValueError("Use an IG_*_TOKEN environment variable for this account before editing it here")
        data[key] = existing | {"ig_user_id": str(body["ig_user_id"]), "login": body["login"], "token_env": token_env,
                               "owners": sorted(set(existing.get("owners", [])) | {owner})}
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, data)
        if body.get("token"):
            set_key(str(root / ".env"), token_env, body["token"])
        if media_url:
            set_key(str(root / ".env"), "PUBLIC_MEDIA_BASE_URL", media_url.rstrip("/"))
        return {"ok": True, "restart_required": True}

    @app.get("/api/youtube/connections")
    def youtube_connections():
        from .youtube_publishing import get_youtube_config, get_token_path
        yt_cfg = get_youtube_config(root)
        client_id = yt_cfg.get("client_id", "")
        client_secret = yt_cfg.get("client_secret", "")
        accounts = []
        for k, v in yt_cfg.get("accounts", {}).items():
            token_path = get_token_path(k, cfg.data_dir)
            authorized = token_path.is_file()
            accounts.append({
                "key": k,
                "title": v.get("title", k),
                "channel_id": v.get("channel_id", ""),
                "privacy": v.get("privacy", "public"),
                "default_tags": v.get("default_tags", ["shorts", "clips"]),
                "thumbnail": v.get("thumbnail", ""),
                "auto_publish": bool(v.get("auto_publish", False)),
                "owner_allowed": owner in v.get("owners", [0]) or owner == 0 or 0 in v.get("owners", [0]),
                "authorized": authorized,
            })
        return {
            "configured": bool(client_id and client_secret),
            "client_id": client_id[:12] + "..." if len(client_id) > 16 else client_id,
            "has_secret": bool(client_secret),
            "accounts": accounts,
        }

    @app.put("/api/youtube/config")
    def update_youtube_config(body: dict):
        from dotenv import set_key
        from .youtube_publishing import get_youtube_config, save_youtube_config
        yt_cfg = get_youtube_config(root)
        client_id = str(body.get("client_id", "")).strip()
        client_secret = str(body.get("client_secret", "")).strip()
        if client_id:
            yt_cfg["client_id"] = client_id
            set_key(str(root / ".env"), "YOUTUBE_CLIENT_ID", client_id)
        if client_secret:
            yt_cfg["client_secret"] = client_secret
            set_key(str(root / ".env"), "YOUTUBE_CLIENT_SECRET", client_secret)
        save_youtube_config(yt_cfg, root)
        return {"ok": True, "configured": bool(yt_cfg.get("client_id") and yt_cfg.get("client_secret"))}

    @app.put("/api/youtube/accounts/{key}")
    def update_youtube_account(key: str, body: dict):
        from .youtube_publishing import get_youtube_config, save_youtube_config
        if not re.fullmatch(r"[a-z0-9_-]{1,40}", key):
            raise ValueError("Use lowercase letters, numbers, hyphens or underscores for account key")
        yt_cfg = get_youtube_config(root)
        accounts = yt_cfg.setdefault("accounts", {})
        existing = accounts.get(key, {})
        privacy = body.get("privacy", existing.get("privacy", "public"))
        if privacy not in {"public", "unlisted", "private"}:
            privacy = "public"
        default_tags = body.get("default_tags", existing.get("default_tags", ["shorts", "clips"]))
        if isinstance(default_tags, str):
            default_tags = [t.strip() for t in default_tags.split(",") if t.strip()]
        accounts[key] = existing | {
            "title": body.get("title", existing.get("title", key)),
            "privacy": privacy,
            "default_tags": default_tags,
            "auto_publish": bool(body.get("auto_publish", existing.get("auto_publish", False))),
            "owners": sorted(set(existing.get("owners", [])) | {owner}),
        }
        save_youtube_config(yt_cfg, root)
        return {"ok": True}

    @app.delete("/api/youtube/accounts/{key}")
    def delete_youtube_account(key: str):
        from .youtube_publishing import get_youtube_config, save_youtube_config, get_token_path
        yt_cfg = get_youtube_config(root)
        accounts = yt_cfg.setdefault("accounts", {})
        if key in accounts:
            del accounts[key]
            save_youtube_config(yt_cfg, root)
        token_path = get_token_path(key, cfg.data_dir)
        if token_path.is_file():
            token_path.unlink(missing_ok=True)
        return {"ok": True}

    @app.get("/api/youtube/auth-url")
    def youtube_auth_url(account: str, request: Request):
        from .youtube_publishing import get_youtube_config, YOUTUBE_SCOPES
        yt_cfg = get_youtube_config(root)
        client_id = yt_cfg.get("client_id")
        if not client_id or not yt_cfg.get("client_secret"):
            raise ValueError("Configure Google OAuth Client ID and Secret first in Settings.")

        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/youtube/callback"
        state_data = json.dumps({"account": account, "nonce": secrets.token_hex(8)})
        auth_url = (
            "https://accounts.google.com/o/oauth2/v2/auth?"
            + urlencode({
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(YOUTUBE_SCOPES),
                "access_type": "offline",
                "prompt": "select_account consent",
                "state": state_data,
            })
        )
        return {"auth_url": auth_url, "redirect_uri": redirect_uri}

    @app.get("/api/youtube/callback")
    async def youtube_callback(code: str = "", state: str = "", error: str = "", request: Request = None):
        if error:
            html = f"<!DOCTYPE html><html><body><h2>Authentication Cancelled</h2><p>{error}</p><script>window.close();</script></body></html>"
            return HTMLResponse(content=html, status_code=400)
        if not code or not state:
            raise HTTPException(400, "Missing authorization code or state")

        try:
            state_data = json.loads(state)
            account_key = state_data.get("account")
        except Exception:
            raise HTTPException(400, "Invalid state parameter")

        from google.oauth2.credentials import Credentials
        from .youtube_publishing import get_youtube_config, save_youtube_config, save_credentials, fetch_channel_profile, YOUTUBE_SCOPES
        yt_cfg = get_youtube_config(root)
        client_id = yt_cfg.get("client_id")
        client_secret = yt_cfg.get("client_secret")
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/youtube/callback"

        token_url = "https://oauth2.googleapis.com/token"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(token_url, data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            })
            token_res = resp.json()

        if "error" in token_res or not token_res.get("access_token"):
            err_desc = token_res.get("error_description", token_res.get("error", "Unknown token exchange failure"))
            html = f"<!DOCTYPE html><html><body><h2>Token Exchange Failed</h2><p>{err_desc}</p><script>setTimeout(() => window.close(), 3000);</script></body></html>"
            return HTMLResponse(content=html, status_code=400)

        creds = Credentials(
            token=token_res.get("access_token"),
            refresh_token=token_res.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=YOUTUBE_SCOPES,
        )
        save_credentials(account_key, creds, cfg.data_dir)

        channel_info = {}
        try:
            channel_info = await asyncio.to_thread(fetch_channel_profile, creds)
        except Exception as exc:
            pass

        accounts = yt_cfg.setdefault("accounts", {})
        accounts[account_key] = accounts.get(account_key, {}) | {
            "channel_id": channel_info.get("channel_id", ""),
            "title": channel_info.get("title") or accounts.get(account_key, {}).get("title", account_key),
            "thumbnail": channel_info.get("thumbnail", ""),
            "owners": sorted(set(accounts.get(account_key, {}).get("owners", [])) | {owner}),
        }
        save_youtube_config(yt_cfg, root)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>YouTube Connected</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 32px; text-align: center; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
        h2 {{ color: #22c55e; margin-top: 0; }}
        p {{ color: #94a3b8; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>Channel Connected!</h2>
        <p><strong>{channel_info.get('title', account_key)}</strong> is now authorized for publishing.</p>
        <p>This window will close automatically...</p>
    </div>
    <script>
        if (window.opener) {{
            window.opener.postMessage({{ type: 'YOUTUBE_AUTH_SUCCESS', account: '{account_key}' }}, '*');
        }}
        setTimeout(() => window.close(), 1500);
    </script>
</body>
</html>"""
        return HTMLResponse(content=html)

    @app.post("/api/publications/youtube")
    def create_youtube_publication(body: dict):
        paths = body.get("paths", [])
        title = body.get("title", "Clip")
        caption = body.get("caption", title)
        tags = body.get("tags", ["shorts", "clips"])
        account = body.get("account", "main")
        privacy = body.get("privacy", "public")
        auto = bool(body.get("auto", False))
        due = body.get("due") or body.get("publish_at")
        if not paths:
            raise ValueError("No video paths provided")
        identity = secrets.token_hex(6)
        origin = body.get("origin") or f"custom:{identity}"
        post = publications.add(
            owner, 0, f"{origin}:yt:{account}", "f1", account,
            paths, caption, tags, auto=auto, due=due, platform="youtube"
        )
        return {"ok": True, "publication": post}

    @app.put("/api/system")
    def update_system(body: dict):
        from dotenv import set_key
        permitted = {"WHISPER_MODEL", "WHISPER_DEVICE", "WHISPER_COMPUTE_TYPE", "WHISPER_BEAM_SIZE", "VIDEO_ENCODER",
                     "MAX_SOURCE_MINUTES", "MAX_DOWNLOAD_MB", "MIN_FREE_DISK_MB", "MAX_ACTIVE_JOBS", "RETENTION_DAYS",
                     "LONG_SOURCE_MINUTES", "SCAN_DOWNLOAD_WORKERS", "CHATGPT_BROWSER_HEADLESS", "CHATGPT_BROWSER_TIMEOUT",
                     "OPENAI_API_KEY", "XAI_API_KEY", "GEMINI_API_KEY", "OPENAI_MODEL", "XAI_MODEL", "GEMINI_MODEL", "TELEGRAM_BOT_TOKEN"}
        if not body or not body.keys() <= permitted:
            raise ValueError("Unsupported system field")
        numeric = {"WHISPER_BEAM_SIZE": (1, 10), "MAX_SOURCE_MINUTES": (1, 1440), "MAX_DOWNLOAD_MB": (10, 100000),
                   "MIN_FREE_DISK_MB": (100, 1000000), "MAX_ACTIVE_JOBS": (1, 50), "RETENTION_DAYS": (1, 3650),
                   "LONG_SOURCE_MINUTES": (1, 1440), "SCAN_DOWNLOAD_WORKERS": (1, 3), "CHATGPT_BROWSER_TIMEOUT": (10, 3600)}
        enums = {"WHISPER_DEVICE": {"cpu", "cuda"}, "VIDEO_ENCODER": {"libx264", "h264_nvenc"},
                 "CHATGPT_BROWSER_HEADLESS": {"true", "false"}, "WHISPER_COMPUTE_TYPE": {"int8", "int8_float16", "float16", "float32", "int8_float32"}}
        for key, value in body.items():
            value = str(value)
            if len(value) > 1000 or "\n" in value or "\r" in value:
                raise ValueError("Invalid setting value")
            if key in numeric and (not value.isdigit() or not numeric[key][0] <= int(value) <= numeric[key][1]):
                raise ValueError(f"{key} must be between {numeric[key][0]} and {numeric[key][1]}")
            if key in enums and value not in enums[key]:
                raise ValueError(f"Unsupported {key}")
        for key, value in body.items():
            set_key(str(root / ".env"), key, str(value))
        return {"ok": True, "restart_required": True, "message": "Saved locally. Restart the web server and Telegram worker to apply engine/credential changes."}

    from .x_web import install_routes
    install_routes(app, cfg, store, owner, save_upload)
    dist = Path(static_root) if static_root else root / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Endpoint not found")
        if not (dist / "index.html").exists():
            raise HTTPException(503, "Build the frontend first: see WEB_STUDIO.md")
        return FileResponse(dist / "index.html")

    return app


def serve(cfg, host="0.0.0.0", port=8788, *, no_engine=False, open_browser=False):
    import uvicorn
    app = create_app(cfg, start_engine=not no_engine)
    local_url = f"http://127.0.0.1:{port}/#key={app.state.launch_token}"

    lan_ip = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
    except Exception:
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass

    print(f"CLIPER Studio (Local):   {local_url}")
    if lan_ip and lan_ip != "127.0.0.1":
        print(f"CLIPER Studio (Network): http://{lan_ip}:{port}/#key={app.state.launch_token}")
    print(f"Access key: {cfg.data_dir / 'web' / 'access-key'}")
    if open_browser:
        import threading
        import webbrowser
        timer = threading.Timer(1.5, lambda: webbrowser.open(local_url))
        timer.daemon = True
        timer.start()
    uvicorn.run(app, host=host, port=port, access_log=False)
