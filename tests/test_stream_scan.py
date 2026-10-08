import asyncio
import json
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cliper import remote_media
from cliper.media import validate_url
from cliper.models import Analysis, Preferences, Segment, Transcript, Word
from cliper.platforms import DEFAULT_HOSTS
from cliper.storage import write_json
from cliper.stream_scan import analyze, parse_vtt, plan_windows, shift, timestamp
from cliper.vision import smooth_center


@pytest.mark.parametrize("host", DEFAULT_HOSTS)
def test_supported_host_registry_and_spoof_rejection(cfg, host):
    assert validate_url(f"https://{host}/video", cfg)
    with pytest.raises(ValueError):
        validate_url(f"https://{host}.evil.invalid/video", cfg)


@pytest.mark.parametrize("hours", [8, 20])
@pytest.mark.parametrize("budget", [6, 24, 60])
def test_long_stream_budget_and_timeline_diversity(hours, budget):
    duration = hours * 3600
    ranges = plan_windows({"duration": duration}, Preferences(scan_minutes=budget))
    assert sum(w["end"] - w["start"] for w in ranges) <= budget * 60
    assert all(0 <= w["start"] < w["end"] <= duration for w in ranges)
    assert all(a["end"] <= b["start"] for a, b in zip(ranges, ranges[1:], strict=False))
    assert max(w["end"] for w in ranges) > duration * .74
    assert len(ranges) <= budget // 3
    if budget >= 24:
        for quarter in range(4):
            assert any(quarter * duration / 4 <= (w["start"] + w["end"]) / 2 < (quarter + 1) * duration / 4 for w in ranges)


def test_focus_replay_and_caption_hints_are_bounded():
    duration = 72000
    info = {"duration": duration, "heatmap": [{"start_time": 65000, "end_time": 65100, "value": 1.0}]}
    prefs = Preferences(scan_minutes=24, focus_times=[1000])
    ranges = plan_windows(info, prefs)
    assert any(w["start"] <= 1000 <= w["end"] and w["reason"] == "user focus" for w in ranges)
    assert any(w["reason"] == "replay signal" for w in ranges)
    with pytest.raises(ValueError, match="beyond"):
        plan_windows(info, prefs.model_copy(update={"focus_times": [80000]}))
    with pytest.raises(ValueError, match="Too many"):
        plan_windows(info, Preferences(scan_minutes=6, focus_times=[10, 2000, 3000]))
    with pytest.raises(ValueError, match="beyond"):
        plan_windows({"duration": 60}, Preferences(focus_times=[100]))


def test_vtt_rolling_captions_and_real_repetition_after_gap():
    transcript = parse_vtt("""WEBVTT

00:00:00.000 --> 00:00:02.000
Hello world

00:00:01.500 --> 00:00:04.000
Hello world this is useful.

00:02:00.000 --> 00:02:02.000
Hello world
""", 180, "en")
    assert [s.text for s in transcript.segments] == ["Hello world", "this is useful.", "Hello world"]
    assert all(not s.words for s in transcript.segments)


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "1:99", "1:2:3:4"])
def test_invalid_focus_times(value):
    with pytest.raises(ValueError):
        timestamp(value)


def test_shift_preserves_absolute_alignment_and_confidence():
    local = Transcript(language="en", duration=20, segments=[Segment(start=2, end=5, text="A useful moment.",
        words=[Word(start=2, end=5, text="A useful moment.", confidence=.8)])])
    moved = shift(local, 65000, 65020)[0]
    assert moved.start == 65002 and moved.words[0].end == 65005 and moved.words[0].confidence == .8
    assert timestamp("18:10:30.5") == 65430.5


