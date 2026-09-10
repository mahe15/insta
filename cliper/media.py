from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .captions import write_captions
from .config import Config
from .models import Clip, Preferences, Transcript
from .process import run
from .storage import write_json
from .vision import center_expression


def validate_url(url: str, cfg: Config) -> str:
    if len(url) > 2048 or any(ord(c) < 32 for c in url):
        raise ValueError("Invalid video URL")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not any(host == h or host.endswith("." + h) for h in cfg.allowed_hosts)):
        raise ValueError("Send an HTTPS link from: " + ", ".join(cfg.allowed_hosts)
                         + ". For other sources, upload a video or use the local CLI.")
    return url


def dimensions(source: Path) -> dict:
    import cv2
    cap = cv2.VideoCapture(str(source))
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        info = {"width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps else 0}
        if min(info.values()) <= 0:
            raise ValueError("Could not read the video. Use a playable MP4/MOV/MKV file with audio.")
        return info
    finally:
        cap.release()


async def download(url: str, directory: Path, cfg: Config, cancelled) -> Path:
    validate_url(url, cfg)
    # Ignore user/global yt-dlp configs and plugins; never interpolate user text into a shell.
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-plugin-dirs", "--no-playlist",
            "--playlist-items", "1",
            "--no-progress", "--no-warnings", "--socket-timeout", "25", "--retries", "3",
            "--extractor-retries", "2", "--max-filesize", f"{cfg.max_download_mb}M",
            "--match-filters", f"duration <= {cfg.max_source_minutes * 60} & !is_live",
            "--format", "bv*[height<=1080]+ba/b[height<=1080]", "--merge-output-format", "mp4",
            "--ffmpeg-location", cfg.ffmpeg(), "--write-info-json", "--no-write-playlist-metafiles",
            "--output", "source.%(ext)s", "--restrict-filenames"]
    if shutil.which("node"):
        args += ["--js-runtimes", "node"]
    elif shutil.which("deno"):
        args += ["--js-runtimes", "deno"]
    else:
        # YouTube frequently needs a JS runtime; doctor exposes this before live use.
        pass

    def bounded():
        if cancelled():
            return True
        # Bounds the total job download, including separate video/audio fragments and merged output.
        size = sum(p.stat().st_size for p in directory.glob("source*") if p.is_file())
        if size > cfg.max_download_mb * 1024**2 * 2.2:
            raise ValueError("Download exceeded the configured disk budget")
        return False

    await run(args + ["--", url], cwd=directory, timeout=2400, cancelled=bounded)
    files = [p for p in directory.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not files:
        raise ValueError("No video downloaded: source may be live, private, unavailable or over the duration limit")
    source = max(files, key=lambda p: p.stat().st_size)
    if source.stat().st_size > cfg.max_download_mb * 1024**2:
        raise ValueError("Source exceeds MAX_DOWNLOAD_MB")
    return source


async def probe(source: Path, cfg: Config, cancelled=lambda: False) -> dict:
    info = await asyncio.to_thread(dimensions, source)
    output = await run([cfg.ffmpeg(), "-hide_banner", "-nostdin", "-i", str(source),
                        "-t", "0.05", "-f", "null", "-"], timeout=60, cancelled=cancelled)
    info["audio"] = "Audio:" in output
    if not info["audio"]:
        raise ValueError("The video has no audio stream")
    if info["duration"] > cfg.max_source_minutes * 60 + 1:
        raise ValueError("Video is longer than MAX_SOURCE_MINUTES")
    return info


async def transcribe(source: Path, directory: Path, prefs: Preferences, cfg: Config, cancelled) -> Transcript:
    audio = directory / "audio.wav"
    await run([cfg.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(source),
               "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", str(audio)], cancelled=cancelled)
    target = directory / "transcript.json"
    await run([sys.executable, "-m", "cliper.transcribe", str(audio), str(target),
               "--model", cfg.whisper_model, "--device", cfg.whisper_device,
               "--compute", cfg.whisper_compute, "--language", prefs.language,
               "--device-index", str(cfg.gpu_device_index),
               "--cache", str(cfg.data_dir / "models")], timeout=14400, cancelled=cancelled)
    return Transcript.model_validate_json(target.read_text(encoding="utf-8"))


def filter_graph(prefs: Preferences, face: dict, subtitle: str, force_blur=False) -> tuple[str, str]:
    w, h = prefs.width, prefs.width * 16 // 9
    mode = prefs.reframe
    if prefs.layout == "square_hook":
        mode = "square_hook"
        graph = (f"[0:v]scale={w}:{w}:force_original_aspect_ratio=increase,crop={w}:{w},"
                 f"pad={w}:{h}:0:{(h - w) // 2}:color=black[framed];")
    elif force_blur or (mode == "auto" and not face.get("safe_crop")):
        mode = "blur"
    if mode == "square_hook":
        pass
    elif mode == "blur":
        graph = (f"[0:v]split=2[bg][fg];[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
                 f"crop={w}:{h},boxblur=20:2,eq=brightness=-0.13[back];"
                 f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[front];"
                 "[back][front]overlay=(W-w)/2:(H-h)/2:shortest=1[framed];")
    else:
        expression = center_expression(face.get("centers", [])) if mode == "auto" else "0.5"
        graph = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                 f"crop={w}:{h}:x='max(0,min(iw-ow,iw*({expression})-ow/2))':y=(ih-oh)/2[framed];")
    graph += "[framed]setsar=1,fps=30"
    if prefs.captions or prefs.layout == "square_hook":
        # Subtitle filename is generated internally, and cwd avoids Windows drive/path escaping.
        graph += f",ass=filename={subtitle}"
    graph += "[out]"
    return graph, mode


