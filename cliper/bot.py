from __future__ import annotations

import asyncio
import importlib.util
import logging
import re
import time
from pathlib import Path

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import NetworkError, RetryAfter
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

if not __package__:
    import sys
    from pathlib import Path
    _parent = Path(__file__).resolve().parent.parent
    if str(_parent) not in sys.path:
        sys.path.insert(0, str(_parent))
    from cliper.config import PROVIDERS, Config, normalize_provider
    from cliper.maintenance import cleanup, export_metadata
    from cliper.media import validate_url
    from cliper.models import Analysis, Preferences
    from cliper.pipeline import Worker, safe_error
    from cliper.storage import Store
else:
    from .config import PROVIDERS, Config, normalize_provider
    from .maintenance import cleanup, export_metadata
    from .media import validate_url
    from .models import Analysis, Preferences
    from .pipeline import Worker, safe_error
    from .storage import Store

log = logging.getLogger(__name__)
WELCOME = """🎬 CLIPER · your private clip studio

Send a video link or upload a video. I’ll transcribe it, find complete moments and build a shortlist.
Choose your clips, then get vertical videos with highlighted captions and balanced audio.

/settings — your editing preferences
/geminiclip YOUTUBE_URL — clipping using Gemini website, no API key
/provider — choose ChatGPT browser, OpenAI, Grok, Gemini or offline ranking
/jobs — recent jobs
/status JOB — progress or shortlist
/cancel JOB — stop a job
/retry JOB — resume after a failure
/export JOB — subtitle files and edit plans
/cleanup — remove expired finished jobs

Scores measure editorial strength, not a promise of views. Only submit videos you have permission to use."""


