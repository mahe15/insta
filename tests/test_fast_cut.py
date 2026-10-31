import json
import pytest
from pathlib import Path

from cliper.captions import write_captions
from cliper.config import Config
from cliper.edit_layout import layout
from cliper.fast_cut import generate_fast_cut_clips
from cliper.media import filter_graph
from cliper.models import Analysis, Clip, Preferences, Ratings, Transcript
from cliper.pipeline import Pipeline


def test_fast_cut_slicing_90s():
    # 180s video into 90s clips -> 2 parts
    clips = generate_fast_cut_clips(duration=180.0, chunk_duration=90.0, skip_intro=False)
    assert len(clips) == 2
    assert clips[0].id == 1
    assert clips[0].title == "Part 1"
    assert clips[0].start == 0.0
    assert clips[0].end == 90.0

    assert clips[1].id == 2
    assert clips[1].title == "Part 2"
    assert clips[1].start == 90.0
    assert clips[1].end == 180.0


def test_fast_cut_two_hour_video():
    # 2 hours (7200 seconds) sliced into 90s clips -> 80 parts
    clips = generate_fast_cut_clips(duration=7200.0, chunk_duration=90.0, skip_intro=False)
    assert len(clips) == 80
    assert clips[0].title == "Part 1"
    assert clips[0].start == 0.0
    assert clips[0].end == 90.0

    assert clips[79].title == "Part 80"
    assert clips[79].start == 7110.0
    assert clips[79].end == 7200.0


def test_fast_cut_skip_first_3_min():
    # 600s video (10 min), skip first 3 min (180s) -> remaining 420s -> 90s chunks
    # 180 to 270 (Part 1), 270 to 360 (Part 2), 360 to 450 (Part 3), 450 to 540 (Part 4), 540 to 600 (Part 5, 60s)
    clips = generate_fast_cut_clips(duration=600.0, chunk_duration=90.0, skip_intro=True, skip_seconds=180.0)
    assert len(clips) == 5
    assert clips[0].id == 1
    assert clips[0].title == "Part 1"
    assert clips[0].start == 180.0
    assert clips[0].end == 270.0
    assert clips[0].editorial["skip_intro_applied"] is True

    assert clips[4].id == 5
    assert clips[4].title == "Part 5"
    assert clips[4].start == 540.0
    assert clips[4].end == 600.0


def test_fast_cut_adjustable_duration():
    # Adjustable clip duration: 45 seconds on a 180s video -> 4 parts
    clips = generate_fast_cut_clips(duration=180.0, chunk_duration=45.0, skip_intro=False)
    assert len(clips) == 4
    for i, c in enumerate(clips, 1):
        assert c.id == i
        assert c.title == f"Part {i}"
        assert c.end - c.start == 45.0


def test_fast_cut_remainder_absorption():
    # 93 second video with 90s chunk -> remainder 3s (<5s) absorbed into Part 1
    clips = generate_fast_cut_clips(duration=93.0, chunk_duration=90.0, skip_intro=False)
    assert len(clips) == 1
    assert clips[0].start == 0.0
    assert clips[0].end == 93.0


def test_fast_cut_invalid_duration():
    with pytest.raises(ValueError, match="Video duration must be greater than 0"):
        generate_fast_cut_clips(duration=0.0)

    with pytest.raises(ValueError, match="Skip intro duration .* meets or exceeds"):
        generate_fast_cut_clips(duration=120.0, skip_intro=True, skip_seconds=180.0)


def test_four_three_layout_geometry():
    prefs = Preferences(width=1080, layout="four_three_hook")
    geo = layout(prefs)
    assert geo["width"] == 1080
    assert geo["height"] == 1920
    assert geo["video_width"] == 1080
    assert geo["video_height"] == 810  # 1080 * 3 / 4
    assert geo["video_y"] == 555        # (1920 - 810) // 2
    assert geo["hook_bottom"] == 528    # 555 - 27 (sits cleanly above video box)
    assert geo["caption_bottom"] == 1306


def test_four_three_captions_part_header(tmp_path):
    prefs = Preferences(width=1080, layout="four_three_hook", fast_cut=True)
    clip = Clip(
        id=1,
        start=0.0,
        end=90.0,
        title="Part 1",
        reason="Fast Cut Part 1",
        hook_text="Part 1",
        score=90,
        ratings=Ratings(hook=90, payoff=90, standalone=90, emotion=90, usefulness=90),
        text="Part 1",
        selection_method="fast_cut"
    )
    transcript = Transcript(language="en", duration=90.0, segments=[])
    ass_path = write_captions(tmp_path, transcript, clip, prefs)
    content = ass_path.read_text("utf-8-sig")

    # Header title is rendered at hook_bottom (528) with \an2 (bottom center)
    assert "\\pos(540,528)" in content
    assert "Part 1" in content


