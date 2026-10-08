import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cliper.faceless import FacelessStore
from cliper.models import Analysis, Preferences
from cliper.publishing import PublishStore
from cliper.storage import write_json
from cliper.web import create_app


@pytest.fixture
def web(cfg, monkeypatch):
    monkeypatch.delenv("NICHES_CONFIG_FILE", raising=False)
    monkeypatch.delenv("INSTAGRAM_ACCOUNTS_FILE", raising=False)
    cfg.owners = {7}
    cfg.api_key = "never-return-this-key"
    app = create_app(cfg, start_engine=False, token="test-key", project_root=cfg.data_dir)
    with TestClient(app) as client:
        response = client.post("/api/session", json={"key": "test-key"})
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        yield client, app.state.store, cfg


def ready_job(store, transcript, clip):
    prefs = Preferences(min_seconds=15, max_seconds=25)
    job = store.create(7, 0, "https://youtu.be/example", prefs, limit=50)
    folder = store.directory(job["id"])
    write_json(folder / "transcript.json", transcript.model_dump())
    write_json(folder / "analysis.json", Analysis(title="A complete story", language="en", duration=40,
        method="fixture", clips=[clip], coverage={"fraction": .5, "ranges": [{"start": 0, "end": 25}]}).model_dump())
    store.update(job["id"], state="awaiting_selection")
    return job["id"]


def test_web_requires_key_and_session_and_rejects_cross_origin(cfg):
    app = create_app(cfg, start_engine=False, token="test-key", project_root=cfg.data_dir)
    with TestClient(app) as client:
        assert client.get("/api/jobs").status_code == 401
        assert client.post("/api/session", json={"key": "wrong"}).status_code == 401
        assert client.post("/api/session", json={"key": "test-key"}, headers={"Origin": "https://evil.invalid"}).status_code == 403
        assert client.get("/api/jobs", headers={"Host": "evil.invalid"}).status_code == 403
        assert client.post("/api/session", json={"key": "test-key"}).status_code == 200
        assert client.put("/api/preferences", json={"clips": 2}).status_code == 403
        assert client.get("/api/bootstrap").status_code == 200
        assert client.get("/api/bootstrap", headers={"Host": "192.168.1.60:8788"}).status_code == 200
        assert client.get("/api/jobs", headers={"Host": "192.168.1.60:8788"}).status_code == 200
        assert client.get("/api/jobs", headers={"Host": "not-allowed.com"}).status_code == 403


def test_bootstrap_is_secret_free_and_preferences_are_real(web):
    client, store, cfg = web
    response = client.get("/api/bootstrap")
    assert response.status_code == 200 and cfg.api_key not in response.text
    assert response.json()["default_provider"] == "heuristic"
    assert "HttpOnly" not in response.headers.get("set-cookie", "")  # cookie only set at login
    result = client.put("/api/preferences", json={"scan_minutes": 60, "music_gain": .15, "preserve_wide_groups": True})
    assert result.status_code == 200
    assert store.prefs(7).scan_minutes == 60 and store.prefs(7).music_gain == .15
    assert client.put("/api/preferences", json={"scan_minutes": 0}).status_code == 400
    assert client.put("/api/preferences", json={"arbitrary_field": True}).status_code == 400
    assert client.put("/api/preferences", json={"enabled_niches": ["unknown"]}).status_code == 400


def test_new_web_job_is_queued_locally_and_validates_hosts(web):
    client, store, _ = web
    result = client.post("/api/jobs", json={"source": "https://kick.com/user/videos/id", "preferences": {"scan_minutes": 6}})
    assert result.status_code == 201
    row = store.get(result.json()["id"])
    assert row["chat"] == 0 and row["owner"] == 7 and row["state"] == "queued_analysis"
    assert result.json()["error"] == ""
    assert json.loads(row["prefs"])["scan_minutes"] == 6
    assert client.post("/api/jobs", json={"source": "https://evil.invalid/private"}).status_code == 400
    assert client.post("/api/jobs", json={"source": "http://youtube.com/watch?v=x"}).status_code == 400
    assert client.post("/api/jobs", json={"source": "C:/secret.env"}).status_code == 400


