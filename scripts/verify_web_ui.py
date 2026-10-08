"""Read-only real-workspace browser checks. Does not submit jobs or publish."""
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / "data" / "browsers" / "engines"))


async def main():
    folder = ROOT / "data" / "verification" / "web-studio"
    folder.mkdir(parents=True, exist_ok=True)
    errors, results = [], {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        response = await context.request.post("http://127.0.0.1:8788/api/session", data={"key": (ROOT / "data" / "web" / "access-key").read_text("utf-8")})
        assert response.ok
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        for path, name in [("/", "studio"), ("/speed", "speed"), ("/x", "x-studio"), ("/carousels", "carousels"), ("/publishing", "publishing"), ("/music", "music"), ("/settings", "settings")]:
            await page.goto("http://127.0.0.1:8788" + path)
            await page.locator("h1").first.wait_for()
            await page.wait_for_timeout(800)
            results[name] = {"heading": await page.locator("h1").first.inner_text(), "overflow": await page.evaluate("document.documentElement.scrollWidth > innerWidth")}
            await page.screenshot(path=str(folder / f"{name}-desktop.png"), full_page=True)
        await page.goto("http://127.0.0.1:8788/")
        await page.get_by_role("button", name="New project", exact=False).first.click()
        await page.get_by_role("dialog").wait_for()
        await page.screenshot(path=str(folder / "intake-desktop.png"))
        await page.keyboard.press("Escape")
        assert await page.get_by_role("dialog").count() == 0
        await page.keyboard.press("Control+k")
        await page.get_by_role("dialog").wait_for()
        await page.get_by_role("textbox", name="Search projects and pages").fill("music")
        await page.get_by_role("dialog").get_by_role("button", name="Music library").click()
        assert page.url.endswith("/music")
        results["keyboard"] = "New project opens; Escape closes; Ctrl+K navigates"
        jobs = await (await context.request.get("http://127.0.0.1:8788/api/jobs")).json()
        if jobs:
            chosen = next((j for j in jobs if j["rendered"]), jobs[0])
            await page.goto("http://127.0.0.1:8788/project/" + chosen["id"])
            await page.locator(".project-heading").wait_for()
            await page.wait_for_timeout(1200)
            await page.screenshot(path=str(folder / "project-desktop.png"), full_page=True)
            results["project"] = {"overflow": await page.evaluate("document.documentElement.scrollWidth > innerWidth")}
        await page.set_viewport_size({"width": 390, "height": 844})
        for path, name in [("/", "studio"), ("/speed", "speed"), ("/x", "x-studio"), ("/carousels", "carousels"), ("/publishing", "publishing"), ("/music", "music"), ("/settings", "settings")]:
            await page.goto("http://127.0.0.1:8788" + path)
            await page.locator("h1").first.wait_for()
            await page.wait_for_timeout(350)
            overflow = await page.evaluate("document.documentElement.scrollWidth > innerWidth")
            results[name + "_mobile"] = {"overflow": overflow}
            await page.screenshot(path=str(folder / f"{name}-mobile.png"), full_page=True)
        await page.get_by_role("button", name="Open navigation").click()
        await page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Music library").click()
        assert page.url.endswith("/music")
        results["mobile_navigation"] = "passed"
        results["page_errors"] = errors
        (folder / "browser-checks.json").write_text(json.dumps(results, indent=2), "utf-8")
        await browser.close()
    print(json.dumps(results, indent=2))


asyncio.run(main())
