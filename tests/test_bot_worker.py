import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cliper.bot import Controller
from cliper.models import Analysis, Preferences
from cliper.pipeline import Worker, safe_error
from cliper.storage import Store, write_json


def test_private_owner_access(cfg):
    cfg.owners = {42}
    controller = Controller(cfg)
    def update(owner, chat_type="private"):
        return SimpleNamespace(effective_user=SimpleNamespace(id=owner),
                               effective_chat=SimpleNamespace(type=chat_type))
    assert controller.authorized(update(42))
    assert not controller.authorized(update(8))
    assert not controller.authorized(update(42, "group"))
    cfg.owners.clear()
    assert not controller.authorized(update(42))


def test_bot_application_registers_handlers(cfg):
    cfg.token = "123456789:abcdefghijklmnopqrstuvwxyzABCDEFGHI"
    app = Controller(cfg).build()
    assert len(app.handlers[0]) == 6


def test_clip_selection_tampering_and_double_click(cfg, clip):
    controller = Controller(cfg)
    job = controller.store.create(42, 42, "source", Preferences())
    write_json(controller.store.directory(job["id"]) / "analysis.json",
               Analysis(title="test", language="en", duration=40, method="test", clips=[clip]).model_dump())
    controller.store.update(job["id"], state="awaiting_selection")
    with pytest.raises(ValueError, match="valid clip"):
        controller.choose(job, "999")
    controller.choose(job, "all")
    with pytest.raises(ValueError, match="not awaiting"):
        controller.choose(job, "all")


async def test_worker_analysis_render_and_delivery_resume(cfg, clip):
    store = Store(cfg.data_dir)
    job = store.create(42, 42, "source", Preferences())
    analysis = Analysis(title="test", language="en", duration=40, method="test", clips=[clip])
    notify, shortlist, deliver = AsyncMock(), AsyncMock(), AsyncMock()
    worker = Worker(cfg, store, notify, shortlist, deliver)
    worker.pipeline.analyze = AsyncMock(return_value=analysis)
    await worker.process(store.claim())
    assert store.get(job["id"])["state"] == "awaiting_selection"
    shortlist.assert_awaited_once()
    write_json(store.directory(job["id"]) / "analysis.json", analysis.model_dump())
    store.select(job["id"], 42, [1])
    worker.pipeline.render_one = AsyncMock(return_value=cfg.data_dir / "clip.mp4")
    await worker.process(store.claim())
    assert store.get(job["id"])["state"] == "complete"
    assert json.loads(store.get(job["id"])["delivered"]) == [1]
    deliver.assert_awaited_once()
    store.update(job["id"], state="queued_render")
    await worker.process(store.claim())
    deliver.assert_awaited_once()  # delivery checkpoint survives a worker restart


async def test_worker_failure_persists_and_next_job_is_processed(cfg):
    store = Store(cfg.data_dir)
    a = store.create(1, 1, "source", Preferences())
    b = store.create(1, 1, "source", Preferences())
    worker = Worker(cfg, store, AsyncMock(), AsyncMock(), AsyncMock())
    worker.pipeline.analyze = AsyncMock(side_effect=ValueError("bad audio"))
    task = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(5):
            while store.get(b["id"])["state"] != "failed":
                await asyncio.sleep(.05)
        assert store.get(a["id"])["state"] == "failed"
        assert "bad audio" in store.get(a["id"])["error"]
    finally:
        await worker.stop()
        await task


def test_secrets_redacted(cfg):
    cfg.token, cfg.api_key = "bot-secret", "ai-secret"
    assert safe_error(ValueError("bot-secret / ai-secret"), cfg) == "[REDACTED] / [REDACTED]"