async def test_twenty_hour_scan_resume_model_batch_and_download_concurrency(cfg, clip, monkeypatch):
    monkeypatch.setattr(remote_media, "metadata", AsyncMock(return_value={"duration": 72000, "title": "Long VOD", "id": "vod"}))
    monkeypatch.setattr(remote_media, "captions", AsyncMock(return_value=None))
    monkeypatch.setattr(remote_media, "audio", AsyncMock(side_effect=AssertionError("No full audio")))
    running, peak = 0, 0
    async def audio(url, target, start, end, *args):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(.01)
        target.mkdir(parents=True, exist_ok=True)
        path = target / "scan.wav"
        path.write_bytes(b"fixture")
        running -= 1
        return path
    download = AsyncMock(side_effect=audio)
    monkeypatch.setattr(remote_media, "audio_window", download)
    async def batch(items, *args):
        for item in items:
            write_json(Path(item["output"]), Transcript(language="en", duration=180, segments=[
                Segment(start=1, end=21, text="A complete example with a payoff.", words=[Word(start=1, end=21, text="A complete example with a payoff.")])]).model_dump())
    transcription = AsyncMock(side_effect=batch)
    monkeypatch.setattr("cliper.stream_scan.batch_transcribe", transcription)
    async def select(transcript, *args):
        assert transcript.duration == 72000 and transcript.coverage["partial"]
        s = transcript.segments[-1]
        return Analysis(title="Selected", language="en", duration=72000, method="fixture",
                        clips=[clip.model_copy(update={"start": s.start, "end": s.end, "text": s.text})])
    selection = AsyncMock(side_effect=select)
    monkeypatch.setattr("cliper.selection.select", selection)
    prefs = Preferences(scan_minutes=9)
    first = await analyze("https://kick.com/user/videos/id", cfg.data_dir, prefs, cfg, AsyncMock(), lambda: False)
    assert first.coverage["analyzed_seconds"] == 540 and first.coverage["fraction"] == .0075
    assert peak <= cfg.scan_download_workers and download.await_count == 3
    assert len(transcription.call_args.args[0]) == 3
    assert first.clips[0].start > 50000
    remote_media.metadata.return_value["heatmap"] = [{"start_time": 65000, "end_time": 65100, "value": 1}]
    second = await analyze("https://kick.com/user/videos/id", cfg.data_dir, prefs, cfg, AsyncMock(), lambda: False)
    assert download.await_count == 3 and selection.await_count == 1
    assert first == second


async def test_caption_index_avoids_all_scan_audio(cfg, clip, monkeypatch):
    monkeypatch.setattr(remote_media, "metadata", AsyncMock(return_value={"duration": 40, "title": "Captioned", "id": "id"}))
    vtt = cfg.data_dir / "source.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:22.000\nA useful complete thought.\n", encoding="utf-8")
    monkeypatch.setattr(remote_media, "captions", AsyncMock(return_value=(vtt, "en")))
    audio = AsyncMock(side_effect=AssertionError("Caption-first must not scan audio"))
    monkeypatch.setattr(remote_media, "audio_window", audio)
    monkeypatch.setattr("cliper.selection.select", AsyncMock(return_value=Analysis(title="test", language="en",
        duration=40, method="test", clips=[clip])))
    result = await analyze("https://youtu.be/test", cfg.data_dir, Preferences(), cfg, AsyncMock(), lambda: False)
    assert result.coverage["method"] == "caption_index" and not result.coverage["partial"]
    assert not audio.called
    source = json.loads((cfg.data_dir / "source.json").read_text())
    assert source["kind"] == "remote_index"


async def test_failed_audio_scan_cancels_sibling_download(cfg, monkeypatch):
    monkeypatch.setattr(remote_media, "metadata", AsyncMock(return_value={"duration": 72000, "title": "VOD"}))
    monkeypatch.setattr(remote_media, "captions", AsyncMock(return_value=None))
    started, stopped = asyncio.Event(), asyncio.Event()
    async def download(url, folder, *args):
        if str(folder).endswith("0001"):
            await started.wait()
            raise ValueError("download failure")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    monkeypatch.setattr(remote_media, "audio_window", download)
    with pytest.raises(ValueError, match="download failure"):
        await analyze("https://youtu.be/test", cfg.data_dir, Preferences(scan_minutes=6), cfg, AsyncMock(), lambda: False)
    assert stopped.is_set()


