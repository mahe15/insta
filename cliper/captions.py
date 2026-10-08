from __future__ import annotations

import re
from pathlib import Path

from .edit_layout import fit_text, font_source, layout
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


def chunks(transcript: Transcript, clip: Clip, max_words: int = 5) -> list[list[Word]]:
    groups, group = [], []
    words = []
    for segment in transcript.segments:
        for w in segment.words:
            if w.end <= clip.start or w.start >= clip.end or not w.text.strip():
                continue
            words.append(Word(start=round(max(0, w.start - clip.start), 2),
                              end=round(min(clip.end, w.end) - clip.start, 2), text=" ".join(w.text.split())))
    words.sort(key=lambda word: word.start)
    unique = []
    for word in words:
        if unique and word.start == unique[-1].start:
            if word.text != unique[-1].text:
                unique[-1].text += " " + word.text
            unique[-1].end = max(unique[-1].end, word.end)
        else:
            unique.append(word)
    words = unique
    for index, word in enumerate(words):
        # Resolve overlapping segments/equal timestamps before emitting ASS or SRT.
        if index + 1 < len(words):
            word.end = min(word.end, words[index + 1].start)
        if word.end <= word.start:
            continue
        if group and (len(group) >= max_words or sum(len(x.text) + 1 for x in group) + len(word.text) > 30
                      or word.start - group[-1].end > .5 or word.end - group[0].start > 2.5
                      or re.search(r"[.!?。！？][\"'’”]*$", group[-1].text)):
            groups.append(group)
            group = []
        group.append(word)
    if group:
        groups.append(group)
    return groups


def write_captions(directory: Path, transcript: Transcript, clip: Clip, prefs: Preferences, geometry=None):
    width, height = prefs.width, prefs.width * 16 // 9
    geometry = geometry or layout(prefs)
    font_name = font_source()[1]
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
Style: Default,{font_name},{font_size},&H00FFFFFF,{accent},&H00141210,&H80000000,-1,0,0,0,100,100,0,0,1,{max(1, round(width * .003))},1,2,{round(width * .08)},{round(width * .08)},{height - geometry['caption_bottom']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events, srt = [], []
    if prefs.overlay_text:
        # Branding stays separate from speech and is visible even when subtitles are off.
        lines, size = fit_text(safe_ass(prefs.overlay_text), width * .82, round(width * .034), round(width * .022), 2)
        y = min(round(height * .90), geometry['video_y'] + geometry['video_height'] + round(width * .05)) if prefs.layout == "square_hook" else round(height * .87)
        events.append(f"Dialogue: 2,0:00:00.00,{ass_time(clip.end - clip.start)},Default,,0,0,0,,"
                      + f"{{\\an8\\q2\\pos({width // 2},{y})\\fs{size}\\1c&H00FFFFFF&}}" + r"\N".join(lines))
    if prefs.layout == "square_hook":
        title_lines, title_size = fit_text(safe_ass(clip.title), width * .86, round(width * .056), round(width * .028), 3)
        title = r"\N".join(title_lines)
        events.append(f"Dialogue: 1,0:00:00.00,{ass_time(clip.end - clip.start)},Default,,0,0,0,,"
                      + f"{{\\an2\\q2\\pos({width // 2},{geometry['hook_bottom']})"
                      + f"\\fn{font_name}\\fs{title_size}\\b1\\1c&H00FFFFFF&\\bord0\\shad0}}{title}")
    for group in chunks(transcript, clip, 3 if prefs.editorial_profile == "ishowspeed" else 5) if prefs.captions else []:
        plain = " ".join(w.text for w in group)
        srt.append(f"{len(srt) + 1}\n{srt_time(group[0].start)} --> {srt_time(group[-1].end)}\n{plain}\n")
        safe = safe_ass(plain)
        lines, size = fit_text(safe, width * .82, font_size, round(width * .030), 2)
        prefix = f"{{\\q2\\fs{size}\\an2\\pos({width // 2},{geometry['caption_bottom']})}}"
        phrase = r"\N".join(lines)
        if prefs.style == "minimal" or any(len(w.text.split()) > 1 for w in group):
            events.append(f"Dialogue: 0,{ass_time(group[0].start)},{ass_time(group[-1].end)},"
                          f"Default,,0,0,0,,{prefix}{phrase}")
        else:
            for i, word in enumerate(group):
                # Keep the phrase stationary; highlight the spoken word using real timestamps.
                left = sum(len(safe_ass(w.text)) + 1 for w in group[:i])
                right = left + len(safe_ass(word.text))
                pieces, cursor = [], 0
                for line in lines:
                    offset = safe.find(line, cursor)
                    a, b = max(0, left - offset), min(len(line), right - offset)
                    pieces.append(line[:a] + f"{{\\1c{accent}}}" + line[a:b] + r"{\1c&H00FFFFFF&}" + line[b:] if a < b else line)
                    cursor = offset + len(line)
                events.append(f"Dialogue: 0,{ass_time(word.start)},{ass_time(word.end)},Default,,0,0,0,,"
                              + prefix + r"\N".join(pieces))
                if i + 1 < len(group) and word.end < group[i + 1].start:
                    events.append(f"Dialogue: 0,{ass_time(word.end)},{ass_time(group[i+1].start)},Default,,0,0,0,,{prefix}{phrase}")
    ass = directory / f"clip_{clip.id:02}.ass"
    ass.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    (directory / f"clip_{clip.id:02}.srt").write_text("\n".join(srt), encoding="utf-8")
    return ass
