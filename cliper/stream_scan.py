"""Caption-first indexing and resumable, bounded audio scans for long VODs."""
from __future__ import annotations

import asyncio
import html
import json
import math
import re
import sys
from pathlib import Path

from .cache import digest
from .models import Analysis, Segment, Transcript, Word
from .process import JobCancelled, run
from .storage import write_json

VERSION = "stream-scan-v3-speed-latin"


def timestamp(value):
    parts = value.replace(",", ".").split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, MM:SS or HH:MM:SS")
    numbers = [float(x) for x in parts]
    if any(not math.isfinite(x) or x < 0 for x in numbers) or any(x >= 60 for x in numbers[1:]):
        raise ValueError("Invalid timestamp")
    return sum(x * 60 ** i for i, x in enumerate(reversed(numbers)))


def parse_vtt(text, duration, language):
    cues, previous_text, previous_end = [], "", -1
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = block.splitlines()
        index = next((i for i, line in enumerate(lines) if " --> " in line), None)
        if index is None:
            continue
        try:
            left, right = lines[index].split(" --> ", 1)
            start, end = timestamp(left.strip()), min(duration, timestamp(right.split()[0]))
        except (ValueError, IndexError):
            continue
        body = html.unescape(re.sub(r"<[^>]*>", "", " ".join(lines[index + 1:]))).strip()
        body = " ".join(body.split())
        if not body or not 0 <= start < end <= duration:
            continue
        if start > previous_end + .5:
            previous_text = ""
        if body == previous_text:
            previous_end = end
            continue
        # Rolling auto-caption tracks repeat the previous phrase as a prefix.
        prior, current = previous_text.split(), body.split()
        overlap = next((n for n in range(min(len(prior), len(current)), 0, -1) if prior[-n:] == current[:n]), 0)
        previous_text = body
        previous_end = end
        if overlap:
            body = " ".join(current[overlap:])
        if body:
            cues.append(Segment(start=start, end=end, text=body))
    return Transcript(language=language, duration=duration, segments=sorted(cues, key=lambda s: s.start))


def salience(text):
    """Cheap candidate prioritization, not a virality score or semantic judgment."""
    words = re.findall(r"\w+", text.casefold())
    if not words:
        return 0
    signals = len(re.findall(r"\b(why|how|mistake|learned|realized|instead|finally|won|lost|because|but|never)\b|[?!]", text, re.I))
    return min(10, signals) + len(set(words)) / len(words) - 3 * bool(re.search(r"starting soon|be right back|sponsor", text, re.I))


