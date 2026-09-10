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
    if frame is None or min(frame.shape[:2]) < 256:
        raise ValueError("Generated image is missing, too small or blank")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if gray.std() < 2:
        raise ValueError("Generated image is a flat/blank frame")
    return {"width": frame.shape[1], "height": frame.shape[0], "luma_std": round(float(gray.std()), 2),
            "upscale_needed": frame.shape[1] < 1080 or frame.shape[0] < 1350}


def compare_images(left: Path, right: Path):
    if not right.is_file():
        return {"near_duplicate": False, "comparison": "unavailable"}
    frames = [cv2.imread(str(p)) for p in (left, right)]
    if any(f is None for f in frames):
        raise ValueError("Image comparison could not decode an asset")
    a, b = [cv2.resize(f, (160, 200), interpolation=cv2.INTER_AREA).astype(np.float32) for f in frames]
    difference = float(np.mean(np.abs(a - b)))
    return {"near_duplicate": difference < 2.0, "mean_pixel_difference": round(difference, 3),
            "method": "normalized pixel comparison; not semantic similarity"}


def contact_sheet(paths: list[Path], output: Path):
    columns = min(4, len(paths))
    rows = (len(paths) + columns - 1) // columns
    sheet = np.full((rows * 370, columns * 280, 3), 240, np.uint8)
    for n, path in enumerate(paths):
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError("Could not read a slide for the contact sheet")
        x, y = n % columns * 280, n // columns * 370
        sheet[y:y + 338, x:x + 270] = cv2.resize(frame, (270, 338), interpolation=cv2.INTER_AREA)
        cv2.putText(sheet, f"Slide {n + 1}", (x + 5, y + 359), cv2.FONT_HERSHEY_SIMPLEX, .55, (20, 20, 20), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(output), sheet):
        raise ValueError("Could not save carousel contact sheet")


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
    if (info["width"], info["height"]) != (1080, 1350) or output.stat().st_size > 8_000_000:
        raise ValueError("Carousel image failed Instagram dimensions/size checks")
    return info