def test_crop_dead_zone_dropout_and_cut_behavior():
    assert smooth_center(.4, .41, 0) == .4
    assert smooth_center(.4, None, 2) == .4
    assert smooth_center(.4, .9, 0) == pytest.approx(.445)
    assert smooth_center(.4, .9, 0, cut=True) == .9


def test_batch_transcriber_reuses_loaded_model(tmp_path):
    from cliper.transcribe import transcribe_file
    model = SimpleNamespace(model=SimpleNamespace(device="cuda", compute_type="int8_float16"))
    calls = []
    def transcribe(path, **kwargs):
        calls.append(kwargs)
        word = SimpleNamespace(start=0, end=1, word="Hello.", probability=.9)
        segment = SimpleNamespace(no_speech_prob=.1, avg_logprob=-.1, words=[word], end=1)
        return iter([segment]), SimpleNamespace(language="en", duration=2)
    model.transcribe = transcribe
    args = SimpleNamespace(beam_size=1, language="auto", device_index=0, model="small")
    for i in range(2):
        transcribe_file(model, "fixture.wav", tmp_path / f"{i}.json", args)
    assert len(calls) == 2 and all(c["vad_filter"] and c["beam_size"] == 1 for c in calls)


@pytest.mark.parametrize("actual_seconds", [3, 8])
async def test_audio_range_transport_cache_and_duration_guard(cfg, monkeypatch, actual_seconds):
    download = AsyncMock()
    monkeypatch.setattr(remote_media, "execute", download)
    async def convert(args, **kwargs):
        with wave.open(args[-1], "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(bytes(actual_seconds * 32000))
    monkeypatch.setattr(remote_media, "run", AsyncMock(side_effect=convert))
    folder = cfg.data_dir / "audio-check"
    if actual_seconds != 3:
        with pytest.raises(ValueError, match="duration does not match"):
            await remote_media.audio_window("https://youtu.be/test", folder, 500, 503, cfg, lambda: False)
        assert not (folder / "audio-range.json").exists()
        return
    await remote_media.audio_window("https://youtu.be/test", folder, 500, 503, cfg, lambda: False)
    args = download.call_args.args[0]
    assert args[args.index("--download-sections") + 1] == "*500.000-503.000"
    assert "-vn" in args[args.index("--downloader-args") + 1]
    await remote_media.audio_window("https://youtu.be/test", folder, 500, 503, cfg, lambda: False)
    assert download.await_count == 1
    await remote_media.audio_window("https://youtu.be/test", folder, 800, 803, cfg, lambda: False)
    assert download.await_count == 2


async def test_empty_selection_batch_does_not_hide_later_moment(cfg, clip, monkeypatch):
    from cliper.selection import NoSuitableClips
    monkeypatch.setattr(remote_media, "metadata", AsyncMock(return_value={"duration": 4000, "title": "Long dialogue"}))
    track = cfg.data_dir / "large.vtt"
    track.write_text("WEBVTT\n\n" + "\n\n".join(
        f"{i * 30}.000 --> {i * 30 + 20}.000\n" + f"Example {i} with useful context. " * 40
        for i in range(110)), encoding="utf-8")
    monkeypatch.setattr(remote_media, "captions", AsyncMock(return_value=(track, "en")))
    selection = AsyncMock(side_effect=[NoSuitableClips("No complete moments"), Analysis(title="later",
        language="en", duration=4000, method="test", clips=[clip])])
    monkeypatch.setattr("cliper.selection.select", selection)
    result = await analyze("https://youtu.be/test", cfg.data_dir, Preferences(scan_minutes=120), cfg, AsyncMock(), lambda: False)
    assert selection.await_count == 2 and len(result.clips) == 1


def test_kick_and_twitch_saved_broadcast_extractors():
    from yt_dlp.extractor.kick import KickVODIE
    from yt_dlp.extractor.twitch import TwitchVodIE
    assert KickVODIE.suitable("https://kick.com/example/videos/8c0f8c80-8e70-43ee-bd64-742877892233")
    assert TwitchVodIE.suitable("https://www.twitch.tv/videos/1234567890")
