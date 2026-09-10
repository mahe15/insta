from __future__ import annotations

import re
import textwrap
from pathlib import Path

from .models import Clip, Preferences, Transcript, Word


def ass_time(t: float) -> str:
    centis = max(0, round(t * 100))
    return f"{centis // 360000}:{centis // 6000 % 60:02}:{centis // 100 % 60:02}.{centis % 100:02}"


def srt_time(t: float) -> str:
    millis = max(0, round(t * 1000))
    return f"{millis // 3600000:02}:{millis // 60000 % 60:02}:{millis // 1000 % 60:02},{millis % 1000:03}"


def safe_ass(text: str) -> str:
    # Source text must never become ASS overrides or drawing commands.
    return re.sub(r"[\x00-\x1f]", " ", text).replace("\\", "／").replace("{", "(").replace("}", ")")


def chunks(transcript: Transcript, clip: Clip) -> list[list[Word]]:
    groups, group = [], []
    for segment in transcript.segments:
        for w in segment.words:
            if w.end <= clip.start or w.start >= clip.end:
                continue
            word = Word(start=max(0, w.start - clip.start), end=min(clip.end, w.end) - clip.start,
                        text=w.text)
            if group and (len(group) >= 5 or sum(len(x.text) + 1 for x in group) + len(w.text) > 30
                          or word.start - group[-1].end > .5 or word.end - group[0].start > 2.5
                          or re.search(r"[.!?。！？][\"'’”]*$", group[-1].text)):
                groups.append(group)
                group = []
            group.append(word)
        # Do not carry caption text across a sentence boundary.
        if group:
            groups.append(group)
            group = []
    return groups


def write_captions(directory: Path, transcript: Transcript, clip: Clip, prefs: Preferences):
    width, height = prefs.width, prefs.width * 16 // 9
    font_size = round(width * (.065 if prefs.style == "bold" else .057))
    accent = {"studio": "&H0064F5BD", "bold": "&H0000E8FF", "minimal": "&H00FFFFFF"}[prefs.style]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,{accent},&H00141210,&H80000000,-1,0,0,0,100,100,0,0,1,{max(1, round(width * .004))},1,2,{round(width * .1)},{round(width * .1)},{round(height * .23)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, srt = [], []
    if prefs.layout == "square_hook":
        top = (height - width) // 2
        columns = 30
        title_lines = textwrap.wrap(safe_ass(clip.title), width=columns)
        while len(title_lines) > 3 and columns < 60:
            columns += 1
            title_lines = textwrap.wrap(safe_ass(clip.title), width=columns)
        title = r"\N".join(title_lines)
        events.append(f"Dialogue: 1,0:00:00.00,{ass_time(clip.end - clip.start)},Default,,0,0,0,,"
                      + f"{{\\an2\\pos({width // 2},{top - round(width * .035)})"
                      + f"\\fnArial\\fs{round(width * .05 * 30 / columns)}\\b1\\1c&H00FFFFFF&\\bord0\\shad0}}{title}")
    for group in chunks(transcript, clip) if prefs.captions else []:
        plain = " ".join(w.text for w in group)
        srt.append(f"{len(srt) + 1}\n{srt_time(group[0].start)} --> {srt_time(group[-1].end)}\n{plain}\n")
        if prefs.style == "minimal":
            events.append(f"Dialogue: 0,{ass_time(group[0].start)},{ass_time(group[-1].end)},"
                          f"Default,,0,0,0,,{safe_ass(plain)}")
        else:
            for i, word in enumerate(group):
                # Keep the phrase stationary; highlight the spoken word using real timestamps.
                pieces = [f"{{\\1c{accent}}}{safe_ass(w.text)}{{\\1c&H00FFFFFF&}}" if j == i
                          else safe_ass(w.text) for j, w in enumerate(group)]
                # Retain the phrase through short gaps; only the active word changes.
                end = group[i + 1].start if i + 1 < len(group) else word.end
                events.append(f"Dialogue: 0,{ass_time(word.start)},{ass_time(end)},Default,,0,0,0,,"
                              + " ".join(pieces))
    ass = directory / f"clip_{clip.id:02}.ass"
    ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    (directory / f"clip_{clip.id:02}.srt").write_text("\n".join(srt), encoding="utf-8")
    return ass
