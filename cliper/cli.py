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
                                       width=args.width, reframe=args.reframe, scan_minutes=args.scan_minutes,
                                       focus_times=args.focus,
                                       captions=not getattr(args, "no_captions", False)))
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
    web = sub.add_parser("web", help="Open the local CLIPER Studio web workspace")
    web.add_argument("--host", default="0.0.0.0", help="Network host interface to bind to (e.g. 0.0.0.0 or 127.0.0.1)")
    web.add_argument("--port", type=int, default=8788)
    web.add_argument("--no-engine", action="store_true", help="Serve controls without starting workers")
    web.add_argument("--open", action="store_true", help="Open the authenticated workspace in your browser")
    sub.add_parser("browser-login", help="Open CLIPER's Chromium profile for manual ChatGPT login")
    sub.add_parser("gemini-login", help="Verify Gemini in the configured shared browser session")
    sub.add_parser("x-login", help="Sign in to X in the existing shared Chromium profile")
    yt_auth = sub.add_parser("youtube-auth", help="Authorize a YouTube account using OAuth in your local browser")
    yt_auth.add_argument("--account", default=None, help="Account identifier key in config/youtube.json (e.g. main, podcast, gaming)")
    yt_auth.add_argument("--list", action="store_true", help="List all configured YouTube accounts and exit")
    server = sub.add_parser("serve-media", help="Serve only staged Instagram media behind your HTTPS reverse proxy")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=8787)
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
    process.add_argument("--scan-minutes", type=int, default=24, help="Long-VOD discovery budget; final clips are verified separately")
    from .stream_scan import timestamp
    process.add_argument("--focus", type=timestamp, nargs="*", default=[], help="Prioritize HH:MM:SS timestamps")
    process.add_argument("--provider", type=normalize_provider, choices=PROVIDERS)
    process.add_argument("--transcript", type=Path, help="Use an existing validated word-timed transcript JSON")
    process.add_argument("--clips", type=int, default=5)
    process.add_argument("--min-seconds", type=int, default=30)
    process.add_argument("--max-seconds", type=int, default=60)
    process.add_argument("--width", type=int, choices=[720, 1080], default=1080)
    process.add_argument("--reframe", choices=["auto", "blur", "center"], default="auto")
    process.add_argument("--no-captions", action="store_true", help="Disable burned-in subtitles on rendered clips")
    process.add_argument("--analyze-only", action="store_true")
    sub.add_parser("cleanup", help="Delete expired finished jobs, never source files supplied via CLI")

    # YouTube Agent Skill Subcommands
    hs_p = sub.add_parser("hookscore", help="Score a YouTube hook against 5 properties and classify into 21 formulas")
    hs_p.add_argument("--hook", default=None, help="Hook line to score")
    hs_p.add_argument("--file", type=Path, default=None, help="File containing hooks to rank (one per line)")
    hs_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    pl_p = sub.add_parser("package-lint", help="Lint YouTube title & thumbnail synergy for mobile/desktop cuts & vagueness")
    pl_p.add_argument("--title", default=None, help="Video title")
    pl_p.add_argument("--thumb", default=None, help="Thumbnail text")
    pl_p.add_argument("--file", type=Path, default=None, help="File with titles to lint")
    pl_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    da_p = sub.add_parser("deadair", help="Generate an edit decision list (DEAD air, FILLER words, REPEAT restarts) from transcript")
    da_p.add_argument("transcript", type=Path, help="Path to transcript (.srt, .vtt, or whisper .json)")
    da_p.add_argument("--floor", type=float, default=0.45, help="Silence gap floor threshold in seconds")
    da_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    ch_p = sub.add_parser("chapters", help="Generate YouTube-compliant chapters from transcript scored by topic shifts")
    ch_p.add_argument("transcript", type=Path, help="Path to transcript (.srt, .vtt, or whisper .json)")
    ch_p.add_argument("--target", type=int, default=7, help="Target number of chapters")
    ch_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    rt_p = sub.add_parser("retention", help="Analyze YouTube Studio audience retention CSV (hook leak, cliffs, slide)")
    rt_p.add_argument("csv_file", type=Path, help="Path to YouTube Studio retention export CSV")
    rt_p.add_argument("--transcript", type=Path, default=None, help="Transcript to name words spoken at retention cliffs")
    rt_p.add_argument("--duration", type=float, default=None, help="Video duration in seconds")
    rt_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    sw_p = sub.add_parser("swipe", help="Rank collected niche videos by multiple over channel median and classify formulas")
    sw_p.add_argument("collected", type=Path, help="Path to JSON file containing collected video records")
    sw_p.add_argument("--min", type=float, default=1.5, help="Minimum multiple over channel median")
    sw_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    vo_p = sub.add_parser("voice", help="View or print current creator voice profile")
    vo_p.add_argument("--path", action="store_true", help="Show path to voice.md file")

    args = parser.parse_args()
    cfg = None
    try:
        cfg = Config.load()
        if getattr(args, "provider", None):
            cfg = replace(cfg, provider=args.provider)
        configure_logging(cfg)
        if args.command == "web":
            from .web import serve
            serve(cfg, host=args.host, port=args.port, no_engine=args.no_engine, open_browser=args.open)
            return
        if args.command == "doctor":
            sys.exit(0 if asyncio.run(doctor(cfg, args.online)) else 2)
        if args.command == "browser-login":
            from .browser_provider import login
            asyncio.run(login(cfg))
            return
        if args.command == "gemini-login":
            from .gemini_images import login
            asyncio.run(login(cfg))
            return
        if args.command == "x-login":
            from .x_browser import login
            asyncio.run(login(cfg))
            return
        if args.command == "youtube-auth":
            from .youtube_publishing import run_cli_auth, list_accounts_cli, suggest_next_account_key, get_youtube_config, get_token_path
            if getattr(args, "list", False):
                list_accounts_cli()
                return
            account_to_auth = args.account
            if not account_to_auth:
                list_accounts_cli()
                suggested = suggest_next_account_key()
                print(f"No --account specified. Next suggested account key: '{suggested}'")
                try:
                    user_input = input(f"Enter account key to authorize [press Enter for '{suggested}']: ").strip()
                    account_to_auth = user_input if user_input else suggested
                except (EOFError, KeyboardInterrupt):
                    print("\nAborted.")
                    return
            account_to_auth = account_to_auth.lower().strip()
            # Safety check if overwriting an existing authorized account
            token_path = get_token_path(account_to_auth)
            if token_path.is_file():
                yt_cfg = get_youtube_config()
                acc_info = yt_cfg.get("accounts", {}).get(account_to_auth, {})
                acc_title = acc_info.get("title", account_to_auth)
                print(f"\n[!] Notice: Account '{account_to_auth}' is already connected to channel '{acc_title}'.")
                try:
                    confirm = input("    Do you want to re-authenticate and overwrite this account? [y/N]: ").strip().lower()
                    if confirm != "y":
                        print("Operation cancelled. Existing account was NOT modified.")
                        return
                except (EOFError, KeyboardInterrupt):
                    print("\nAborted.")
                    return
            asyncio.run(run_cli_auth(account_to_auth, cfg))
            return
        if args.command == "serve-media":
            from .public_media import serve
            serve(args.host, args.port)
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

        if args.command == "hookscore":
            from .youtube_agent import score_hook, score_hooks
            hooks_to_score = []
            if args.hook:
                hooks_to_score = [args.hook]
            elif args.file and args.file.is_file():
                hooks_to_score = [line.strip() for line in args.file.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                parser.exit(1, "Specify either --hook \"...\" or --file hooks.txt\n")

            if len(hooks_to_score) == 1 and not args.file:
                res = score_hook(hooks_to_score[0])
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f"\n  {res['hook']}")
                    print(f"  {'-' * min(72, max(24, len(res['hook'])))}")
                    for k, v in res["properties"].items():
                        print(f"    {k:<12} {v:3d}  {'#' * (v // 5)}")
                    print(f"    {'VERDICT':<12} {res['verdict']:3d}  [{res['band']}]")
                    formula_str = res['formula'] + (f" ({res['formula_hits']} pattern(s) matched)" if res['formula_hits'] else " (no formula matched)")
                    print(f"    formula      {formula_str}")
                    print(f"    weakest      {res['weakest']} - {res['fix']}\n")
            else:
                scored = score_hooks(hooks_to_score)
                if args.json:
                    print(json.dumps(scored, indent=2))
                else:
                    print(f"\nRanked {len(scored)} hooks:\n")
                    for s in scored:
                        print(f"  [{s['verdict']:2d}/100 {s['band']:<8}] ({s['formula']:<18}) {s['hook'][:60]}")
                        print(f"         weakest: {s['weakest']} ({s['fix']})")
                    print()
            return

        if args.command == "package-lint":
            from .youtube_agent import lint_title_and_thumb, lint_titles
            if args.title:
                res = lint_title_and_thumb(args.title, args.thumb)
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    print(f'\n  "{res["title"]}"')
                    print(f"  {res['chars']} chars   score {res['score']}/100  [{res['status']}]")
                    if res.get("thumb"):
                        print(f'  Thumbnail: "{res["thumb"]}"')
                    print(f"  Desktop Search View: \"{res['desktop_preview']}\"")
                    print(f"  Mobile Feed View:    \"{res['mobile_preview']}\"")
                    for m in res["issues"]:
                        print(f"    [x] {m['kind']:<12} {m['message']}")
                    for g in res["good"]:
                        print(f"    [ok]             {g}")
                    print()
            elif args.file and args.file.is_file():
                titles = [l.strip() for l in args.file.read_text(encoding="utf-8").splitlines() if l.strip()]
                results = lint_titles(titles, args.thumb)
                if args.json:
                    print(json.dumps(results, indent=2))
                else:
                    for r in results:
                        print(f"  [{r['score']:3d}/100] {r['title'][:55]}")
                        for i in r["issues"]:
                            print(f"       [x] {i['kind']}: {i['message']}")
            else:
                parser.exit(1, "Specify --title \"...\" [--thumb \"...\"] or --file titles.txt\n")
            return

        if args.command == "deadair":
            from .youtube_agent import detect_deadair
            if not args.transcript.is_file():
                parser.exit(1, f"Transcript file not found: {args.transcript}\n")
            res = detect_deadair(args.transcript, floor=args.floor)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"\n  {args.transcript} | {res['duration']:.2f}s total | floor: {args.floor}s\n")
                for c in res["cuts"]:
                    print(f"    {c['kind']:<7} {c['start']:8.2f} -> {c['end']:8.2f}  ({c['duration']:5.2f}s)  {c['why']}")
                print(f"\n  {len(res['cuts'])} cuts: {res['removed_seconds']:.2f}s removed -> {res['out_seconds']:.2f}s out ({res['percent_saved']:.1f}% shorter)\n")
            return

        if args.command == "chapters":
            from .youtube_agent import generate_youtube_chapters
            if not args.transcript.is_file():
                parser.exit(1, f"Transcript file not found: {args.transcript}\n")
            res = generate_youtube_chapters(args.transcript, target=args.target)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"\n  YouTube Chapters ({len(res['chapters'])} sections) - {'VALID' if res['valid'] else 'INVALID'}:\n")
                for c in res["chapters"]:
                    print(f"    {c['label']} {c['draft_title']} ({c['duration']:.1f}s)")
                print(f"\n-- Paste Block --\n{res['formatted_text']}\n")
            return

        if args.command == "retention":
            from .youtube_agent import parse_retention_csv
            if not args.csv_file.is_file():
                parser.exit(1, f"CSV file not found: {args.csv_file}\n")
            transcript_cues = None
            if args.transcript and args.transcript.is_file():
                from .youtube_agent import parse_cues_from_text
                transcript_cues = parse_cues_from_text(args.transcript.read_text(encoding="utf-8", errors="replace"))
            res = parse_retention_csv(args.csv_file, transcript_cues=transcript_cues, duration=args.duration)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                if "error" in res:
                    print(f"Error: {res['error']}")
                else:
                    print(f"\n  Retention Diagnostic ({res['points']} points): {res['start']}% -> {res['end']}%\n")
                    print(f"  HOOK LEAK:   {res['hook_leak']:.1f}% lost in first 30s  [{res['hook_verdict'].upper()}]")
                    print(f"  SLIDE RATE:  {res['slide_rate']:.3f}% bleed per unit across middle")
                    print(f"  ADVICE:      {res['advice']}\n")
                    print("  CLIFF DROPS:")
                    for c in res["cliffs"]:
                        spoken_str = f' - "{c.get("spoken","")}"' if c.get("spoken") else ""
                        print(f"    -{c['lost']:4.1f}% at {c['label']:>7}{spoken_str}")
                    print()
            return

        if args.command == "swipe":
            from .youtube_agent import analyze_swipe_outliers
            if not args.collected.is_file():
                parser.exit(1, f"JSON file not found: {args.collected}\n")
            data = json.loads(args.collected.read_text(encoding="utf-8"))
            vids = data.get("videos", data if isinstance(data, list) else [])
            res = analyze_swipe_outliers(vids, min_multiple=args.min)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"\n  Analyzed {res['total_analyzed']} videos across {res['channel_count']} channels (threshold: >={args.min}x)\n")
                for o in res["outliers"][:25]:
                    print(f"    {o['multiple']:5.2f}x  {o['views']:>9,} views (median {o['median']:>9,})  {o['channel'][:20]:<20} {o['title'][:45]}")
                    print(f"            formula: {o['formula']}")
                if res["top_formulas"]:
                    print("\n  Winning formulas in outliers:")
                    for f in res["top_formulas"]:
                        print(f"    {f['count']:2d}x {f['formula']}")
                print()
            return

        if args.command == "voice":
            from .youtube_agent import get_voice_profile, CONFIG
            vp = get_voice_profile()
            if args.path:
                print(str(CONFIG / "voice.md"))
            else:
                print(vp)
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
