"""Tests for YouTube Data API v3 publishing and multi-account Web API."""
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cliper.config import Config
from cliper.models import Preferences
from cliper.publishing import PublishStore
from cliper.storage import Store
from cliper.web import create_app
from cliper.youtube_publishing import (
    YouTubePublisher,
    get_token_path,
    get_youtube_config,
    save_credentials,
    save_youtube_config,
    upload_to_youtube,
)


def test_youtube_config_persistence(tmp_path):
    cfg_file = tmp_path / "youtube.json"
    data = {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "accounts": {
            "gaming": {
                "title": "Gaming Shorts",
                "channel_id": "UC12345",
                "privacy": "public",
                "default_tags": ["gaming", "shorts"],
                "auto_publish": True,
                "owners": [0],
            }
        },
    }
    with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
        save_youtube_config(data, tmp_path)
        loaded = get_youtube_config(tmp_path)
        assert loaded["client_id"] == "test-client-id"
        assert loaded["client_secret"] == "test-client-secret"
        assert "gaming" in loaded["accounts"]
        assert loaded["accounts"]["gaming"]["title"] == "Gaming Shorts"


def test_publish_store_youtube_platform_segregation(tmp_path):
    store = Store(tmp_path)
    ps = PublishStore(store)

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"dummy video data")

    # Add Instagram post
    ig_post = ps.add(
        0, 0, "origin:ig", "f1", "clips", [str(video)], "IG post", ["#reel"],
        auto=True, platform="instagram"
    )
    assert ig_post["platform"] == "instagram"

    # Add YouTube post
    yt_post = ps.add(
        0, 0, "origin:yt", "f1", "gaming", [str(video)], "YT Short", ["#shorts"],
        auto=True, platform="youtube"
    )
    assert yt_post["platform"] == "youtube"

    # Claim for YouTube only claims the YouTube post
    claimed_yt = ps.claim(platform="youtube")
    assert claimed_yt is not None
    assert claimed_yt["id"] == yt_post["id"]
    assert claimed_yt["platform"] == "youtube"

    # Claim for Instagram only claims the Instagram post
    claimed_ig = ps.claim(platform="instagram")
    assert claimed_ig is not None
    assert claimed_ig["id"] == ig_post["id"]
    assert claimed_ig["platform"] == "instagram"


@pytest.mark.asyncio
async def test_youtube_publisher_mocked_upload(tmp_path):
    store = Store(tmp_path)
    ps = PublishStore(store)
    video = tmp_path / "short.mp4"
    video.write_bytes(b"sample video bytes")

    post = ps.add(
        0, 0, "job1:clip1", "f1", "main", [str(video)], "Crazy Moment", ["#viral"],
        auto=True, platform="youtube"
    )

    cfg_file = tmp_path / "youtube.json"
    cfg_data = {
        "client_id": "test-client",
        "client_secret": "test-secret",
        "accounts": {
            "main": {
                "title": "Main Channel",
                "channel_id": "UC_MAIN",
                "privacy": "public",
                "default_tags": ["shorts"],
                "owners": [0],
            }
        },
    }
    cfg_file.write_text(json.dumps(cfg_data), encoding="utf-8")

    claimed = ps.claim(platform="youtube")
    assert claimed is not None

    with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
        publisher = YouTubePublisher(ps, project_root=tmp_path)
        with patch("cliper.youtube_publishing.upload_to_youtube") as mock_upload:
            mock_upload.return_value = {
                "id": "yt_video_123",
                "url": "https://youtu.be/yt_video_123",
                "shorts_url": "https://www.youtube.com/shorts/yt_video_123",
                "status": "public",
            }
            video_id = await publisher.process(claimed)
            assert video_id == "yt_video_123"

    updated = ps.get(post["id"])
    assert updated["state"] == "published"
    assert updated["media_id"] == "yt_video_123"
    assert updated["target_id"] == "UC_MAIN"
    assert updated["published_at"] is not None


