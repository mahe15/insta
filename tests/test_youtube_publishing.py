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


def test_schedule_all_rendered_clips_with_2_hour_gap(tmp_path):
    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, token="", owners={0})
    store = Store(data_dir)

    job = store.create(0, 0, "sample_5clips.mp4", Preferences(), 3)
    job_dir = store.directory(job["id"])
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 5 clips in analysis
    clips_list = []
    for i in range(1, 6):
        clips_list.append({
            "id": i,
            "title": f"Clip #{i} Highlight",
            "start": (i - 1) * 20.0,
            "end": i * 20.0,
            "score": 80 + i,
            "reason": f"Moment {i}",
            "text": f"Text for moment {i}",
            "hook_text": f"Hook {i}",
            "hook_variants": [],
            "music_category": "energetic_hype",
            "caption": f"Highlight {i} caption",
            "hashtags": ["shorts", "viral"],
            "ratings": {},
            "editorial": {},
            "moment_type": "highlight",
            "payoff_time": 15.0,
        })
        # Render each clip
        (clips_dir / f"clip_{i:02}.mp4").write_bytes(f"dummy video content {i}".encode())

    analysis_data = {
        "title": "5 Clips Stream",
        "duration": 100.0,
        "coverage": {"fraction": 1.0},
        "clips": clips_list,
    }
    (job_dir / "analysis.json").write_text(json.dumps(analysis_data), encoding="utf-8")

    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "test-cid",
        "client_secret": "test-sec",
        "accounts": {
            "main": {
                "title": "Main Channel",
                "channel_id": "UC55555",
                "privacy": "public",
                "default_tags": ["shorts"],
                "owners": [0],
            }
        }
    }), encoding="utf-8")

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

            # Schedule all 5 clips with default 2 hour gap directly on YouTube
            uploaded_calls = []

            def fake_upload(**kwargs):
                uploaded_calls.append(dict(kwargs))
                cid = kwargs.get("video_path").stem
                return {
                    "id": f"yt_{cid}",
                    "url": f"https://youtu.be/yt_{cid}",
                    "shorts_url": f"https://www.youtube.com/shorts/yt_{cid}",
                    "status": "scheduled" if kwargs.get("publish_at") else "public",
                    "scheduled_at": kwargs.get("publish_at"),
                }

            with patch("cliper.youtube_publishing.upload_to_youtube", side_effect=fake_upload):
                before_schedule = time.time()
                resp = client.post(
                    f"/api/jobs/{job['id']}/schedule-all",
                    json={
                        "platform": "youtube",
                        "account": "main",
                        "gap_hours": 2.0,
                        "publish_first_now": True,
                        "privacy": "public",
                        "schedule_on_youtube": True,
                    },
                )
                assert resp.status_code == 200, resp.text
                res_data = resp.json()
                assert res_data["ok"] is True
                assert res_data["count"] == 5
                assert res_data["gap_hours"] == 2.0
                items = res_data["items"]
                assert len(items) == 5

                # Verify all 5 clips were uploaded to YouTube side
                assert len(uploaded_calls) == 5

                # Clip 1 should be immediate
                assert uploaded_calls[0]["publish_at"] is None
                assert uploaded_calls[0]["privacy"] == "public"

                # Clips 2 through 5 must have 2-hour staggered publish_at timestamps
                first_due = items[0]["due"]
                assert before_schedule - 2 <= first_due <= time.time() + 2

                for idx in range(1, 5):
                    expected_due = round(first_due + (idx * 7200))
                    actual_due = round(items[idx]["due"])
                    assert actual_due == expected_due, f"Clip {idx+1} due time mismatch: {actual_due} vs {expected_due}"
                    assert round(uploaded_calls[idx]["publish_at"]) == expected_due
                    # YouTube requires private for scheduled videos
                    assert uploaded_calls[idx]["privacy"] == "private"
                    assert items[idx]["scheduled_on_youtube"] is True

                # Verify job_detail reflects the publications on each clip
                job_resp = client.get(f"/api/jobs/{job['id']}")
                assert job_resp.status_code == 200
                detail_clips = job_resp.json()["analysis"]["clips"]
                assert len(detail_clips) == 5
                for c in detail_clips:
                    assert "publications" in c
                    assert len(c["publications"]) == 1
                    assert c["publications"][0]["state"] == "published"
                    assert c["publications"][0]["media_id"] is not None
                    assert "due" in c["publications"][0]

                # Test individual publication cancellation
                first_pub_id = items[0]["publication_id"]
                cancel_resp = client.post(f"/api/jobs/{job['id']}/publications/{first_pub_id}/cancel")
                assert cancel_resp.status_code == 200
                assert cancel_resp.json()["ok"] is True

                # Verify it's marked rejected
                job_resp_after = client.get(f"/api/jobs/{job['id']}")
                first_clip_pubs = job_resp_after.json()["analysis"]["clips"][0]["publications"]
                assert any(p["id"] == first_pub_id and p["state"] == "rejected" for p in first_clip_pubs)


