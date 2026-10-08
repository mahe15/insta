import asyncio
import hashlib
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from cliper.storage import Store
from cliper.web import create_app
from cliper.x_browser import XBrowser
from cliper.x_content import (
    DraftResult,
    ResearchInput,
    ResearchResult,
    XSettings,
    check_text,
    commons_image,
    evidence_flags,
    research,
    text_weight,
)
from cliper.x_studio import XStore, XWorker, fingerprint


def evidence():
    now = datetime.now(UTC).isoformat()
    return ResearchResult.model_validate({"web_search_used": True, "topic": "A club changes its shape", "event_at": now,
        "sources": [{"url": "https://club.example/news/shape", "title": "The official shape announcement", "publisher": "Club", "primary": True, "published_at": now, "evidence": "The club confirmed a new tactical setup."},
                    {"url": "https://league.example/news/shape", "title": "The league confirms a tactical update", "publisher": "League", "primary": False, "published_at": now, "evidence": "The league confirmed the same tactical setup."}],
        "claims": ["A tactical setup changed."], "media_query": "football stadium", "audience_value": "Understand how the new shape affects midfield."})


def make_ready(db, owner=7, phrase="The midfield shape changed. Here is why it matters."):
    db.save_settings(owner, XSettings(handle="fixture", browser_risk_accepted=True))
    job = db.create(owner, ResearchInput())
    path = db.folder(job["id"]) / "media.jpg"
    Image.new("RGB", (400, 400), "green").save(path)
    result = {"text": phrase, "researched_at": time.time(), "flags": [], "human_reviewed": True,
              "research": evidence().model_dump(mode="json"),
              "media": {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "reviewed": True,
                        "kind": "image", "alt": "A generic football pitch", "license": "Owner-confirmed rights"}}
    db.update(job["id"], state="review", result=result, fingerprint=fingerprint(phrase))
    return db.get(job["id"], owner)


def test_live_evidence_missing_citations_is_review_only():
    result = evidence()
    assert evidence_flags(result, [s.url for s in result.sources], 24) == []
    assert "citation" in evidence_flags(result, [], 24)[0]
    result.web_search_used = False
    with pytest.raises(ValueError, match="live web"):
        evidence_flags(result, [], 24)


@pytest.mark.parametrize("hours", [-25, 2])
def test_old_or_future_event_is_rejected(hours):
    result = evidence()
    result.event_at = datetime.now(UTC) + timedelta(hours=hours)
    with pytest.raises(ValueError, match="freshness"):
        evidence_flags(result, [s.url for s in result.sources], 24)


@pytest.mark.parametrize("text", ["x" * 281, "Look @stranger this is a promotion", "#one #two #three"])
def test_post_bounds_and_unsolicited_mentions(text):
    with pytest.raises(ValueError):
        check_text(text)
    assert text_weight("https://example.com/" + "x" * 200) == 23


