"""Real browser actions against isolated state; no model, Telegram or publish calls."""
import asyncio
import json
import socket
import threading
from pathlib import Path

import pytest

from cliper.models import Analysis, Preferences
from cliper.publishing import PublishStore
from cliper.storage import Store, write_json
from cliper.web import create_app


async def test_studio_browser_real_mutations(cfg, transcript, clip, monkeypatch):
    playwright = pytest.importorskip("playwright.async_api")
    uvicorn = pytest.importorskip("uvicorn")
    root = Path(__file__).resolve().parents[1]
    dist = root / "frontend" / "dist"
    if not (dist / "index.html").exists():
        pytest.skip("Build frontend first to run browser integration")
    monkeypatch.setenv("NICHES_CONFIG_FILE", str(cfg.data_dir / "config" / "niches.json"))
    monkeypatch.setenv("INSTAGRAM_ACCOUNTS_FILE", str(cfg.data_dir / "config" / "instagram.json"))
    cfg.owners = {7}
    store = Store(cfg.data_dir)
    prefs = Preferences(min_seconds=15, max_seconds=25)
    store.save_prefs(7, prefs)
    job = store.create(7, 0, "https://youtu.be/fixture", prefs)
    folder = store.directory(job["id"])
    write_json(folder / "analysis.json", Analysis(title="A smaller test changed the whole plan", language="en", duration=40,
        method="fixture", clips=[clip]).model_dump())
    write_json(folder / "transcript.json", transcript.model_dump())
    store.update(job["id"], state="awaiting_selection")
    # No external media is required for the publication state-machine test.
    pub = PublishStore(store)
    post = pub.add(7, 0, "fixture:1", "f1", "clips", [], "A complete useful story. #learning", [])
    app = create_app(cfg, start_engine=False, token="isolated-test-key", project_root=cfg.data_dir, static_root=dist)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(.05)
    assert server.started
    errors = []
    try:
        async with playwright.async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
            except playwright.Error as exc:
                if "Executable doesn't exist" in str(exc):
                    pytest.skip("Playwright Chromium is not installed")
                raise
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(f"http://127.0.0.1:{port}/#key=isolated-test-key")
            await page.get_by_role("heading", name="Make something worth watching.").wait_for()
            assert "key=" not in page.url
            await page.get_by_role("link").filter(has_text="A smaller test changed the whole plan").click()
            title = page.get_by_label("Hook title", exact=False)
            await title.fill("One small test changed the plan")
            await page.get_by_role("button", name="Save edits", exact=True).click()
            await page.get_by_text("Clip edits saved.", exact=False).wait_for()
            analysis = json.loads((folder / "analysis.json").read_text("utf-8"))
            assert analysis["clips"][0]["title"] == "One small test changed the plan"
            await page.get_by_role("button", name="Edit settings", exact=True).click()
            dialog = page.get_by_role("dialog")
            await dialog.get_by_role("switch", name="Background music", exact=True).click()
            await dialog.get_by_role("button", name="Save project settings").click()
            await page.get_by_text("Editing settings saved for this project only.", exact=True).wait_for()
            assert json.loads(store.get(job["id"])["prefs"])["music"] is False
            assert store.prefs(7).music is True
            await page.get_by_role("checkbox", name="Select clip 1", exact=True).check()
            await page.get_by_role("button", name="Render 1 selected", exact=True).click()
            await page.get_by_text("1 clips queued for rendering.", exact=True).wait_for()
            assert store.get(job["id"])["state"] == "queued_render"

            await page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Settings", exact=True).click()
            await page.get_by_role("switch", name="Background music", exact=True).click()
            await page.get_by_role("button", name="Save changes", exact=True).first.click()
            await page.get_by_text("Preferences saved. New projects will use these settings.", exact=True).wait_for()
            assert store.prefs(7).music is False
            await page.reload()
            await page.get_by_role("switch", name="Background music", exact=True).wait_for()
            assert await page.get_by_role("switch", name="Background music", exact=True).get_attribute("aria-checked") == "false"

            await page.get_by_role("button", name="New project", exact=False).first.click()
            await page.get_by_label("Video or saved stream URL").fill("https://evil.invalid/video")
            await page.get_by_role("button", name="Create project", exact=True).click()
            await page.get_by_role("dialog").get_by_role("alert").wait_for()
            assert len(store.recent(7)) == 1
            await page.get_by_label("Video or saved stream URL").fill("https://youtu.be/another-source")
            await page.get_by_role("button", name="Create project", exact=True).click()
            await page.get_by_text("Project added to your production queue.", exact=True).wait_for()
            new_id = page.url.rsplit("/", 1)[-1]
            assert store.get(new_id)["chat"] == 0
            await page.get_by_role("button", name="Cancel project", exact=True).click()
            await page.get_by_role("dialog").get_by_role("button", name="Cancel project", exact=True).click()
            await page.get_by_text("Project cancelled.", exact=True).wait_for()
            assert store.get(new_id)["state"] == "cancelled"

            await page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Publishing", exact=True).click()
            await page.locator(".publication-card").first.click()
            await page.get_by_label("Caption & hashtags", exact=False).fill("A reviewed caption. #learning")
            await page.get_by_role("button", name="Save details", exact=True).click()
            await page.get_by_text("Publication details saved.", exact=True).wait_for()
            assert json.loads(pub.get(post["id"])["payload"])["caption"] == "A reviewed caption. #learning"
            await page.get_by_role("button", name="Publish now", exact=True).click()
            # Approving changes only the isolated DB; there is no running publisher.
            await page.get_by_role("dialog").filter(has_text="Publish this post now?").get_by_role("button", name="Publish now", exact=True).click()
            await page.get_by_text("Publication approved and queued to publish now.", exact=True).wait_for()
            assert pub.get(post["id"])["state"] == "queued"
            await page.goto(f"http://127.0.0.1:{port}/speed")
            await page.get_by_role("heading", name="Find the moment. Keep the reaction.").wait_for()
            await page.get_by_label("YouTube stream or video link").fill("https://youtu.be/abcdefghijk")
            await page.get_by_label("Maximum seconds", exact=True).fill("12")
            await page.get_by_role("switch", name="Sound accents", exact=True).click()
            await page.get_by_role("button", name="Find Speed moments", exact=True).click()
            await page.get_by_text("Speed project added.", exact=False).wait_for()
            speed_job = store.get(page.url.rsplit("/", 1)[-1])
            speed_prefs = json.loads(speed_job["prefs"])
            assert speed_prefs["editorial_profile"] == "ishowspeed"
            assert speed_prefs["text_mode"] == "english" and speed_prefs["max_seconds"] == 12
            assert speed_prefs["sound_effects"] is False
            await page.goto(f"http://127.0.0.1:{port}/settings")
            await page.get_by_label("Hook & caption language", exact=False).select_option("source")
            await page.get_by_role("button", name="Save changes", exact=True).first.click()
            await page.get_by_text("Preferences saved.", exact=False).wait_for()
            assert store.prefs(7).text_mode == "source"
            await page.goto(f"http://127.0.0.1:{port}/x")
            await page.get_by_role("heading", name="A sharper take. A stronger source.").wait_for()
            await page.get_by_label("Keywords or topic", exact=False).fill("Arsenal midfield")
            await page.get_by_role("button", name="Research a post", exact=True).click()
            await page.get_by_text("Research queued. Follow its progress below.", exact=True).wait_for()
            assert app.state.x_store.recent(7)[0]["request"]["keywords"] == "Arsenal midfield"
            await page.get_by_role("button", name="Account & automation", exact=True).click()
            await page.get_by_label("X username", exact=False).fill("fixture")
            await page.get_by_role("button", name="Save X settings", exact=True).click()
            await page.get_by_text("X settings saved.", exact=True).wait_for()
            assert app.state.x_store.settings(7).handle == "fixture"
            assert not app.state.x_store.settings(7).auto_publish
            await page.keyboard.press("Escape")
            await page.set_viewport_size({"width": 390, "height": 844})
            assert not await page.evaluate("document.documentElement.scrollWidth > innerWidth")
            assert not errors
            await browser.close()
    finally:
        server.should_exit = True
        await asyncio.to_thread(thread.join, 10)
