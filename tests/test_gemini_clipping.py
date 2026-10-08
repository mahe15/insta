import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cliper.browser_provider import BrowserProviderError
from cliper.gemini_clipping import (
    GeminiVideo,
    VideoResult,
    parse_gemini_video_result,
    validate_result,
    verify_range,
    youtube_url,
)
from cliper.models import Preferences, Segment, Transcript, Word
from cliper.pipeline import Pipeline
from cliper.storage import write_json

URL = "https://www.youtube.com/watch?v=abcdefghijk"


def test_all_features_reuse_original_chromium_profile(cfg, monkeypatch):
    from cliper.browser_provider import BrowserEditorialClient
    from cliper.gemini_images import GeminiImages
    monkeypatch.delenv("GEMINI_BROWSER_PROFILE", raising=False)
    chatgpt, images, clipping = BrowserEditorialClient(cfg), GeminiImages(cfg), GeminiVideo(cfg)
    assert Path(chatgpt.profile).resolve() == images.profile == clipping.profile
    assert chatgpt.lock.lock_file == images.lock.lock_file == clipping.lock.lock_file


def payload():
    phrases = ["Test one useful idea first.", "Ask someone what they actually need.",
               "Build the smallest thing that helps.", "Use their feedback to improve it."]
    return {"source_url": URL, "accessible": True, "access_note": "Video accessed", "language": "en", "clips": [{
        "start": 10, "end": 30, "title": "Test demand before building your idea", "reason": "Complete practical lesson",
        "ratings": dict.fromkeys(["hook", "payoff", "standalone", "emotion", "usefulness"], 90),
        "transcript": " ".join(phrases), "captions": [{"start": 10 + i * 5, "end": 14 + i * 5,
        "text": text, "words": []} for i, text in enumerate(phrases)]}]}


def validated(data=None, verify=True):
    return validate_result(VideoResult.model_validate(data or payload()), URL, {"duration": 80, "title": "Test"},
                           Preferences(min_seconds=15, max_seconds=30, gemini_verify_captions=verify))


@pytest.mark.parametrize("url", ["https://youtu.be/abcdefghijk?t=15", URL + "&list=ignored",
                                 "https://m.youtube.com/shorts/abcdefghijk"])
def test_video_url_normalized(url):
    assert youtube_url(url) == URL


@pytest.mark.parametrize("url", ["http://youtu.be/abcdefghijk", "https://youtube.com.evil.org/watch?v=abcdefghijk",
                                 "https://youtube.com/playlist?list=abcdefghijk", "https://vimeo.com/123",
                                 "https://user:pass@youtu.be/abcdefghijk", "https://youtu.be/short"])
def test_video_url_restricted(url):
    with pytest.raises(ValueError):
        youtube_url(url)


def test_phrase_captions_preserve_absolute_timing_and_manual_gate():
    analysis, transcript = validated(verify=False)
    clip = analysis.clips[0]
    assert clip.start == 10 and clip.end == 30
    assert transcript.segments[0].words[0].text == "Test one useful idea first."
    assert transcript.segments[0].words[0].start == 10
    assert not clip.editorial["automatic_ready"]
    assert analysis.method == "gemini_browser_youtube"


@pytest.mark.parametrize("defect", ["wrong_video", "unavailable", "end", "duration", "relative", "overlap", "mismatch", "category", "nan"])
def test_reject_unusable_gemini_data(defect):
    data = payload()
    moment = data["clips"][0]
    if defect == "wrong_video":
        data["source_url"] = URL.replace("abcdefghijk", "ZYXWVUTSRQP")
    elif defect == "unavailable":
        data["accessible"] = False
    elif defect == "end":
        moment["end"] = 100
    elif defect == "duration":
        moment["end"] = 60
    elif defect == "relative":
        moment["captions"][0]["start"] = 0
    elif defect == "overlap":
        moment["captions"][1]["start"] = 11
    elif defect == "mismatch":
        moment["transcript"] = "Invented unrelated transcript."
    elif defect == "category":
        moment["music_category"] = "../../outside"
    else:
        moment["start"] = float("nan")
    with pytest.raises(ValueError):
        validated(data)


def test_overlapping_candidates_are_not_downloaded_twice():
    data = payload()
    data["clips"].append(copy.deepcopy(data["clips"][0]))
    assert len(validated(data)[0].clips) == 1


