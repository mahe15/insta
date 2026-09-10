"""Local sampled visual diagnostics, distinct from full FFmpeg decoding."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def visual_report(path: Path, *, square=False):
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps if fps else 0
    if not duration:
        cap.release()
        raise ValueError("Cannot measure video duration for visual checks")
    step = max(.5, duration / 160)
    times = np.arange(0, max(.01, duration - .04), step)
    previous, samples = None, []
    freeze, longest_freeze, black, longest_black = 0., 0., 0., 0.
    best, best_score = .0, -1.
    try:
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t) * 1000)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"Output frame could not be decoded near {t:.1f}s")
            if square:
                h, w = frame.shape[:2]
                top = max(0, (h - w) // 2)
                frame = frame[top:top + min(w, h)]
            gray = cv2.cvtColor(cv2.resize(frame, (240, 240)), cv2.COLOR_BGR2GRAY)
            dark = float(np.mean(gray < 12)) > .985
            diff = float(np.mean(cv2.absdiff(gray, previous))) if previous is not None else None
            frozen = diff is not None and diff < .12
            freeze = freeze + step if frozen else 0.
            black = black + step if dark else 0.
            longest_freeze, longest_black = max(longest_freeze, freeze), max(longest_black, black)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if not dark and sharpness > best_score and t <= min(duration * .6, 20):
                best, best_score = float(t), sharpness
            samples.append({"time": round(float(t), 2), "black": dark, "difference": round(diff, 3) if diff is not None else None})
            previous = gray
    finally:
        cap.release()
    warnings = []
    if longest_black >= 1:
        warnings.append("black_frames_review")
    if longest_freeze >= 4:
        warnings.append("static_or_frozen_sequence_review")
    return {"method": "sampled content-area frames", "samples": len(samples), "sample_step": round(step, 3),
            "black_fraction": round(sum(s["black"] for s in samples) / max(1, len(samples)), 3),
            "longest_black_seconds": round(longest_black, 2), "longest_static_seconds": round(longest_freeze, 2),
            "suggested_cover_seconds": round(best, 2), "warnings": warnings,
            "note": "Black fades and still shots can be intentional; these are review signals, not automatic cuts."}


def save_cover(path: Path, output: Path, seconds: float):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        if not ok or not cv2.imwrite(str(output), frame):
            raise ValueError("Could not create the clip cover preview")
    finally:
        cap.release()
