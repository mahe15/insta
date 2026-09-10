from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from . import media
from .config import Config
from .models import Analysis, Clip, Preferences, Transcript
from .process import JobCancelled
from .selection import select
from .storage import Store, write_json

log = logging.getLogger(__name__)


def safe_error(exc: BaseException, cfg: Config) -> str:
    message = str(exc) or type(exc).__name__
    for secret in (cfg.token, cfg.api_key, cfg.xai_api_key, cfg.gemini_api_key):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[-2000:]


class Pipeline:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    async def analyze(self, source_input: str, directory: Path, prefs: Preferences,
                      progress: Callable[[str], Awaitable[None]], cancelled=lambda: False) -> Analysis:
        directory.mkdir(parents=True, exist_ok=True)
        self.cfg.check_disk()
        cache = directory / "analysis.json"
        if cache.exists():
            return Analysis.model_validate_json(cache.read_text(encoding="utf-8"))
        self.cfg.check_ai(prefs.ai_provider, prefs.ai_model)
        reference = directory / "source.json"
        if reference.exists():
            source = Path(json.loads(reference.read_text(encoding="utf-8"))["path"])
            if not source.is_file():
                raise ValueError("Source file was removed. Submit a new job.")
        else:
            if source_input.startswith("https://"):
                from .remote_media import audio
                await progress("Downloading audio only for analysis")
                source, info = await audio(source_input, directory / "audio-source", self.cfg, cancelled)
                write_json(reference, {"path": str(source), "media": info, "kind": "remote_audio", "url": source_input})
            else:
                source = Path(source_input).resolve()
                if not source.is_file():
                    raise ValueError("Source file does not exist")
                if source.stat().st_size > self.cfg.max_download_mb * 1024**2:
                    raise ValueError("Source exceeds MAX_DOWNLOAD_MB")
            if not reference.exists():
                await progress("Checking source video and audio")
                info = await media.probe(source, self.cfg, cancelled)
                write_json(reference, {"path": str(source), "media": info})
        transcript_path = directory / "transcript.json"
        if transcript_path.exists():
            transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        else:
            await progress("Transcribing speech with word timestamps · first run may download the model")
            transcript = await media.transcribe(source, directory, prefs, self.cfg, cancelled)
        source_info = json.loads(reference.read_text(encoding="utf-8"))["media"]
        if transcript.duration > source_info["duration"] + 1:
            raise ValueError("Transcript duration exceeds the source video. Supply the matching transcript.")
        if prefs.captions and any(s.text.strip() and not s.words for s in transcript.segments):
            raise ValueError("Captions require word timestamps. Supply a word-timed transcript or disable captions.")
        if cancelled():
            raise JobCancelled()
        await progress("Selecting complete, compelling moments")
        analysis = await select(transcript, prefs, self.cfg, progress)
        write_json(cache, analysis.model_dump())
        return analysis

    async def render_one(self, directory: Path, clip: Clip, prefs: Preferences, cancelled=lambda: False):
        self.cfg.check_disk()
        reference = json.loads((directory / "source.json").read_text(encoding="utf-8"))
        source = Path(reference["path"])
        transcript = Transcript.model_validate_json((directory / "transcript.json").read_text(encoding="utf-8"))
        output = directory / "clips" / f"clip_{clip.id:02}.mp4"
        if output.exists():
            try:
                metadata = json.loads(output.with_suffix(".json").read_text("utf-8"))
                if metadata.get("preferences") != prefs.model_dump():
                    raise ValueError("Editing preferences changed")
                await media.quality_check(output, clip, prefs, self.cfg, cancelled)
                return output
            except (ValueError, RuntimeError, OSError, KeyError):
                log.warning("Cached export failed validation; rendering again")
        if reference.get("kind") == "remote_audio":
            from .models import Segment, Word
            from .remote_media import section
            source = await section(reference["url"], directory / "ranges" / f"clip_{clip.id:02}",
                                   clip.start, clip.end, self.cfg, cancelled)
            original = clip
            segments = []
            for s in transcript.segments:
                if s.start >= clip.start and s.end <= clip.end + .01:
                    segments.append(Segment(start=max(0, s.start - clip.start), end=s.end - clip.start,
                                            text=s.text, words=[Word(start=max(0, w.start - clip.start),
                                            end=w.end - clip.start, text=w.text) for w in s.words]))
            transcript = Transcript(language=transcript.language, duration=clip.end - clip.start, segments=segments)
            clip = clip.model_copy(update={"start": 0, "end": clip.end - clip.start})
            output = await media.render(source, directory / "clips", transcript, clip, prefs, self.cfg, cancelled)
            meta_path = output.with_suffix(".json")
            metadata = json.loads(meta_path.read_text("utf-8"))
            metadata["clip"] = original.model_dump()
            metadata["source_range"] = {"start": original.start, "end": original.end, "local_start": 0}
            write_json(meta_path, metadata)
            return output
        return await media.render(source, directory / "clips", transcript, clip, prefs, self.cfg, cancelled)