def test_caption_currency_mismatch_is_rejected():
    data = payload()
    moment = data["clips"][0]
    moment["captions"][0]["text"] = "Save $100 today."
    moment["transcript"] = " ".join(s["text"] for s in moment["captions"]).replace("$", "£")
    with pytest.raises(ValueError, match="differs"):
        validated(data)


async def test_metadata_only_and_stale_metadata_rejected(cfg, monkeypatch):
    from cliper.remote_media import metadata
    folder = cfg.data_dir / "metadata"
    folder.mkdir()
    old = folder / "source.info.json"
    write_json(old, {"duration": 80, "id": "old"})
    execute = AsyncMock()
    monkeypatch.setattr("cliper.remote_media.execute", execute)
    with pytest.raises(ValueError, match="unavailable"):
        await metadata(URL, folder, cfg, lambda: False)
    assert "--skip-download" in execute.call_args.args[0]
    assert not old.exists()


def test_export_includes_gemini_and_corrected_captions(cfg):
    import zipfile

    from cliper.maintenance import export_metadata
    write_json(cfg.data_dir / "gemini-clips.json", payload())
    corrected = cfg.data_dir / "ranges" / "clip_01" / "caption-verification" / "transcript.json"
    corrected.parent.mkdir(parents=True)
    write_json(corrected, {"fixture": True})
    with zipfile.ZipFile(export_metadata(cfg.data_dir)) as archive:
        assert "gemini-clips.json" in archive.namelist()
        assert "ranges/clip_01/caption-verification/transcript.json" in archive.namelist()


async def test_link_first_pipeline_never_downloads_full_audio_or_checks_paid_key(cfg, monkeypatch):
    from cliper import gemini_clipping
    cfg.provider = "gemini"
    cfg.gemini_api_key = ""
    metadata = AsyncMock(return_value={"duration": 80, "title": "Test", "id": "abcdefghijk"})
    audio = AsyncMock(side_effect=AssertionError("Must not download full audio"))
    monkeypatch.setattr("cliper.remote_media.metadata", metadata)
    monkeypatch.setattr("cliper.remote_media.audio", audio)
    class Client:
        def __init__(self, cfg):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def request_video(self, prompt, cancelled):
            assert URL in prompt and "ORIGINAL VIDEO" in prompt
            return VideoResult.model_validate(payload())
    monkeypatch.setattr(gemini_clipping, "GeminiVideo", Client)
    prefs = Preferences(clipping_mode="gemini_browser", min_seconds=15, max_seconds=30)
    directory = cfg.data_dir / "job"
    analysis = await Pipeline(cfg).analyze(URL, directory, prefs, AsyncMock())
    assert analysis.clips and not audio.called
    assert json.loads((directory / "source.json").read_text())["kind"] == "remote_gemini"
    assert not (directory / "audio.wav").exists()
    await Pipeline(cfg).analyze(URL, directory, prefs, AsyncMock())
    assert metadata.await_count == 1


@pytest.mark.parametrize("repair_succeeds", [True, False])
async def test_gemini_repair_is_bounded_and_only_valid_results_are_cached(cfg, monkeypatch, repair_succeeds):
    from cliper import gemini_clipping

    monkeypatch.setattr("cliper.remote_media.metadata", AsyncMock(return_value={
        "duration": 80, "title": "Test", "id": "abcdefghijk"}))
    bad = payload()
    bad["clips"][0]["transcript"] = "Unrelated invented dialogue."
    responses = [bad, payload()] if repair_succeeds else [bad] * 3
    prompts = []

    class Client:
        def __init__(self, cfg):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def request_video(self, prompt, cancelled):
            prompts.append(prompt)
            return VideoResult.model_validate(responses[len(prompts) - 1])

    monkeypatch.setattr(gemini_clipping, "GeminiVideo", Client)
    prefs = Preferences(min_seconds=15, max_seconds=30, focus_times=[15])
    call = gemini_clipping.analyze(URL, cfg.data_dir, prefs, cfg, AsyncMock(), lambda: False)
    if repair_succeeds:
        assert (await call).clips
        cached = VideoResult.model_validate_json((cfg.data_dir / "gemini-clips.json").read_text("utf-8"))
        assert cached.clips[0].transcript == payload()["clips"][0]["transcript"]
        assert validate_result(cached, URL, {"duration": 80, "title": "Test"}, prefs)[0].clips
    else:
        with pytest.raises(ValueError, match="differs"):
            await call
        assert not (cfg.data_dir / "gemini-clips.json").exists()
        assert not (cfg.data_dir / "analysis.json").exists()
    assert len(prompts) == (2 if repair_succeeds else 3)
    assert "[15.0]" in prompts[0] or "[15]" in prompts[0]
    assert "failed local validation" in prompts[1]
    assert (cfg.data_dir / "gemini-rejected-1.json").exists()


