import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cliper.bot import Controller
from cliper.browser_provider import BrowserEditorialClient, BrowserProviderError, ContextResult, parse_result
from cliper.config import normalize_provider
from cliper.models import Preferences, Proposals
from cliper.selection import select


def result_json(request_id="abc", summary="A complete summary"):
    return json.dumps({"request_id": request_id, "result": {"summary": summary}})


def test_strict_browser_json():
    assert parse_result(result_json(), "abc", ContextResult).summary == "A complete summary"
    assert parse_result("```json\n" + result_json() + "\n```", "abc", ContextResult).summary
    assert parse_result("JSON\n<escape>" + result_json() + "</escape>", "abc", ContextResult).summary


@pytest.mark.parametrize("raw", [
    result_json("stale"), '{"request_id":"abc","result":',
    "Here is your JSON: " + result_json(),
    result_json() + result_json(),
    '{"request_id":"abc","request_id":"abc","result":{"summary":"hello"}}',
    '{"request_id":"abc","result":{"summary":123}}',
    '{"request_id":"abc","result":{"summary":"hello","execute":"bad"}}',
    '{"request_id":"abc","result":{"summary":""}}',
    'I cannot help with that request.',
])
def test_invalid_stale_or_refused_json_rejected(raw):
    with pytest.raises(ValueError):
        parse_result(raw, "abc", ContextResult)


async def test_bounded_repair_and_no_retry_on_transport_failure(cfg, monkeypatch):
    client = BrowserEditorialClient(cfg)
    exchange = AsyncMock(return_value="invalid")
    monkeypatch.setattr(client, "exchange", exchange)
    with pytest.raises(BrowserProviderError, match="one repair"):
        await client.text("summarize", "source", 100)
    assert exchange.await_count == 2
    exchange.reset_mock()
    exchange.side_effect = BrowserProviderError("Usage limit")
    with pytest.raises(BrowserProviderError, match="Usage limit"):
        await client.text("summarize", "source", 100)
    assert exchange.await_count == 1


async def test_research_repair_preserves_visible_source_links(cfg, monkeypatch):
    client = BrowserEditorialClient(cfg)
    attempts = []
    async def exchange(payload):
        attempts.append(payload)
        client.last_web_links = [f"https://source{len(attempts)}.example/story"]
        request_id = re.search(r"Use request_id ([a-f0-9]+)\.", payload)[1]
        return "invalid" if len(attempts) == 1 else result_json(request_id)
    monkeypatch.setattr(client, "exchange", exchange)
    await client.request("Research", "topic", ContextResult, 100, allow_web_search=True)
    assert client.last_web_links == ["https://source1.example/story", "https://source2.example/story"]


async def test_browser_size_guard_and_cancellation(cfg, monkeypatch):
    client = BrowserEditorialClient(cfg)
    exchange = AsyncMock()
    monkeypatch.setattr(client, "exchange", exchange)
    with pytest.raises(BrowserProviderError, match="exceeds"):
        await client.proposals("edit", "x" * cfg.browser_max_chars, 100)
    exchange.assert_not_awaited()
    started = asyncio.Event()

    async def pending(payload):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(client, "exchange", pending)
    task = asyncio.create_task(client.text("summarize", "source", 100))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not client.request_lock.locked()


async def test_browser_routes_full_selection_without_api_keys(cfg, transcript, monkeypatch):
    cfg.provider = "chatgpt_browser"
    calls = []

    async def enter(self):
        return self

    async def leave(self, *exc):
        pass

    async def exchange(self, payload):
        calls.append(payload)
        request_id = re.search(r"Use request_id ([a-f0-9]+)\.", payload)[1]
        schema = json.loads(payload.split("JSON SCHEMA:\n")[1].split("\nSOURCE DATA:")[0])
        if "summary" in schema["properties"]["result"]["properties"]:
            result = {"summary": "A lesson about testing demand before building."}
        else:
            # $ref must resolve from the root of the envelope schema.
            assert "Proposal" in schema["$defs"]
            result = {"clips": [{"first_segment": 0, "last_segment": 3, "title": "Test demand first",
                                  "reason": "Complete lesson", "hook_text": "Why did my first project fail?",
                                  "ratings": {"hook": 80, "payoff": 80, "standalone": 85,
                                              "emotion": 70, "usefulness": 85}}]}
        return json.dumps({"request_id": request_id, "result": result})

    monkeypatch.setattr(BrowserEditorialClient, "__aenter__", enter)
    monkeypatch.setattr(BrowserEditorialClient, "__aexit__", leave)
    monkeypatch.setattr(BrowserEditorialClient, "exchange", exchange)
    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kwargs: pytest.fail("Browser must not create an API client"))
    prefs = cfg.snapshot_ai(Preferences(min_seconds=15, max_seconds=25))
    analysis = await select(transcript, prefs, cfg, AsyncMock())
    assert len(calls) == 3
    assert analysis.method == "chatgpt_browser" and analysis.model == "website-session"
    assert (analysis.clips[0].start, analysis.clips[0].end) == (0, 19)