class Controller:
    def __init__(self, cfg: Config):
        self.cfg, self.store = cfg, Store(cfg.data_dir)
        self.app: Application | None = None
        self.worker: Worker | None = None
        self.worker_task: asyncio.Task | None = None
        self.maintenance_task: asyncio.Task | None = None
        self.progress_messages: dict[str, tuple[int, float]] = {}
        from cliper.controls import Controls
        self.controls = Controls(self)
        self.publisher_task = None
        self.faceless_task = None

    def authorized(self, update: Update) -> bool:
        return bool(update.effective_user and update.effective_user.id in self.cfg.owners
                    and update.effective_chat and update.effective_chat.type == "private")

    async def guard(self, update: Update) -> bool:
        if self.authorized(update):
            return True
        if update.callback_query:
            await update.callback_query.answer("This is a private bot.", show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text("Private bot. Use /whoami, then add your ID to "
                                                      "ALLOWED_USER_IDS in the local .env and restart.")
        return False

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type == "private":
            await update.message.reply_text(f"Your Telegram user ID: {update.effective_user.id}")

    async def notify(self, job, text):
        text = f"🎬 {job['id']}\n{text}"
        previous = self.progress_messages.get(job["id"])
        if previous:
            try:
                await self.app.bot.edit_message_text(text, chat_id=job["chat"], message_id=previous[0])
                return
            except Exception:
                pass
        sent = await self.app.bot.send_message(job["chat"], text)
        self.progress_messages[job["id"]] = (sent.message_id, time.monotonic())
        if len(self.progress_messages) > 100:
            self.progress_messages.pop(next(iter(self.progress_messages)))

    def board(self, job, analysis):
        description = f"✨ Your shortlist · {job['id']}\nRanking: {analysis.method}"
        description += f" / {analysis.model}\n" if analysis.model else "\n"
        for clip in analysis.clips:
            description += f"\n{clip.id}. {clip.title}\n{clip.score}/100 editorial score · "
            description += f"{clip.end - clip.start:.0f}s · {clip.start:.1f}–{clip.end:.1f}s\n"
        description += "\nChoose what to produce. Scores are estimates, not predicted views."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Generate all", callback_data=f"all:{job['id']}"),
             InlineKeyboardButton("🔥 Top 3", callback_data=f"top:{job['id']}")],
            [InlineKeyboardButton("Choose clip numbers", callback_data=f"custom:{job['id']}"),
             InlineKeyboardButton("Cancel", callback_data=f"cancel:{job['id']}")],
            *[[InlineKeyboardButton(f"Review hook / quality · clip {clip.id}",
                                    callback_data=f"ui:clipinfo:{job['id']}:{clip.id}")]
              for clip in analysis.clips]])
        return description, keyboard

    async def shortlist(self, job, analysis):
        text, keyboard = self.board(job, analysis)
        await self.app.bot.send_message(job["chat"], text, reply_markup=keyboard)

    async def deliver(self, job, clip, output: Path):
        post = self.controls.clip_publication(job, clip, output)
        caption = f"🎬 {clip.title}\n\n{clip.score}/100 editorial score · {clip.end - clip.start:.0f}s\n"
        caption += f"{clip.reason}\n\nSource: {clip.start:.1f}–{clip.end:.1f}s · Job {job['id']}"
        for attempt in range(3):
            try:
                with output.open("rb") as video:
                    await self.app.bot.send_video(job["chat"], video=video, caption=caption[:1024],
                                                  supports_streaming=True, read_timeout=180, write_timeout=180,
                                                  connect_timeout=30, pool_timeout=30,
                                                  reply_markup=self.controls.publication_buttons(post))
                return
            except RetryAfter as exc:
                if attempt == 2:
                    raise
                delay = exc.retry_after
                await asyncio.sleep(delay.total_seconds() if hasattr(delay, "total_seconds") else delay)
            except NetworkError:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** (attempt + 1))

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.guard(update):
            return
        owner = update.effective_user.id
        name = update.message.text.split()[0].split("@")[0][1:]
        args = context.args
        try:
            if name in {"start", "help"}:
                await self.controls.show(update.message, owner)
                return
            elif name in {"autopublish", "music", "feature"}:
                p = self.store.prefs(owner)
                if name == "feature":
                    if not args or args[0].lower() not in {"f1", "f2", "both"}:
                        raise ValueError("Use /feature f1, f2 or both; enable each feature with the dashboard buttons")
                    mode = args[0].lower()
                    p = p.model_copy(update={"active_feature": mode, "f1_enabled": mode in {"f1", "both"},
                                            "f2_enabled": mode in {"f2", "both"}})
                else:
                    if not args or args[0].lower() not in {"on", "off"}:
                        raise ValueError(f"Use /{name} on or off")
                    key = "music" if name == "music" else ("f2_auto_publish" if len(args) > 1 and args[1].lower() == "f2" else "auto_publish")
                    p = p.model_copy(update={key: args[0].lower() == "on"})
                    if name == "autopublish" and args[0].lower() == "off":
                        self.controls.publications.hold_auto(owner, "f2" if key == "f2_auto_publish" else "f1")
                self.store.save_prefs(owner, p)
                await self.controls.show(update.message, owner)
                return
            elif name in {"generate", "schedule"}:
                from cliper.faceless import handle_command
                await handle_command(self.controls, update, context, name)
                return
            elif name == "jobs":
                jobs = self.store.recent(owner)
                reply = "\n\n".join(f"{j['id']} · {j['state']}\n{j['stage']}" for j in jobs) or "No jobs yet. Send a video link."
            elif name == "settings":
                p = self.store.prefs(owner)
                ai = self.cfg.ai(p.ai_provider, p.ai_model)
                reply = (f"⚙️ Your editing defaults\n\n{p.clips} clips · {p.min_seconds}–{p.max_seconds}s\n"
                         f"AI: {ai.provider} / {ai.model}\n/provider — switch provider\n"
                         f"{p.width}×{p.width * 16 // 9} · {p.style} · captions {'on' if p.captions else 'off'}\n"
                         f"Reframe: {p.reframe} · Language: {p.language} · Auto-render: {p.auto_render}\n\n"
                         "/clips 5\n/length 30-60\n/style studio|bold|minimal\n/captions on|off\n"
                         "/reframe auto|blur|center\n/language auto|en|hi\n/resolution 720|1080\n/auto on|off\n\n"
                         "Changes apply to new jobs. Auto uses face detection; blur preserves the whole frame.")
            elif name == "provider":
                prefs = self.store.prefs(owner)
                if args:
                    if len(args) != 1:
                        raise ValueError("Use /provider chatgpt, grok, gemini, openai, heuristic, or default")
                    provider = None if args[0].lower() == "default" else normalize_provider(args[0])
                    ai = self.cfg.check_ai(provider)
                    self.store.save_prefs(owner, prefs.model_copy(update={"ai_provider": provider, "ai_model": None}))
                    reply = f"AI provider: {ai.provider} / {ai.model}. Saved for new videos. Existing jobs keep their selection."
                else:
                    ai = self.cfg.ai(prefs.ai_provider, prefs.ai_model)
                    reply = f"Current AI: {ai.provider} / {ai.model}\n\n"
                    for provider in PROVIDERS:
                        option = self.cfg.ai(provider)
                        ready = "configured" if option.key or provider == "heuristic" else "API key needed"
                        if provider == "chatgpt_browser":
                            ready = "no API key; Chromium login required"
                        reply += f"{provider}: {ready} · {option.model}\n"
                    reply += "\n/provider chatgpt\n/provider grok\n/provider gemini\n/provider openai\n/provider heuristic\n/provider default"
            elif name in {"clips", "length", "style", "captions", "reframe", "language", "resolution", "auto"}:
                if not args:
                    raise ValueError("Supply a value. Use /settings for examples.")
                data = self.store.prefs(owner).model_dump()
                full_text = " ".join(args).strip().lower()
                value = args[0].lower()
                target_job_id = None
                for arg in args:
                    clean_arg = arg.strip().lower()
                    if len(clean_arg) == 12 and all(c in "0123456789abcdef" for c in clean_arg):
                        target_job_id = clean_arg
                        break
                if name == "clips":
                    data["clips"] = int(re.search(r"\d+", full_text).group()) if re.search(r"\d+", full_text) else int(value)
                elif name == "length":
                    nums = re.findall(r"\b\d+\b", full_text)
                    if len(nums) < 2:
                        raise ValueError("Use /length 15-90 (e.g. /length 15-90 or /length 10-60)")
                    min_s, max_s = int(nums[0]), int(nums[1])
                    if max_s < min_s:
                        min_s, max_s = max_s, min_s
                    data["min_seconds"], data["max_seconds"] = min_s, max_s
                elif name in {"captions", "auto"}:
                    val = "on" if "on" in full_text.split() else ("off" if "off" in full_text.split() else value)
                    if val not in {"on", "off"}:
                        raise ValueError("Use on or off")
                    data["captions" if name == "captions" else "auto_render"] = val == "on"
                elif name == "resolution":
                    if "1080" in full_text:
                        data["width"] = 1080
                    elif "720" in full_text:
                        data["width"] = 720
                    else:
                        raise ValueError("Choose 720 or 1080")
                elif name == "language":
                    if value != "auto" and not re.fullmatch(r"[a-z]{2,3}", value):
                        raise ValueError("Use auto or a language code such as en or hi")
                    data["language"] = value
                else:
                    data[name] = value
                new_prefs = Preferences.model_validate(data)
                self.store.save_prefs(owner, new_prefs)
                if not target_job_id:
                    recent = self.store.recent(owner)
                    failed = [j for j in recent if j["state"] == "failed"]
                    if failed:
                        target_job_id = failed[0]["id"]
                job_msg = ""
                if target_job_id:
                    try:
                        self.store.update_job_prefs(target_job_id, owner, new_prefs)
                        job_msg = f"\nUpdated failed job {target_job_id}. Send /retry {target_job_id} to rerun."
                    except Exception:
                        pass
                if name == "length":
                    reply = f"Length set to {new_prefs.min_seconds}–{new_prefs.max_seconds} seconds.{job_msg}"
                else:
                    reply = f"Saved for your next video.{job_msg} /settings shows all preferences."
            elif name in {"status", "cancel", "retry", "render", "export"}:
                if not args:
                    raise ValueError(f"Use /{name} JOB_ID. Find the ID with /jobs.")
                try:
                    job = self.store.get(args[0], owner)
                    is_f2 = False
                except Exception:
                    from .faceless import FacelessStore
                    f2_store = FacelessStore(self.store)
                    try:
                        job = f2_store.get(args[0], owner)
                        is_f2 = True
                    except Exception:
                        raise ValueError(f"Job {args[0]} not found") from None
                if is_f2:
                    if name == "retry":
                        if job["state"] != "failed":
                            raise ValueError("Only failed carousel jobs can be retried")
                        f2_store.update(job["id"], state="queued", error="")
                        reply = f"F2 job {job['id']} queued for retry."
                    elif name == "status":
                        reply = f"F2 · {job['id']} · {job['state']}\nNiche: {job['niche']}\n{job['stage']}"
                        if job.get("error"):
                            reply += "\n" + job["error"][:900]
                    elif name == "cancel":
                        f2_store.cancel(job["id"], owner)
                        reply = f"F2 job {job['id']} cancelled."
                    else:
                        raise ValueError(f"/{name} is not applicable to carousel jobs")
                else:
                    directory = self.store.directory(job["id"])
                if name == "status":
                    if job["state"] == "awaiting_selection":
                        await self.shortlist(job, Analysis.model_validate_json(
                            (directory / "analysis.json").read_text(encoding="utf-8")))
                        return
                    saved = Preferences.model_validate_json(job["prefs"])
                    ai = self.cfg.ai(saved.ai_provider, saved.ai_model)
                    reply = f"{job['id']} · {job['state']}\n{job['stage']}\nAI: {ai.provider} / {ai.model}"
                    if job["error"]:
                        reply += "\n" + job["error"][:900]
                elif name == "cancel":
                    if job["state"] in {"complete", "failed", "cancelled"}:
                        raise ValueError("This job has already stopped")
                    self.store.update(job["id"], state="cancelled", stage="Cancelled by you")
                    reply = "Cancellation requested. Running work will stop shortly."
                elif name == "retry":
                    current_prefs = self.store.prefs(owner)
                    self.store.retry(job["id"], owner, self.cfg.max_active_jobs, prefs=current_prefs)
                    reply = "Queued again with your current settings. Previously delivered clips will be skipped."
                elif name == "render":
                    if len(args) < 2:
                        raise ValueError("Use /render JOB_ID 1,3,5 or /render JOB_ID all")
                    self.choose(job, args[1])
                    reply = "Queued for rendering. I’ll send each clip as it finishes."
                else:
                    if not (directory / "analysis.json").exists():
                        raise ValueError("Analysis is not ready yet")
                    # No await inside packaging: prevent concurrent creation of the same ZIP.
                    bundle = export_metadata(directory)
                    with bundle.open("rb") as document:
                        await update.message.reply_document(document, filename=bundle.name,
                                                            caption="Subtitle files, transcript and edit metadata")
                    return
            elif name == "cleanup":
                count = await asyncio.to_thread(cleanup, self.store, self.cfg.retention_days)
                reply = f"Removed {count} finished jobs older than {self.cfg.retention_days} days."
            else:
                reply = "Use /help for available commands."
            await update.message.reply_text(reply)
        except (ValueError, OSError) as exc:
            await update.message.reply_text(safe_error(exc, self.cfg)[:1800])

    def choose(self, job: dict, selection: str):
        analysis = Analysis.model_validate_json((self.store.directory(job["id"]) / "analysis.json").read_text("utf-8"))
        available = [c.id for c in analysis.clips]
        if selection == "all":
            ids = available
        elif selection == "top":
            ids = available[:3]
        else:
            ids = sorted({int(x) for x in selection.split(",")})
        if not ids or any(x not in available for x in ids):
            raise ValueError("Choose valid clip numbers from the shortlist")
        self.store.select(job["id"], job["owner"], ids)

    async def callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.guard(update):
            return
        query = update.callback_query
        await query.answer()
        try:
            action, job_id = query.data.split(":", 1)
            job = self.store.get(job_id, update.effective_user.id)
            if action == "custom":
                await query.message.reply_text(f"Send /render {job_id} 1,3,5 with your chosen clip numbers.")
                return
            if action == "cancel":
                if job["state"] not in {"awaiting_selection", "queued_render", "queued_analysis", "analyzing", "rendering"}:
                    raise ValueError("This job has already stopped")
                self.store.update(job_id, state="cancelled", stage="Cancelled by you")
                text = "Job cancelled."
            elif action in {"all", "top"}:
                self.choose(job, action)
                text = "🎬 Queued for production. Clips will arrive here as they finish."
            else:
                raise ValueError("Unknown action")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(text)
        except (ValueError, OSError) as exc:
            await query.message.reply_text(safe_error(exc, self.cfg)[:1000])

    async def submit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.guard(update):
            return
        job = None
        try:
            self.cfg.check_disk()
            owner, chat = update.effective_user.id, update.effective_chat.id
            prefs = self.cfg.snapshot_ai(self.store.prefs(owner))
            command = (update.message.text or "").split(maxsplit=1)[0].split("@")[0]
            if command == "/geminiclip":
                prefs = prefs.model_copy(update={"clipping_mode": "gemini_browser"})
            if (prefs.clipping_mode == "audio_first" or prefs.gemini_verify_captions) and not importlib.util.find_spec("faster_whisper"):
                raise ValueError('Transcription is not installed. Run: pip install -e ".[transcribe]"')
            if not prefs.f1_enabled:
                raise ValueError("Feature 1 is paused. Enable F1 in the dashboard before submitting a video.")
            if prefs.clipping_mode == "audio_first":
                self.cfg.check_ai(prefs.ai_provider, prefs.ai_model)
            attachment = update.message.video or update.message.document
            if attachment:
                if prefs.clipping_mode == "gemini_browser":
                    raise ValueError("Clipping using Gemini takes YouTube links. Select Audio-first clipping for uploads.")
                if not attachment.file_size or attachment.file_size > 20 * 1024**2:
                    raise ValueError("Telegram cloud bots can download uploads up to 20 MB. Send a video link for larger videos.")
                job = self.store.create(owner, chat, "telegram-upload", prefs, self.cfg.max_active_jobs, "uploading")
                path = self.store.directory(job["id"]) / "upload.mp4"
                await update.message.reply_text(f"📥 Receiving video · {job['id']}")
                file = await attachment.get_file()
                await file.download_to_drive(custom_path=path, read_timeout=120)
                self.store.update(job["id"], source=str(path.resolve()), state="queued_analysis")
            else:
                url = (update.message.text or "").strip()
                if command in {"/clip", "/geminiclip"}:
                    url = url.split(maxsplit=1)[1].strip() if len(url.split(maxsplit=1)) == 2 else ""
                if prefs.clipping_mode == "gemini_browser":
                    from .gemini_clipping import youtube_url
                    url = youtube_url(url)
                validate_url(url, self.cfg)
                job = self.store.create(owner, chat, url, prefs, self.cfg.max_active_jobs)
            await update.message.reply_text(f"🎬 Queued · {job['id']}\nI’ll send the shortlist when it’s ready.\n"
                                            f"/status {job['id']} · /cancel {job['id']}")
        except Exception as exc:
            if job and self.store.get(job["id"])["state"] == "uploading":
                self.store.update(job["id"], state="failed", error="Upload interrupted; send the video again")
            await update.message.reply_text(safe_error(exc, self.cfg)[:1600])

    async def error(self, update, context):
        log.error("Telegram handler: %s", safe_error(context.error, self.cfg))
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("A connection or processing error occurred. Try /status or /jobs.")
            except Exception:
                pass

    async def maintain(self):
        while True:
            try:
                await asyncio.to_thread(cleanup, self.store, self.cfg.retention_days)
            except Exception as exc:
                log.warning("Cleanup: %s", safe_error(exc, self.cfg))
            await asyncio.sleep(3600)

    async def start(self, app):
        self.app = app
        await app.bot.set_my_commands([BotCommand("start", "Open your clip studio"),
                                      BotCommand("geminiclip", "Clip a YouTube link using Gemini website"),
                                      BotCommand("settings", "Editing defaults"), BotCommand("jobs", "Recent jobs"),
                                      BotCommand("status", "Job progress"), BotCommand("whoami", "Your user ID"),
                                      BotCommand("provider", "Switch ChatGPT browser, OpenAI, Grok or Gemini"),
                                      BotCommand("help", "All commands")])
        self.worker = Worker(self.cfg, self.store, self.notify, self.shortlist, self.deliver)
        self.worker_task = asyncio.create_task(self.worker.run())
        self.maintenance_task = asyncio.create_task(self.maintain())
        from cliper.faceless import FacelessWorker
        from cliper.publishing import InstagramPublisher
        async def publish_notify(post, message):
            await self.app.bot.send_message(post["chat"], message)
        self.publisher_task = asyncio.create_task(InstagramPublisher(self.controls.publications).run(publish_notify))
        self.faceless_task = asyncio.create_task(FacelessWorker(self.controls).run())

    async def stop(self, app):
        for task in (self.publisher_task, self.faceless_task):
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        if self.maintenance_task:
            self.maintenance_task.cancel()
            await asyncio.gather(self.maintenance_task, return_exceptions=True)
        if self.worker:
            await self.worker.stop()
            if self.worker_task:
                await self.worker_task

    def build(self) -> Application:
        if not self.cfg.token:
            raise ValueError("Set TELEGRAM_BOT_TOKEN in .env. Use @BotFather to create your bot.")
        app = (Application.builder().token(self.cfg.token).post_init(self.start).post_stop(self.stop)
               .concurrent_updates(4).read_timeout(60).write_timeout(180).connect_timeout(30).build())
        app.add_handler(CommandHandler("whoami", self.whoami))
        app.add_handler(CommandHandler(["clip", "geminiclip"], self.submit))
        app.add_handler(CommandHandler(["start", "help", "jobs", "settings", "provider", "clips", "length", "style",
                                        "captions", "reframe", "language", "resolution", "auto", "status",
                                        "cancel", "retry", "render", "export", "cleanup", "autopublish", "music",
                                        "feature", "generate", "schedule"], self.command))
        app.add_handler(CallbackQueryHandler(self.controls.callback, pattern=r"^(ui|pub):"))
        app.add_handler(CallbackQueryHandler(self.callback, pattern=r"^(all|top|custom|cancel):[0-9a-f]{12}$"))
        app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO | (filters.TEXT & ~filters.COMMAND),
                                       self.submit))
        app.add_error_handler(self.error)
        return app


if __name__ == "__main__":
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from cliper.cli import main
    sys.argv = [sys.argv[0], "bot"] + sys.argv[1:]
    main()