async def test_gemini_focus_outside_source_fails_before_browser(cfg, monkeypatch):
    from cliper import gemini_clipping

    monkeypatch.setattr("cliper.remote_media.metadata", AsyncMock(return_value={
        "duration": 80, "title": "Test", "id": "abcdefghijk"}))
    browser = AsyncMock(side_effect=AssertionError("No browser should open"))
    monkeypatch.setattr(gemini_clipping, "GeminiVideo", browser)
    with pytest.raises(ValueError, match="focus timestamp"):
        await gemini_clipping.analyze(URL, cfg.data_dir, Preferences(focus_times=[80]), cfg, AsyncMock(), lambda: False)
    browser.assert_not_called()


async def test_selected_range_correction_caches_and_flags_disagreement(cfg, transcript, monkeypatch):
    analysis, _ = validated()
    clip = analysis.clips[0]
    source = cfg.data_dir / "range.mp4"
    source.write_bytes(b"range")
    local = transcript.model_copy(update={"duration": 20, "segments": transcript.segments[:4]})
    async def transcribe(source, target, *args):
        write_json(target / "transcript.json", local.model_dump())
        return local
    speech = AsyncMock(side_effect=transcribe)
    monkeypatch.setattr("cliper.remote_media.section", AsyncMock(return_value=source))
    monkeypatch.setattr("cliper.media.transcribe", speech)
    prefs = Preferences(min_seconds=15, max_seconds=30)
    await verify_range({"url": URL}, cfg.data_dir, clip, prefs, cfg, lambda: False)
    assert clip.editorial["caption_verification"] == "completed"
    assert not clip.editorial["automatic_ready"]
    await verify_range({"url": URL}, cfg.data_dir, clip, prefs, cfg, lambda: False)
    assert speech.await_count == 1


async def test_fast_render_shifts_gemini_phrases_to_local_range(cfg, monkeypatch):
    analysis, transcript = validated(verify=False)
    write_json(cfg.data_dir / "source.json", {"kind": "remote_gemini", "url": URL, "path": "unused"})
    write_json(cfg.data_dir / "transcript.json", transcript.model_dump())
    source = cfg.data_dir / "range.mp4"
    source.write_bytes(b"range")
    section = AsyncMock(return_value=source)
    monkeypatch.setattr("cliper.remote_media.section", section)
    async def render(source, directory, shifted, clip, *args):
        assert clip.start == 0 and clip.end == 20
        assert shifted.segments[0].words[0].start == 0
        assert shifted.segments[-1].end == 19
        directory.mkdir(exist_ok=True)
        output = directory / "clip_01.mp4"
        output.write_bytes(b"result")
        write_json(output.with_suffix(".json"), {})
        return output
    monkeypatch.setattr("cliper.media.render", render)
    await Pipeline(cfg).render_one(cfg.data_dir, analysis.clips[0], Preferences(gemini_verify_captions=False))
    assert section.call_args.args[2:4] == (10, 30)


async def test_corrected_caption_changes_invalidate_render_cache(cfg, transcript, monkeypatch):
    analysis, gemini_transcript = validated()
    write_json(cfg.data_dir / "source.json", {"kind": "remote_gemini", "url": URL, "path": "unused"})
    write_json(cfg.data_dir / "transcript.json", gemini_transcript.model_dump())
    local = transcript.model_copy(update={"duration": 20, "segments": transcript.segments[:4]}, deep=True)
    corrected = local.model_copy(deep=True)
    corrected.segments[0].words[0].text = "How"
    source = cfg.data_dir / "range.mp4"
    source.write_bytes(b"range")
    monkeypatch.setattr("cliper.gemini_clipping.verify_range", AsyncMock(side_effect=[(source, local), (source, corrected)]))
    monkeypatch.setattr("cliper.media.quality_check", AsyncMock())
    async def render(source, directory, shifted, clip, *args):
        directory.mkdir(exist_ok=True)
        output = directory / "clip_01.mp4"
        output.write_bytes(b"result")
        write_json(output.with_suffix(".json"), {})
        return output
    renderer = AsyncMock(side_effect=render)
    monkeypatch.setattr("cliper.media.render", renderer)
    pipeline = Pipeline(cfg)
    for _ in range(2):
        await pipeline.render_one(cfg.data_dir, analysis.clips[0], Preferences())
    assert renderer.await_count == 2