class Worker:
    """One durable worker per data directory, with cooperative cancellation at every stage."""
    def __init__(self, cfg: Config, store: Store, notify, shortlist, deliver):
        self.cfg, self.store = cfg, store
        self.pipeline = Pipeline(cfg)
        self.notify, self.shortlist, self.deliver = notify, shortlist, deliver
        self.stopping = asyncio.Event()
        self.current: asyncio.Task | None = None

    async def process(self, job: dict):
        job_id = job["id"]
        directory = self.store.directory(job_id)
        prefs = Preferences.model_validate_json(job["prefs"])

        def cancelled():
            return self.stopping.is_set() or self.store.get(job_id)["state"] == "cancelled"

        async def progress(message):
            if cancelled():
                raise JobCancelled()
            self.store.update(job_id, stage=message)
            try:
                await self.notify(job, message)
            except Exception:
                # A transient Telegram outage must not lose an expensive analysis/render.
                log.warning("Progress notification unavailable for job %s", job_id)

        if job["state"] == "analyzing":
            analysis = await self.pipeline.analyze(job["source"], directory, prefs, progress, cancelled)
            if cancelled():
                raise JobCancelled()
            self.store.update(job_id, state="awaiting_selection", stage="Choose clips to render")
            if prefs.auto_render or prefs.auto_publish:
                self.store.select(job_id, job["owner"], [c.id for c in analysis.clips])
            else:
                await self.shortlist(job, analysis)
            return
        analysis = Analysis.model_validate_json((directory / "analysis.json").read_text(encoding="utf-8"))
        selected = json.loads(job["selected"])
        delivered = json.loads(job["delivered"])
        clips = [c for c in analysis.clips if c.id in selected]
        if not clips:
            raise ValueError("No clips were selected")
        for n, clip in enumerate(clips, 1):
            if clip.id in delivered:
                continue
            await progress(f"Rendering and checking clip {n}/{len(clips)} · {clip.title}")
            output = await self.pipeline.render_one(directory, clip, prefs, cancelled)
            await progress(f"Sending clip {n}/{len(clips)}")
            await self.deliver(job, clip, output)
            delivered.append(clip.id)
            self.store.update(job_id, delivered=json.dumps(delivered))
        if cancelled():
            raise JobCancelled()
        self.store.update(job_id, state="complete", stage=f"Delivered {len(clips)} clips")
        try:
            await self.notify(job, f"Done · {len(clips)} clips delivered. Use /export {job_id} for captions and metadata.")
        except Exception:
            log.warning("Completion notification unavailable for job %s", job_id)

    async def run(self):
        self.store.recover()
        while not self.stopping.is_set():
            job = self.store.claim()
            if not job:
                try:
                    await asyncio.wait_for(self.stopping.wait(), timeout=1)
                except TimeoutError:
                    pass
                continue
            self.current = asyncio.create_task(self.process(job))
            try:
                while not self.current.done():
                    if (self.stopping.is_set() or self.store.get(job["id"])["state"] == "cancelled"
                            or not self.store.prefs(job["owner"]).f1_enabled) and not self.current.cancelling():
                        self.current.cancel()
                    await asyncio.wait({self.current}, timeout=.4)
                await self.current
            except (asyncio.CancelledError, JobCancelled):
                # On shutdown leave the durable state for recovery; explicit /cancel is already saved.
                if not self.stopping.is_set() and self.store.get(job["id"])["state"] != "cancelled":
                    self.store.update(job["id"], state="queued_analysis" if job["state"] == "analyzing" else "queued_render",
                                      stage="Feature 1 paused")
                pass
            except Exception as exc:
                error = safe_error(exc, self.cfg)
                log.error("Job %s failed: %s", job["id"], error)
                self.store.update(job["id"], state="failed", stage="Needs attention", error=error)
                try:
                    await self.notify(job, f"Job paused: {error[:600]}\nUse /retry {job['id']} after fixing it.")
                except Exception:
                    log.warning("Failure notification unavailable")
            finally:
                self.current = None

    async def stop(self):
        self.stopping.set()
        if self.current:
            self.current.cancel()
