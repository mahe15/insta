import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import openai
import pytest
from pydantic import ValidationError

from cliper.bot import Controller
from cliper.config import Config, normalize_provider
from cliper.models import Preferences, Proposal, Proposals, Ratings
from cliper.pipeline import safe_error
from cliper.providers import EditorialClient, verify_model
from cliper.selection import select
from cliper.storage import Store


def proposals_json():
    return Proposals(clips=[Proposal(first_segment=0, last_segment=3, title="Test an idea first",
                                     reason="Complete setup and payoff", hook_text="Why did my first project fail?",
                                     ratings=Ratings(hook=80, payoff=80, standalone=85, emotion=70,
                                                     usefulness=85))]).model_dump_json()


def completion(content, finish="stop", refusal=None):
    return {"id": "test-completion", "object": "chat.completion", "created": 1, "model": "test-model",
            "choices": [{"index": 0, "finish_reason": finish,
                         "message": {"role": "assistant", "content": content, "refusal": refusal}}]}


@pytest.mark.parametrize(("provider", "host", "key"), [
    ("xai", "api.x.ai", "xai-test-secret"),
    ("gemini", "generativelanguage.googleapis.com", "gemini-test-secret"),
])
async def test_real_sdk_provider_routing_and_full_selection(monkeypatch, cfg, transcript, provider, host, key):
    cfg.provider = "openai"
    cfg.api_key = "openai-must-not-be-used"
    cfg.xai_api_key, cfg.gemini_api_key = "xai-test-secret", "gemini-test-secret"
    requests = []

    def handler(request):
        requests.append(request)
        payload = json.loads(request.content)
        content = proposals_json() if "response_format" in payload else "A lesson about testing demand early."
        return httpx.Response(200, json=completion(content))

    real_client = openai.AsyncOpenAI
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **kwargs: real_client(
        **kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    prefs = cfg.snapshot_ai(Preferences(ai_provider=provider, min_seconds=15, max_seconds=25))
    analysis = await select(transcript, prefs, cfg, AsyncMock())
    assert len(requests) == 3  # full context, discovery, critique
    assert analysis.method == provider and analysis.model == cfg.ai(provider).model
    assert analysis.clips[0].selection_method == provider
    assert (analysis.clips[0].start, analysis.clips[0].end) == (0, 19)
    for request in requests:
        assert request.url.host == host
        assert str(request.url).endswith("/chat/completions")
        assert request.headers["authorization"] == f"Bearer {key}"
        payload = json.loads(request.content)
        assert payload["model"] == prefs.ai_model
        assert payload["reasoning_effort"] == "low"
        assert "store" not in payload and "openai-must-not-be-used" not in str(payload)
    schema = json.loads(requests[-1].content)["response_format"]["json_schema"]
    if provider == "gemini":
        assert "strict" not in schema
        assert "$defs" not in schema["schema"]
        assert "hook" in schema["schema"]["properties"]["clips"]["items"]["properties"]["ratings"]["properties"]
    else:
        assert schema["strict"] is True
        assert schema["schema"]["$defs"]["Ratings"]["properties"]["hook"]["maximum"] == 100


@pytest.mark.parametrize("provider", ["xai", "gemini"])
@pytest.mark.parametrize(("payload", "error"), [
    (completion("{truncated", "length"), ValueError),
    (completion(None, "stop", "declined"), ValueError),
    (completion("not JSON"), ValidationError),
    (completion('{"clips": [{"invented": true}]}'), ValidationError),
    ({"id": "empty", "created": 1, "model": "test", "choices": []}, ValueError),
])
async def test_invalid_blocked_or_incomplete_provider_output(cfg, provider, payload, error):
    cfg.xai_api_key, cfg.gemini_api_key = "xai-key", "gemini-key"
    settings = cfg.ai(provider)
    async with openai.AsyncOpenAI(api_key=settings.key, base_url=settings.base_url,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(
                                     lambda request: httpx.Response(200, json=payload)))) as client:
        with pytest.raises(error):
            await EditorialClient(client, settings).proposals("edit", "transcript", 5000)


