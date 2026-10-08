"""Conservative face-aware reframing. This is not active-speaker diarization."""
from __future__ import annotations

import argparse
from itertools import pairwise
from pathlib import Path

from .storage import write_json


def smooth_center(previous, observed, missing, cut=False):
    if cut:
        return observed if observed is not None else .5
    target = previous if observed is None and missing <= 4 else (.5 if observed is None else observed)
    delta = target - previous
    return previous if abs(delta) < .025 else previous + max(-.045, min(.045, delta * .4))


def inspect(source: Path, start: float, end: float, model: Path | None = None) -> dict:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(source))
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    neural, detector_name = None, "haar_fallback"
    detector_warning = "YuNet model missing; run python -m cliper.face_model"
    if model and model.is_file():
        try:
            neural = cv2.FaceDetectorYN.create(str(model), "", (640, 360), score_threshold=.85, nms_threshold=.3)
            detector_name, detector_warning = "yunet_2023mar", None
        except cv2.error:
            detector_warning = "YuNet model could not be loaded; Haar fallback used. Reinstall the face model."
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    samples, scenes, previous = [], [], None
    square_centers, wide_groups = [], 0
    if width <= 0 or height <= 0 or end <= start:
        cap.release()
        raise ValueError("Face analysis requires a readable video and valid interval")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step_frames = max(1, round(fps * .5))
    missing, last_center = 0, .5
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    try:
        t = start
        while t < end:
            ok, frame = cap.read()
            if not ok:
                break
            scale_width = min(640, width)
            small = cv2.resize(frame, (scale_width, max(1, round(height * scale_width / width))))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if neural is not None:
                neural.setInputSize((small.shape[1], small.shape[0]))
                _, found = neural.detect(small)
                faces = [row[:4] for row in found] if found is not None else []
            else:
                faces = detector.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))
            faces = [face for face in faces if face[2] * face[3] >= small.shape[0] * small.shape[1] * .0015]
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
            square_center = None
            if len(faces):
                left_face = min(x for x, y, w, h in faces)
                right_face = max(x + w for x, y, w, h in faces)
                square_center = float((left_face + right_face) / (2 * small.shape[1]))
                if right_face - left_face + 30 > small.shape[0]:
                    wide_groups += 1
            # Reset at scene cuts rather than panning between unrelated shots.
            missing = missing + 1 if not len(faces) else 0
            cut = round(t - start, 2) in scenes
            square_center = smooth_center(last_center, square_center, missing, cut)
            if cut and square_centers:
                square_centers.append([round(t - start - .01, 3), last_center])
            square_centers.append([round(t - start, 2), round(square_center, 4)])
            last_center = square_center
            for _ in range(step_frames - 1):
                if not cap.grab():
                    break
            t += step_frames / fps
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
            "detector": detector_name, "sample_step": step_frames / fps, "tracking": "dead-zone, dropout hold, velocity limit, scene reset",
            "detector_warning": detector_warning,
            "square_centers": square_centers, "square_mode": "fit" if wide_groups else "track",
            "wide_face_group_samples": wide_groups,
            "scene_changes": scenes, "sample_count": len(samples), "width": width, "height": height}


def center_expression(points: list[list[float]]) -> str:
    if not points:
        return "0.5"
    spans = list(pairwise(points))
    def branch(left, right):
        if right - left == 1:
            (t0, x0), (t1, x1) = spans[left]
            return f"({x0:.4f}+({x1 - x0:.4f})*max(0,t-{t0:.2f})/{max(.01, t1 - t0):.2f})"
        middle = (left + right) // 2
        return f"if(lt(t,{spans[middle][0][0]:.2f}),{branch(left, middle)},{branch(middle, right)})"
    # Balanced decisions keep FFmpeg expression parser depth logarithmic. A linear
    # chain fails on ordinary 45–60 second face tracks in newer FFmpeg builds.
    last = f"{points[-1][1]:.4f}"
    return f"if(lt(t,{points[-1][0]:.2f}),{branch(0, len(spans))},{last})" if spans else last


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("end", type=float)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", type=Path)
    args = parser.parse_args()
    write_json(args.output, inspect(args.source, args.start, args.end, args.model))


if __name__ == "__main__":
    main()
