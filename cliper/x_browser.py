"""Visible X composer automation in CLIPER's existing shared Chromium profile."""
from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path
from urllib.parse import urlsplit

from .browser_provider import BrowserEditorialClient, BrowserProviderError, STEALTH_SCRIPT
from .x_content import check_text


class XBrowser(BrowserEditorialClient):
    async def account(self, page, expected):
        link = page.locator('a[data-testid="AppTabBar_Profile_Link"]')
        try:
            await link.wait_for(state="visible", timeout=20000)
        except Exception:
            arkose = page.locator('iframe[src*="arkoselabs"], iframe[title*="challenge" i]')
            if await arkose.count() and await arkose.first.is_visible():
                raise BrowserProviderError(
                    "X presented a bot verification challenge (Arkose). Open scripts/x-login.ps1 to solve it in the browser."
                ) from None
            raise BrowserProviderError("Sign in to X in the shared Chromium profile using scripts/x-login.ps1") from None
        actual = urlsplit(await link.get_attribute("href")).path.strip("/")
        if actual.lower() != expected.lower():
            raise ValueError(f"Wrong X account is signed in. Expected @{expected}; switch accounts before publishing")

    async def publish(self, handle: str, text: str, media: Path, alt: str, submitting):
        check_text(text)
        page = await self.context.new_page()
        try:
            await page.add_init_script(STEALTH_SCRIPT)
        except Exception:
            pass
        try:
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
            await self.account(page, handle)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=45000)
            editor = page.locator('[data-testid="tweetTextarea_0"]').first
            await editor.wait_for(state="visible", timeout=15000)
            try:
                await editor.hover()
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await editor.click()
            except Exception:
                pass
            try:
                await editor.press_sequentially(text, delay=random.randint(10, 25))
            except Exception:
                await editor.fill(text)
            if (await editor.inner_text()).strip() != text.strip():
                await editor.fill(text)
            await asyncio.sleep(random.uniform(0.4, 0.8))
            await page.locator('input[data-testid="fileInput"]').first.set_input_files(str(media.resolve()))
            attachments = page.locator('[data-testid="attachments"]').first
            await attachments.wait_for(state="visible", timeout=60000)
            if media.suffix.lower() in {".jpg", ".jpeg", ".png"} and alt:
                description = page.get_by_role("button", name=re.compile("Add description|Add image description", re.I)).first
                if await description.is_visible():
                    try:
                        await description.hover()
                        await asyncio.sleep(random.uniform(0.1, 0.2))
                    except Exception:
                        pass
                    await description.click()
                    field = page.get_by_role("textbox", name=re.compile("description", re.I)).first
                    await field.fill(alt[:1000])
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await page.get_by_role("button", name="Save", exact=True).click()
            button = page.locator('[data-testid="tweetButton"]').first
            deadline = asyncio.get_running_loop().time() + 180
            while not await button.is_enabled():
                if asyncio.get_running_loop().time() > deadline:
                    raise ValueError("X did not finish preparing the attachment; nothing was submitted")
                await asyncio.sleep(.5)
            if (await editor.inner_text()).strip() != text.strip():
                raise ValueError("X composer text does not match the approved draft")
            if await page.locator('[data-testid="toast"]').filter(has_text=re.compile("failed|error|unsupported", re.I)).count():
                raise ValueError("X reported an attachment error; nothing was submitted")
            arkose = page.locator('iframe[src*="arkoselabs"], iframe[title*="challenge" i]')
            if await arkose.count() and await arkose.first.is_visible():
                raise BrowserProviderError("X triggered an Arkose bot verification challenge; submission held.")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            try:
                await button.hover()
                await asyncio.sleep(random.uniform(0.2, 0.4))
            except Exception:
                pass
            # Commit submission intent before the sole irreversible UI action. Any subsequent failure is uncertain.
            submitting()
            await button.click(timeout=10000)
            sent = page.locator('[data-testid="toast"] a[href*="/status/"]').first
            await sent.wait_for(state="visible", timeout=30000)
            href = await sent.get_attribute("href")
            url = "https://x.com" + href if href.startswith("/") else href
            parsed = urlsplit(url)
            if parsed.hostname not in {"x.com", "www.x.com", "twitter.com"} or not re.fullmatch(r"/[A-Za-z0-9_]+/status/\d+", parsed.path):
                raise ValueError("X submission has no usable confirmation URL; inspect your profile")
            author = parsed.path.split("/")[1]
            if author.lower() != handle.lower() and author != "i":
                raise ValueError("X confirmation points at a different account")
            return url
        finally:
            if not page.is_closed():
                await page.close()


async def login(cfg):
    from dataclasses import replace
    async with XBrowser(replace(cfg, browser_headless=False)) as browser:
        page = await browser.context.new_page()
        try:
            await page.add_init_script(STEALTH_SCRIPT)
        except Exception:
            pass
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
        print("Sign in to the intended X account in the shared CLIPER Chromium. Close this browser when finished.", flush=True)
        while browser.context.pages:
            await asyncio.sleep(.5)

