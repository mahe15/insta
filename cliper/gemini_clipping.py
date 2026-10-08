"""Link-first Gemini website selection; download only reviewed time ranges."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlsplit

import json_repair
from pydantic import Field

from .browser_provider import BrowserProviderError
from .creative import text_matches
from .editorial import CLIP_BRIEF, attention_report, choose_hook, similarity, tokens
from .gemini_images import RESPONSE, SEND, GeminiImages
from .models import Analysis, Clip, Model, Preferences, Ratings, Segment, Transcript, Word
from .process import JobCancelled
from .storage import write_json

log = logging.getLogger(__name__)


def parse_time_str(val) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if ":" in val:
            parts = [float(p) for p in val.split(":")]
            if len(parts) == 2:
                return parts[0] * 60 + parts[1]
            if len(parts) == 3:
                return parts[0] * 3600 + parts[1] * 60 + parts[2]
        try:
            return float(val)
        except ValueError:
            pass
    return 0.0


def extract_json_candidate(text: str) -> str:
    """Extract JSON from raw text, trying markdown fences, then outermost braces."""
    content = text.strip().replace("\r\n", "\n")
    fences = re.findall(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL | re.IGNORECASE)
    for fence in reversed(fences):
        cleaned = fence.strip()
        if (cleaned.startswith("{") and cleaned.endswith("}")) or (cleaned.startswith("[") and cleaned.endswith("]")):
            return cleaned
    content = re.sub(r"^(?:Gemini said\s*|json\s*|JSON\s*)", "", content).strip()
    first = content.find("{")
    last = content.rfind("}")
    if first != -1 and last > first:
        return content[first : last + 1]
    return content


def sanitize_gemini_moment(m: dict) -> dict:
    clean = {}
    clean["moment_type"] = m.get("moment_type") if m.get("moment_type") in {"reaction", "challenge", "fan_encounter", "football", "wholesome", "other"} else "other"
    clean["payoff_time"] = parse_time_str(m["payoff_time"]) if m.get("payoff_time") is not None else None
    clean["start"] = parse_time_str(m.get("start", 0))
    clean["end"] = parse_time_str(m.get("end", 0))
    clean["title"] = str(m.get("title", "Clip"))[:90] or "Clip"
    variants = m.get("hook_variants", [])
    if isinstance(variants, list):
        clean["hook_variants"] = [str(v) for v in variants[:3]]
    else:
        clean["hook_variants"] = []
    clean["reason"] = str(m.get("reason", "Key moment"))[:500] or "Key moment"

    r = m.get("ratings", {})
    if not isinstance(r, dict):
        r = {}
    ratings_dict = {}
    for k in ("hook", "payoff", "standalone", "emotion", "usefulness"):
        val = r.get(k, 80)
        try:
            val = float(val)
            if val <= 10.0:
                val = val * 10
            ratings_dict[k] = max(0, min(100, round(val)))
        except (ValueError, TypeError):
            ratings_dict[k] = 80
    clean["ratings"] = ratings_dict

    raw_captions = m.get("captions", [])
    clean_captions = []
    if isinstance(raw_captions, list):
        for c in raw_captions:
            if not isinstance(c, dict):
                continue
            c_start = parse_time_str(c.get("start", clean["start"]))
            c_end = parse_time_str(c.get("end", clean["end"]))
            c_text = str(c.get("text", "")).strip()
            if not c_text or c_end <= c_start:
                continue
            words_raw = c.get("words", [])
            words_clean = []
            if isinstance(words_raw, list):
                for w in words_raw:
                    if isinstance(w, dict) and "text" in w:
                        w_start = parse_time_str(w.get("start", c_start))
                        w_end = parse_time_str(w.get("end", c_end))
                        words_clean.append({"start": w_start, "end": w_end, "text": str(w["text"])})
            clean_captions.append({"start": c_start, "end": c_end, "text": c_text, "words": words_clean})
    clean["captions"] = clean_captions

    transcript = str(m.get("transcript", "")).strip()
    if not transcript and clean_captions:
        transcript = " ".join(c["text"] for c in clean_captions)
    clean["transcript"] = transcript[:8000]

    cat = str(m.get("music_category", "chill_ambient")).strip()
    valid_cats = {"cinematic_epic", "emotional_sad", "suspense_thriller", "energetic_hype", "chill_ambient"}
    clean["music_category"] = cat if cat in valid_cats else "chill_ambient"
    clean["caption"] = str(m.get("caption", ""))[:1800]
    hashtags = m.get("hashtags", [])
    if isinstance(hashtags, list):
        clean["hashtags"] = [str(h) for h in hashtags[:5]]
    else:
        clean["hashtags"] = []
    clean["audience_value"] = str(m.get("audience_value", ""))[:300]
    return clean


def sanitize_gemini_payload(data: dict) -> dict:
    if not isinstance(data, dict):
        return data
    clean = {}
    clean["source_url"] = str(data.get("source_url", "")).strip()
    clean["accessible"] = bool(data.get("accessible", False))
    clean["access_note"] = str(data.get("access_note", ""))[:1000]
    clean["language"] = str(data.get("language", "en"))[:30] or "en"

    raw_clips = data.get("clips", [])
    clean_clips = []
    if isinstance(raw_clips, list):
        for m in raw_clips[:10]:
            if not isinstance(m, dict):
                continue
            clean_clips.append(sanitize_gemini_moment(m))
    clean["clips"] = clean_clips
    return clean


def parse_gemini_video_result(raw: str, request_id: str = "") -> VideoResult:
    """Robustly parse Gemini's response into a VideoResult model, tolerating text wrappers and extra keys."""
    candidate = extract_json_candidate(raw)
    candidate = re.sub(r"\.replace\([^)]*\)", "", candidate)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        repaired = json_repair.repair_json(candidate)
        value = json.loads(repaired)

    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object from Gemini")

    target = value.get("result", value)
    if not isinstance(target, dict):
        target = {k: v for k, v in value.items() if k != "request_id"}

    sanitized = sanitize_gemini_payload(target)
    return VideoResult.model_validate(sanitized, strict=False)


