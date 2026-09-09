"""Make a designed demo from a local speech WAV, using real Whisper and the normal pipeline.

Usage: python scripts/render_speech_demo.py path/to/speech.wav --model tiny
The first run needs internet to download the selected speech model.
"""
from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from cliper.cli import progress
from cliper.config import Config
from cliper.models import Preferences
from cliper.pipeline import Pipeline
from cliper.process import run


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model", default="tiny")
    args = parser.parse_args()
    cfg = replace(Config.load(), provider="heuristic", whisper_model=args.model)
    folder = cfg.data_dir / "speech-demo" / uuid.uuid4().hex[:8]
    folder.mkdir(parents=True)
    frame = np.full((1280, 720, 3), (24, 20, 15), dtype=np.uint8)
    mint, white, muted = (174, 244, 137), (241, 245, 246), (136, 147, 150)
    cv2.rectangle(frame, (44, 46), (58, 60), mint, -1)
    cv2.putText(frame, "CLIPER", (76, 64), cv2.FONT_HERSHEY_SIMPLEX, .8, white, 2, cv2.LINE_AA)
    cv2.putText(frame, "STUDIO DEMO / 01", (418, 60), cv2.FONT_HERSHEY_SIMPLEX, .45, muted, 1, cv2.LINE_AA)
    cv2.line(frame, (44, 95), (676, 95), (57, 54, 45), 1)
    cv2.putText(frame, "GOOD IDEAS NEED A", (48, 235), cv2.FONT_HERSHEY_SIMPLEX, .75, muted, 1, cv2.LINE_AA)
    cv2.putText(frame, "SMALLER", (44, 330), cv2.FONT_HERSHEY_SIMPLEX, 2.5, white, 5, cv2.LINE_AA)
    cv2.putText(frame, "FIRST STEP.", (44, 426), cv2.FONT_HERSHEY_SIMPLEX, 2.5, mint, 5, cv2.LINE_AA)
    for i in range(37):
        x = 64 + i * 16
        amplitude = int(18 + 90 * abs(np.sin(i * .51)) * np.sin((i + 1) / 38 * np.pi))
        cv2.line(frame, (x, 626 - amplitude), (x, 626 + amplitude), mint, 5, cv2.LINE_AA)
    cv2.putText(frame, "ONE USEFUL THING. SHARED TODAY.", (108, 814), cv2.FONT_HERSHEY_SIMPLEX,
                .7, muted, 1, cv2.LINE_AA)
    cv2.line(frame, (44, 1140), (676, 1140), (57, 54, 45), 1)
    cv2.putText(frame, "LOCAL SPEECH  /  REAL TIMESTAMPS", (48, 1182), cv2.FONT_HERSHEY_SIMPLEX,
                .55, muted, 1, cv2.LINE_AA)
    artwork = folder / "source-card.png"
    cv2.imwrite(str(artwork), frame)
    source = folder / "speech-source.mp4"
    await run([cfg.ffmpeg(), "-v", "error", "-y", "-loop", "1", "-i", str(artwork),
               "-i", str(args.audio.resolve()), "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
               "-c:a", "aac", "-pix_fmt", "yuv420p", "-shortest", str(source)], timeout=180)
    pipeline = Pipeline(cfg)
    prefs = Preferences(clips=1, min_seconds=15, max_seconds=30, width=1080, reframe="center")
    analysis = await pipeline.analyze(str(source), folder, prefs, progress)
    for clip in analysis.clips:
        output = await pipeline.render_one(folder, clip, prefs)
        print(output)
        await run([cfg.ffmpeg(), "-v", "error", "-y", "-ss", "2", "-i", str(output),
                   "-frames:v", "1", str(folder / "preview.png")], timeout=30)


if __name__ == "__main__":
    asyncio.run(main())
