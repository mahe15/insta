from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cliper import cli, demo


async def test_default_demo_routes_to_speech(cfg, monkeypatch):
    speech = AsyncMock(return_value=cfg.data_dir)
    diagnostic = AsyncMock()
    monkeypatch.setattr(demo, "speech_demo", speech)
    monkeypatch.setattr(cli, "diagnostic_demo", diagnostic)
    assert await cli.demo(cfg) == cfg.data_dir
    assert speech.call_args.kwargs["width"] == 1080
    diagnostic.assert_not_awaited()
    await cli.demo(cfg, 360, diagnostic=True)
    diagnostic.assert_awaited_once_with(cfg, 360)
    with pytest.raises(ValueError, match="cannot be combined"):
        await cli.demo(cfg, diagnostic=True, audio=cfg.data_dir / "speech.wav")


async def test_speech_demo_requires_real_transcription_and_keeps_gpu(cfg, clip, monkeypatch):
    cfg = replace(cfg, video_encoder="h264_nvenc", whisper_device="cuda", whisper_compute="int8_float16")
    audio = cfg.data_dir / "recording.wav"
    audio.write_bytes(b"audio supplied by caller")
    commands = []

    async def fake_run(args, **kwargs):
        commands.append(args)

    class Pipeline:
        def __init__(self, configuration):
            assert configuration.whisper_device == "cuda"
            assert configuration.provider == "heuristic"

        async def analyze(self, source, folder, prefs, progress):
            # No fixture transcript may bypass real transcription in Pipeline.analyze.
            assert not (folder / "transcript.json").exists()
            assert prefs.width == 1080
            return SimpleNamespace(clips=[clip])

        async def render_one(self, folder, clip, prefs):
            return folder / "clip.mp4"

    monkeypatch.setattr(demo, "Pipeline", Pipeline)
    monkeypatch.setattr(demo, "run", fake_run)
    synth = AsyncMock()
    monkeypatch.setattr(demo, "synthesize_speech", synth)
    folder = await demo.speech_demo(cfg, audio=audio, progress=AsyncMock())
    synth.assert_not_awaited()
    assert "h264_nvenc" in commands[0]
    assert not any("testsrc" in arg or "sine=" in arg for command in commands for arg in command)
    assert (folder / "preview.png").name in commands[-1][-1]
    assert (folder / "DEMO-NOTE.json").is_file()


async def test_empty_synthesis_fails_instead_of_substituting_tone(cfg, monkeypatch):
    monkeypatch.setattr(demo, "run", AsyncMock())
    monkeypatch.setattr(demo.shutil, "which", lambda _: "espeak")
    with pytest.raises(RuntimeError, match="produced no audio"):
        await demo.synthesize_speech(cfg.data_dir)
