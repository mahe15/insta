import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import cv2
import numpy as np
import pytest

from cliper.bot import Controller
from cliper.carousel_models import (
    Calculation,
    CarouselPlan,
    ContentReview,
    ContentScore,
    Idea,
    Ideas,
    ImageReview,
    Slide,
)
from cliper.faceless import FacelessStore, FacelessWorker, next_daily, niche_config
from cliper.models import Preferences


def score(value=95):
    return ContentScore(**{key: value for key in ContentScore.model_fields})


def test_weighted_scores_arithmetic_and_daily_timezone():
    assert score(90).total() == 90
    assert Calculation(expression="30 * 365 / 60", result=182.5, explanation="Minutes to annual hours").result == 182.5
    for expression, result in [("__import__('os').system('anything')", 0), ("1/0", 0), ("30*365/60", 180), ("(", 0)]:
        with pytest.raises(ValueError):
            Calculation(expression=expression, result=result, explanation="invalid")
    now = datetime(2026, 9, 9, 12, 0, tzinfo=UTC).timestamp()
    due = datetime.fromtimestamp(next_daily("20:00", "Asia/Kolkata", now), UTC)
    assert (due.hour, due.minute, due.day) == (14, 30, 9)


def test_missing_character_and_feature_pause(cfg, monkeypatch):
    config = cfg.data_dir / "niches.json"
    config.write_text(json.dumps({"dark": {"character_path": ""}}))
    monkeypatch.setenv("NICHES_CONFIG_FILE", str(config))
    with pytest.raises(ValueError, match="character_path"):
        niche_config("dark")
    c = Controller(cfg)
    store = FacelessStore(c.store)
    with pytest.raises(ValueError, match="Enable"):
        store.create(42, 42, "dark", 1, Preferences())


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize("auto", [True, False])
async def test_full_carousel_pipeline_and_pre_image_gate(cfg, monkeypatch, approved, auto):
    cfg.provider = "chatgpt_browser"
    reference = cfg.data_dir / "character.png"
    frame = np.zeros((400, 320, 3), np.uint8)
    frame[:, :, 0] = np.linspace(20, 220, 400, dtype=np.uint8)[:, None]
    frame[:, :, 1] = 80
    cv2.imwrite(str(reference), frame)
    config = cfg.data_dir / "niches.json"
    config.write_text(json.dumps({"dark": {"character_path": str(reference), "instagram_account": "dark", "threshold": 90}}))
    monkeypatch.setenv("NICHES_CONFIG_FILE", str(config))
    cfg.skip_image_qa = False
    c = Controller(cfg)
    c.app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock(), send_media_group=AsyncMock()))
    prefs = Preferences(f2_enabled=True, f2_auto_publish=auto)
    c.store.save_prefs(42, prefs)
    worker = FacelessWorker(c.controls)
    publish_at = time.time() + 1800
    identity = worker.store.create(42, 42, "dark", 1, cfg.snapshot_ai(prefs), publish_at=publish_at)
    plan = CarouselPlan(topic="Start small", pillar="Discipline", hook="Start with one useful step",
                        caption="A small action makes the next step easier.", hashtags=["discipline"],
                        slides=[Slide(text=f"Step {n}", environment="Library", action="The character reads",
                                      lighting="Warm desk light", camera="Medium shot", mood="Calm",
                                      image_prompt="A cinematic portrait of the original character reading") for n in range(4)])
    calls = []

    class AI:
        def __init__(self, *args):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def structured(self, instructions, prompt, result_type, max_tokens):
            calls.append(result_type)
            assert str(reference) not in prompt
            if result_type is Ideas:
                return Ideas(ideas=[Idea(topic=f"Small action {i}", pillar="Discipline", hook=f"Start small today {i}",
                                        angle="Practice one small useful action each day", score=score()) for i in range(3)])
            if result_type is CarouselPlan:
                return plan
            return ContentReview(approved=approved, score=score(95 if approved else 70), issues=[] if approved else ["Weak payoff"])

    generated, reviewed = [], []
    class Gemini(AI):
        async def generate(self, ref, prompt, output):
            assert ContentReview in calls
            assert ref == reference
            generated.append(ref)
            cv2.imwrite(str(output), frame)
        async def review(self, ref, output, text):
            reviewed.append(text)
            return ImageReview(text_matches=True, character_matches=True, composition_ok=True, issues=[])

    monkeypatch.setattr("cliper.faceless.ScopedEditorialClient", AI)
    monkeypatch.setattr("cliper.faceless.GeminiImages", Gemini)
    monkeypatch.setattr("cliper.faceless.research", AsyncMock(return_value={"mode": "fixture", "headlines": []}))
    if not approved:
        with pytest.raises(ValueError, match="pre-image review"):
            await worker.process(worker.store.get(identity))
        assert generated == []
        assert c.controls.publications.recent(42) == []
        return
    await worker.process(worker.store.get(identity))
    assert len(generated) == len(reviewed) == 4
    assert worker.store.get(identity)["state"] == "ready"
    posts = c.controls.publications.recent(42)
    assert len(posts) == 1 and posts[0]["state"] == ("queued" if auto else "approval") and posts[0]["account"] == "dark"
    if auto:
        assert posts[0]["due"] == publish_at and c.controls.publications.claim() is None
    paths = json.loads(posts[0]["payload"])["paths"]
    assert len(paths) == 4 and cv2.imread(paths[0]).shape[:2] == (1350, 1080)
    first, last = cv2.imread(paths[0]), cv2.imread(paths[-1])
    assert np.mean(cv2.absdiff(first[-130:, -320:], last[-130:, -320:])) > 1
    await worker.process(worker.store.get(identity))
    assert len(c.controls.publications.recent(42)) == 1 and len(generated) == 4
    c.app.bot.send_media_group.assert_awaited_once()


