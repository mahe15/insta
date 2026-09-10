"""Gemini supplies the finished design; FFmpeg sizes it and adds a swipe marker."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .process import run


def inspect_image(path: Path):
    if path.stat().st_size > 40 * 1024**2:
        raise ValueError("Generated image exceeds the image budget")
    frame = cv2.imread(str(path))
    if frame is None or min(frame.shape[:2]) < 256 or frame.std() < 4:
        raise ValueError("Generated image is missing, too small or blank")
    return {"width": frame.shape[1], "height": frame.shape[0]}


def swipe_asset(path: Path):
    if path.exists():
        return
    frame = np.zeros((70, 230, 4), dtype=np.uint8)
    cv2.rectangle(frame, (0, 0), (229, 69), (0, 0, 0, 175), -1)
    cv2.putText(frame, "SWIPE >", (18, 46), cv2.FONT_HERSHEY_SIMPLEX, .95,
                (255, 255, 255, 255), 2, cv2.LINE_AA)
    if not cv2.imwrite(str(path), frame):
        raise ValueError("Could not create swipe overlay")


async def render_slide(source: Path, output: Path, cfg, *, last=False, cancelled=lambda: False):
    inspect_image(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    overlay = output.parent / "swipe.png"
    swipe_asset(overlay)
    graph = "[0:v]scale=1080:1350:force_original_aspect_ratio=decrease,pad=1080:1350:(ow-iw)/2:(oh-ih)/2:black[base]"
    if not last:
        graph += ";[base][1:v]overlay=W-w-35:H-h-35:format=auto,scale=1080:1350[out]"
    else:
        graph += ";[base]scale=1080:1350[out]"
    await run([cfg.ffmpeg(), "-v", "error", "-nostdin", "-y", "-i", str(source),
               *([] if last else ["-i", str(overlay)]), "-filter_complex", graph,
               "-map", "[out]", "-frames:v", "1", "-q:v", "2", str(output)],
              timeout=90, cancelled=cancelled)
    info = inspect_image(output)
    if (info["width"], info["height"]) != (1080, 1350):
        img = cv2.imread(str(output))
        if img is not None:
            fixed = cv2.resize(img, (1080, 1350), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(output), fixed, [cv2.IMWRITE_JPEG_QUALITY, 95])
            info = inspect_image(output)
    if (info["width"], info["height"]) != (1080, 1350) or output.stat().st_size > 8_000_000:
        raise ValueError("Carousel image failed Instagram dimensions/size checks")
    return info