def youtube_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Clipping using Gemini needs a public HTTPS YouTube video link")
    parts = parsed.path.strip("/").split("/")
    video = ""
    if host == "youtu.be" and len(parts) == 1:
        video = parts[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video = parse_qs(parsed.query).get("v", [""])[0]
        elif len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}:
            video = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
        raise ValueError("Send one YouTube watch, Shorts or youtu.be video link; playlists are not supported")
    return "https://www.youtube.com/watch?v=" + video


class VideoMoment(Model):
    moment_type: Literal["reaction", "challenge", "fan_encounter", "football", "wholesome", "other"] = "other"
    payoff_time: float | None = Field(default=None, ge=0)
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    title: str = Field(min_length=1, max_length=90)
    hook_variants: list[str] = Field(default_factory=list, max_length=3)
    reason: str = Field(min_length=1, max_length=500)
    ratings: Ratings
    transcript: str = Field(default="", max_length=8000)
    captions: list[Segment] = Field(default_factory=list, max_length=250)
    music_category: str = "chill_ambient"
    caption: str = Field(default="", max_length=1800)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    audience_value: str = Field(default="", max_length=300)


class VideoResult(Model):
    source_url: str
    accessible: bool
    access_note: str = Field(max_length=1000)
    language: str = Field(min_length=1, max_length=30)
    clips: list[VideoMoment] = Field(max_length=10)


