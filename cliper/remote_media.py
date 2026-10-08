"""Audio-first source acquisition and exact selected-range video downloads."""
from __future__ import annotations

import json
import math
import shutil
import sys
import wave
from pathlib import Path

from .config import Config
from .media import probe, validate_url, video_encoder_args
from .process import run
from .storage import write_json


def arguments(url: str, cfg: Config, stem: str, filter_duration: bool = True) -> list[str]:
    validate_url(url, cfg)
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs", "--no-playlist",
            "--playlist-items", "1", "--no-progress", "--socket-timeout", "45", "--retries", "3",
            "--extractor-retries", "3", "--retry-sleep", "2"]
    if filter_duration:
        args += ["--match-filters", f"duration <= {cfg.max_source_minutes * 60} & !is_live"]
    args += ["--ffmpeg-location", cfg.ffmpeg(),
             "--write-info-json", "--no-write-playlist-metafiles", "--restrict-filenames",
             "--output", stem + ".%(ext)s"]
    for runtime in ("node", "deno"):
        if shutil.which(runtime):
            args += ["--js-runtimes", runtime]
            break
    if any(h in url.lower() for h in ("youtube.com", "youtu.be")):
        args += ["--extractor-args", "youtube:player_client=android,web"]
    return args


async def execute(args, directory, cfg, cancelled, timeout: int = 600):
    directory.mkdir(parents=True, exist_ok=True)

    def bounded():
        if cancelled():
            return True
        cfg.check_disk()
        if sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) > cfg.max_download_mb * 1024**2 * 2.2:
            raise ValueError("Download exceeded the disk budget")
        return False

    await run(args, cwd=directory, timeout=timeout, cancelled=bounded)


async def audio(url: str, directory: Path, cfg: Config, cancelled) -> tuple[Path, dict]:
    args = arguments(url, cfg, "audio-source") + ["--max-filesize", f"{cfg.max_download_mb}M",
                                                "--format", "bestaudio", "--", url]
    await execute(args, directory, cfg, cancelled)
    info_path = directory / "audio-source.info.json"
    if not info_path.is_file():
        raise ValueError("Source metadata unavailable; audio download was not completed")
    info = json.loads(info_path.read_text("utf-8"))
    duration = float(info.get("duration") or 0)
    if not math.isfinite(duration) or not 0 < duration <= cfg.max_source_minutes * 60 or info.get("is_live"):
        raise ValueError("Source duration is missing, live, or exceeds the configured limit")
    files = [p for p in directory.glob("audio-source.*") if p.suffix in {".m4a", ".webm", ".mp3", ".opus", ".ogg", ".aac", ".wav", ".flac", ".mp4", ".mkv"}]
    if len(files) != 1:
        raise ValueError("No unambiguous audio source was downloaded")
    return files[0].resolve(), {"duration": duration, "audio": True, "title": info.get("title", "Video")}


async def metadata(url: str, directory: Path, cfg: Config, cancelled) -> dict:
    """Read extractor metadata without downloading video or audio streams."""
    (directory / "source.info.json").unlink(missing_ok=True)
    await execute(arguments(url, cfg, "source", filter_duration=False) + ["--skip-download", "--", url], directory, cfg, cancelled)
    path = directory / "source.info.json"
    if not path.is_file():
        raise ValueError("Video metadata is unavailable. Send a public, saved VOD or clip URL.")
    info = json.loads(path.read_text("utf-8"))
    duration = float(info.get("duration") or 0)
    if not math.isfinite(duration) or duration <= 0 or info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming"}:
        raise ValueError("Source is live or missing its duration")
    if duration > cfg.max_source_minutes * 60:
        raise ValueError(f"Source duration ({round(duration / 60, 1)}m) exceeds MAX_SOURCE_MINUTES ({cfg.max_source_minutes}m). Set MAX_SOURCE_MINUTES={math.ceil(duration / 60)} in your .env to process this video.")
    return {"duration": duration, "title": info.get("title", "Video"), "id": info.get("id"), "audio": True,
            "extractor": info.get("extractor_key", info.get("extractor", "unknown")),
            "chapters": info.get("chapters") or [], "heatmap": info.get("heatmap") or [],
            "language": info.get("language"), "subtitles": list((info.get("subtitles") or {}).keys()),
            "automatic_captions": list((info.get("automatic_captions") or {}).keys())}


