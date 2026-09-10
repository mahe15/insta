"""Audio-first source acquisition and exact selected-range video downloads."""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

from .config import Config
from .media import probe, validate_url, video_encoder_args
from .process import run
from .storage import write_json


def arguments(url: str, cfg: Config, stem: str) -> list[str]:
    validate_url(url, cfg)
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs", "--no-playlist",
            "--playlist-items", "1", "--no-progress", "--socket-timeout", "25", "--retries", "2",
            "--match-filters",
            f"duration <= {cfg.max_source_minutes * 60} & !is_live", "--ffmpeg-location", cfg.ffmpeg(),
            "--write-info-json", "--no-write-playlist-metafiles", "--restrict-filenames",
            "--output", stem + ".%(ext)s"]
    for runtime in ("node", "deno"):
        if shutil.which(runtime):
            args += ["--js-runtimes", runtime]
            break
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
    files = [p for p in directory.glob("audio-source.*") if p.suffix in {".m4a", ".webm", ".mp3", ".opus", ".ogg", ".aac", ".wav", ".flac"}]
    if len(files) != 1:
        raise ValueError("No unambiguous audio-only source was downloaded")
    return files[0].resolve(), {"duration": duration, "audio": True, "title": info.get("title", "Video")}


async def section(url: str, directory: Path, start: float, end: float, cfg: Config, cancelled) -> Path:
    if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= cfg.max_source_minutes * 60:
        raise ValueError("Invalid video range")
    marker = directory / "range.json"
    expected = {"url": url, "start": start, "end": end}
    if marker.exists() and json.loads(marker.read_text("utf-8")) == expected:
        cached = directory / "range.mp4"
        if cached.exists() and abs((await probe(cached, cfg, cancelled))["duration"] - (end - start)) <= .65:
            return cached
    # The extractor's filesize describes the entire source, not the selected range.
    # execute() bounds the actual range download on disk instead.
    args = arguments(url, cfg, "range") + [
        "--format", "bv*[protocol^=m3u8][height<=1080]+ba[protocol^=m3u8]/b[protocol^=m3u8][height<=1080]/bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start:.3f}-{end:.3f}", "--force-keyframes-at-cuts",
        "--force-overwrites",
        "--downloader-args", "ffmpeg_i:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -timeout 15000000",
        "--downloader-args", "ffmpeg_o:" + " ".join(video_encoder_args(cfg, 6500) + ["-c:a", "aac"]),
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