@pytest.mark.parametrize("signed_out", [False, True])
async def test_real_chromium_link_json_without_file_attachment(cfg, signed_out):
    playwright = pytest.importorskip("playwright.async_api")
    html = '''<rich-textarea><div contenteditable="true" role="textbox"></div></rich-textarea>
    SIGNIN<button aria-label="Send message" onclick="send()">Send</button><script>
    function send(){const text=document.querySelector('[contenteditable]').textContent;
    const id=text.match(/"request_id": "([a-f0-9]+)"/)[1];
    const r=document.createElement('model-response');r.innerHTML='<code></code><button aria-label="Copy"></button>';
    r.querySelector('code').textContent=JSON.stringify({request_id:id,result:PAYLOAD});document.body.appendChild(r);}
    </script>'''.replace("PAYLOAD", json.dumps(payload())).replace("SIGNIN", '<button>Sign in</button>' if signed_out else "")
    async with playwright.async_playwright() as pw:
        if not Path(pw.chromium.executable_path).exists():
            pytest.skip("Chromium not installed")
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            await context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            client = GeminiVideo(cfg)
            client.context = context
            if signed_out:
                with pytest.raises(BrowserProviderError, match="signed out"):
                    await client.request_video("Analyze " + URL)
            else:
                result = await client.request_video("Analyze " + URL)
                assert result.accessible and result.clips[0].start == 10
            assert not context.pages
        finally:
            await browser.close()


async def test_telegram_command_uses_gemini_website_without_api_key(cfg):
    from cliper.bot import Controller
    cfg.token = "test"
    cfg.allowed_users = frozenset({123})
    controller = Controller(cfg)
    controller.guard = AsyncMock(return_value=True)
    message = SimpleNamespace(text="/geminiclip@mybot " + URL, video=None, document=None, reply_text=AsyncMock())
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=123), effective_chat=SimpleNamespace(id=123))
    await controller.submit(update, None)
    jobs = controller.store.recent(123)
    assert jobs, message.reply_text.call_args
    assert json.loads(jobs[0]["prefs"])["clipping_mode"] == "gemini_browser"
    assert controller.store.prefs(123).clipping_mode == "audio_first"


def test_long_caption_phrases_are_automatically_split():
    data = payload()
    moment = data["clips"][0]
    # Replace captions with a single 15-second sentence of 20 words
    long_sentence = "This is a single long conversational sentence spoken in the YouTube video that spans fifteen seconds without pausing."
    moment["captions"] = [{"start": 10.0, "end": 25.0, "text": long_sentence, "words": []}]
    moment["transcript"] = long_sentence
    moment["start"] = 10.0
    moment["end"] = 28.0
    analysis, transcript = validated(data, verify=False)
    assert len(transcript.segments) > 1
    assert all(s.end - s.start <= 6.0 for s in transcript.segments)
    assert " ".join(s.text for s in transcript.segments) == long_sentence


def test_parse_gemini_video_result_real_wrapped_response():
    raw_response = """Gemini said

{"request_id": "304fa6201e534cb590562b36151c2ff0", "result": {"source_url": "https://www.youtube.com/watch?v=fQiofWCOvrg", "accessible": false, "access_note": "Video content is not accessible directly as real-time tool access to external web/YouTube transcript endpoints is disabled.", "language": "en", "clips": []}}

How To Become a Great Communicator | Speak Like a Pro | English Podcast 
Try To Thrive · 147K views"""
    result = parse_gemini_video_result(raw_response)
    assert result.source_url == "https://www.youtube.com/watch?v=fQiofWCOvrg"
    assert result.accessible is False
    assert "disabled" in result.access_note
    assert result.clips == []