def test_ownership_and_transcript_filtering(web, transcript, clip):
    client, store, _ = web
    identity = ready_job(store, transcript, clip)
    secret = store.create(999, 999, "https://youtu.be/private", Preferences(), limit=50)
    listed = client.get("/api/jobs").json()
    assert identity in {x["id"] for x in listed} and secret["id"] not in {x["id"] for x in listed}
    assert client.get(f"/api/jobs/{secret['id']}").status_code == 404
    result = client.get(f"/api/jobs/{identity}/transcript?q=tomato").json()
    assert result["total"] == 1 and "tomato" in result["segments"][0]["text"]
    assert client.get(f"/api/jobs/{identity}").json()["analysis"]["clips"][0]["video"] is None


def test_clip_edits_and_select_render_use_real_state_machine(web, transcript, clip):
    client, store, _ = web
    identity = ready_job(store, transcript, clip)
    edit = {"title": "One conversation changed the plan", "start": 0, "end": 19, "caption": "A grounded lesson", "hashtags": ["#learning"], "music_category": "chill_ambient"}
    assert client.put(f"/api/jobs/{identity}/clips/1", json=edit | {"end": 35}).status_code == 400
    assert client.put(f"/api/jobs/{identity}/clips/1", json=edit).status_code == 200
    data = client.get(f"/api/jobs/{identity}").json()
    assert data["analysis"]["clips"][0]["title"] == edit["title"]
    assert data["analysis"]["clips"][0]["editorial"]["automatic_ready"] is False
    assert client.post(f"/api/jobs/{identity}/render", json={"ids": [99]}).status_code == 400
    assert client.post(f"/api/jobs/{identity}/render", json={"ids": [1]}).status_code == 200
    assert store.get(identity)["state"] == "queued_render"
    assert client.put(f"/api/jobs/{identity}/clips/1", json=edit).status_code == 400
    assert client.post(f"/api/jobs/{identity}/render", json={"ids": [1]}).status_code == 400


def test_cancel_and_retry_are_state_checked(web):
    client, store, _ = web
    job = store.create(7, 0, "https://youtu.be/example", Preferences())
    assert client.post(f"/api/jobs/{job['id']}/actions/retry").status_code == 400
    store.update(job["id"], state="failed")
    assert client.post(f"/api/jobs/{job['id']}/actions/retry").status_code == 200
    assert client.post(f"/api/jobs/{job['id']}/actions/cancel").status_code == 200
    assert store.get(job["id"])["state"] == "cancelled"


def test_media_is_authenticated_bounded_and_seekable(web):
    client, store, cfg = web
    job = store.create(7, 0, "https://youtu.be/test", Preferences())
    folder = store.directory(job["id"]) / "clips"
    folder.mkdir()
    (folder / "clip_01.mp4").write_bytes(bytes(range(256)))
    response = client.get(f"/api/jobs/{job['id']}/files/clip_01.mp4", headers={"Range": "bytes=0-9"})
    assert response.status_code == 206 and len(response.content) == 10
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/jobs/{job['id']}/files/.env").status_code == 404
    assert client.get(f"/api/jobs/{job['id']}/files/..%2F.env").status_code == 404


def test_web_uploads_stay_in_managed_folders(web):
    client, store, cfg = web
    response = client.post("/api/jobs/upload", files={"file": ("../../evil.mp4", b"video", "video/mp4")})
    assert response.status_code == 201
    row = store.get(response.json()["id"])
    assert Path(row["source"]).parent == store.directory(row["id"])
    assert Path(row["source"]).name == "uploaded-source.mp4"
    assert row["state"] == "queued_analysis"
    assert client.post("/api/jobs/upload", files={"file": ("secret.exe", b"x")}).status_code == 400
    assert client.post("/api/jobs/upload", files={"file": ("empty.mp4", b"")}).status_code == 400


def test_music_upload_preview_and_category_validation(web):
    client, _, cfg = web
    result = client.post("/api/music/chill_ambient/upload", files={"file": ("../../track.mp3", b"sound", "audio/mpeg")})
    assert result.status_code == 200
    category = next(c for c in client.get("/api/music").json() if c["id"] == "chill_ambient")
    assert len(category["tracks"]) == 1
    assert client.get(category["tracks"][0]["url"]).content == b"sound"
    assert client.post("/api/music/unknown/upload", files={"file": ("a.mp3", b"sound")}).status_code == 400
    assert not (cfg.data_dir / "track.mp3").exists()


