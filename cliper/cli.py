from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import shutil
import sys
import uuid
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path

from filelock import FileLock, Timeout

from .config import PROVIDERS, Config, normalize_provider
from .maintenance import cleanup
from .media import video_encoder_args
from .models import Preferences, Segment, Transcript, Word
from .pipeline import Pipeline, safe_error
from .process import run
from .providers import verify_model
from .storage import Store, write_json


def configure_logging(cfg: Config):
    class Redact(logging.Filter):
        def filter(self, record):
            record.msg = safe_error(Exception(record.getMessage()), cfg)
            record.args = ()
            return True

    log_dir = cfg.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), RotatingFileHandler(log_dir / "cliper.log", maxBytes=2_000_000,
                                                           backupCount=3, encoding="utf-8")]
    for handler in handlers:
        handler.addFilter(Redact())
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True)
    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def doctor(cfg: Config, online: bool = False) -> bool:
    checks = {}
    ai = cfg.ai()
    try:
        binary = cfg.ffmpeg()
        output = await run([binary, "-hide_banner", "-filters"], timeout=30)
        checks["FFmpeg + caption/blur/audio filters"] = all(x in output for x in (" ass ", "boxblur", "loudnorm"))
        encoder = await run([binary, "-hide_banner", "-encoders"], timeout=30)
        checks["H.264 and AAC encoders"] = cfg.video_encoder in encoder and " aac " in encoder
        if cfg.video_encoder == "h264_nvenc":
            await run([binary, "-hide_banner", "-loglevel", "error", "-nostdin", "-f", "lavfi", "-i",
                       "color=size=320x180:rate=30", "-t", "0.3", *video_encoder_args(cfg, 1000),
                       "-f", "null", "-"], timeout=30)
            checks["NVENC real encode"] = True
    except Exception as exc:
        print(safe_error(exc, cfg))
        checks["FFmpeg"] = False
    checks["Local transcription installed"] = bool(importlib.util.find_spec("faster_whisper"))
    if cfg.whisper_device == "cuda":
        try:
            result = await run([sys.executable, "-m", "cliper.hardware", "--device-index",
                                str(cfg.gpu_device_index), "--compute", cfg.whisper_compute], timeout=30)
            print("GPU: " + result.strip())
            checks["CUDA inference libraries and compute support"] = True
        except Exception as exc:
            checks["CUDA inference libraries and compute support"] = False
            print(safe_error(exc, cfg))
    checks["Telegram token configured"] = bool(cfg.token)
    checks["Owner allowlist configured"] = bool(cfg.owners)
    checks["AI configuration"] = ai.provider in {"heuristic", "chatgpt_browser"} or bool(ai.key)
    if ai.provider == "chatgpt_browser":
        checks["Browser provider installed"] = bool(importlib.util.find_spec("playwright"))
        print("ChatGPT website session: run scripts/chatgpt-login.ps1 once; no API key required.")
    checks["JavaScript runtime for YouTube (Node or Deno)"] = bool(shutil.which("node") or shutil.which("deno"))
    checks["Disk headroom"] = shutil.disk_usage(cfg.data_dir).free > cfg.min_free_disk_mb * 1024**2
    if online:
        if cfg.token:
            try:
                from telegram import Bot
                async with Bot(cfg.token) as bot:
                    me = await bot.get_me()
                    print(f"Telegram: @{me.username}")
                    checks["Telegram credentials accepted"] = True
            except Exception as exc:
                checks["Telegram credentials accepted"] = False
                print(safe_error(exc, cfg)[:500])
        if ai.provider != "heuristic" and ai.key:
            try:
                from openai import AsyncOpenAI
                async with AsyncOpenAI(api_key=ai.key, base_url=ai.base_url, timeout=20) as client:
                    await verify_model(client, ai)
                checks["AI model visible to account"] = True
            except Exception as exc:
                checks["AI model visible to account"] = False
                print(safe_error(exc, cfg)[:500])
    for label, ok in checks.items():
        print(f"[{'OK' if ok else 'SETUP'}] {label}")
    print(f"Data: {cfg.data_dir}\nAI: {ai.provider} / {ai.model}\n"
          f"Transcription: {cfg.whisper_device} / {cfg.whisper_compute}\nVideo encoder: {cfg.video_encoder}\n"
          "Offline doctor does not contact Telegram or the AI provider. --online checks credentials without generating clips.")
    return all(checks.values())


