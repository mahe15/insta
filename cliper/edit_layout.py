"""Shared geometry for video framing and ASS typography."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def layout(prefs, face=None, force_fit=False):
    face = face or {}
    w, h = prefs.width, prefs.width * 16 // 9
    fit = force_fit or prefs.reframe == "blur" or bool(prefs.preserve_wide_groups and (
        face.get("square_mode") == "fit" or face.get("height", 0) > face.get("width", 0)))
    if prefs.layout == "four_three_hook":
        cw = w
        ch = round(w * 3 / 4 / 2) * 2
        x, y = 0, (h - ch) // 2
        if fit:
            sw, sh = face.get("width", w), face.get("height", ch)
            ratio = min(w / max(1, sw), ch / max(1, sh))
            cw, ch = max(2, round(sw * ratio / 2) * 2), max(2, round(sh * ratio / 2) * 2)
            x, y = (w - cw) // 2, y + (round(w * 3 / 4 / 2) * 2 - ch) // 2
        return {"width": w, "height": h, "fit": fit,
                "video_x": x, "video_y": y, "video_width": cw, "video_height": ch,
                "hook_bottom": max(0, y - round(w * .025)),
                "caption_bottom": min(y + ch - round(w * .055), round(h * .82))}
    x, y, cw, ch = 0, (h - w) // 2, w, w
    if prefs.layout == "square_hook" and fit:
        sw, sh = face.get("width", w), face.get("height", w)
        ratio = min(w / max(1, sw), w / max(1, sh))
        cw, ch = max(2, round(sw * ratio / 2) * 2), max(2, round(sh * ratio / 2) * 2)
        x, y = (w - cw) // 2, y + (w - ch) // 2
    elif prefs.layout != "square_hook":
        x, y, cw, ch = 0, 0, w, h
    return {"width": w, "height": h, "fit": fit,
            "video_x": x, "video_y": y, "video_width": cw, "video_height": ch,
            "hook_bottom": max(0, y - round(w * .025)),
            "caption_bottom": min(y + ch - round(w * .055), round(h * .82))}


@lru_cache(maxsize=1)
def font_source():
    # Measure the same installed bold font that libass uses. No proprietary font is bundled.
    for path, name in [("C:/Windows/Fonts/arialbd.ttf", "Arial"),
                       ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVu Sans"),
                       ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Arial")]:
        if Path(path).is_file():
            return path, name
    return "DejaVuSans-Bold.ttf", "DejaVu Sans"


def fit_text(text, width, preferred, minimum, max_lines=2):
    """Pixel-based wrapping; preserve every word, shrink only when necessary."""
    from PIL import ImageFont
    words = text.split()
    for size in range(preferred, minimum - 1, -1):
        try:
            font = ImageFont.truetype(font_source()[0], size)
        except OSError:
            font = ImageFont.load_default(size=size)
        lines = []
        for word in words:
            if lines and font.getlength(lines[-1] + " " + word) <= width:
                lines[-1] += " " + word
            else:
                # Long romanized tokens/URLs also need safe line breaks.
                part = ""
                for char in word:
                    if part and font.getlength(part + char) > width:
                        lines.append(part)
                        part = ""
                    part += char
                if part:
                    lines.append(part)
        if len(lines) <= max_lines:
            return lines, size
    return lines, minimum
