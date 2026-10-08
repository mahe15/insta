import hashlib
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from cliper.display_text import Translation, display_clip, non_latin, prepare, romanize
from cliper.gemini_clipping import VideoMoment, VideoResult, validate_result
from cliper.models import Preferences, Segment, Transcript, Word
from cliper.speed_edit import ASSETS, envelope_peaks, make_plan
from cliper.speed_profile import instructions, preset
from cliper.web import create_app


def test_speed_preset_isolated_and_duration_limits():
    original = Preferences(min_seconds=30, max_seconds=90, auto_publish=False)
    speed = preset(original)
    assert (speed.min_seconds, speed.max_seconds, speed.text_mode) == (6, 60, "english")
    assert original.max_seconds == 90 and original.editorial_profile == "standard"
    assert speed.auto_publish is False and speed.gemini_verify_captions
    assert "ISHOWSPEED" in instructions(speed)
    with pytest.raises(ValueError):
        preset(original, max_seconds=61)
    with pytest.raises(ValueError):
        preset(original, min_seconds=5)


@pytest.mark.parametrize("text,language", [("तुम कैसे हो?", "hi"), ("تم کیسے ہو", "ur"), ("你好世界", "zh"), ("Привет мир", "ru")])
def test_romanization_preserves_content_in_latin_letters(text, language):
    converted = romanize(text, language)
    assert converted.strip() and converted != text and not non_latin(converted)


async def test_romanization_preserves_word_times_and_source(cfg, clip):
    transcript = Transcript(language="hi", duration=8, segments=[Segment(start=1, end=3, text="तुम कैसे हो?",
        words=[Word(start=1, end=1.5, text="तुम"), Word(start=1.5, end=2.3, text="कैसे"), Word(start=2.3, end=3, text="हो?")])])
    original = transcript.model_dump_json()
    clip = clip.model_copy(update={"end": 8, "title": "तुम कैसे हो?", "caption": "यह गलती मत करो", "hashtags": ["#हिंदी"]})
    result, edited, report = await prepare(transcript, clip, Preferences(), cfg, cfg.data_dir)
    assert [(w.start, w.end) for w in result.segments[0].words] == [(1, 1.5), (1.5, 2.3), (2.3, 3)]
    assert result.segments[0].text == "tum kaise ho?"
    assert not non_latin(edited.title + edited.caption + "".join(edited.hashtags))
    assert transcript.model_dump_json() == original and non_latin(clip.title)
    assert report["timing"] == "original word timestamps"


async def test_english_translation_keeps_phrase_times_and_caches(cfg, clip, monkeypatch):
    cfg.provider = "openai"
    cfg.api_key = "test-key"
    transcript = Transcript(language="hi", duration=10, segments=[Segment(start=2, end=4, text="तुम कैसे हो?", words=[])])
    client = type("Client", (), {"structured": AsyncMock(return_value=Translation.model_validate({"lines": [{"id": 0, "text": "How are you?"}]}))})()
    @asynccontextmanager
    async def fake(*args):
        yield client
    monkeypatch.setattr("cliper.providers.editorial_client", fake)
    result, _, report = await prepare(transcript, clip, preset(Preferences()), cfg, cfg.data_dir)
    assert result.segments[0].words == [Word(start=2, end=4, text="How are you?")]
    assert "phrase" in report["timing"]
    await prepare(transcript, clip, preset(Preferences()), cfg, cfg.data_dir)
    assert client.structured.await_count == 1


def test_peak_planning_is_sparse_and_respects_payoff(cfg, clip):
    samples = np.full(16000 * 8, .02, dtype=np.float32)
    samples[16000*3:16000*3+1600] = .4
    samples[16000*4:16000*4+1600] = .3
    peaks = envelope_peaks(samples, 16000)
    c = clip.model_copy(update={"end": 8, "moment_type": "reaction", "payoff_time": 3})
    p = preset(Preferences())
    plan = make_plan(peaks, c, p)
    assert len(plan["effects"]) == 1 and plan["effects"][0]["time"] == 3
    assert len(plan["zoom"]) == 1
    assert not make_plan(peaks, c.model_copy(update={"moment_type": "wholesome"}), p)["effects"]
    assert not make_plan(peaks, c.model_copy(update={"payoff_time": 7}), p)["effects"]
    assert not make_plan(peaks, c, preset(Preferences(), sound_effects=False, reaction_zoom=False))["effects"]
    assert envelope_peaks(np.zeros(16000), 16000) == []


def test_sound_assets_match_pinned_license_manifest():
    manifest = json.loads((ASSETS / "manifest.json").read_text())
    assert manifest["license"] == "CC0-1.0"
    assert "Creative Commons Zero" in (ASSETS / "LICENSE.txt").read_text()
    for name, info in manifest["files"].items():
        assert hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() == info["sha256"]