async def progress(message: str):
    print(message, flush=True)


async def diagnostic_demo(cfg: Config, width: int = 360) -> Path:
    cfg = replace(cfg, provider="heuristic")
    directory = cfg.data_dir / "demo" / uuid.uuid4().hex[:8]
    directory.mkdir(parents=True)
    source = directory / "demo-source.mp4"
    await progress("Creating synthetic demo footage and a timed fixture transcript (no API calls)")
    await run([cfg.ffmpeg(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=64",
               "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=64",
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-af", "volume=0.15", "-shortest", str(source)], timeout=180)
    sentences = [
        "Why do most good ideas disappear before anyone sees them?",
        "The problem is waiting until every single detail feels perfect.",
        "Start with one small useful thing and show someone today.",
        "Their questions will tell you what to build next.",
        "I learned a different lesson when I tried growing tomatoes.",
        "Watering them every hour was slowly drowning the roots.",
        "A gardener taught me to check the soil before reaching for the hose.",
        "Once I gave them space to breathe the leaves came back.",
        "Imagine learning a song by playing only the difficult bar.",
        "You slow it down until your hands can find every note.",
        "Then you connect that bar to the phrase before it.",
        "Practice gets easier when you make the next step smaller.",
    ]
    segments = []
    for i, sentence in enumerate(sentences):
        start = i * 5 + .2
        tokens = sentence.split()
        step = 4.5 / len(tokens)
        words = [Word(start=start + j * step, end=start + (j + 1) * step - .02, text=word)
                 for j, word in enumerate(tokens)]
        segments.append(Segment(start=start, end=words[-1].end, text=sentence, words=words))
    transcript = Transcript(language="en", duration=64, segments=segments)
    write_json(directory / "transcript.json", transcript.model_dump())
    prefs = Preferences(clips=2, min_seconds=15, max_seconds=25, width=width)
    pipeline = Pipeline(cfg)
    analysis = await pipeline.analyze(str(source), directory, prefs, progress)
    for clip in analysis.clips:
        await progress(f"Rendering demo clip {clip.id}/{len(analysis.clips)}")
        output = await pipeline.render_one(directory, clip, prefs)
        print(output)
    write_json(directory / "DEMO-NOTE.json", {"synthetic": True, "audio": "test tone",
                                              "transcript": "fixture, not transcribed",
                                              "purpose": "Real rendering/QA smoke test, not an AI quality demonstration"})
    print(f"Demo complete: {directory}")
    return directory


async def demo(cfg: Config, width: int = 1080, *, diagnostic: bool = False,
               audio: Path | None = None) -> Path:
    if diagnostic:
        if audio is not None:
            raise ValueError("--audio cannot be combined with --diagnostic")
        return await diagnostic_demo(cfg, width)
    from .demo import speech_demo
    return await speech_demo(cfg, width=width, audio=audio, progress=progress)


async def local(cfg: Config, args):
    cfg.check_ai()
    store = Store(cfg.data_dir)
    prefs = cfg.snapshot_ai(Preferences(clips=args.clips, min_seconds=args.min_seconds, max_seconds=args.max_seconds,
                                       width=args.width, reframe=args.reframe))
    source = args.source if args.source.startswith("https://") else str(Path(args.source).resolve())
    job = store.create(0, 0, source, prefs, cfg.max_active_jobs)
    directory = store.directory(job["id"])
    if args.transcript:
        transcript = Transcript.model_validate_json(args.transcript.read_text(encoding="utf-8"))
        write_json(directory / "transcript.json", transcript.model_dump())
    pipeline = Pipeline(cfg)
    try:
        store.update(job["id"], state="analyzing")
        analysis = await pipeline.analyze(source, directory, prefs, progress)
        print(analysis.model_dump_json(indent=2))
        if not args.analyze_only:
            store.update(job["id"], state="rendering", selected=json.dumps([c.id for c in analysis.clips]))
            for clip in analysis.clips:
                print(await pipeline.render_one(directory, clip, prefs))
            store.update(job["id"], state="complete", stage="Local exports ready")
        else:
            store.update(job["id"], state="complete", stage="Local analysis exported")
        print(f"Saved: {directory}")
    except asyncio.CancelledError:
        store.update(job["id"], state="cancelled", stage="Stopped from terminal")
        raise
    except Exception as exc:
        store.update(job["id"], state="failed", error=safe_error(exc, cfg))
        raise


def main():
    parser = argparse.ArgumentParser(prog="cliper", description="Your private Telegram clip studio")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bot", help="Start Telegram polling and the persistent worker")
    sub.add_parser("browser-login", help="Open CLIPER's Chromium profile for manual ChatGPT login")
    sub.add_parser("browser-check", help="Send a tiny JSON request through the saved ChatGPT website session")
    check = sub.add_parser("doctor", help="Check tools and configuration")
    check.add_argument("--online", action="store_true")
    check.add_argument("--provider", type=normalize_provider, choices=PROVIDERS)
    sample = sub.add_parser("demo", help="Render a spoken studio sample with real transcription; no paid AI calls")
    sample.add_argument("--width", type=int, choices=[360, 720, 1080], default=1080)
    sample.add_argument("--audio", type=Path, help="Use a local speech recording instead of system text-to-speech")
    sample.add_argument("--diagnostic", action="store_true", help="Explicitly use color bars, a tone and fixture captions")
    process = sub.add_parser("run", help="Process a local video or supported URL")
    process.add_argument("source")
    process.add_argument("--provider", type=normalize_provider, choices=PROVIDERS)
    process.add_argument("--transcript", type=Path, help="Use an existing validated word-timed transcript JSON")
    process.add_argument("--clips", type=int, default=5)
    process.add_argument("--min-seconds", type=int, default=30)
    process.add_argument("--max-seconds", type=int, default=60)
    process.add_argument("--width", type=int, choices=[720, 1080], default=1080)
    process.add_argument("--reframe", choices=["auto", "blur", "center"], default="auto")
    process.add_argument("--analyze-only", action="store_true")
    sub.add_parser("cleanup", help="Delete expired finished jobs, never source files supplied via CLI")
    args = parser.parse_args()
    cfg = None
    try:
        cfg = Config.load()
        if getattr(args, "provider", None):
            cfg = replace(cfg, provider=args.provider)
        configure_logging(cfg)
        if args.command == "doctor":
            sys.exit(0 if asyncio.run(doctor(cfg, args.online)) else 2)
        if args.command == "browser-login":
            from .browser_provider import login
            asyncio.run(login(cfg))
            return
        if args.command == "browser-check":
            from .browser_provider import BrowserEditorialClient

            async def browser_check():
                async with BrowserEditorialClient(cfg) as client:
                    await client.text("You are testing JSON connectivity. Summarize the supplied text.",
                                      "CLIPER browser connection test.", 200)
                print("ChatGPT browser returned validated JSON. No API key or API request used.")
            asyncio.run(browser_check())
            return
        # A single lock prevents competing workers, retention jobs and local CLI jobs sharing a store.
        with FileLock(str(cfg.data_dir / "worker.lock"), timeout=0):
            if args.command == "bot":
                from .bot import Controller
                print("Starting CLIPER. Ctrl+C stops safely; unfinished jobs resume on restart.")
                Controller(cfg).build().run_polling(allowed_updates=["message", "callback_query"])
            elif args.command == "demo":
                asyncio.run(demo(cfg, args.width, diagnostic=args.diagnostic, audio=args.audio))
            elif args.command == "run":
                asyncio.run(local(cfg, args))
            else:
                print(f"Removed {cleanup(Store(cfg.data_dir), cfg.retention_days)} expired jobs")
    except Timeout:
        parser.exit(1, "Another CLIPER process is using this data directory. Stop it first.\n")
    except KeyboardInterrupt:
        print("Stopped.")
    except Exception as exc:
        parser.exit(1, (safe_error(exc, cfg) if cfg else str(exc)) + "\n")


if __name__ == "__main__":
    main()