@pytest.mark.parametrize("provider", ["xai", "gemini"])
async def test_provider_failure_does_not_fall_back_or_leak_keys(cfg, provider):
    cfg.api_key, cfg.xai_api_key, cfg.gemini_api_key = "oa-secret", "xa-secret", "gg-secret"
    settings = cfg.ai(provider)
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(429, json={"error": {"message": "Quota exceeded", "type": "rate_limit"}})

    async with openai.AsyncOpenAI(api_key=settings.key, base_url=settings.base_url, max_retries=0,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
        with pytest.raises(openai.RateLimitError):
            await EditorialClient(client, settings).text("edit", "transcript", 1800)
    assert len(requests) == 1
    assert "secret" not in safe_error(ValueError("oa-secret xa-secret gg-secret"), cfg)


def test_provider_configuration_and_aliases(monkeypatch, tmp_path):
    monkeypatch.setattr("cliper.config.load_dotenv", lambda: None)
    values = {"AI_PROVIDER": "Grok", "XAI_API_KEY": "xai-only", "XAI_MODEL": "custom-grok",
              "GEMINI_API_KEY": "gemini-only", "GEMINI_MODEL": "custom-gemini", "OPENAI_API_KEY": "",
              "DATA_DIR": str(tmp_path)}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    cfg = Config.load()
    assert cfg.check_ai().key == "xai-only"
    assert cfg.ai().model == "custom-grok"
    assert cfg.check_ai("google").model == "custom-gemini"
    assert cfg.ai("gemini").base_url.startswith("https://generativelanguage.googleapis.com/")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        cfg.check_ai("openai")
    with pytest.raises(ValueError, match="Choose"):
        normalize_provider("unknown")
    assert "xai-only" not in repr(cfg)


def test_job_snapshot_and_legacy_settings(cfg):
    cfg.provider, cfg.xai_model = "xai", "original-model"
    store = Store(cfg.data_dir)
    prefs = cfg.snapshot_ai(Preferences())
    job = store.create(42, 42, "source", prefs)
    cfg.provider, cfg.xai_model = "gemini", "new-model"
    saved = Preferences.model_validate_json(store.get(job["id"])["prefs"])
    assert cfg.ai(saved.ai_provider, saved.ai_model).provider == "xai"
    assert cfg.ai(saved.ai_provider, saved.ai_model).model == "original-model"
    legacy = Preferences.model_validate_json('{"clips": 3}')
    assert legacy.ai_provider is None and cfg.snapshot_ai(legacy).ai_provider == "gemini"


def fake_update(text, owner=42):
    return SimpleNamespace(effective_user=SimpleNamespace(id=owner),
                           effective_chat=SimpleNamespace(id=owner, type="private"),
                           callback_query=None, effective_message=SimpleNamespace(reply_text=AsyncMock()),
                           message=SimpleNamespace(text=text, reply_text=AsyncMock(), video=None, document=None))


async def test_telegram_switching_and_submission_snapshot(monkeypatch, cfg):
    cfg.provider, cfg.owners = "openai", {42}
    cfg.xai_api_key, cfg.gemini_api_key = "xai-key", "gemini-key"
    controller = Controller(cfg)
    await controller.command(fake_update("/provider grok"), SimpleNamespace(args=["grok"]))
    assert controller.store.prefs(42).ai_provider == "xai"
    # CI deliberately excludes Whisper. Submission only queues work in this test.
    monkeypatch.setattr("cliper.bot.importlib.util.find_spec", lambda name: True)
    await controller.submit(fake_update("https://youtu.be/test-video"), SimpleNamespace())
    jobs = controller.store.recent(42)
    assert len(jobs) == 1
    await controller.command(fake_update("/provider gemini"), SimpleNamespace(args=["gemini"]))
    assert Store(cfg.data_dir).prefs(42).ai_provider == "gemini"
    assert Preferences.model_validate_json(jobs[0]["prefs"]).ai_provider == "xai"
    # Missing OpenAI credentials must not silently change the saved provider.
    update = fake_update("/provider openai")
    await controller.command(update, SimpleNamespace(args=["openai"]))
    assert "OPENAI_API_KEY" in update.message.reply_text.await_args.args[0]
    assert controller.store.prefs(42).ai_provider == "gemini"
    await controller.command(fake_update("/provider heuristic", owner=99), SimpleNamespace(args=["heuristic"]))
    assert controller.store.prefs(99).ai_provider is None


async def test_provider_request_can_be_cancelled(cfg):
    cfg.gemini_api_key = "test-key"
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    settings = cfg.ai("gemini")
    async with openai.AsyncOpenAI(api_key=settings.key, base_url=settings.base_url,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
        task = asyncio.create_task(EditorialClient(client, settings).text("edit", "transcript", 1800))
        await asyncio.wait_for(started.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_gemini_model_discovery(cfg):
    cfg.gemini_api_key = "test-key"
    settings = cfg.ai("gemini")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"object": "list", "data": [
            {"id": f"models/{settings.model}", "created": 1, "object": "model", "owned_by": "google"}]})

    async with openai.AsyncOpenAI(api_key=settings.key, base_url=settings.base_url,
                                 http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
        await verify_model(client, settings)
    assert requests[0].method == "GET"
    assert requests[0].url.path.endswith("/openai/models")