def test_schedule_produces_early_once_and_cancel_stays_cancelled(cfg, monkeypatch):
    monkeypatch.setattr("cliper.faceless.niche_config", lambda key: {})
    c = Controller(cfg)
    c.store.save_prefs(42, Preferences(f2_enabled=True))
    store = FacelessStore(c.store)
    store.schedule(42, 42, "dark", hours=3)
    target = time.time() + 1800
    with c.store.connect() as db:
        db.execute("UPDATE content_schedules SET next_due=?", (target,))
    store.tick(cfg)
    jobs = store.recent(42)
    assert len(jobs) == 1 and jobs[0]["publish_at"] == target
    store.tick(cfg)
    assert len(store.recent(42)) == 1
    store.cancel(jobs[0]["id"], 42)
    store.update(jobs[0]["id"], state="queued", stage="Paused")
    assert store.get(jobs[0]["id"])["state"] == "cancelled" and store.claim() is None


async def test_feature_modes_and_auto_off_hold_queue(cfg):
    cfg.owners = {42}
    c = Controller(cfg)
    pub = c.controls.publications.add(42, 42, "queued", "f1", "clips", ["x.mp4"], "caption", [], auto=True)
    c.store.save_prefs(42, Preferences(auto_publish=True))
    query = SimpleNamespace(data="ui:toggle:auto_publish", answer=AsyncMock(), message=SimpleNamespace(reply_text=AsyncMock()))
    update = SimpleNamespace(effective_user=SimpleNamespace(id=42), effective_chat=SimpleNamespace(id=42, type="private"), callback_query=query)
    await c.controls.callback(update, SimpleNamespace())
    assert c.controls.publications.get(pub["id"])["state"] == "approval"
    query.data = "ui:mode:both"
    await c.controls.callback(update, SimpleNamespace())
    assert c.store.prefs(42).f1_enabled and c.store.prefs(42).f2_enabled


async def test_gemini_browser_reference_upload_download_and_review(cfg):
    import base64
    from pathlib import Path

    from cliper.gemini_images import GeminiImages
    playwright = pytest.importorskip("playwright.async_api")
    frame = np.full((400, 320, 3), (20, 80, 120), dtype=np.uint8)
    reference = cfg.data_dir / "reference.png"
    cv2.imwrite(str(reference), frame)
    encoded = base64.b64encode(reference.read_bytes()).decode()
    uploads = []
    html = '''<input type="file" multiple onchange="recordUploads([...this.files].map(f=>f.name))">
        <rich-textarea><div contenteditable="true" role="textbox"></div></rich-textarea>
        <button aria-label="Send message" onclick="send()">Send</button>
        <script>function send(){
            if(document.querySelector('input').files.length===2){
                const r=document.createElement('model-response');
                r.innerHTML='<code></code><button aria-label="Copy"></button>';
                r.querySelector('code').textContent=JSON.stringify({text_matches:true,character_matches:true,composition_ok:true,issues:[]});
                document.body.appendChild(r);
            }else{
                const b=document.createElement('button'); b.setAttribute('aria-label','Download full size');
                b.onclick=()=>{const a=document.createElement('a');a.href='data:image/png;base64,IMAGE';a.download='result.png';a.click();};
                document.body.appendChild(b);
            }
        }</script>'''.replace("IMAGE", encoded)
    async with playwright.async_playwright() as pw:
        if not Path(pw.chromium.executable_path).exists():
            pytest.skip("Optional browser test needs Chromium")
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(accept_downloads=True)
            await context.expose_function("recordUploads", lambda names: uploads.append(names))
            await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            client = GeminiImages(cfg)
            client.context = context
            for n in range(2):
                output = cfg.data_dir / f"slide{n}.png"
                await client.generate(reference, "Generate a test slide", output)
                review = await client.review(reference, output, "Test text")
                assert review.text_matches and output.exists()
            assert uploads == [["reference.png"], ["reference.png", "slide0.png"],
                               ["reference.png"], ["reference.png", "slide1.png"]]
        finally:
            await browser.close()