class GeminiVideo(GeminiImages):
    async def request_video(self, prompt, cancelled=lambda: False):
        request_id = uuid.uuid4().hex
        envelope = (prompt + "\nReturn ONLY one completed JSON object inside a ```json ... ``` code fence: "
                    + json.dumps({"request_id": request_id, "result": "OBJECT MATCHING SCHEMA BELOW"})
                    + "\nResult schema: " + json.dumps(VideoResult.model_json_schema()))
        if len(envelope) > self.cfg.browser_max_chars:
            raise ValueError("Gemini clipping prompt exceeds browser text budget")
        page, composer = await self.prepare([])
        try:
            if cancelled():
                raise JobCancelled()
            await composer.fill(envelope)
            await page.locator(os.getenv("GEMINI_SEND_SELECTOR", SEND)).first.click()
            response = page.locator(RESPONSE).last
            deadline = time.monotonic() + self.cfg.browser_timeout
            previous, stable = "", time.monotonic()
            attempt = 0
            while time.monotonic() < deadline:
                if cancelled():
                    raise JobCancelled()
                if await response.count():
                    raw = await response.inner_text()
                    code = response.locator("code")
                    if await code.count() == 1:
                        raw = await code.inner_text()
                    if len(raw) > 300000:
                        raise BrowserProviderError("Gemini clipping response exceeded the JSON size limit")
                    if raw != previous:
                        previous, stable = raw, time.monotonic()
                    copied = await response.locator('button[aria-label*="Copy" i], [data-test-id*="copy" i]').count()
                    stopped = await page.locator('button[aria-label*="Stop response" i]:visible, button[aria-label*="Stop generating" i]:visible').count()
                    if copied and not stopped and time.monotonic() - stable >= 2:
                        try:
                            return parse_gemini_video_result(raw, request_id)
                        except Exception as exc:
                            log.warning("Attempt %d failed Gemini JSON validation: %s", attempt, exc)
                            try:
                                raw_log_dir = self.cfg.data_dir / "logs"
                                raw_log_dir.mkdir(parents=True, exist_ok=True)
                                (raw_log_dir / "gemini_last_failed_raw.txt").write_text(raw, encoding="utf-8")
                            except Exception:
                                pass
                            if attempt == 0 and not page.is_closed():
                                attempt += 1
                                try:
                                    repair_msg = (
                                        f"A previous attempt failed validation: {str(exc)[:200]}. "
                                        "Please return ONLY a valid JSON object matching the exact schema with all clips, inside a ```json ... ``` code fence."
                                    )
                                    await composer.fill(repair_msg)
                                    await page.locator(os.getenv("GEMINI_SEND_SELECTOR", SEND)).first.click()
                                    response = page.locator(RESPONSE).last
                                    previous, stable = "", time.monotonic()
                                    deadline = time.monotonic() + 120
                                    continue
                                except Exception:
                                    pass
                            raise BrowserProviderError(f"Gemini returned invalid clip JSON ({exc}). Retry this job; no ranges were downloaded.") from None
                await asyncio.sleep(.5)
            raise BrowserProviderError("Gemini did not finish clip JSON. Check the website session and account limits, then retry.")
        finally:
            await page.close()


def normalize_segments(segments: list[Segment], moment_start: float, moment_end: float) -> list[Segment]:
    """Split long caption segments into readable short subtitle phrases while preserving exact text."""
    normalized: list[Segment] = []
    for s in segments:
        text = s.text.strip()
        if not text:
            continue
        duration = s.end - s.start
        toks = tokens(text)
        if (duration > 5.0 or len(toks) > 10) and duration > 0:
            chunks_count = max(1, math.ceil(max(duration / 4.5, len(toks) / 8.0)))
            words_list = text.split()
            if chunks_count > 1 and len(words_list) >= chunks_count:
                time_step = duration / chunks_count
                words_per_chunk = math.ceil(len(words_list) / chunks_count)
                for i in range(chunks_count):
                    chunk_words = words_list[i * words_per_chunk : (i + 1) * words_per_chunk]
                    if not chunk_words:
                        continue
                    chunk_text = " ".join(chunk_words)
                    sub_start = round(s.start + i * time_step, 3)
                    sub_end = round(min(s.end, s.start + (i + 1) * time_step), 3) if i < chunks_count - 1 else s.end
                    sub_w = []
                    if s.words and len(s.words) == len(words_list):
                        sub_w = s.words[i * words_per_chunk : (i + 1) * words_per_chunk]
                    else:
                        sub_w = [Word(start=sub_start, end=sub_end, text=chunk_text)]
                    normalized.append(Segment(
                        start=sub_start,
                        end=sub_end,
                        text=chunk_text,
                        words=sub_w
                    ))
                continue
        normalized.append(s)
    return normalized