def test_speed_gemini_accepts_nonverbal_complete_moment_only_in_speed_mode(clip):
    url = "https://www.youtube.com/watch?v=abcdefghijk"
    moment = VideoMoment(start=1, end=9, title="Speed lands the challenge", reason="An observed complete visual event",
                         ratings=clip.ratings, moment_type="challenge", payoff_time=6)
    result = VideoResult(source_url=url, accessible=True, access_note="fixture", language="en", clips=[moment])
    analysis, transcript = validate_result(result, url, {"title": "fixture", "duration": 10}, preset(Preferences()))
    assert analysis.clips[0].payoff_time == 6 and transcript.segments == []
    with pytest.raises(ValueError, match="speech captions"):
        validate_result(result, url, {"title": "fixture", "duration": 10}, Preferences(min_seconds=6, max_seconds=10))


def test_speed_api_creates_real_isolated_job_and_keeps_global_prefs(cfg):
    cfg.owners = {7}
    app = create_app(cfg, start_engine=False, token="test", project_root=cfg.data_dir)
    with TestClient(app) as client:
        response = client.post("/api/session", json={"key": "test"})
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        source = "https://youtu.be/abcdefghijk"
        result = client.post("/api/speed/jobs", json={"source": source, "preferences": {"min_seconds": 6, "max_seconds": 12}})
        assert result.status_code == 201 and result.json()["editorial_profile"] == "ishowspeed"
        job = app.state.store.get(result.json()["id"])
        prefs = json.loads(job["prefs"])
        assert prefs["text_mode"] == "english" and prefs["max_seconds"] == 12 and job["chat"] == 0
        assert app.state.store.prefs(7).editorial_profile == "standard"
        assert client.post("/api/speed/jobs", json={"source": "https://twitch.tv/example"}).status_code == 400
        assert client.post("/api/speed/jobs", json={"source": source, "preferences": {"max_seconds": 90}}).status_code == 400
        sounds = client.get("/api/speed/sounds").json()
        assert sounds["license"] == "CC0-1.0"
        assert client.get(sounds["files"][0]["url"]).content[:4] == b"RIFF"


async def test_real_speed_ffmpeg_render_with_sfx_zoom_and_romanized_captions(cfg, clip, monkeypatch):
    from cliper.media import render
    from cliper.process import run
    cfg.video_encoder = "libx264"
    source = cfg.data_dir / "fixture.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=7",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=7", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source)])
    c = clip.model_copy(update={"end": 6, "moment_type": "reaction", "payoff_time": 3})
    p = preset(Preferences(), width=360, reframe="center", music=False)
    plan = make_plan([{"time":3, "strength":4}], c, p)
    monkeypatch.setattr("cliper.speed_edit.plan", AsyncMock(return_value=plan))
    transcript = Transcript(language="en", duration=7, segments=[Segment(start=1,end=3,text="Look at that!",words=[Word(start=1,end=2,text="Look"),Word(start=2,end=2.5,text="at"),Word(start=2.5,end=3,text="that!")])])
    output = await render(source, cfg.data_dir / "exports", transcript, c, p, cfg, lambda: False)
    meta = json.loads(output.with_suffix(".json").read_text())
    assert meta["quality"]["full_decode"] == "passed"
    assert meta["speed_edit"]["effects"][0]["time"] == 3
    assert abs(meta["quality"]["duration"] - 6) < .1
    assert output.with_suffix(".srt").read_text().strip()
    monkeypatch.setattr("cliper.speed_edit.plan", AsyncMock(return_value={"effects": [], "zoom": []}))
    hindi = Transcript(language="hi", duration=7, segments=[Segment(start=1, end=3, text="तुम कैसे हो?",
        words=[Word(start=1, end=1.5, text="तुम"), Word(start=1.5, end=2.3, text="कैसे"), Word(start=2.3, end=3, text="हो?")])])
    normal = Preferences(width=360, reframe="center", music=False)
    roman_output = await render(source, cfg.data_dir / "romanized", hindi, c.model_copy(update={"title": "तुम कैसे हो?"}), normal, cfg, lambda: False)
    captions = roman_output.with_suffix(".srt").read_text("utf-8")
    assert "tum kaise ho?" in captions and not non_latin(captions)
    assert not non_latin(roman_output.with_suffix(".ass").read_text("utf-8-sig"))


async def test_long_face_track_expression_decodes_in_real_ffmpeg(cfg):
    from cliper.process import run
    from cliper.vision import center_expression
    expr = center_expression([[i*.5, .4 if i % 2 else .6] for i in range(120)])
    await run([cfg.ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=1",
               "-vf", f"crop=360:360:x='max(0,min(iw-ow,iw*({expr})-ow/2))'", "-frames:v", "2", "-f", "null", "-"])


def test_original_script_remains_optional(clip):
    c = clip.model_copy(update={"title":"नमस्ते"})
    assert display_clip(c, Preferences(text_mode="source")).title == "नमस्ते"