def test_schedule_all_skips_already_live_clips_on_youtube(tmp_path):
    data_dir = tmp_path / "data"
    cfg = Config(data_dir=data_dir, token="", owners={0})
    store = Store(data_dir)
    pubs = PublishStore(store)

    job = store.create(0, 0, "sample_stream.mp4", Preferences(), 3)
    job_dir = store.directory(job["id"])
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clips_list = []
    for i in range(1, 6):
        clips_list.append({
            "id": i,
            "title": f"Moment #{i}",
            "start": (i - 1) * 15.0,
            "end": i * 15.0,
            "score": 85,
            "reason": f"Highlight {i}",
            "text": f"Clip {i} text",
            "hook_text": f"Hook {i}",
            "hook_variants": [],
            "music_category": "energetic_hype",
            "caption": f"Clip {i} caption",
            "hashtags": ["shorts"],
            "ratings": {},
            "editorial": {},
            "moment_type": "highlight",
            "payoff_time": 10.0,
        })
        (clips_dir / f"clip_{i:02}.mp4").write_bytes(f"video {i}".encode())

    analysis_data = {
        "title": "Stream Highlights",
        "duration": 75.0,
        "coverage": {"fraction": 1.0},
        "clips": clips_list,
    }
    (job_dir / "analysis.json").write_text(json.dumps(analysis_data), encoding="utf-8")

    # Mark Clip 1 and Clip 3 as already published on YouTube
    p1 = pubs.add(0, 0, f"{job['id']}:1:yt:main:test1", "f1", "main", [clips_dir / "clip_01.mp4"],
                  caption="Clip 1", hashtags=["shorts"], auto=False, platform="youtube")
    pubs.update(p1["id"], state="published", media_id="yt_live_01", published_at=time.time() - 3600)

    p3 = pubs.add(0, 0, f"{job['id']}:3:yt:main:test3", "f1", "main", [clips_dir / "clip_03.mp4"],
                  caption="Clip 3", hashtags=["shorts"], auto=False, platform="youtube")
    pubs.update(p3["id"], state="published", media_id="yt_live_03", published_at=time.time() - 1800)

    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "test-cid",
        "client_secret": "test-sec",
        "accounts": {
            "main": {
                "title": "Channel Live",
                "channel_id": "UC99999",
                "privacy": "public",
                "default_tags": ["shorts"],
                "owners": [0],
            }
        }
    }), encoding="utf-8")

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

            # Schedule all clips for YouTube with 2-hour gap
            def fake_upload(**kwargs):
                cid = kwargs.get("video_path").stem
                return {
                    "id": f"yt_{cid}",
                    "url": f"https://youtu.be/yt_{cid}",
                    "shorts_url": f"https://www.youtube.com/shorts/yt_{cid}",
                    "status": "scheduled" if kwargs.get("publish_at") else "public",
                    "scheduled_at": kwargs.get("publish_at"),
                }

            with patch("cliper.youtube_publishing.upload_to_youtube", side_effect=fake_upload):
                schedule_resp = client.post(
                    f"/api/jobs/{job['id']}/schedule-all",
                    json={
                        "platform": "youtube",
                        "account": "main",
                        "gap_hours": 2.0,
                        "publish_first_now": True,
                        "privacy": "public",
                        "schedule_on_youtube": True,
                    },
                )
                assert schedule_resp.status_code == 200, schedule_resp.text
                res = schedule_resp.json()
                assert res["ok"] is True
                # Clips 1 and 3 are live, so only clips 2, 4, 5 scheduled (count == 3)
                assert res["count"] == 3
                assert res["skipped_live_count"] == 2
                assert res["skipped_clip_ids"] == [1, 3]

                scheduled_cids = [item["clip_id"] for item in res["items"]]
                assert scheduled_cids == [2, 4, 5]

                # Verify 2-hour gap between scheduled items
                first_due = res["items"][0]["due"]
                assert round(res["items"][1]["due"]) == round(first_due + 7200)
                assert round(res["items"][2]["due"]) == round(first_due + 14400)

                # Check job_detail confirms clips 1 and 3 remain published, while 2, 4, 5 are scheduled on YouTube
                job_resp = client.get(f"/api/jobs/{job['id']}")
                clips_by_id = {c["id"]: c for c in job_resp.json()["analysis"]["clips"]}

                clip1_pub = clips_by_id[1]["publications"][0]
                assert clip1_pub["state"] == "published"
                assert clip1_pub["media_id"] == "yt_live_01"

                clip3_pub = clips_by_id[3]["publications"][0]
                assert clip3_pub["state"] == "published"
                assert clip3_pub["media_id"] == "yt_live_03"

                for scheduled_id in [2, 4, 5]:
                    pubs_for_clip = clips_by_id[scheduled_id]["publications"]
                    assert any(p["state"] == "published" and p["media_id"] == f"yt_clip_{scheduled_id:02}" for p in pubs_for_clip)

            # Now mark clips 2, 4, 5 as also published
            for scheduled_id in [2, 4, 5]:
                p = pubs.add(0, 0, f"{job['id']}:{scheduled_id}:yt:main:t{scheduled_id}", "f1", "main",
                             [clips_dir / f"clip_{scheduled_id:02}.mp4"], caption=f"Clip {scheduled_id}", hashtags=["shorts"],
                             auto=False, platform="youtube")
                pubs.update(p["id"], state="published", media_id=f"yt_live_{scheduled_id}")

            # Now attempting to schedule all should inform that all rendered clips are already live
            all_live_resp = client.post(
                f"/api/jobs/{job['id']}/schedule-all",
                json={
                    "platform": "youtube",
                    "account": "main",
                    "gap_hours": 2.0,
                    "publish_first_now": True,
                },
            )
            assert all_live_resp.status_code == 400
            assert "already live on Youtube" in all_live_resp.json()["detail"]