def test_publication_review_caption_schedule_and_uncertain_guard(web):
    client, store, cfg = web
    path = cfg.data_dir / "clip.mp4"
    path.write_bytes(b"video")
    pub = PublishStore(store)
    post = pub.add(7, 0, "origin:1", "f1", "clips", [path], "Original caption", [])
    due = time.time() + 7200
    assert client.put(f"/api/publications/{post['id']}", json={"caption": "A new caption #one", "due": due}).status_code == 200
    assert client.post(f"/api/publications/{post['id']}/schedule").status_code == 200
    assert pub.get(post["id"])["due"] == due and pub.get(post["id"])["state"] == "queued"
    assert client.post(f"/api/publications/{post['id']}/approve").status_code == 200
    assert pub.get(post["id"])["due"] < due
    pub.update(post["id"], state="uncertain")
    assert client.post(f"/api/publications/{post['id']}/approve").status_code == 400
    assert client.put(f"/api/publications/{post['id']}", json={"caption": "Changed"}).status_code == 400
    assert client.get(f"/api/publications/{post['id']}/media/0").content == b"video"


def test_turning_off_automatic_publishing_holds_queued_posts(web):
    client, store, cfg = web
    pub = PublishStore(store)
    store.save_prefs(7, Preferences(auto_publish=True))
    post = pub.add(7, 0, "auto:1", "f1", "clips", [], "caption", [], auto=True)
    assert client.put("/api/preferences", json={"auto_publish": False}).status_code == 200
    assert pub.get(post["id"])["state"] == "approval"


def test_system_credentials_are_write_only_and_bounded(web):
    client, _, cfg = web
    assert client.put("/api/system", json={"SCAN_DOWNLOAD_WORKERS": "99"}).status_code == 400
    assert client.put("/api/system", json={"DATA_DIR": "C:/outside"}).status_code == 400
    assert client.put("/api/system", json={"VIDEO_ENCODER": "arbitrary -command"}).status_code == 400
    result = client.put("/api/system", json={"GEMINI_API_KEY": "private-test-value", "SCAN_DOWNLOAD_WORKERS": "3"})
    assert result.status_code == 200 and result.json()["restart_required"]
    assert "private-test-value" not in result.text
    assert "private-test-value" in (cfg.data_dir / ".env").read_text("utf-8")
    assert "private-test-value" not in client.get("/api/bootstrap").text


def test_instagram_account_mapping_and_token_storage(web):
    client, _, cfg = web
    body = {"ig_user_id": "1234567890", "login": "instagram", "token": "secret-instagram-token", "media_base_url": "https://media.example.test/cliper"}
    result = client.put("/api/connections/clips", json=body)
    assert result.status_code == 200 and "secret-instagram-token" not in result.text
    config = json.loads((cfg.data_dir / "config" / "instagram.json").read_text("utf-8"))
    assert config["clips"]["owners"] == [7]
    assert config["clips"]["token_env"] == "IG_CLIPS_TOKEN"
    assert "secret-instagram-token" not in client.get("/api/connections").text
    assert client.put("/api/connections/clips", json=body | {"media_base_url": "http://insecure.test"}).status_code == 400


def test_niche_config_and_web_only_claiming(web):
    client, store, cfg = web
    assert client.put("/api/niches/dark", json={"name": "Original series", "threshold": 85, "pillars": ["Practice"]}).status_code == 200
    assert client.get("/api/niches").json()[0]["config"]["name"] == "Original series"
    assert client.put("/api/niches/dark", json={"threshold": 120}).status_code == 400
    assert client.put("/api/schedules/dark", json={"daily_time": "25:00"}).status_code == 400
    telegram = store.create(7, 7, "https://youtu.be/tg", Preferences(), limit=10)
    browser = store.create(7, 0, "https://youtu.be/web", Preferences(), limit=10)
    assert store.claim(web_only=True)["id"] == browser["id"]
    assert store.get(telegram["id"])["state"] == "queued_analysis"
    assert store.claim(web_only=True) is None
    pubs = PublishStore(store, web_only=True)
    tgpost = pubs.add(7, 7, "tg", "f1", "clips", [], "caption", [], auto=True)
    webpost = pubs.add(7, 0, "web", "f1", "clips", [], "caption", [], auto=True)
    assert pubs.claim()["id"] == webpost["id"]
    assert pubs.get(tgpost["id"])["state"] == "queued"
    FacelessStore(store, web_only=True)  # migration is compatible with existing store