async def test_browser_telegram_alias_and_persistence(cfg):
    cfg.owners = {42}
    assert normalize_provider("ChatGPT") == normalize_provider("browser") == "chatgpt_browser"
    assert cfg.check_ai("chatgpt").key == ""
    controller = Controller(cfg)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=42),
                             effective_chat=SimpleNamespace(id=42, type="private"), callback_query=None,
                             message=SimpleNamespace(text="/provider chatgpt", reply_text=AsyncMock()))
    await controller.command(update, SimpleNamespace(args=["chatgpt"]))
    assert controller.store.prefs(42).ai_provider == "chatgpt_browser"
    assert cfg.snapshot_ai(controller.store.prefs(42)).ai_model == "website-session"


@pytest.mark.parametrize("tag", ["article", "section"])
async def test_real_chromium_waits_for_completed_turn_and_ignores_old_reply(cfg, tag):
    playwright = pytest.importorskip("playwright.async_api")
    async with playwright.async_playwright() as pw:
        if not Path(pw.chromium.executable_path).exists():
            pytest.skip("Optional Chromium integration test requires playwright install chromium")
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.set_content('''<article><div data-message-author-role="assistant">old reply</div>
                <button data-testid="copy-turn-action-button">Copy</button></article>
                <div id="prompt-textarea" contenteditable="true"></div>
                <button data-testid="user-menu-button">Profile</button>
                <button data-testid="send-button">Send</button>''')
            client = BrowserEditorialClient(cfg)
            assert await client.signed_in(page)
            # A valid-looking JSON response pauses for > 2 seconds without the final copy action.
            await page.evaluate('''(tag) => {
                const a = document.createElement(tag);
                a.setAttribute('data-turn', 'assistant');
                a.innerHTML = '<div data-message-author-role="assistant"><div class="markdown"></div></div>';
                a.querySelector('.markdown').textContent = JSON.stringify({request_id:'abc',result:{summary:'partial'}});
                document.body.appendChild(a);
                setTimeout(() => {
                    a.querySelector('.markdown').textContent = JSON.stringify({request_id:'abc',result:{summary:'finished'}});
                    a.insertAdjacentHTML('beforeend', '<button data-testid="copy-turn-action-button">Copy</button>');
                }, 3000);
            }''', tag)
            raw = await client.wait_reply(page, before=1)
            assert parse_result(raw, "abc", ContextResult).summary == "finished"
            await page.set_content('<div role="alert">You have reached your usage limit</div>')
            with pytest.raises(BrowserProviderError, match="limit"):
                await client.wait_reply(page, before=0)
        finally:
            await browser.close()


def test_parse_result_proposals_resilient_to_long_strings_and_ratings():
    raw = json.dumps({
        "request_id": "test_req",
        "result": {
            "clips": [
                {
                    "first_segment": 0,
                    "last_segment": 5,
                    "title": "A" * 110,
                    "reason": "B" * 600,
                    "hook_text": "So every time when I saw them, you know, going out, and you know, making a lot of money and being successful, I felt like, you know, inferior from them. " * 3,
                    "ratings": {"hook": 9, "payoff": 8.5, "standalone": 9, "emotion": 8, "usefulness": 9.5, "extra": "ignored"},
                    "music_category": "unrecognized_genre",
                    "caption": "Check this out!",
                    "hashtags": ["#one", "#two", "#three", "#four", "#five", "#six"],
                    "hook_variants": ["Hook 1", "Hook 2", "Hook 3", "Hook 4"],
                    "audience_value": "Very insightful career and life advice for ambitious viewers"
                }
            ]
        }
    })
    proposals = parse_result(raw, "test_req", Proposals)
    assert len(proposals.clips) == 1
    clip = proposals.clips[0]
    assert len(clip.title) <= 120
    assert len(clip.reason) <= 1000
    assert len(clip.hook_text) <= 500
    assert clip.ratings.hook == 90
    assert clip.ratings.payoff == 85
    assert clip.music_category == "chill_ambient"
    assert len(clip.hashtags) == 5
    assert len(clip.hook_variants) == 3


def test_parse_result_context_result_long_summary():
    long_text = "The guest discusses career perspectives and lessons. " * 300
    assert len(long_text) > 10000
    raw = json.dumps({"request_id": "summary_req", "result": {"summary": long_text}})
    result = parse_result(raw, "summary_req", ContextResult)
    assert len(result.summary) > 10000
