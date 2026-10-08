"""Project-scoped editorial guidance and deterministic publishing text."""
from __future__ import annotations

import re


def instructions(prefs):
    if not prefs.project_rules:
        return ""
    return ("\nPROJECT EDITORIAL RULES (apply to every candidate, hook and post description):\n"
            + prefs.project_rules
            + "\nFollow these creative preferences within the configured duration and output schema. "
            "Keep transcript, dialogue and timestamps faithful to the source. Never turn branding "
            "or a requested slogan into spoken dialogue. Exact description text and overlay text "
            "are added separately by the application; do not invent them.\n")


def description(caption, hashtags, prefs):
    """Reserve hashtag slots for required tags; append exact prose once, before limits."""
    suffix = prefs.description_suffix
    if not suffix:
        return caption, hashtags
    required = re.findall(r"#(\w+)", suffix)
    inline = re.findall(r"#(\w+)", caption)
    tags, seen = [], set()
    for tag in required + inline + hashtags:
        clean = re.sub(r"\W", "", tag)
        if clean and clean.casefold() not in seen:
            tags.append(clean)
            seen.add(clean.casefold())
    text = re.sub(r"#\w+", "", caption).strip()
    footer = re.sub(r"#\w+", "", suffix).strip()
    if footer:
        if text == footer:
            text = ""
        elif text.endswith("\n\n" + footer):
            text = text[:-len(footer)].rstrip()
        text = (text[:max(0, 1800 - len(footer) - 2)].rstrip() + "\n\n" + footer).strip()
    return text, tags[:5]


def apply(clip, prefs):
    result = clip.model_copy(deep=True)
    result.caption, result.hashtags = description(result.caption or result.title, result.hashtags, prefs)
    return result