def test_web_recovery_does_not_reset_a_telegram_job(web):
    _, store, _ = web
    tg = store.create(7, 7, "https://youtu.be/tg", Preferences(), limit=10)
    browser = store.create(7, 0, "https://youtu.be/web", Preferences(), limit=10)
    store.update(tg["id"], state="analyzing")
    store.update(browser["id"], state="analyzing")
    store.recover(web_only=True)
    assert store.get(tg["id"])["state"] == "analyzing"
    assert store.get(browser["id"])["state"] == "queued_analysis"


def test_reference_upload_checks_pixels_and_persists_path(web):
    import cv2
    import numpy as np

    client, _, cfg = web
    ok, image = cv2.imencode(".png", np.full((16, 16, 3), 120, dtype=np.uint8))
    assert ok
    response = client.post("/api/niches/dark/upload", files={"file": ("reference.png", image.tobytes(), "image/png")})
    assert response.status_code == 200
    path = Path(response.json()["character_path"])
    assert path.is_file() and path.is_relative_to(cfg.data_dir)
    assert client.get("/api/niches").json()[0]["reference_ready"]
    before = set(path.parent.iterdir())
    assert client.post("/api/niches/dark/upload", files={"file": ("fake.png", b"not an image", "image/png")}).status_code == 400
    assert set(path.parent.iterdir()) == before


def test_lock_studio_requires_csrf_and_revokes_session(web):
    client, _, _ = web
    assert client.delete("/api/session", headers={"X-CSRF-Token": "wrong"}).status_code == 403
    assert client.get("/api/bootstrap").status_code == 200
    assert client.delete("/api/session").status_code == 200
    assert client.get("/api/bootstrap").status_code == 401


def test_prompts_crud_and_carousel_input_prompt(web):
    client, store, cfg = web
    # Verify getting all prompts
    res = client.get("/api/prompts")
    assert res.status_code == 200
    prompts = res.json()
    keys = {p["key"] for p in prompts}
    assert "carousel_editor" in keys
    assert "carousel_brief" in keys
    assert "carousel_slide_prompt" in keys
    assert "clip_brief" in keys
    assert "speed_brief" in keys
    assert "x_research_prompt" in keys

    # Verify editing a prompt
    custom_text = "Custom carousel prompt: Focus heavily on morning routines vs yearly success."
    put_res = client.put("/api/prompts/carousel_editor", json={"value": custom_text})
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["value"] == custom_text
    assert updated["is_custom"] is True

    # Verify get single prompt
    get_res = client.get("/api/prompts/carousel_editor")
    assert get_res.status_code == 200
    assert get_res.json()["value"] == custom_text

    # Verify reset prompt
    reset_res = client.post("/api/prompts/carousel_editor/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["is_custom"] is False
    assert reset_res.json()["value"] != custom_text

    # Verify carousel creation with prompt
    # First enable F2 in preferences
    client.put("/api/preferences", json={"f2_enabled": True})
    # Set up dark niche with dummy character
    niche_dir = cfg.data_dir / "config"
    niche_dir.mkdir(parents=True, exist_ok=True)
    dummy_char = cfg.data_dir / "char.png"
    dummy_char.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    (niche_dir / "niches.json").write_text(json.dumps({
        "dark": {"name": "Dark series", "character_path": str(dummy_char), "threshold": 80}
    }), encoding="utf-8")

    car_res = client.post("/api/carousels", json={
        "niche": "dark",
        "count": 1,
        "prompt": "10 pages a day compounding habits"
    })
    assert car_res.status_code == 201
    job_id = car_res.json()["id"]

    # Verify that get carousels lists the prompt
    list_car = client.get("/api/carousels").json()
    our_job = next((j for j in list_car if j["id"] == job_id), None)
    assert our_job is not None
    assert our_job["prompt"] == "10 pages a day compounding habits"

