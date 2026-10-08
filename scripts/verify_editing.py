"""Render existing local footage with the configured encoder; never publishes."""
import asyncio
import json
from pathlib import Path

from cliper.config import Config
from cliper.media import render
from cliper.models import Clip, Preferences, Transcript
from cliper.quality import save_cover


async def main():
    cfg = Config.load()
    root = Path(__file__).resolve().parents[1]
    job = root / "data/jobs/a5d9b0ec86ff"
    metadata = json.loads((job / "clips/clip_01.json").read_text("utf-8"))
    clip = Clip.model_validate(metadata["clip"])
    verified = job / "ranges/clip_01/caption-verification/transcript.json"
    if not verified.is_file():
        raise ValueError("The local caption-verified sample is unavailable")
    transcript = Transcript.model_validate_json(verified.read_text("utf-8"))
    clip = clip.model_copy(update={"start": 0, "end": min(10, transcript.duration)})
    folder = root / "data/verification/editing-1080p60"
    for name, frame in [("square", "center"), ("preserved-frame", "blur")]:
        prefs = Preferences(width=1080, fps=60, reframe=frame, music=False)
        output = await render(job / "ranges/clip_01/range.mp4", folder / name, transcript, clip, prefs, cfg, lambda: False)
        save_cover(output, output.with_suffix(".preview.jpg"), 2)
        print(json.dumps({"sample": name, "output": str(output), "encoder": cfg.video_encoder,
                          "quality": json.loads(output.with_suffix(".json").read_text("utf-8"))["quality"]}), flush=True)


asyncio.run(main())