def validate_result(result: VideoResult, url: str, info: dict, prefs: Preferences):
    if youtube_url(result.source_url) != url:
        raise ValueError("Gemini analyzed a different YouTube video; no clips accepted")
    if not result.accessible:
        note = f": {result.access_note}" if result.access_note else ""
        raise ValueError(f"Gemini could not access this video{note}. Try the audio-first clipping mode.")
    duration = info["duration"]
    clips, segments = [], []
    from .speed_profile import score
    for moment in sorted(result.clips, key=lambda c: score(c.ratings, prefs), reverse=True):
        if not 0 <= moment.start < moment.end <= duration:
            raise ValueError("Gemini clip timestamps fall outside the source video")
        if not prefs.min_seconds <= moment.end - moment.start <= prefs.max_seconds:
            raise ValueError("Gemini clip duration does not match your length settings")
        normalized_captions = normalize_segments(moment.captions, moment.start, moment.end)
        if not normalized_captions and prefs.editorial_profile != "ishowspeed":
            raise ValueError("Normal clipping requires observed speech captions")
        timed = Transcript(language=result.language, duration=duration, segments=normalized_captions)
        previous_end = moment.start
        for s in timed.segments:
            if s.start < previous_end - .02 or s.start < moment.start or s.end > moment.end:
                raise ValueError("Gemini captions must be ordered, non-overlapping and inside their clip")
            if not s.text.strip() or len(tokens(s.text)) > 24 or s.end - s.start > 20:
                raise ValueError("Gemini captions must be short readable phrases")
            if s.words:
                if not text_matches(" ".join(w.text for w in s.words), s.text):
                    raise ValueError("Gemini timed words do not match caption text")
                if any(b.start < a.end - .02 for a, b in zip(s.words, s.words[1:], strict=False)):
                    raise ValueError("Gemini word timestamps overlap")
            else:
                # Preserve actual phrase timing; never fabricate per-word timing.
                s.words = [Word(start=s.start, end=s.end, text=s.text)]
            previous_end = s.end
        text = " ".join(s.text for s in timed.segments)
        if (text or moment.transcript) and not text_matches(text, moment.transcript):
            sim = similarity(text, moment.transcript)
            has_currency_diff = any(c in text or c in moment.transcript for c in ("$", "£", "€", "¥")) and not text_matches(text, moment.transcript)
            if sim >= 0.75 and not has_currency_diff:
                moment.transcript = text
            else:
                raise ValueError("Gemini transcript differs from its timed captions")
        if any(min(moment.end, c.end) > max(moment.start, c.start) or similarity(text, c.text) > .85 for c in clips):
            continue
        title, variants = choose_hook(moment.title, moment.hook_variants, text)
        report = attention_report(timed.segments, moment.start, moment.end, title)
        report["caption_source"] = "gemini_website"
        report["caption_verification"] = "selected_range_pending" if prefs.gemini_verify_captions else "unverified"
        if not prefs.gemini_verify_captions:
            report["automatic_ready"] = False
            report["flags"].append("gemini_timing_needs_manual_review")
        from .display_text import display_clip
        clips.append(display_clip(Clip(id=len(clips) + 1, start=moment.start, end=moment.end, title=title,
            hook_variants=variants, reason=moment.reason, hook_text=timed.segments[0].text if timed.segments else "",
            score=score(moment.ratings, prefs), ratings=moment.ratings, text=text,
            selection_method="gemini_browser_youtube", music_category=moment.music_category,
            caption=moment.caption, hashtags=moment.hashtags, audience_value=moment.audience_value, editorial=report, moment_type=moment.moment_type,
            payoff_time=moment.payoff_time if moment.payoff_time is not None and moment.start <= moment.payoff_time < moment.end else None), prefs, result.language))
        segments.extend(timed.segments)
        if len(clips) == prefs.clips:
            break
    if not clips:
        raise ValueError("Gemini returned no usable complete clips. Retry or use audio-first clipping.")
    transcript = Transcript(language=result.language, duration=duration, segments=sorted(segments, key=lambda s: s.start))
    return Analysis(title=info["title"], language=result.language, duration=duration,
                    method="gemini_browser_youtube", model="Gemini website session", clips=clips), transcript


