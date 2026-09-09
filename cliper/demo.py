"""A speech sample that exercises the same transcription and export path as real jobs."""
from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from .config import Config
from .media import video_encoder_args
from .models import Preferences
from .pipeline import Pipeline
from .process import run
from .storage import write_json

SPEECH = (
    "Why do most good ideas disappear before anyone sees them? "
    "The problem is waiting until every single detail feels perfect. "
    "Start with one small useful thing and show someone today. "
    "Their questions will tell you what to build next. "
    "Practice gets easier when you make the next step smaller."
)


async def synthesize_speech(directory: Path) -> Path:
    audio = directory / "speech.wav"
    text = directory / "speech.txt"
    text.write_text(SPEECH, encoding="utf-8")
    if os.name == "nt":
        args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(Path(__file__).with_name("demo_speech.ps1")),
                "-TextPath", str(text.resolve()), "-OutputPath", str(audio.resolve())]
    elif engine := (shutil.which("espeak-ng") or shutil.which("espeak")):
        args = [engine, "-s", "170", "-f", str(text), "-w", str(audio)]
    else:
        raise RuntimeError("No system speech engine. Supply a 15-30 second recording with demo --audio PATH.")
    try:
        await run(args, timeout=45)
    except (RuntimeError, TimeoutError) as exc:
        raise RuntimeError("System speech generation failed. Try demo --audio PATH with a speech recording.") from exc
    if not audio.is_file() or audio.stat().st_size <= 44:
        raise RuntimeError("Speech engine produced no audio. Supply a recording with demo --audio PATH.")
    return audio


def draw_card(path: Path, *, custom_audio: bool = False):
    frame = np.full((1280, 720, 3), (24, 20, 15), dtype=np.uint8)
    mint, white, muted = (174, 244, 137), (241, 245, 246), (136, 147, 150)
    cv2.rectangle(frame, (44, 46), (58, 60), mint, -1)
    cv2.putText(frame, "CLIPER", (76, 64), cv2.FONT_HERSHEY_SIMPLEX, .8, white, 2, cv2.LINE_AA)
    cv2.putText(frame, "STUDIO DEMO / 01", (418, 60), cv2.FONT_HERSHEY_SIMPLEX, .45, muted, 1, cv2.LINE_AA)
    cv2.line(frame, (44, 95), (676, 95), (57, 54, 45), 1)
    eyebrow, line1, line2 = (("YOUR RECORDING", "YOUR VOICE.", "IN FOCUS.") if custom_audio else
                               ("GOOD IDEAS NEED A", "SMALLER", "FIRST STEP."))
    cv2.putText(frame, eyebrow, (48, 235), cv2.FONT_HERSHEY_SIMPLEX, .75, muted, 1, cv2.LINE_AA)
    cv2.putText(frame, line1, (44, 330), cv2.FONT_HERSHEY_SIMPLEX, 2.5, white, 5, cv2.LINE_AA)
    cv2.putText(frame, line2, (44, 426), cv2.FONT_HERSHEY_SIMPLEX, 2.5, mint, 5, cv2.LINE_AA)
    for i in range(37):
        x = 64 + i * 16
        amplitude = int(18 + 90 * abs(np.sin(i * .51)) * np.sin((i + 1) / 38 * np.pi))
        cv2.line(frame, (x, 626 - amplitude), (x, 626 + amplitude), mint, 5, cv2.LINE_AA)
    cv2.putText(frame, "SPEECH TO CAPTIONED CLIP", (138, 814), cv2.FONT_HERSHEY_SIMPLEX,
                .7, muted, 1, cv2.LINE_AA)
    cv2.line(frame, (44, 1140), (676, 1140), (57, 54, 45), 1)
    cv2.putText(frame, "LOCAL SPEECH  /  REAL TIMESTAMPS", (48, 1182), cv2.FONT_HERSHEY_SIMPLEX,
                .55, muted, 1, cv2.LINE_AA)
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError("Could not write demo artwork")


async def speech_demo(cfg: Config, *, width: int = 1080, audio: Path | None = None, progress) -> Path:
    cfg = replace(cfg, provider="heuristic")
    if audio is not None:
        audio = audio.resolve()
        if not audio.is_file():
            raise ValueError("Demo speech recording does not exist")
    folder = cfg.data_dir / "demo" / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True)
    cfg.check_disk()
    custom_audio = audio is not None
    await progress("Creating a spoken studio sample with real transcription (no paid AI calls)")
    audio = audio or await synthesize_speech(folder)
    artwork = folder / "source-card.png"
    draw_card(artwork, custom_audio=custom_audio)
    source = folder / "speech-source.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-loop", "1", "-framerate", "30",
               "-i", str(artwork), "-i", str(audio), *video_encoder_args(cfg, 3500),
               "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest",
               "-t", str(cfg.max_source_minutes * 60), str(source)], timeout=180)
    prefs = Preferences(clips=1, min_seconds=15, max_seconds=30, width=width, reframe="center")
    pipeline = Pipeline(cfg)
    analysis = await pipeline.analyze(str(source), folder, prefs, progress)
    if not analysis.clips:
        raise ValueError("No complete 15-30 second spoken clip found in demo audio")
    for clip in analysis.clips:
        output = await pipeline.render_one(folder, clip, prefs)
        await progress(str(output))
        await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-ss", "2", "-i", str(output),
                   "-frames:v", "1", str(folder / "preview.png")], timeout=30)
    write_json(folder / "DEMO-NOTE.json", {
        "synthetic": not custom_audio, "visuals": "Designed studio title card",
        "audio": "User supplied recording" if custom_audio else "System-generated speech",
        "transcript": "Real Whisper transcription; see transcript.runtime.json for device",
        "ranking": "Offline heuristic, not a virality benchmark", "encoder": cfg.video_encoder,
        "purpose": "Spoken demo using the production transcription, caption and export pipeline",
    })
    await progress(f"Demo complete: {folder}")
    return folder