def test_four_three_filter_graph():
    prefs = Preferences(width=1080, layout="four_three_hook")
    graph, mode = filter_graph(prefs, {"width": 1920, "height": 1080}, "sub.ass")
    assert mode == "four_three_hook"
    assert "scale=1080:810" in graph
    assert "crop=1080:810" in graph
    assert "pad=1080:1920:0:555" in graph
    assert "ass=filename=sub.ass" in graph


@pytest.mark.asyncio
async def test_pipeline_analyze_fast_cut(tmp_path):
    cfg = Config(data_dir=tmp_path, min_free_disk_mb=1)
    pipeline = Pipeline(cfg)
    prefs = Preferences(
        fast_cut=True,
        fast_cut_duration=90,
        fast_cut_skip_intro=False,
        layout="four_three_hook"
    )

    # Create dummy source json simulating probed video
    source_dir = tmp_path / "job_fast_cut"
    source_dir.mkdir(parents=True)
    video_file = source_dir / "source.mp4"
    video_file.write_bytes(b"dummy")

    # Mock media.probe and media.transcribe
    import cliper.media as media
    orig_probe = media.probe
    orig_transcribe = media.transcribe
    async def mock_probe(path, *args, **kwargs):
        return {"width": 1920, "height": 1080, "duration": 270.0, "fps": 30.0}
    async def mock_transcribe(*args, **kwargs):
        return Transcript(language="en", duration=270.0, segments=[])
    media.probe = mock_probe
    media.transcribe = mock_transcribe

    progress_messages = []
    async def progress(msg):
        progress_messages.append(msg)

    try:
        analysis = await pipeline.analyze(str(video_file), source_dir, prefs, progress)
        assert analysis.method == "fast_cut"
        assert analysis.duration == 270.0
        assert len(analysis.clips) == 3
        assert analysis.clips[0].title == "Part 1"
        assert analysis.clips[1].title == "Part 2"
        assert analysis.clips[2].title == "Part 3"
        assert (source_dir / "analysis.json").exists()
    finally:
        media.probe = orig_probe
        media.transcribe = orig_transcribe


def test_fast_cut_publishing_and_scheduling(tmp_path):
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    from cliper.storage import Store
    from cliper.publishing import PublishStore
    from cliper.web import create_app

    cfg = Config(data_dir=tmp_path / "data", min_free_disk_mb=1)
    store = Store(cfg.data_dir)
    pubs = PublishStore(store)

    prefs = Preferences(fast_cut=True, fast_cut_duration=90, layout="four_three_hook")
    job = store.create(0, 0, "https://example.com/test-vod", prefs, limit=10)
    job_dir = store.directory(job["id"])
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # 3 parts of fast cut
    fast_clips = generate_fast_cut_clips(duration=270.0, chunk_duration=90.0)
    for c in fast_clips:
        (clips_dir / f"clip_{c.id:02}.mp4").write_bytes(b"fast-cut-mp4-data")

    analysis_data = {
        "title": "Fast Cut Source Video",
        "language": "en",
        "duration": 270.0,
        "method": "fast_cut",
        "clips": [c.model_dump() for c in fast_clips]
    }
    (job_dir / "analysis.json").write_text(json.dumps(analysis_data), encoding="utf-8")

    # Setup YouTube config and tokens for testing
    cfg_file = tmp_path / "youtube.json"
    cfg_file.write_text(json.dumps({
        "client_id": "test-cid",
        "client_secret": "test-sec",
        "accounts": {
            "main": {
                "title": "My Channel",
                "channel_id": "UC12345",
                "privacy": "public",
                "default_tags": ["shorts"],
                "owners": [0]
            }
        }
    }), encoding="utf-8")

    token_file = cfg.data_dir / "youtube" / "tokens" / "main.json"
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

            # 1. Test single clip publishing for Instagram
            ig_resp = client.post(
                f"/api/jobs/{job['id']}/clips/1/publish",
                json={"platform": "instagram", "account": "clips", "publish_now": True}
            )
            assert ig_resp.status_code == 200
            ig_data = ig_resp.json()
            assert ig_data["ok"] is True
            assert ig_data["platform"] == "instagram"
            assert ig_data["state"] == "queued"

            # 2. Test batch scheduling for YouTube Shorts
            sched_resp = client.post(
                f"/api/jobs/{job['id']}/schedule-all",
                json={
                    "platform": "youtube",
                    "account": "main",
                    "gap_hours": 2.0,
                    "publish_first_now": False,
                    "schedule_on_youtube": False
                }
            )
            assert sched_resp.status_code == 200
            sched_data = sched_resp.json()
            assert sched_data["ok"] is True
            assert sched_data["count"] == 3
            assert sched_data["items"][0]["title"] == "Part 1"
            assert sched_data["items"][1]["title"] == "Part 2"
            assert sched_data["items"][2]["title"] == "Part 3"

