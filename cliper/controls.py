"""Owner-only Telegram button dashboard shared by both production features."""
from __future__ import annotations

import json

from telegram import InlineKeyboardButton as Button
from telegram import InlineKeyboardMarkup as Keyboard

from .config import PROVIDERS, normalize_provider
from .models import Preferences
from .publishing import PublishStore

NICHES = {"dark": "Dark self-improvement", "men": "Men's self-improvement", "money": "Money psychology",
          "tech": "Technology & AI", "finance": "Finance & business"}


class Controls:
    def __init__(self, controller):
        self.c = controller
        self.publications = PublishStore(controller.store)

    def menu(self, owner):
        p = self.c.store.prefs(owner)
        ai = self.c.cfg.ai(p.ai_provider, p.ai_model)
        text = (f"CLIPER control center · {p.active_feature.upper()}\n"
                f"AI: {ai.provider}\nF1: square clips + hook title · music {'on' if p.music else 'off'}\n"
                f"F1 publishing: {'automatic' if p.auto_publish else 'approve each clip'}\n"
                f"Clipping: {'using Gemini website' if p.clipping_mode == 'gemini_browser' else 'audio-first'}\n"
                f"F2 publishing: {'automatic' if p.f2_auto_publish else 'approve each carousel'}\n"
                f"Selected niche: {NICHES.get(p.selected_niche, p.selected_niche)}")
        rows = [
            [Button("Clipping using Gemini", callback_data="ui:clipmode:gemini_browser"),
             Button("Audio-first clipping", callback_data="ui:clipmode:audio_first")],
            [Button(f"Gemini: {'GPU caption correction' if p.gemini_verify_captions else 'fast captions / manual review'}",
                    callback_data="ui:toggle:gemini_verify_captions")],
            [Button("F1 · Clips", callback_data="ui:mode:f1"), Button("F2 · Carousels", callback_data="ui:mode:f2"),
             Button("Together", callback_data="ui:mode:both")],
            [Button(f"F1 {'ON' if p.f1_enabled else 'OFF'}", callback_data="ui:toggle:f1_enabled"),
             Button(f"F2 {'ON' if p.f2_enabled else 'OFF'}", callback_data="ui:toggle:f2_enabled")],
            [Button(f"F1 auto-publish {'ON' if p.auto_publish else 'OFF'}", callback_data="ui:toggle:auto_publish"),
             Button(f"F2 auto-publish {'ON' if p.f2_auto_publish else 'OFF'}", callback_data="ui:toggle:f2_auto_publish")],
            [Button(f"Music {'ON' if p.music else 'OFF'}", callback_data="ui:toggle:music"),
             Button(f"Captions {'ON' if p.captions else 'OFF'}", callback_data="ui:toggle:captions")],
            [Button("AI provider", callback_data="ui:providers"), Button("Niches", callback_data="ui:niches")],
            [Button("Generate carousels", callback_data="ui:generate"), Button("Publishing queue", callback_data="ui:posts")],
            [Button("Schedules", callback_data="ui:schedules"), Button("Editing settings", callback_data="ui:editing")],
            [Button("Clip jobs", callback_data="ui:jobs"), Button("Help", callback_data="ui:help")],
        ]
        return text, Keyboard(rows)

    async def show(self, message, owner):
        text, keyboard = self.menu(owner)
        await message.reply_text(text, reply_markup=keyboard)

    async def callback(self, update, context):
        if not await self.c.guard(update):
            return
        q = update.callback_query
        await q.answer()
        owner = update.effective_user.id
        parts = q.data.split(":")
        try:
            if parts[0] == "pub":
                self.publications.decide(parts[2], owner, parts[1] == "approve")
                await q.message.reply_text("Queued to publish immediately." if parts[1] == "approve" else "Publication rejected.")
                await q.edit_message_reply_markup(reply_markup=None)
                return
            action = parts[1]
            p = self.c.store.prefs(owner)
            if action == "clipmode":
                p = Preferences.model_validate(p.model_dump() | {"clipping_mode": parts[2], "f1_enabled": True})
                await q.message.reply_text("Send a YouTube video link. Gemini website mode needs its saved login; "
                    "it downloads only selected ranges. Fast captions require review before publishing."
                    if p.clipping_mode == "gemini_browser" else "Audio-first clipping selected. Send a video link or upload.")
            elif action == "mode":
                p = Preferences.model_validate(p.model_dump() | {"active_feature": parts[2],
                    "f1_enabled": parts[2] in {"f1", "both"}, "f2_enabled": parts[2] in {"f2", "both"}})
            elif action == "toggle":
                key = parts[2]
                if key not in {"f1_enabled", "f2_enabled", "auto_publish", "f2_auto_publish", "music", "captions", "auto_render", "smart_crop", "music_ducking", "trim_edges", "preserve_wide_groups", "gemini_verify_captions"}:
                    raise ValueError("Unknown toggle")
                p = p.model_copy(update={key: not getattr(p, key)})
                if key in {"auto_publish", "f2_auto_publish"} and not getattr(p, key):
                    self.publications.hold_auto(owner, "f1" if key == "auto_publish" else "f2")
            elif action == "providers":
                await q.message.reply_text("Choose the AI provider for new jobs", reply_markup=Keyboard([
                    [Button(name, callback_data=f"ui:provider:{name}")] for name in PROVIDERS]))
                return
            elif action == "provider":
                provider = normalize_provider(parts[2])
                self.c.cfg.check_ai(provider)
                p = p.model_copy(update={"ai_provider": provider, "ai_model": None})
            elif action == "niches":
                await q.message.reply_text("Select a niche; enable/disable each independently.", reply_markup=Keyboard([
                    [Button(name, callback_data=f"ui:niche:{key}"),
                     Button("ON" if key in p.enabled_niches else "OFF", callback_data=f"ui:niche_toggle:{key}")]
                    for key, name in NICHES.items()]))
                return
            elif action in {"niche", "niche_toggle"}:
                niche = parts[2]
                if niche not in NICHES:
                    raise ValueError("Unknown niche")
                enabled = set(p.enabled_niches)
                if action == "niche_toggle":
                    enabled.symmetric_difference_update({niche})
                    p = p.model_copy(update={"enabled_niches": sorted(enabled)})
                else:
                    p = p.model_copy(update={"selected_niche": niche})
            elif action == "posts":
                posts = self.publications.recent(owner)
                for post in posts[:10]:
                    markup = self.publication_buttons(post)
                    await q.message.reply_text(f"{post['id']} · {post['feature']} · {post['account']} · {post['state']}\n"
                                               f"{json.loads(post['payload'])['caption']}\n"
                                               f"{json.loads(post['payload']).get('review_note', '')}\n{post['error']}", reply_markup=markup)
                if not posts:
                    await q.message.reply_text("No publications yet. Generate a clip or carousel first.")
                return
            elif action == "editing":
                await q.message.reply_text("Choose clip count, duration, title style or editing controls. "
                    "Use short clips for a single insight and longer clips when the story needs context.", reply_markup=Keyboard([
                    [Button(f"{n} clips", callback_data=f"ui:setting:clips:{n}") for n in (1, 3, 5, 10)],
                    [Button(f"{a}–{b}s", callback_data=f"ui:length:{a}:{b}") for a, b in ((15, 30), (30, 60), (60, 90))],
                    [Button(f"{n}p", callback_data=f"ui:setting:width:{n}") for n in (720, 1080)],
                    [Button(f"Hook: {style}", callback_data=f"ui:hookstyle:{style}") for style in ("auto", "curiosity", "contrast", "direct")],
                    [Button(f"Smart crop {'ON' if p.smart_crop else 'OFF'}", callback_data="ui:toggle:smart_crop"),
                     Button(f"Music ducking {'ON' if p.music_ducking else 'OFF'}", callback_data="ui:toggle:music_ducking")],
                    [Button(f"Trim silent edges {'ON' if p.trim_edges else 'OFF'}", callback_data="ui:toggle:trim_edges")],
                    [Button(f"Fit wide groups {'ON' if p.preserve_wide_groups else 'OFF'}", callback_data="ui:toggle:preserve_wide_groups")],
                    [Button(f"Auto-render {'ON' if p.auto_render else 'OFF'}", callback_data="ui:toggle:auto_render")]]))
                return
            elif action == "hookstyle":
                p = Preferences.model_validate(p.model_dump() | {"hook_style": parts[2]})
            elif action == "setting":
                if parts[2] not in {"clips", "width"}:
                    raise ValueError("Unknown setting")
                p = Preferences.model_validate(p.model_dump() | {parts[2]: int(parts[3])})
            elif action == "length":
                p = Preferences.model_validate(p.model_dump() | {"min_seconds": int(parts[2]), "max_seconds": int(parts[3])})
            elif action == "jobs":
                found = False
                for job in self.c.store.recent(owner):
                    found = True
                    await q.message.reply_text(f"{job['id']} · {job['state']} · {job['stage']}", reply_markup=Keyboard([
                        [Button("Status / clips", callback_data=f"ui:job:{job['id']}"),
                         Button("Retry", callback_data=f"ui:retry:{job['id']}")]]))
                from .faceless import FacelessStore
                f2_store = FacelessStore(self.c.store)
                for f2job in f2_store.recent(owner):
                    found = True
                    buttons = [Button("Status", callback_data=f"ui:f2job:{f2job['id']}")]
                    if f2job["state"] == "failed":
                        buttons.append(Button("Retry", callback_data=f"ui:f2retry:{f2job['id']}"))
                    await q.message.reply_text(
                        f"F2 {f2job['id']} · {f2job['niche']} · {f2job['state']}\n{f2job['stage']}",
                        reply_markup=Keyboard([buttons, [Button("Regenerate as new job", callback_data=f"ui:regen:{f2job['id']}")]])
                    )
                if not found:
                    await q.message.reply_text("No recent jobs.")
                return
            elif action in {"clipinfo", "hook"}:
                from .editorial import hook_checks
                from .models import Analysis
                from .storage import write_json
                job = self.c.store.get(parts[2], owner)
                file = self.c.store.directory(job["id"]) / "analysis.json"
                analysis = Analysis.model_validate_json(file.read_text("utf-8"))
                clip = next((c for c in analysis.clips if c.id == int(parts[3])), None)
                if not clip:
                    raise ValueError("Clip not found")
                if action == "hook":
                    index = int(parts[4])
                    if not 0 <= index < len(clip.hook_variants):
                        raise ValueError("Hook option not found")
                    with self.c.store.connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        state = db.execute("SELECT state FROM jobs WHERE id=? AND owner=?", (job["id"], owner)).fetchone()
                        if not state or state[0] != "awaiting_selection":
                            raise ValueError("Hook edits are available before rendering; submit a new job to re-edit")
                        title = clip.hook_variants[index]
                        if hook_checks(title, clip.text):
                            raise ValueError("This hook fails local title checks; choose another option")
                        clip.title = title
                        write_json(file, analysis.model_dump())
                report = clip.editorial
                await q.message.reply_text(f"Clip {clip.id} · {clip.title}\n{clip.audience_value}\n"
                    f"Speech: {report.get('words_per_minute', 'not measured')} words/min\n"
                    f"Review: {', '.join(report.get('flags', [])) or 'No local flags'}\n\n{clip.text[:1800]}",
                    reply_markup=Keyboard([[Button(f"Use: {title[:50]}",
                        callback_data=f"ui:hook:{job['id']}:{clip.id}:{n}")] for n, title in enumerate(clip.hook_variants)]))
                return
            elif action in {"job", "retry"}:
                job = self.c.store.get(parts[2], owner)
                if action == "retry":
                    self.c.store.retry(job["id"], owner, self.c.cfg.max_active_jobs, prefs=self.c.cfg.snapshot_ai(p))
                    await q.message.reply_text("Queued for retry.")
                elif job["state"] == "awaiting_selection":
                    from .models import Analysis
                    await self.c.shortlist(job, Analysis.model_validate_json(
                        (self.c.store.directory(job["id"]) / "analysis.json").read_text("utf-8")))
                else:
                    await q.message.reply_text(f"{job['state']} · {job['stage']}\n{job['error']}")
                return
            elif action in {"generate", "count", "schedules", "schedule", "f2job", "f2retry", "f2cancel", "regen"}:
                from .faceless import handle_button
                await handle_button(self, update, context, parts)
                return
            elif action == "help":
                await q.message.reply_text("F1: enable Clips, send a video link or upload, then choose clips. "
                                           "F2: enable Carousels, select a niche, then Generate. "
                                           "Automatic publishing skips approval; otherwise each finished item has Publish/Reject buttons. "
                                           "Add Instagram credentials and a public media URL locally before publishing.")
                return
            elif action != "home":
                raise ValueError("Unknown action")
            self.c.store.save_prefs(owner, Preferences.model_validate(p.model_dump()))
            await self.show(q.message, owner)
        except (ValueError, OSError) as exc:
            await q.message.reply_text(str(exc)[:1400])

    def publication_buttons(self, post):
        if post["state"] not in {"approval", "failed", "queued"}:
            return None
        return Keyboard([[Button("Publish now", callback_data=f"pub:approve:{post['id']}"),
                          Button("Reject", callback_data=f"pub:reject:{post['id']}")]])

    def clip_publication(self, job, clip, path):
        p = Preferences.model_validate_json(job["prefs"])
        selected = sorted(json.loads(job["selected"]))
        index = selected.index(clip.id) if clip.id in selected else 0
        predecessor = None
        if index:
            with self.c.store.connect() as db:
                row = db.execute("SELECT id FROM publications WHERE owner=? AND origin=?",
                                 (job["owner"], f"{job['id']}:{selected[index-1]}")).fetchone()
                predecessor = row[0] if row else None
        auto = p.auto_publish and self.c.store.prefs(job["owner"]).auto_publish
        review_note = ""
        if clip.editorial.get("automatic_ready") is False:
            auto = False
            review_note = "Local editorial checks require review: " + ", ".join(clip.editorial.get("flags", []))
        return self.publications.add(job["owner"], job["chat"], f"{job['id']}:{clip.id}", "f1", p.instagram_account,
                                     [path], clip.caption or clip.title, clip.hashtags, auto=auto,
                                     predecessor=predecessor if auto else None, gap=7200 if auto and index else 0,
                                     review_note=review_note)