def plan_windows(info, prefs, captions=None):
    duration = float(info["duration"])
    span = float(max(180, prefs.max_seconds + 60))
    budget = min(duration, prefs.scan_minutes * 60)
    count = max(1, int(budget // span))
    span = min(span, duration)
    if any(t >= duration for t in prefs.focus_times):
        raise ValueError("A /focus timestamp is beyond this video's duration; reset /focus or correct it")
    if duration <= budget:
        return [{"start": start, "end": min(duration, start + span), "reason": "complete coverage"}
                for start in range(0, math.ceil(duration), int(span))]
    chosen = []
    if len(prefs.focus_times) > count:
        raise ValueError("Too many focus timestamps for this scan budget. Increase /scan or reduce /focus.")
    def add(center, reason):
        start = round(max(0, min(duration - span, center - span / 2)), 3)
        end = min(duration, start + span)
        if len(chosen) < count and all(min(end, p["end"]) - max(start, p["start"]) <= 0 for p in chosen):
            chosen.append({"start": start, "end": end, "reason": reason})
    for t in prefs.focus_times:
        add(t, "user focus")
    # Reserve at least half the remaining slots for time diversity, including later hours.
    slots = max(min(2, count), math.ceil((count - len(chosen)) / 2))
    for i in range(slots):
        add((i + .5) * duration / slots, "timeline coverage")
    from .speed_profile import stream_signal
    def priority(text):
        return salience(text) + (stream_signal(text) if prefs.editorial_profile == "ishowspeed" else 0)
    signals = []
    for item in info.get("heatmap", []):
        try:
            t = (float(item["start_time"]) + float(item["end_time"])) / 2
            score = float(item["value"])
            if math.isfinite(t) and math.isfinite(score) and 0 <= t < duration:
                signals.append((score * 15, t, "replay signal"))
        except (KeyError, ValueError, TypeError):
            continue
    for chapter in info.get("chapters", []):
        try:
            t = float(chapter["start_time"]) + span / 2
            if math.isfinite(t) and 0 <= t < duration:
                signals.append((3 + priority(chapter.get("title", "")), t, "chapter"))
        except (KeyError, ValueError, TypeError):
            continue
    if captions:
        buckets = {}
        for s in captions.segments:
            buckets.setdefault(int(s.start // span), []).append(s.text)
        signals.extend((priority(" ".join(text)), (key + .5) * span, "caption signal") for key, text in buckets.items())
    for _, t, reason in sorted(signals, reverse=True):
        add(t, reason)
    # Fill the largest unexamined gaps first, rather than consuming early-time slots.
    candidates = [(i + .5) * duration / (count * 8) for i in range(count * 8)]
    while len(chosen) < count and candidates:
        center = max(candidates, key=lambda t: min(abs(t - (w["start"] + w["end"]) / 2) for w in chosen)
                     if chosen else min(t, duration - t))
        candidates.remove(center)
        add(center, "timeline coverage")
    return sorted(chosen, key=lambda p: p["start"])


def crop_captions(transcript, ranges):
    selected = []
    for window in ranges:
        selected.extend(s for s in transcript.segments if s.start >= window["start"] and s.end <= window["end"])
    return transcript.model_copy(update={"segments": sorted(selected, key=lambda s: s.start)})


def shift(transcript, start, end):
    segments = []
    for s in transcript.segments:
        if s.start + start >= end:
            continue
        words = [Word(start=w.start + start, end=min(end, w.end + start), text=w.text, confidence=w.confidence)
                 for w in s.words if w.start + start < end]
        segments.append(Segment(start=s.start + start, end=min(end, s.end + start), text=s.text, words=words))
    return segments


async def batch_transcribe(items, cfg, prefs, cancelled):
    if not items:
        return
    manifest = Path(items[0]["output"]).parent.parent / "transcription-batch.json"
    write_json(manifest, items)
    await run([sys.executable, "-m", "cliper.transcribe", "--manifest", str(manifest),
               "--model", cfg.whisper_model, "--device", cfg.whisper_device, "--compute", cfg.whisper_compute,
               "--device-index", str(cfg.gpu_device_index), "--language", prefs.language,
               "--beam-size", "1", "--cache", str(cfg.data_dir / "models")],
              timeout=max(1800, prefs.scan_minutes * 180), cancelled=cancelled)


async def analyze(url, directory, prefs, cfg, progress, cancelled):
    from . import remote_media
    from .selection import NoSuitableClips, deduplicate, select
    await progress("Inspecting VOD metadata and available captions · no video download")
    info = await remote_media.metadata(url, directory / "source-metadata", cfg, cancelled)
    key = digest({"version": VERSION, "url": url, "id": info.get("id"), "duration": info["duration"],
                  "language": prefs.language, "budget": prefs.scan_minutes, "focus": prefs.focus_times,
                  "max_seconds": prefs.max_seconds, "whisper_model": cfg.whisper_model,
                  "long_source_minutes": cfg.long_source_minutes})
    folder = directory / "scan" / key[:16]
    folder.mkdir(parents=True, exist_ok=True)
    subtitle_index = folder / "caption-index.json"
    indexed = None
    caption_error = None
    if subtitle_index.exists():
        indexed = Transcript.model_validate_json(subtitle_index.read_text("utf-8"))
    else:
        try:
            track = await remote_media.captions(url, folder / "captions", info, prefs.language, cfg, cancelled)
            if track:
                indexed = parse_vtt(track[0].read_text("utf-8-sig"), info["duration"], track[1])
                if indexed.segments:
                    write_json(subtitle_index, indexed.model_dump())
                else:
                    indexed = None
        except (RuntimeError, OSError, ValueError):
            caption_error = "Caption track unavailable or malformed; bounded audio scan used"
    # Short sources retain exhaustive analysis. Long sources obey the user's explicit budget.
    plan_prefs = prefs
    if info["duration"] <= cfg.long_source_minutes * 60 and not prefs.focus_times:
        plan_prefs = prefs.model_copy(update={"scan_minutes": max(prefs.scan_minutes, math.ceil(info["duration"] / 60))})
    plan_path = folder / "plan.json"
    # Freeze the original ranges on retries: host replay/chapter metadata can change.
    # Window indices must continue to refer to the same absolute media intervals.
    if plan_path.exists():
        ranges = json.loads(plan_path.read_text("utf-8"))["ranges"]
    else:
        ranges = plan_windows(info, plan_prefs, indexed)
    scanned = sum(w["end"] - w["start"] for w in ranges)
    coverage = {"version": VERSION, "source_seconds": info["duration"], "analyzed_seconds": scanned,
                "fraction": round(scanned / info["duration"], 6), "partial": scanned < info["duration"] - .01,
                "method": "caption_index" if indexed else "audio_windows", "ranges": ranges,
                "caption_index_available": bool(indexed), "caption_warning": caption_error,
                "note": "Candidate search covers these ranges; unexamined moments may be missed."}
    write_json(folder / "plan.json", coverage)
    await progress(f"{'Caption index' if indexed else 'Audio scan'} · {scanned / 60:.1f} of "
                   f"{info['duration'] / 60:.1f} minutes · {len(ranges)} windows")
    if indexed:
        transcript = crop_captions(indexed, ranges)
    else:
        semaphore = asyncio.Semaphore(cfg.scan_download_workers)
        async def acquire(index, window):
            async with semaphore:
                if cancelled():
                    raise JobCancelled()
                target = folder / f"window_{index:04}"
                cached = target / "transcript.json"
                if cached.exists():
                    Transcript.model_validate_json(cached.read_text("utf-8"))
                    return None
                await progress(f"Fetching scan audio {index + 1}/{len(ranges)} · {window['reason']}")
                audio = await remote_media.audio_window(url, target, window["start"], window["end"], cfg, cancelled)
                return {"audio": str(audio), "output": str(cached)}
        tasks = [asyncio.create_task(acquire(i, w)) for i, w in enumerate(ranges)]
        try:
            items = [item for item in await asyncio.gather(*tasks) if item]
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        await progress("Transcribing scan windows · one model load, VAD, fast discovery beam")
        await batch_transcribe(items, cfg, prefs, cancelled)
        segments, language = [], prefs.language
        for i, w in enumerate(ranges):
            local = Transcript.model_validate_json((folder / f"window_{i:04}" / "transcript.json").read_text("utf-8"))
            if local.duration > w["end"] - w["start"] + .75:
                raise ValueError("Scan transcript exceeds its downloaded audio interval")
            segments.extend(shift(local, w["start"], w["end"]))
            language = local.language
        transcript = Transcript(language=language, duration=info["duration"], segments=segments)
    transcript.coverage = coverage
    write_json(directory / "transcript.json", transcript.model_dump())
    write_json(directory / "source.json", {"kind": "remote_index", "url": url,
               "path": str((folder / "plan.json").resolve()), "media": info, "coverage": coverage})
    # Bound AI context per batch even when a user deliberately chooses a large scan budget.
    batches, current, chars = [], [], 0
    for segment in transcript.segments:
        size = len(segment.text) + 50
        if current and chars + size > 90000:
            batches.append(current)
            # Carry up to a clip's context into the next batch without adding new media time.
            current = [s for s in current if s.end >= current[-1].end - prefs.max_seconds]
            chars = sum(len(s.text) + 50 for s in current)
        current.append(segment)
        chars += size
    if current:
        batches.append(current)
    if not batches:
        raise ValueError("No speech found in the scanned windows. Increase /scan or add /focus timestamps.")
    clips = []
    for n, group in enumerate(batches):
        if cancelled():
            raise JobCancelled()
        batch_key = digest({"segments": [s.model_dump() for s in group], "prefs": prefs.model_dump(), "version": VERSION})
        cache = folder / f"selection_{n}_{batch_key[:12]}.json"
        if cache.exists():
            result = Analysis.model_validate_json(cache.read_text("utf-8"))
        else:
            try:
                result = await select(transcript.model_copy(update={"segments": group}), prefs, cfg, progress)
            except NoSuitableClips:
                # An uneventful batch must not hide good moments in a later batch.
                result = Analysis(title=info["title"], language=transcript.language,
                                  duration=info["duration"], method="no_complete_moments", clips=[])
            write_json(cache, result.model_dump())
        clips.extend(result.clips)
    if not clips:
        raise NoSuitableClips("No complete moments found in the scanned ranges. Increase /scan, add /focus, or widen /length.")
    result = Analysis(title=info["title"], language=transcript.language, duration=info["duration"],
        method="caption_first_stream_scan" if indexed else "bounded_stream_scan", coverage=coverage,
        model=cfg.ai(prefs.ai_provider, prefs.ai_model).model, clips=deduplicate(clips, prefs.clips))
    for clip in result.clips:
        clip.editorial["caption_verification"] = "selected_range_pending"
        clip.editorial["scan_fraction"] = coverage["fraction"]
    write_json(directory / "analysis.json", result.model_dump())
    return result