def test_multi_account_token_discovery_and_casing(tmp_path):
    from cliper.youtube_publishing import get_youtube_config, get_token_path, suggest_next_account_key
    tokens_dir = tmp_path / "data" / "youtube" / "tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)
    # Write tokens with varying cases
    (tokens_dir / "Podcast.json").write_text(json.dumps({"token": "tok1", "refresh_token": "ref1"}))
    (tokens_dir / "main.json").write_text(json.dumps({"token": "tok2", "refresh_token": "ref2"}))

    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({"accounts": {"main": {"title": "Main Channel"}}}), encoding="utf-8")

    with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
        cfg = get_youtube_config(tmp_path)
        # podcast should be auto-discovered
        assert "podcast" in cfg["accounts"]
        assert "main" in cfg["accounts"]

        # Case-insensitive token lookup
        resolved_lower = get_token_path("podcast", data_dir=tmp_path / "data")
        assert resolved_lower.is_file()
        assert resolved_lower.stem == "Podcast"

        resolved_exact = get_token_path("Podcast", data_dir=tmp_path / "data")
        assert resolved_exact.is_file()

        # Key suggestions
        assert suggest_next_account_key(tmp_path) == "channel_2"


def test_upload_to_youtube_publish_at_normalization(tmp_path):
    from cliper.youtube_publishing import upload_to_youtube

    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"\x00" * 1024)

    token_dir = tmp_path / "data" / "youtube" / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "main.json").write_text(json.dumps({
        "token": "fake_tok",
        "refresh_token": "fake_ref",
        "client_id": "cid",
        "client_secret": "sec",
    }))

    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "cid",
        "client_secret": "sec",
        "accounts": {"main": {"title": "Channel 1"}}
    }))

    inserted_body = {}

    class MockVideos:
        def insert(self, part, body, media_body):
            nonlocal inserted_body
            inserted_body = body
            class MockRequest:
                def next_chunk(self):
                    return None, {"id": "mock_yt_vid", "status": {"privacyStatus": body["status"]["privacyStatus"]}}
            return MockRequest()

    class MockYouTube:
        def videos(self):
            return MockVideos()

    with patch("cliper.youtube_publishing.build", return_value=MockYouTube()):
        with patch.dict("os.environ", {"YOUTUBE_ACCOUNTS_FILE": str(cfg_file)}):
            # Test 1: Future timestamp (2 hours ahead)
            future_ts = time.time() + 7200
            res = upload_to_youtube(
                account_key="main",
                video_path=video_file,
                title="Future Clip",
                description="Desc",
                publish_at=future_ts,
                project_root=tmp_path,
                data_dir=tmp_path / "data",
            )
            assert res["id"] == "mock_yt_vid"
            assert res["status"] == "scheduled"
            assert inserted_body["status"]["privacyStatus"] == "private"
            assert inserted_body["status"]["publishAt"].endswith(".000Z")

            # Test 2: ISO string
            res_iso = upload_to_youtube(
                account_key="main",
                video_path=video_file,
                title="ISO Clip",
                description="Desc",
                publish_at="2028-05-10T14:30:00Z",
                project_root=tmp_path,
                data_dir=tmp_path / "data",
            )
            assert res_iso["status"] == "scheduled"
            assert inserted_body["status"]["publishAt"] == "2028-05-10T14:30:00.000Z"

            # Test 3: Past timestamp gets safely clamped to future (120s ahead)
            past_ts = time.time() - 3600
            res_past = upload_to_youtube(
                account_key="main",
                video_path=video_file,
                title="Past Clip",
                description="Desc",
                publish_at=past_ts,
                project_root=tmp_path,
                data_dir=tmp_path / "data",
            )
            assert res_past["status"] == "scheduled"
            # publishAt must still be set and in the future
            assert inserted_body["status"]["privacyStatus"] == "private"
            assert inserted_body["status"]["publishAt"].endswith(".000Z")