def test_youtube_web_api_endpoints(tmp_path):
    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "test-cid.apps.googleusercontent.com",
        "client_secret": "test-secret",
        "accounts": {
            "speed": {
                "title": "Speed Clips",
                "channel_id": "UC_SPEED",
                "privacy": "public",
                "default_tags": ["speed", "shorts"],
                "auto_publish": True,
                "owners": [0],
            }
        }
    }), encoding="utf-8")

    cfg = Config(data_dir=tmp_path / "data", token="", owners={0})
    with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
        app = create_app(cfg, token="test-key", project_root=tmp_path, start_engine=False)
        with TestClient(app) as client:
            session_resp = client.post("/api/session", json={"key": "test-key"})
            assert session_resp.status_code == 200
            client.headers["X-CSRF-Token"] = session_resp.json()["csrf"]

            # 1. GET /api/youtube/connections
            resp = client.get("/api/youtube/connections")
            assert resp.status_code == 200
            data = resp.json()
            assert data["configured"] is True
            assert len(data["accounts"]) == 1
            assert data["accounts"][0]["key"] == "speed"
            assert data["accounts"][0]["title"] == "Speed Clips"

            # 2. PUT /api/youtube/accounts/speed (update tags and privacy)
            resp = client.put("/api/youtube/accounts/speed", json={
                "title": "Speed Clips Daily",
                "privacy": "unlisted",
                "default_tags": ["speed", "gaming", "shorts"],
                "auto_publish": False,
            })
            assert resp.status_code == 200

            # Check updated
            resp = client.get("/api/youtube/connections")
            acc = resp.json()["accounts"][0]
            assert acc["title"] == "Speed Clips Daily"
            assert acc["privacy"] == "unlisted"
            assert acc["auto_publish"] is False

            # 3. GET /api/youtube/auth-url
            resp = client.get("/api/youtube/auth-url?account=speed")
            assert resp.status_code == 200
            assert "accounts.google.com" in resp.json()["auth_url"]
            assert "response_type=code" in resp.json()["auth_url"]

            # 4. DELETE /api/youtube/accounts/speed
            resp = client.delete("/api/youtube/accounts/speed")
            assert resp.status_code == 200

            resp = client.get("/api/youtube/connections")
            assert len(resp.json()["accounts"]) == 0


def test_publish_clip_endpoint(tmp_path):
    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, token="", owners={0})
    store = Store(data_dir)

    job = store.create(0, 0, "sample.mp4", Preferences(), 3)
    job_dir = store.directory(job["id"])
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    analysis_data = {
        "title": "Stream Highlights",
        "duration": 120.0,
        "coverage": {"fraction": 1.0},
        "clips": [
            {
                "id": 1,
                "title": "High Energy Moment",
                "start": 10.0,
                "end": 40.0,
                "score": 95,
                "reason": "Epic climax",
                "text": "What just happened!",
                "hook_text": "Watch this",
                "hook_variants": [],
                "music_category": "energetic_hype",
                "caption": "Insane highlight from today's stream",
                "hashtags": ["hype", "epic"],
                "ratings": {},
                "editorial": {},
                "moment_type": "highlight",
                "payoff_time": 30.0,
            }
        ],
    }
    (job_dir / "analysis.json").write_text(json.dumps(analysis_data), encoding="utf-8")
    (clips_dir / "clip_01.mp4").write_bytes(b"dummy video content")

    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "test-cid",
        "client_secret": "test-sec",
        "accounts": {
            "main": {
                "title": "Mahendra Desai",
                "channel_id": "UC12345",
                "privacy": "public",
                "default_tags": ["shorts"],
                "owners": [0],
            }
        }
    }), encoding="utf-8")

    # Write mock token file
    token_file = data_dir / "youtube" / "tokens" / "main.json"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps({
        "token": "mock-token",
        "refresh_token": "mock-refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-cid",
        "client_secret": "test-sec",
    }), encoding="utf-8")

    with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
        app = create_app(cfg, token="test-key", project_root=tmp_path, start_engine=False)
        with TestClient(app) as client:
            session_resp = client.post("/api/session", json={"key": "test-key"})
            assert session_resp.status_code == 200
            client.headers["X-CSRF-Token"] = session_resp.json()["csrf"]

            with patch("cliper.youtube_publishing.upload_to_youtube") as mock_upload:
                mock_upload.return_value = {
                    "id": "mock_short_999",
                    "url": "https://youtu.be/mock_short_999",
                    "shorts_url": "https://www.youtube.com/shorts/mock_short_999",
                    "status": "public",
                }

                resp = client.post(
                    f"/api/jobs/{job['id']}/clips/1/publish",
                    json={
                        "platform": "youtube",
                        "account": "main",
                        "title": "High Energy Moment #Shorts",
                        "caption": "Insane highlight!",
                        "hashtags": ["hype", "viral"],
                        "privacy": "public",
                        "publish_now": True,
                    },
                )
                assert resp.status_code == 200, resp.text
                data = resp.json()
                assert data["ok"] is True
                assert data["state"] == "published"
                assert data["media_id"] == "mock_short_999"
                assert data["url"] == "https://www.youtube.com/shorts/mock_short_999"

            # Verify that job_detail now includes the publication history on the clip
            resp = client.get(f"/api/jobs/{job['id']}")
            assert resp.status_code == 200
            clip_res = resp.json()["analysis"]["clips"][0]
            assert "publications" in clip_res
            assert len(clip_res["publications"]) >= 1
            pub = clip_res["publications"][0]
            assert pub["platform"] == "youtube"
            assert pub["state"] == "published"
            assert pub["media_id"] == "mock_short_999"


