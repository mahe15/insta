"""Conservative face-aware reframing. This is not active-speaker diarization."""
from __future__ import annotations

import argparse
from itertools import pairwise
from pathlib import Path

from .storage import write_json


def inspect(source: Path, start: float, end: float) -> dict:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(source))
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    samples, scenes, previous = [], [], None
    try:
        t = start
        while t < end:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            small = cv2.resize(frame, (480, max(1, round(height * 480 / width))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            faces = detector.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))
            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)
            if previous is not None and cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA) > .55:
                scenes.append(round(t - start, 2))
            previous = hist
            center, fits = .5, False
            if len(faces) == 1:
                x, y, w, h = faces[0]
                center = float((x + w / 2) / small.shape[1])
                crop_width = small.shape[0] * 9 / 16
                left = max(0, min(small.shape[1] - crop_width, center * small.shape[1] - crop_width / 2))
                # Include a margin around the whole face, including when near a frame edge.
                fits = bool(x >= left + 5 and x + w <= left + crop_width - 5)
            samples.append({"time": round(t - start, 2), "faces": len(faces), "center": center, "fits": fits})
            t += 1.0
    finally:
        cap.release()
    coverage = sum(x["fits"] for x in samples) / max(1, len(samples))
    # Multiple faces/slides/no reliable detection => preserve the complete frame with blur.
    safe = bool(samples) and coverage >= .8 and all(s["faces"] <= 1 for s in samples)
    centers = []
    for index in range(0, len(samples), 3):
        group = samples[index:index + 3]
        good = [x["center"] for x in group if x["fits"]]
        center = float(np.median(good)) if good else (centers[-1][1] if centers else .5)
        if centers:
            center = .65 * center + .35 * centers[-1][1]
        centers.append([group[0]["time"], round(center, 4)])
    return {"safe_crop": safe, "face_coverage": round(coverage, 3), "centers": centers,
            "scene_changes": scenes, "sample_count": len(samples), "width": width, "height": height}


def center_expression(points: list[list[float]]) -> str:
    if not points:
        return "0.5"
    expression = f"{points[-1][1]:.4f}"
    for (t0, x0), (t1, x1) in reversed(list(pairwise(points))):
        interpolation = f"({x0:.4f}+({x1 - x0:.4f})*max(0,t-{t0:.2f})/{max(.01, t1 - t0):.2f})"
        expression = f"if(lt(t,{t1:.2f}),{interpolation},{expression})"
    return expression


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("end", type=float)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    write_json(args.output, inspect(args.source, args.start, args.end))


if __name__ == "__main__":
    main()