async def captions(url, directory, info, language, cfg, cancelled):
    """Fetch one advertised text track, not media, with a bounded response on disk."""
    manual = info.get("subtitles", [])
    automatic = info.get("automatic_captions", [])
    wanted = language if language != "auto" else info.get("language")
    candidates = [wanted, (wanted or "").split("-")[0], "en", "en-orig"]
    available = manual + automatic
    chosen = next((x for x in candidates if x and x in available), None)
    if chosen is None and language == "auto":
        chosen = next((x for x in available if x != "live_chat"), None)
    if chosen is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob("captions.*.vtt"):
        path.unlink()
    args = arguments(url, cfg, "captions", filter_duration=False) + ["--skip-download", "--sub-format", "vtt",
        "--sub-langs", re_escape(chosen), "--write-subs" if chosen in manual else "--write-auto-subs", "--", url]
    await execute(args, directory, cfg, cancelled, timeout=180)
    paths = list(directory.glob("captions.*.vtt"))
    if len(paths) != 1 or paths[0].stat().st_size > 10 * 1024**2:
        return None
    return paths[0], chosen


def re_escape(value):
    import re
    return re.escape(value)


async def audio_window(url, directory, start, end, cfg, cancelled):
    """Accurately decode only this interval's audio; never save a whole VOD video."""
    if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= cfg.max_source_minutes * 60:
        raise ValueError("Invalid scan interval")
    directory.mkdir(parents=True, exist_ok=True)
    marker, target = directory / "audio-range.json", directory / "scan.wav"
    expected = {"version": 1, "url": url, "start": start, "end": end}
    def valid():
        try:
            with wave.open(str(target)) as wav:
                return abs(wav.getnframes() / wav.getframerate() - (end - start)) <= .75
        except (OSError, EOFError, wave.Error):
            return False
    if marker.exists() and json.loads(marker.read_text("utf-8")) == expected and valid():
        return target.resolve()
    acquired = directory / "scan-input.m4a"
    acquired.unlink(missing_ok=True)
    args = arguments(url, cfg, "scan-input.m4a")
    # A fixed filename is intentional: the downloader output is explicitly an audio-only MP4 container.
    args[args.index("--output") + 1] = acquired.name
    args += ["--format", "bestaudio/b[height<=360]/worst", "--fixup", "never", "--force-overwrites",
             "--downloader", "ffmpeg", "--download-sections", f"*{start:.3f}-{end:.3f}",
             "--downloader-args", "ffmpeg_o:-vn -c:a aac -b:a 64k -ac 1 -ar 16000 -f ipod", "--", url]
    await execute(args, directory, cfg, cancelled, timeout=max(600, int(end - start) * 3))
    await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-i", str(acquired), "-map", "0:a:0",
               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(target)], cancelled=cancelled)
    if not valid():
        raise ValueError("Audio scan duration does not match its requested interval; refusing misaligned timestamps")
    write_json(marker, expected)
    acquired.unlink(missing_ok=True)
    return target.resolve()


async def section(url: str, directory: Path, start: float, end: float, cfg: Config, cancelled) -> Path:
    if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= cfg.max_source_minutes * 60:
        raise ValueError("Invalid video range")
    marker = directory / "range.json"
    expected = {"url": url, "start": start, "end": end}
    if marker.exists() and json.loads(marker.read_text("utf-8")) == expected:
        cached = directory / "range.mp4"
        if cached.exists() and abs((await probe(cached, cfg, cancelled))["duration"] - (end - start)) <= .65:
            return cached
    # A skipped/failed extraction must not relabel an old range as the new request.
    for extension in ("mp4", "webm", "mkv", "mov"):
        (directory / f"range.{extension}").unlink(missing_ok=True)
    # The extractor's filesize describes the entire source, not the selected range.
    # execute() bounds the actual range download on disk instead.
    args = arguments(url, cfg, "range") + [
        "--format", "bv*[protocol^=m3u8][height<=1080]+ba[protocol^=m3u8]/b[protocol^=m3u8][height<=1080]/bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start:.3f}-{end:.3f}", "--force-keyframes-at-cuts",
        "--force-overwrites",
        "--downloader-args", "ffmpeg_i:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -timeout 15000000",
        "--downloader-args", "ffmpeg_o:" + " ".join(video_encoder_args(cfg, 6500, fast=True) + ["-c:a", "aac"]),
        "--", url]
    await execute(args, directory, cfg, cancelled)
    source = directory / "range.mp4"
    if not source.exists():
        matches = [p for p in directory.glob("range.*") if p.suffix in {".webm", ".mkv", ".mov"}]
        if len(matches) != 1:
            raise ValueError("Selected video range was not downloaded; no full-video fallback was attempted")
        await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-i", str(matches[0]),
                   "-c", "copy", str(source)], cancelled=cancelled)
    actual = await probe(source, cfg, cancelled)
    if abs(actual["duration"] - (end - start)) > .65:
        raise ValueError("The host did not return the exact requested video range. No misaligned clip will be rendered.")
    write_json(marker, expected)
    return source.resolve()
