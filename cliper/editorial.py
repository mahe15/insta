"""Evidence-aware editorial prompts and local, explainable attention checks."""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

from .models import Preferences

VERSION = "editorial-2026-09-v2"
CLIP_BRIEF = """
Edit for a stranger seeing this for the first time. The first spoken sentence should establish a
specific tension, useful promise, surprising observation or emotional event within roughly 1–3s.
Keep the context required to understand the payoff; the shortest COMPLETE story wins, not the
shortest arbitrary duration. No universal duration predicts reach. Consider a 15–30s single insight,
30–60s explanation or 45–90s story only when it fits the requested bounds and earns its length.
An ending must deliver the opening promise. Do not cut off qualifications or use a fabricated loop.
Distinguish earned suspense from dead air; do not select greetings, sponsor reads or vague teasers.
Write the display title as a readable 4–10 word hook, preferably <=65 characters, not a news summary.
Use concrete stakes, an honest contrast or a precise question answered by THIS clip. No ALL CAPS
paragraphs, unsupported numbers, fake certainty, 'you won't believe', 'watch till the end', or
manufactured outrage. Keep necessary names and use the source language. Provide three distinct
hook_variants (direct value, curiosity, contrast), each grounded in the supplied transcript.
audience_value must name a specific viewer and why they would send this to a friend or save it.
Do not guess algorithm weights or promise views. Ratings are editorial judgments only.
"""

STOP = set("a an the to of in on for and or is are be it this that your you with from at as by".split())


def tokens(text):
    return re.findall(r"\w+(?:['’]\w+)?", text.casefold())


def similarity(left, right):
    """Lexical near-duplicate signal, deliberately not claimed to be semantic embeddings."""
    a, b = tokens(left), tokens(right)
    if not a or not b:
        return 0.0
    sa, sb = set(a) - STOP, set(b) - STOP
    jaccard = len(sa & sb) / max(1, len(sa | sb))
    return max(jaccard, SequenceMatcher(None, " ".join(a), " ".join(b)).ratio())


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", re.sub(r"(?<=\d),(?=\d)", "", text)))


def hook_checks(title, source):
    flags = []
    if len(tokens(title)) > 12 or len(title) > 78:
        flags.append("title_too_dense")
    if re.search(r"you won.t believe|watch (?:till|until) the end|guaranteed|100% viral", title, re.I):
        flags.append("generic_or_unearned_promise")
    if numbers(title) - numbers(source):
        flags.append("title_numbers_not_in_source")
    if not title.strip():
        flags.append("empty_title")
    return flags


def choose_hook(title, variants, source):
    candidates = list(dict.fromkeys(" ".join(x.split()) for x in [title, *variants] if x.strip()))
    if not candidates:
        candidates = [" ".join(source.split()[:9])]
    ranked = sorted(candidates, key=lambda x: (
        "title_numbers_not_in_source" in hook_checks(x, source), len(hook_checks(x, source)),
        not 4 <= len(tokens(x)) <= 10, len(x) > 65))
    best = ranked[0]
    if "title_numbers_not_in_source" in hook_checks(best, source):
        best = " ".join(source.split()[:9])[:90]
    return best[:90], [x[:90] for x in ranked[:3]]


def boundaries(segments, start, end, prefs: Preferences):
    words = [w for s in segments for w in s.words if w.end > start and w.start < end]
    if prefs.trim_edges and words:
        left, right = max(start, words[0].start - .08), min(end, words[-1].end + .12)
        if prefs.min_seconds <= right - left <= prefs.max_seconds:
            return left, right
    return start, end


def attention_report(segments, start, end, title):
    text = " ".join(s.text for s in segments)
    words = sorted((w for s in segments for w in s.words if w.end > start and w.start < end), key=lambda w: w.start)
    length = max(.01, end - start)
    pauses = [{"start": round(a.end - start, 2), "duration": round(b.start - a.end, 2)}
              for a, b in zip(words, words[1:], strict=False) if b.start - a.end >= .8]
    lead = max(0, words[0].start - start) if words else 0
    tail = max(0, end - words[-1].end) if words else 0
    wpm = len(tokens(text)) * 60 / length
    flags = hook_checks(title, text)
    if lead > .8:
        flags.append("late_first_word")
    if tail > 1.2:
        flags.append("long_tail")
    if wpm > 240:
        flags.append("fast_speech_check_caption_readability")
    if pauses and max(p["duration"] for p in pauses) > 2.5:
        flags.append("long_pause_review")
    if re.match(r"\s*(and that|as i said|as we discussed|because of that)\b", text, re.I):
        flags.append("context_dependent_opening")
    sequence = tokens(text)
    grams = Counter(tuple(sequence[i:i + 6]) for i in range(max(0, len(sequence) - 5)))
    if grams and max(grams.values()) >= 3:
        flags.append("repeated_phrase_check_transcript")
    known = [w.confidence for w in words if w.confidence is not None]
    low_confidence = sum(p < .45 for p in known) / max(1, len(known))
    if len(known) >= 5 and low_confidence > .25:
        flags.append("low_transcription_confidence")
    if not re.search(r"[.!?。！？][\"'’”]*\s*$", text):
        flags.append("ending_needs_editorial_review")
    return {"version": VERSION, "words_per_minute": round(wpm, 1), "first_word_delay": round(lead, 2),
            "trailing_gap": round(tail, 2), "pauses": pauses, "flags": flags,
            "low_confidence_word_fraction": round(low_confidence, 3) if known else None,
            "automatic_ready": not any(f in flags for f in ("title_numbers_not_in_source", "empty_title",
                "repeated_phrase_check_transcript", "low_transcription_confidence")), "note": "Local heuristics; not a prediction of reach or retention."}