async def quality_check(path: Path, clip: Clip, prefs: Preferences, cfg: Config, cancelled) -> dict:
    info = await probe(path, cfg, cancelled)
    if (info["width"], info["height"]) != (prefs.width, prefs.width * 16 // 9):
        raise ValueError("Output did not pass the vertical resolution check")
    if abs(info["duration"] - (clip.end - clip.start)) > .65:
        raise ValueError("Output duration does not match the edit plan")
    if path.stat().st_size >= 49_000_000:
        raise ValueError("Output exceeds the Telegram delivery budget")
    # Decode the entire output, not just its container header.
    await run([cfg.ffmpeg(), "-v", "error", "-xerror", "-nostdin", "-i", str(path),
               "-f", "null", "-"], cancelled=cancelled, timeout=300)
    volume = await run([cfg.ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path),
                        "-vn", "-af", "volumedetect", "-f", "null", "-"], cancelled=cancelled, timeout=120)
    match = re.search(r"max_volume: ([\-\w.]+) dB", volume)
    if match and float(match[1]) < -55:
        raise ValueError("Output audio is effectively silent")
    return info | {"bytes": path.stat().st_size, "full_decode": "passed", "audio_level": "passed"}


def video_encoder_args(cfg: Config, bitrate: int) -> list[str]:
    if cfg.video_encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-gpu", str(cfg.gpu_device_index), "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", "-cq", "21", "-b:v", f"{bitrate}k"]
    if cfg.video_encoder == "libx264":
        return ["-c:v", "libx264", "-threads", "4", "-preset", "fast", "-crf", "21"]
    raise ValueError("Unknown VIDEO_ENCODER; choose h264_nvenc or libx264")


async def render(source: Path, directory: Path, transcript: Transcript, clip: Clip,
                 prefs: Preferences, cfg: Config, cancelled) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    ass = write_captions(directory, transcript, clip, prefs)
    face_path = directory / f"clip_{clip.id:02}.vision.json"
    if prefs.reframe == "auto" and prefs.layout == "legacy":
        await run([sys.executable, "-m", "cliper.vision", str(source), str(clip.start), str(clip.end),
                   str(face_path)], cancelled=cancelled, timeout=300)
        face = json.loads(face_path.read_text(encoding="utf-8"))
    else:
        face = {}
    length = clip.end - clip.start
    from .music import choose
    track_note = directory / f"clip_{clip.id:02}.music.json"
    track = None
    if prefs.music:
        if track_note.exists():
            saved = json.loads(track_note.read_text("utf-8"))
            candidate = Path(saved["path"]) if saved.get("path") else None
            if candidate and candidate.is_file() and saved.get("category") == clip.music_category:
                track = candidate
        if track is None:
            track = choose(cfg.music_dir, clip.music_category)
        write_json(track_note, {"category": clip.music_category, "path": str(track) if track else None,
                                "gain": 0.2, "status": "selected" if track else "category folder is empty"})
    # Limit peak video bitrate with ample mux/audio headroom for Telegram's cloud API.
    bitrate = min(6500, int((43_000_000 * 8 / length) / 1000) - 160)
    target = directory / f"clip_{clip.id:02}.mp4"
    partial = directory / f"clip_{clip.id:02}.partial.mp4"
    for attempt in range(2):
        graph, mode = filter_graph(prefs, face, ass.name, force_blur=bool(attempt))
        audio_map = ["-map", "0:a:0", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
        if track:
            graph += (";[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice];"
                      "[1:a]volume=0.20[music];[voice][music]amix=inputs=2:duration=first:"
                      "dropout_transition=0:normalize=0,alimiter=limit=0.95:level=false[aout]")
            audio_map = ["-map", "[aout]"]
        await run([cfg.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-ss", f"{clip.start:.3f}", "-i", str(source),
                   *(["-stream_loop", "-1", "-i", str(track)] if track else []), "-t", f"{length:.3f}",
                   "-filter_complex_threads", "2", "-filter_complex", graph,
                   "-map", "[out]", *audio_map,
                   *video_encoder_args(cfg, bitrate),
                   "-maxrate", f"{bitrate}k", "-bufsize", f"{bitrate * 2}k",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
                   "-movflags", "+faststart", "-map_metadata", "-1", str(partial)],
                  cwd=directory, cancelled=cancelled, timeout=3600)
        try:
            qa = await quality_check(partial, clip, prefs, cfg, cancelled)
        except ValueError:
            if attempt:
                raise
            bitrate = int(bitrate * .8)
            continue
        partial.replace(target)
        write_json(directory / f"clip_{clip.id:02}.json", {
            "clip": clip.model_dump(), "preferences": prefs.model_dump(), "render": {"layout": mode, "captions": prefs.captions,
                                                 "style": prefs.style, "encoder": cfg.video_encoder}, "quality": qa,
            "music": {"category": clip.music_category, "file": str(track) if track else None, "gain": .2},
            "vision": face, "review_note": "Automated technical QA; editorial and face visibility review advised."})
        return target
    raise ValueError("Could not produce a valid export")