def test_owner_fencing_approval_and_immutable_media(cfg):
    db = XStore(Store(cfg.data_dir))
    job = make_ready(db)
    with pytest.raises(ValueError, match="not found"):
        db.get(job["id"], 8)
    db.approve(job["id"], 7)
    with pytest.raises(ValueError):
        db.approve(job["id"], 7)
    (db.folder(job["id"]) / "media.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        db.ready(db.get(job["id"], 7))


def test_auto_holds_flags_and_disabling_holds_existing(cfg):
    db = XStore(Store(cfg.data_dir))
    job = make_ready(db)
    settings = XSettings(handle="fixture", auto_publish=True, browser_risk_accepted=True)
    db.save_settings(7, settings)
    flagged = job | {"result": job["result"] | {"flags": ["Unconfirmed source"]}}
    with pytest.raises(ValueError, match="editorial review"):
        db.ready(flagged, automatic=True)
    db.approve(job["id"], 7, automatic=True)
    settings.auto_publish = False
    db.save_settings(7, settings)
    assert db.get(job["id"], 7)["state"] == "review"


def test_rate_limit_freshness_and_uncertain_recovery(cfg):
    db = XStore(Store(cfg.data_dir))
    job = make_ready(db)
    db.approve(job["id"], 7)
    claimed = db.claim()
    assert claimed["state"] == "preparing"
    db.update(job["id"], state="publishing", submitted=time.time())
    db.recover()
    assert db.get(job["id"], 7)["state"] == "uncertain"
    second = make_ready(db, phrase="A different club has a different tactical update.")
    db.approve(second["id"], 7)
    assert db.claim() is None  # uncertain attempt counts against the gap
    result = second["result"] | {"researched_at": time.time() - 25 * 3600}
    db.update(second["id"], result=result)
    with pytest.raises(ValueError, match="stale"):
        db.ready(db.get(second["id"], 7))


def test_schedule_does_not_backfill_a_burst(cfg):
    db = XStore(Store(cfg.data_dir))
    db.save_schedule(7, ResearchInput(keywords="club tactics"), 12, True)
    with db.store.connect() as connection:
        connection.execute("UPDATE x_schedules SET next_run=1")
    db.schedule_tick()
    db.schedule_tick()
    assert len(db.recent(7)) == 1
    assert db.schedules(7)[0]["next_run"] > time.time()


def test_duplicate_edit_has_actionable_error(cfg):
    db = XStore(Store(cfg.data_dir))
    first = make_ready(db)
    second = make_ready(db, phrase="A second story with a different explanation.")
    with pytest.raises(ValueError, match="duplicates"):
        db.save_draft(second["id"], 7, first["result"]["text"], True)


async def test_media_search_never_fetches_ai_or_private_urls(tmp_path):
    calls = []
    def respond(request):
        calls.append(request.url.host)
        return httpx.Response(200, json={"query": {"pages": {"1": {"imageinfo": [{
            "url": "https://127.0.0.1/private", "mime": "image/jpeg", "size": 1000, "width": 600, "height": 400,
            "extmetadata": {"LicenseShortName": {"value": "Public domain"}}}]}}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await commons_image("football", tmp_path, client=client) is None
    assert calls == ["commons.wikimedia.org"]


async def test_media_download_decodes_and_preserves_license(tmp_path):
    output = BytesIO()
    Image.new("RGB", (400, 400), "blue").save(output, format="JPEG")
    def respond(request):
        if request.url.host == "upload.wikimedia.org":
            return httpx.Response(200, content=output.getvalue())
        return httpx.Response(200, json={"query": {"pages": {"1": {"title": "File:Football pitch", "imageinfo": [{
            "url": "https://upload.wikimedia.org/example.jpg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Football_pitch",
            "mime": "image/jpeg", "size": 1000, "width": 400, "height": 400,
            "extmetadata": {"LicenseShortName": {"value": "CC0"}, "Artist": {"value": "Photographer"}}}]}}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await commons_image("football", tmp_path, client=client)
    assert result["license"] == "CC0" and not result["reviewed"]
    assert (tmp_path / result["file"]).exists()


def test_x_api_auth_upload_review_and_scheduling(cfg):
    cfg.owners = {7}
    app = create_app(cfg, start_engine=False, token="fixture-key", project_root=cfg.data_dir)
    with TestClient(app) as client:
        assert client.get("/api/x").status_code == 401
        response = client.post("/api/session", json={"key": "fixture-key"})
        assert client.post("/api/x/research", json={}).status_code == 403
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert len(client.get("/api/x").json()["categories"]) == 6
        assert client.put("/api/x/settings", json={"auto_publish": True}).status_code == 400
        job = client.post("/api/x/research", json={"category": "football", "keywords": "Arsenal"}).json()
        assert job["state"] == "queued"
        assert client.post(f"/api/x/jobs/{job['id']}/approve", json={}).status_code == 400
        assert client.put("/api/x/schedule", json={"request": {"category": "football"}, "hours": 12}).status_code == 200
        image = BytesIO()
        Image.new("RGB", (800, 800), "green").save(image, format="PNG", compress_level=0)
        assert len(image.getvalue()) > 1024**2  # multipart uploads bypass the JSON 1 MB limit
        response = client.post("/api/x/library", data={"category": "football", "alt": "A generic football pitch", "rights": "true"}, files={"file": ("pitch.png", image.getvalue(), "image/png")})
        assert response.status_code == 200, response.text
        media = response.json()
        assert client.get(f"/api/x/library/{media['id']}/media").headers["content-type"] == "image/png"
        assert client.delete(f"/api/x/library/{media['id']}").status_code == 200
        assert client.get(f"/api/x/library/{media['id']}/media").status_code == 404
        assert client.post("/api/x/library", data={"category": "football", "alt": "A pitch", "rights": "false"}, files={"file": ("pitch.jpg", image.getvalue(), "image/jpeg")}).status_code == 400


async def test_worker_uses_existing_profile_and_never_retries_uncertain(cfg, monkeypatch):
    from cliper.browser_provider import BrowserEditorialClient
    base, publisher = BrowserEditorialClient(cfg), XBrowser(cfg)
    assert base.profile == publisher.profile and base.lock.lock_file == publisher.lock.lock_file
    worker = XWorker(cfg, Store(cfg.data_dir))
    job = make_ready(worker.db)
    worker.db.approve(job["id"], 7)
    class Browser:
        def __init__(self, cfg): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def publish(self, handle, text, path, alt, submitting):
            submitting()
            raise RuntimeError("Lost connection after submit")
    monkeypatch.setattr("cliper.x_browser.XBrowser", Browser)
    task = asyncio.create_task(worker.run())
    for _ in range(100):
        if worker.db.get(job["id"], 7)["state"] == "uncertain":
            break
        await asyncio.sleep(.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert worker.db.get(job["id"], 7)["state"] == "uncertain"
    assert worker.db.claim() is None


async def test_research_failure_does_not_produce_a_publishable_job(cfg, monkeypatch):
    worker = XWorker(cfg, Store(cfg.data_dir))
    job = worker.db.create(7, ResearchInput())
    monkeypatch.setattr("cliper.x_studio.research", AsyncMock(side_effect=ValueError("No fresh sources")))
    task = asyncio.create_task(worker.run())
    for _ in range(100):
        if worker.db.get(job["id"], 7)["state"] == "failed":
            break
        await asyncio.sleep(.01)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert worker.db.get(job["id"], 7)["state"] == "failed"
    assert not worker.db.get(job["id"], 7)["result"]


async def test_research_retries_stale_story_with_explicit_cutoff(cfg, monkeypatch):
    fresh = evidence()
    old = fresh.model_copy(update={"event_at": datetime.now(UTC) - timedelta(hours=25)})
    draft = DraftResult(text="A new tactical shape changes how the midfield builds attacks.", reasoning="A precise development and useful implication.", hook_score=80, clarity_score=90, source_score=90, media_relevant=True)
    calls = []
    class Browser:
        def __init__(self, cfg): self.last_web_links = [s.url for s in fresh.sources]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def request(self, system, prompt, schema, tokens, **kwargs):
            calls.append((prompt, kwargs))
            return [old, fresh, draft][len(calls) - 1]
    monkeypatch.setattr("cliper.x_content.BrowserEditorialClient", Browser)
    result = await research(cfg, ResearchInput(), [], "A football pitch")
    assert len(calls) == 3 and calls[0][1]["allow_web_search"]
    assert "Only developments AFTER" in calls[0][0]
    assert "do not adjust dates" in calls[1][0]
    assert result["flags"] == []


def test_scheduled_post_rechecks_event_age(cfg):
    db = XStore(Store(cfg.data_dir))
    job = make_ready(db)
    job["result"]["research"]["event_at"] = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    with pytest.raises(ValueError, match="event is stale"):
        db.ready(job)


async def test_telegram_x_command_is_private_and_queues_keywords(cfg):
    from types import SimpleNamespace

    from cliper.bot import Controller
    cfg.owners = {7}
    controller = Controller(cfg)
    message = SimpleNamespace(text="/xpost football Arsenal tactics", reply_text=AsyncMock())
    update = SimpleNamespace(effective_user=SimpleNamespace(id=7), effective_chat=SimpleNamespace(type="group"),
                             message=message, effective_message=message, callback_query=None)
    await controller.x_command(update, SimpleNamespace(args=["football", "Arsenal", "tactics"]))
    db = XStore(controller.store)
    assert not db.recent(7)
    update.effective_chat.type = "private"
    await controller.x_command(update, SimpleNamespace(args=["football", "Arsenal", "tactics"]))
    assert db.recent(7)[0]["request"]["keywords"] == "Arsenal tactics"


@pytest.mark.parametrize("handle", ["fixture", "wrong_account"])
async def test_real_chromium_composer_upload_and_identity_guard(cfg, handle):
    from playwright.async_api import async_playwright
    page_html = '''<a data-testid="AppTabBar_Profile_Link" href="/fixture">Profile</a>
    <div contenteditable="true" data-testid="tweetTextarea_0"></div>
    <input type="file" data-testid="fileInput" onchange="document.getElementById('attachments').style.display='block';document.getElementById('post').disabled=false">
    <div id="attachments" data-testid="attachments" style="display:none">Image ready</div>
    <button id="post" data-testid="tweetButton" disabled onclick="document.getElementById('toast').innerHTML='<a href=/fixture/status/123456789>View</a>'">Post</button>
    <div id="toast" data-testid="toast"></div>'''
    path = cfg.data_dir / "upload.jpg"
    Image.new("RGB", (400, 400), "green").save(path)
    submitted = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.route("https://x.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body=page_html))
        adapter = XBrowser(cfg)
        adapter.context = context
        if handle == "fixture":
            url = await adapter.publish(handle, "A grounded update from the original source.", path, "", lambda: submitted.append(True))
            assert url == "https://x.com/fixture/status/123456789" and submitted == [True]
        else:
            with pytest.raises(ValueError, match="Wrong X account"):
                await adapter.publish(handle, "A grounded update.", path, "", lambda: submitted.append(True))
            assert not submitted
        await browser.close()