async def analyze(url, directory: Path, prefs, cfg, progress, cancelled):
    from .remote_media import metadata
    url = youtube_url(url)
    await progress("Clipping using Gemini · reading YouTube metadata without downloading media")
    info = await metadata(url, directory / "youtube-metadata", cfg, cancelled)
    if info.get("id") != parse_qs(urlsplit(url).query)["v"][0]:
        raise ValueError("YouTube metadata does not match the submitted video")
    if any(t >= info["duration"] for t in prefs.focus_times):
        raise ValueError("A focus timestamp is beyond this video's duration")
    raw_path = directory / "gemini-clips.json"
    from .prompts import get_prompt
    from .speed_profile import instructions
    active_clip_brief = get_prompt("clip_brief") or CLIP_BRIEF
    tmpl = get_prompt("gemini_clipping_prompt")
    if "{url}" in tmpl and "{duration}" in tmpl:
        try:
            body = tmpl.format(
                url=url,
                duration=info["duration"],
                clips_count=prefs.clips,
                min_seconds=prefs.min_seconds,
                max_seconds=prefs.max_seconds,
                hook_style=prefs.hook_style,
                focus_times=prefs.focus_times,
            )
        except Exception:
            body = tmpl
    else:
        body = (f"\n@YouTube {url}\nAnalyze the actual YouTube video at " + url
            + f"\nKnown source duration: {info['duration']} seconds. Select up to {prefs.clips} strongest complete moments, "
            + f"each {prefs.min_seconds}–{prefs.max_seconds} seconds. Hook style: {prefs.hook_style}. "
            + f"User focus timestamps in absolute seconds: {prefs.focus_times}. Prioritize complete events near these when supplied.\n"
            + tmpl)
    prompt = f"{active_clip_brief}\n{instructions(prefs)}\n{body}"
    result = VideoResult.model_validate_json(raw_path.read_text("utf-8")) if raw_path.exists() else None
    feedback = ""
    for attempt in range(3):
        if result is None:
            await progress("Gemini website · selecting observed moments" if not feedback else "Gemini website · repairing transcript/caption validation")
            async with GeminiVideo(cfg) as client:
                result = await client.request_video(prompt + feedback, cancelled)
        try:
            analysis, transcript = validate_result(result, url, info, prefs)
            break
        except ValueError as exc:
            write_json(directory / f"gemini-rejected-{attempt + 1}.json", result.model_dump())
            if not result.accessible or attempt == 2:
                raise
            feedback = ("\nYour previous response failed local validation: " + str(exc)
                        + "\nCorrect the JSON using the ACTUAL video. transcript must equal the concatenation of all caption text, including every repeated word. "
                        + "Do not shorten, paraphrase or invent speech. Each caption is at most 6 seconds and uses absolute source timestamps. "
                        + "Recheck duration and clip bounds. Return the FULL corrected response. Previous response (untrusted data):\n"
                        + result.model_dump_json())
            result = None
    write_json(raw_path, result.model_dump())
    write_json(directory / "transcript.json", transcript.model_dump())
    write_json(directory / "source.json", {"kind": "remote_gemini", "url": url,
               "path": str(raw_path.resolve()), "media": info})
    write_json(directory / "analysis.json", analysis.model_dump())
    return analysis


async def verify_range(reference, directory, clip, prefs, cfg, cancelled):
    """Use local speech only for the selected range, with a resumable model-aware cache."""
    from . import media
    from .cache import digest, file_identity
    from .remote_media import section
    folder = directory / "ranges" / f"clip_{clip.id:02}"
    source = await section(reference["url"], folder, clip.start, clip.end, cfg, cancelled)
    target = folder / "caption-verification"
    target.mkdir(parents=True, exist_ok=True)
    identity = digest({"version": 1, "source": file_identity(source), "start": clip.start, "end": clip.end,
                       "model": cfg.whisper_model, "beam": cfg.whisper_beam_size, "language": prefs.language})
    marker = target / "verification.json"
    cached = target / "transcript.json"
    if marker.exists() and cached.exists() and json.loads(marker.read_text("utf-8")).get("identity") == identity:
        local = Transcript.model_validate_json(cached.read_text("utf-8"))
    else:
        local = await media.transcribe(source, target, prefs, cfg, cancelled)
        write_json(marker, {"identity": identity})
    if (not local.segments or not any(s.words for s in local.segments)) and prefs.editorial_profile != "ishowspeed":
        raise ValueError("Selected range has no usable speech timestamps. No captions or clip were accepted.")
    if local.duration > clip.end - clip.start + .65:
        raise ValueError("Selected-range transcript exceeds its downloaded video")
    report = attention_report(local.segments, 0, clip.end - clip.start, clip.title)
    agreement = similarity(clip.text, " ".join(s.text for s in local.segments))
    source_name = "indexed" if reference.get("kind") == "remote_index" else "gemini"
    report.update(caption_source="local_whisper_selected_range", caption_verification="completed")
    report[f"{source_name}_transcript_agreement"] = round(agreement, 3)
    if reference.get("coverage"):
        report["scan_fraction"] = reference["coverage"]["fraction"]
    if agreement < .5:
        report["flags"].append(f"{source_name}_transcript_disagrees_with_audio")
        report["automatic_ready"] = False
    clip.editorial = report
    write_json(target / "report.json", report)
    return source, local
