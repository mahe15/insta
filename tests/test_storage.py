import json
import time

import pytest

from cliper.maintenance import cleanup
from cliper.models import Preferences
from cliper.storage import Store


def test_ownership_capacity_and_atomic_claim(tmp_path):
    store = Store(tmp_path)
    job = store.create(1, 1, "source", Preferences(), limit=1)
    with pytest.raises(ValueError, match="not found"):
        store.get(job["id"], 2)
    with pytest.raises(ValueError, match="queue is full"):
        store.create(2, 2, "source", Preferences(), limit=1)
    assert store.claim()["state"] == "analyzing"
    assert store.claim() is None
    store.update(job["id"], state="cancelled")
    store.update(job["id"], state="complete")
    assert store.get(job["id"])["state"] == "cancelled"


def test_recovery_and_idempotent_selection(tmp_path):
    store = Store(tmp_path)
    job = store.create(1, 1, "source", Preferences())
    store.claim()
    store.recover()
    assert store.get(job["id"])["state"] == "queued_analysis"
    store.update(job["id"], state="awaiting_selection")
    store.select(job["id"], 1, [1, 3])
    with pytest.raises(ValueError, match="not awaiting"):
        store.select(job["id"], 1, [1])
    assert json.loads(store.get(job["id"])["selected"]) == [1, 3]
    store.claim()
    store.recover()
    assert store.get(job["id"])["state"] == "queued_render"


def test_preferences_persist_across_connections(tmp_path):
    Store(tmp_path).save_prefs(7, Preferences(clips=2, style="bold"))
    assert Store(tmp_path).prefs(7).style == "bold"
    assert Store(tmp_path).prefs(8).clips == 5


def test_retry_respects_capacity_and_rejects_incomplete_upload(tmp_path):
    store = Store(tmp_path)
    failed = store.create(1, 1, "source", Preferences(), limit=1)
    store.update(failed["id"], state="failed")
    active = store.create(1, 1, "source", Preferences(), limit=1)
    with pytest.raises(ValueError, match="queue is full"):
        store.retry(failed["id"], 1, 1)
    store.update(active["id"], state="cancelled")
    store.retry(failed["id"], 1, 1)
    assert store.get(failed["id"])["state"] == "queued_analysis"
    store.update(failed["id"], state="failed", source="telegram-upload")
    with pytest.raises(ValueError, match="send the video again"):
        store.retry(failed["id"], 1, 1)


def test_retention_only_removes_old_terminal_jobs(tmp_path):
    store = Store(tmp_path)
    source = tmp_path / "original.mp4"
    source.write_bytes(b"original")
    old = store.create(1, 1, str(source), Preferences())
    active = store.create(1, 1, str(source), Preferences())
    store.update(old["id"], state="complete")
    with store.connect() as db:
        db.execute("UPDATE jobs SET updated=?", (time.time() - 10 * 86400,))
    assert cleanup(store, 7) == 1
    assert source.read_bytes() == b"original"
    assert store.directory(active["id"]).exists()


@pytest.mark.parametrize("value", ["../escape", "a" * 13, "a" * 11 + "/", "A" * 12])
def test_job_paths_cannot_escape(tmp_path, value):
    with pytest.raises(ValueError):
        Store(tmp_path).directory(value)