def test_parse_gemini_video_result_handles_extra_fields_and_string_times():
    raw_response = """
```json
{
  "request_id": "OBJECT MATCHING SCHEMA BELOW",
  "result": {
    "source_url": "https://www.youtube.com/watch?v=abcdefghijk",
    "accessible": true,
    "access_note": "ok",
    "language": "en",
    "extra_summary": "Ignored extra field",
    "clips": [
      {
        "start": "00:10",
        "end": "00:30",
        "title": "Great Communication Tip That Changes Everything You Know About Speaking In Public Today",
        "hook_variants": ["Hook 1", "Hook 2", "Hook 3", "Hook 4"],
        "reason": "Very clear and helpful explanation",
        "ratings": {"hook": 9, "payoff": 8.5, "standalone": 9, "emotion": 8, "usefulness": 9, "engagement": 10},
        "transcript": "Speak with confidence. Practice daily. Listen carefully to others.",
        "captions": [
          {"start": "00:10", "end": "00:15", "text": "Speak with confidence.", "words": []},
          {"start": "00:15", "end": "00:22", "text": "Practice daily.", "words": []},
          {"start": "00:22", "end": "00:30", "text": "Listen carefully to others.", "words": []}
        ],
        "music_category": "unknown_genre",
        "caption": "Check out these tips!",
        "hashtags": ["#speech", "#public", "#talk", "#english", "#tips", "#extra"],
        "audience_value": "High value advice",
        "unrecognized_field": 12345
      }
    ]
  }
}
```
"""
    result = parse_gemini_video_result(raw_response)
    assert result.accessible is True
    assert len(result.clips) == 1
    clip = result.clips[0]
    assert clip.start == 10.0 and clip.end == 30.0
    assert len(clip.hook_variants) == 3
    assert len(clip.hashtags) == 5
    assert clip.ratings.hook == 90
    assert clip.music_category == "chill_ambient"
    assert clip.captions[0].start == 10.0


async def test_gemini_accessible_false_falls_back_to_audio_first(cfg, monkeypatch):
    from cliper import gemini_clipping
    from cliper.models import Analysis, Clip, Ratings
    metadata = AsyncMock(return_value={"duration": 80, "title": "Test Video", "id": "abcdefghijk"})
    monkeypatch.setattr("cliper.remote_media.metadata", metadata)

    class UnavailableGeminiClient:
        def __init__(self, cfg):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def request_video(self, prompt, cancelled):
            return VideoResult(source_url=URL, accessible=False, access_note="Disabled tool", language="en", clips=[])

    monkeypatch.setattr(gemini_clipping, "GeminiVideo", UnavailableGeminiClient)

    # Mock audio-first pipeline dependencies
    audio_path = cfg.data_dir / "audio.wav"
    audio_path.write_bytes(b"dummy audio")
    monkeypatch.setattr("cliper.remote_media.audio", AsyncMock(return_value=(audio_path, {"duration": 80, "title": "Test Video"})))
    dummy_transcript = Transcript(language="en", duration=80, segments=[
        Segment(start=10, end=30, text="Audio first fallback worked.", words=[Word(start=10, end=30, text="Audio first fallback worked.")])
    ])
    monkeypatch.setattr("cliper.media.transcribe", AsyncMock(return_value=dummy_transcript))
    dummy_clip = Clip(id=1, start=10, end=30, title="Fallback Clip", hook_variants=[], reason="Fallback",
                      hook_text="Audio", score=85, ratings=Ratings(hook=85, payoff=85, standalone=85, emotion=85, usefulness=85),
                      text="Audio first fallback worked.", selection_method="heuristic")
    dummy_analysis = Analysis(title="Test Video", language="en", duration=80, method="audio_first", clips=[dummy_clip])
    monkeypatch.setattr("cliper.pipeline.select", AsyncMock(return_value=dummy_analysis))
    scan = AsyncMock(return_value=dummy_analysis)
    monkeypatch.setattr("cliper.stream_scan.analyze", scan)

    prefs = Preferences(clipping_mode="gemini_browser", min_seconds=15, max_seconds=30)
    directory = cfg.data_dir / "job_fallback"
    progress = AsyncMock()
    analysis = await Pipeline(cfg).analyze(URL, directory, prefs, progress)
    assert analysis.method == "audio_first"
    scan.assert_awaited_once()
    assert any("falling back" in str(call.args[0]).lower() for call in progress.await_args_list)
