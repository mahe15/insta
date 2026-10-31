"""Authenticated YouTube Agent endpoints for CLIPER Web Studio."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import Field

from .models import Model
from .youtube_agent import (
    HOOK_FORMULAS,
    analyze_swipe_outliers,
    detect_deadair,
    generate_youtube_chapters,
    get_voice_profile,
    lint_title_and_thumb,
    lint_titles,
    parse_retention_csv,
    save_voice_profile,
    score_hook,
    score_hooks,
)

log = logging.getLogger("cliper.youtube_agent_web")


class HookScoreRequest(Model):
    hook: str = Field(default="", max_length=1000)
    hooks: list[str] = Field(default_factory=list, max_length=50)


class PackageLintRequest(Model):
    title: str = Field(min_length=1, max_length=200)
    thumb: str | None = Field(default=None, max_length=100)
    thumb_text: str | None = Field(default=None, max_length=100)


class DeadAirRequest(Model):
    job_id: str | None = None
    srt: str | None = Field(default=None, max_length=500000)
    floor: float = Field(default=0.45, ge=0.1, le=5.0)


class ChaptersRequest(Model):
    job_id: str | None = None
    srt: str | None = Field(default=None, max_length=500000)
    target: int = Field(default=7, ge=3, le=50)


class RetentionRequest(Model):
    csv_text: str = Field(min_length=10, max_length=500000)
    duration: float | None = Field(default=None, ge=1.0, le=86400.0)
    job_id: str | None = None


class SwipeRequest(Model):
    videos: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    min_multiple: float = Field(default=1.5, ge=1.0, le=50.0)


class VoiceProfileRequest(Model):
    content: str = Field(max_length=50000)


def _load_job_cues(store: Any, job_id: str, owner: int) -> list[tuple[float, float, str]]:
    try:
        folder = store.directory(job_id)
    except Exception:
        raise HTTPException(400, "Invalid job ID")

    # Ensure ownership check
    try:
        job = store.get(job_id, owner)
    except Exception:
        raise HTTPException(404, "Job not found")

    analysis_file = folder / "analysis.json"
    if analysis_file.is_file():
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
            segments = data.get("transcript", {}).get("segments", [])
            return [(float(s["start"]), float(s["end"]), (s.get("text") or "").strip()) for s in segments]
        except Exception as e:
            log.warning("Could not read transcript from %s: %s", analysis_file, e)

    srt_file = folder / "transcript.srt"
    if srt_file.is_file():
        try:
            from .youtube_agent import parse_cues_from_text
            return parse_cues_from_text(srt_file.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            log.warning("Could not parse srt from %s: %s", srt_file, e)

    raise HTTPException(404, "No transcript found for this job yet. Analysis must complete first.")


def install_routes(app, cfg, store, owner):
    """Mount YouTube Agent API routes inside the authenticated Web Studio boundary."""

    @app.get("/api/yt/status")
    def yt_status():
        vp = get_voice_profile()
        has_voice = bool(vp and "No voice profile created yet" not in vp)
        return {
            "ok": True,
            "status": "active",
            "skills_count": 11,
            "version": "1.0",
            "formulas_count": len(HOOK_FORMULAS),
            "has_voice_profile": has_voice,
            "tools": ["hookscore", "package-lint", "deadair", "chapters", "retention", "swipe"],
        }

    @app.post("/api/yt/hookscore")
    def api_hookscore(body: HookScoreRequest):
        if body.hooks:
            scored = score_hooks(body.hooks)
            return {"results": scored, "count": len(scored)}
        if not body.hook.strip():
            raise HTTPException(400, "Please provide a hook or a list of hooks to score.")
        return score_hook(body.hook)

    @app.post("/api/yt/package-lint")
    def api_package_lint(body: PackageLintRequest):
        return lint_title_and_thumb(body.title, body.thumb or body.thumb_text)

    @app.post("/api/yt/deadair")
    def api_deadair(body: DeadAirRequest):
        cues: list[tuple[float, float, str]] = []
        if body.job_id:
            cues = _load_job_cues(store, body.job_id, owner)
        elif body.srt:
            from .youtube_agent import parse_cues_from_text
            cues = parse_cues_from_text(body.srt)
        else:
            raise HTTPException(400, "Provide either a job_id or srt transcript text.")

        if not cues:
            raise HTTPException(400, "No valid speech cues found to analyze.")

        return detect_deadair(cues, floor=body.floor)

    @app.post("/api/yt/chapters")
    def api_chapters(body: ChaptersRequest):
        cues: list[tuple[float, float, str]] = []
        if body.job_id:
            cues = _load_job_cues(store, body.job_id, owner)
        elif body.srt:
            from .youtube_agent import parse_cues_from_text
            cues = parse_cues_from_text(body.srt)
        else:
            raise HTTPException(400, "Provide either a job_id or srt transcript text.")

        if not cues:
            raise HTTPException(400, "No valid speech cues found to generate chapters.")

        return generate_youtube_chapters(cues, target=body.target)

    @app.post("/api/yt/retention")
    def api_retention(body: RetentionRequest):
        transcript_cues: list[tuple[float, float, str]] | None = None
        if body.job_id:
            try:
                transcript_cues = _load_job_cues(store, body.job_id, owner)
            except Exception:
                pass

        result = parse_retention_csv(body.csv_text, transcript_cues=transcript_cues, duration=body.duration)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    @app.post("/api/yt/swipe")
    def api_swipe(body: SwipeRequest):
        return analyze_swipe_outliers(body.videos, min_multiple=body.min_multiple)

    @app.get("/api/yt/formulas")
    def api_formulas():
        return {"count": len(HOOK_FORMULAS), "formulas": HOOK_FORMULAS}

    @app.get("/api/yt/voice")
    def api_get_voice():
        return {"content": get_voice_profile()}

    @app.post("/api/yt/voice")
    def api_save_voice(body: VoiceProfileRequest):
        save_voice_profile(body.content)
        return {"ok": True, "message": "Voice profile updated and synced successfully."}
