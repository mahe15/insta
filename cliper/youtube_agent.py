"""YouTube Agent Skill Suite for CLIPER.

End-to-end implementation of the eleven YouTube agent capabilities and six execution engines:
1. Hook Scoring & 21-Formula Classifier (hookscore.py + hooks.json)
2. Title & Thumbnail Synergy Linter (title.py)
3. Dead Air, Filler & Retake Edit Decision List (deadair.py)
4. YouTube-Compliant Chapter Generator & Validator (chapters.py)
5. Audience Retention Export Diagnostic & Spoken Cliff Mapper (retention.py)
6. Viral Swipe Outlier Ranker (swipe.py)
7. Creator Voice Profile Management (voice.md)
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger("cliper.youtube_agent")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = HERE / "assets"
CONFIG = ROOT / "config"

# --- Constants & Dictionaries ---

FILLER = {
    "basically", "actually", "literally", "just", "really", "very", "so", "kind", "sort", "like",
    "guys", "hey", "welcome", "today", "video", "subscribe", "channel"
}
VAGUE = {
    "amazing", "incredible", "insane", "crazy", "huge", "massive", "game", "changer", "secret",
    "powerful", "ultimate", "best", "revolutionary", "mind", "blowing", "unbelievable",
    "mindblowing", "epic", "perfect", "complete", "everything"
}
CONCRETE = re.compile(
    r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b",
    re.I
)
YOU = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE = re.compile(
    r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b",
    re.I
)
CURIOSITY = re.compile(
    r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b",
    re.I
)
STOP_WORDS = {
    "the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are", "was", "were", "be",
    "been", "with", "this", "that", "it", "as", "at", "by", "from", "you", "your", "i", "my", "we",
    "our", "they", "them", "he", "she", "but", "so", "if", "then", "than", "there", "here", "what",
    "which", "who", "how", "when", "where", "why", "not", "no", "yes", "do", "does", "did", "just",
    "really", "very", "like", "about", "into", "over", "out", "up", "down", "can", "could", "will",
    "would", "should", "have", "has", "had", "get", "got", "make", "made", "go", "going", "went",
    "one", "two"
}
FILLER_ONLY = re.compile(
    r"^[\s,.-]*((um+|uh+|er+|ah+|so|okay|ok|right|yeah|like|anyway|basically|"
    r"actually|you know|i mean|let me see|hold on)[\s,.-]*)+$",
    re.I
)

FIX_SUGGESTIONS = {
    "SPECIFICITY": "swap one adjective for a number, a name or a date",
    "ADDRESS": "say 'you' in the first six words",
    "STAKES": "name what it costs them to keep doing it the current way",
    "CURIOSITY": "open a question or create an honest tension",
    "BREVITY": "land between 9 and 24 words (~10s spoken)",
}


# --- Load 21 Hook Formulas ---

def _load_hook_formulas() -> list[dict[str, Any]]:
    candidates = [
        ASSETS / "hooks.json",
        CONFIG / "hooks.json",
        ROOT / ".agents" / "skills" / "yt-script" / "hooks.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data.get("hooks", [])
            except Exception as e:
                log.warning("Could not read hook formulas from %s: %s", p, e)
    return []


HOOK_FORMULAS = _load_hook_formulas()


def load_formulas() -> list[dict[str, Any]]:
    return list(HOOK_FORMULAS)


# --- Helper Functions ---

def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9'%$.]+", text.lower())


def norm_words(text: str) -> list[str]:
    return re.sub(r"[^a-z ]", "", text.lower()).split()


def parse_timestamp(s: str) -> float:
    s = s.strip().replace(",", ".")
    p = s.split(":")
    if len(p) == 3:
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
    elif len(p) == 2:
        return int(p[0]) * 60 + float(p[1])
    return float(s)


def format_mmss(seconds: float) -> str:
    t = int(seconds)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# --- 1. Hook Scorer & 21-Formula Classifier ---

def calculate_specificity(text: str) -> int:
    w = words(text)
    if not w:
        return 0
    nums = len(CONCRETE.findall(text))
    vague_cnt = sum(1 for x in w if x in VAGUE)
    filler_cnt = sum(1 for x in w if x in FILLER)
    score = 34 + nums * 22 - vague_cnt * 16 - filler_cnt * 5
    score += min(18, 6 * sum(1 for x in text.split()[1:] if x[:1].isupper()))
    return max(0, min(100, score))


def calculate_address(text: str) -> int:
    n = len(YOU.findall(text))
    first = 30 if YOU.search(" ".join(text.split()[:6])) else 0
    return max(0, min(100, 26 + n * 20 + first))


def calculate_stakes(text: str) -> int:
    n = len(STAKE.findall(text))
    concrete_bonus = 14 if CONCRETE.search(text) else 0
    return max(0, min(100, 22 + n * 26 + concrete_bonus))


def calculate_curiosity(text: str) -> int:
    n = len(CURIOSITY.findall(text))
    q = 18 if text.strip().endswith("?") else 0
    closed = -18 if re.search(r"\b(because|so that|which means)\b", text, re.I) else 0
    return max(0, min(100, 24 + n * 17 + q + closed))


def calculate_brevity(text: str) -> int:
    n = len(words(text))
    if n == 0:
        return 0
    if 9 <= n <= 24:
        return 100
    if n < 9:
        return max(30, 100 - (9 - n) * 11)
    return max(10, 100 - (n - 24) * 7)


def classify_hook_formula(text: str) -> tuple[str, int, dict[str, Any] | None]:
    best, hits = None, 0
    for f in HOOK_FORMULAS:
        n = sum(1 for p in f.get("match", []) if re.search(p, text, re.I))
        if n > hits:
            best, hits = f, n
    name = best["name"] if best else "Unclassified"
    return name, hits, best


def score_hook(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        return {
            "hook": "",
            "properties": {
                "SPECIFICITY": 0,
                "ADDRESS": 0,
                "STAKES": 0,
                "CURIOSITY": 0,
                "BREVITY": 0,
            },
            "verdict": 0,
            "band": "WEAK",
            "formula": "Unclassified",
            "formula_hits": 0,
            "formula_info": None,
            "weakest": "SPECIFICITY",
            "fix": FIX_SUGGESTIONS["SPECIFICITY"],
            "word_count": 0,
        }

    props = {
        "SPECIFICITY": calculate_specificity(text),
        "ADDRESS": calculate_address(text),
        "STAKES": calculate_stakes(text),
        "CURIOSITY": calculate_curiosity(text),
        "BREVITY": calculate_brevity(text),
    }
    vals = list(props.values())
    verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))
    band = "STRONG" if verdict >= 72 else "WORKABLE" if verdict >= 55 else "WEAK"
    formula_name, hits, formula_info = classify_hook_formula(text)
    weakest = min(props, key=lambda k: props[k])

    return {
        "hook": text,
        "properties": props,
        "verdict": verdict,
        "band": band,
        "formula": formula_name,
        "formula_hits": hits,
        "formula_info": {
            "id": formula_info.get("id"),
            "name": formula_info.get("name"),
            "shape": formula_info.get("shape"),
            "example": formula_info.get("example"),
            "fails_when": formula_info.get("fails_when"),
        } if formula_info else None,
        "weakest": weakest,
        "fix": FIX_SUGGESTIONS.get(weakest, ""),
        "word_count": len(words(text)),
    }


def score_hooks(texts: list[str]) -> list[dict[str, Any]]:
    scored = [score_hook(t) for t in texts if t.strip()]
    scored.sort(key=lambda s: -s["verdict"])
    return scored


# --- 2. Title & Thumbnail Synergy Linter ---

DESKTOP_CUT = 60
MOBILE_CUT = 40
HARD_LIMIT = 100


def lint_title_and_thumb(title: str, thumb: str | None = None) -> dict[str, Any]:
    t = (title or "").strip()
    n = len(t)
    issues: list[dict[str, str]] = []
    good: list[str] = []

    if n > HARD_LIMIT:
        issues.append({"kind": "length", "message": f"{n} characters - YouTube hard limit is {HARD_LIMIT}"})
    elif n > DESKTOP_CUT:
        issues.append({"kind": "length", "message": f"{n} characters - desktop search cuts near {DESKTOP_CUT}"})
    else:
        good.append(f"{n} characters, inside the {DESKTOP_CUT}-character desktop cut")

    if n > MOBILE_CUT:
        head = t[:MOBILE_CUT].rsplit(" ", 1)[0]
        issues.append({"kind": "mobile", "message": f'mobile feed shows about "{head}..." - check subject survives'})
    else:
        good.append("fits completely within mobile feed view (under 40 chars)")

    caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(caps) > 2:
        issues.append({"kind": "shouting", "message": f"{len(caps)} all-caps words - 2 is the ceiling before it reads as spam"})
    elif caps:
        good.append(f"{len(caps)} all-caps word for emphasis")

    vague_matches = [w for w in words(t) if w in VAGUE]
    if vague_matches:
        v_list = ", ".join(sorted(set(vague_matches)))
        issues.append({"kind": "vague", "message": f"vague word(s): {v_list} - swap for a number, name or date"})

    nums = re.findall(r"\d[\d,.]*%?", t)
    if nums:
        good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
    else:
        issues.append({"kind": "no-number", "message": "no number, date or name - the most reliable single fix"})

    if t.endswith("?"):
        good.append("open question in the title")

    front = [w for w in words(t)[:3] if w not in STOP_WORDS]
    if not front and len(words(t)) >= 3:
        issues.append({"kind": "front-load", "message": "first three words are filler - move the subject forward"})

    if thumb and thumb.strip():
        th = thumb.strip()
        tw = set(words(t)) - STOP_WORDS
        hw = set(words(th)) - STOP_WORDS
        shared = tw & hw
        if shared:
            s_list = ", ".join(sorted(shared))
            issues.append({
                "kind": "duplicate",
                "message": f"thumbnail repeats the title on: {s_list} - thumbnail should say what the title does not"
            })
        else:
            good.append("thumbnail and title carry distinct words")

        if len(words(th)) > 4:
            issues.append({
                "kind": "thumb-length",
                "message": f"{len(words(th))} words on thumbnail - 3-4 is the maximum at feed size"
            })
        else:
            good.append(f"{len(words(th))} words on thumbnail, readable at small feed size")

    score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))
    mobile_preview = t[:MOBILE_CUT].rsplit(" ", 1)[0] + ("..." if n > MOBILE_CUT else "")
    desktop_preview = t[:DESKTOP_CUT].rsplit(" ", 1)[0] + ("..." if n > DESKTOP_CUT else "")

    return {
        "title": t,
        "thumb": thumb.strip() if thumb else None,
        "chars": n,
        "score": score,
        "status": "PASS" if score >= 75 else "WARN" if score >= 50 else "FAIL",
        "desktop_preview": desktop_preview,
        "mobile_preview": mobile_preview,
        "issues": issues,
        "good": good,
    }


def lint_titles(titles: list[str], thumb: str | None = None) -> list[dict[str, Any]]:
    results = [lint_title_and_thumb(t, thumb) for t in titles if t.strip()]
    results.sort(key=lambda r: -r["score"])
    return results


# --- 3. Dead Air, Filler & Retake EDL (Edit Decision List) ---

def parse_cues_from_text(raw: str) -> list[tuple[float, float, str]]:
    raw = raw.strip()
    if not raw:
        return []
    # Try parsing as JSON first
    if raw.startswith("{") or raw.startswith("["):
        try:
            d = json.loads(raw)
            segs = d.get("segments", d if isinstance(d, list) else [])
            return [
                (float(s["start"]), float(s["end"]), (s.get("text") or "").strip())
                for s in segs
                if "start" in s and "end" in s
            ]
        except Exception:
            pass

    # Parse SRT or VTT lines
    cues: list[list[Any]] = []
    cur: list[Any] | None = None
    for line in raw.splitlines():
        m = re.match(r"\s*(\d[\d:.,]+)\s*-->\s*(\d[\d:.,]+)", line)
        if m:
            cur = [parse_timestamp(m.group(1)), parse_timestamp(m.group(2)), []]
            cues.append(cur)
        elif cur is not None and line.strip() and not line.strip().isdigit():
            cur[2].append(line.strip())
    return [(a, b, " ".join(t)) for a, b, t in cues if t]


def detect_deadair(
    source_cues: list[tuple[float, float, str]] | str | Path,
    floor: float = 0.45
) -> dict[str, Any]:
    """Find DEAD air gaps, FILLER cues, and REPEAT restarts to create an Edit Decision List."""
    if isinstance(source_cues, (str, Path)):
        p = Path(source_cues)
        if p.exists() and p.is_file():
            cues = parse_cues_from_text(p.read_text(encoding="utf-8", errors="replace"))
        else:
            cues = parse_cues_from_text(str(source_cues))
    else:
        cues = [(float(s), float(e), str(t)) for s, e, t in source_cues]

    if not cues:
        return {
            "duration": 0.0,
            "cuts": [],
            "removed_seconds": 0.0,
            "out_seconds": 0.0,
            "percent_saved": 0.0,
            "cues_count": 0,
        }

    dur = cues[-1][1]
    cuts: list[dict[str, Any]] = []

    for i, (s, e, t) in enumerate(cues):
        # 1. Pure filler cues
        if FILLER_ONLY.match(t):
            cuts.append({
                "kind": "FILLER",
                "start": round(s, 3),
                "end": round(e, 3),
                "duration": round(e - s, 3),
                "why": t.strip()[:48],
            })

        # 2. Dead air gaps
        if i > 0:
            gap = s - cues[i - 1][1]
            if gap > floor:
                keep = floor / 2
                cuts.append({
                    "kind": "DEAD",
                    "start": round(cues[i - 1][1] + keep, 3),
                    "end": round(s - keep, 3),
                    "duration": round((s - keep) - (cues[i - 1][1] + keep), 3),
                    "why": f"{gap:.2f}s pause between speech",
                })

        # 3. Retakes and restarts
        if t.strip() and not FILLER_ONLY.match(t):
            j = i - 1
            while j >= 0 and (FILLER_ONLY.match(cues[j][2]) or not cues[j][2].strip()):
                j -= 1
            if j >= 0:
                a1 = norm_words(cues[j][2])[:5]
                b1 = norm_words(t)[:5]
                if len(a1) >= 3 and a1 == b1:
                    cuts.append({
                        "kind": "REPEAT",
                        "start": round(cues[j][0], 3),
                        "end": round(cues[j][1], 3),
                        "duration": round(cues[j][1] - cues[j][0], 3),
                        "why": f'restart of "{" ".join(a1)}"',
                    })

    cuts = [c for c in cuts if c["end"] > c["start"]]
    cuts.sort(key=lambda c: c["start"])
    removed = sum(c["duration"] for c in cuts)

    return {
        "duration": round(dur, 2),
        "cuts": cuts,
        "removed_seconds": round(removed, 3),
        "out_seconds": round(max(0.0, dur - removed), 3),
        "percent_saved": round((removed / dur * 100) if dur > 0 else 0.0, 1),
        "cues_count": len(cues),
    }


# --- 4. YouTube-Compliant Chapter Generator & Validator ---

def extract_keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']{4,}", text.lower()) if w not in STOP_WORDS}


def generate_youtube_chapters(
    source_cues: list[tuple[float, float, str]] | str | Path,
    target: int = 7
) -> dict[str, Any]:
    """Generate YouTube chapters scored by pauses and vocabulary shifts, checking compliance."""
    if isinstance(source_cues, (str, Path)):
        p = Path(source_cues)
        if p.exists() and p.is_file():
            cues = parse_cues_from_text(p.read_text(encoding="utf-8", errors="replace"))
        else:
            cues = parse_cues_from_text(str(source_cues))
    else:
        cues = [(float(s), float(e), str(t)) for s, e, t in source_cues]

    if len(cues) < 4:
        return {
            "valid": False,
            "error": "Too few speech cues to generate meaningful chapters.",
            "chapters": [],
            "formatted_text": "",
        }

    dur = cues[-1][1]
    candidates = []
    for i in range(1, len(cues)):
        gap = cues[i][0] - cues[i - 1][1]
        before = " ".join(c[2] for c in cues[max(0, i - 12):i])
        after = " ".join(c[2] for c in cues[i:i + 12])
        kb, ka = extract_keywords(before), extract_keywords(after)
        shift = 1.0 - (len(kb & ka) / len(kb | ka)) if (kb | ka) else 0.0
        candidates.append((gap * 1.6 + shift * 3.2, cues[i][0], i))

    candidates.sort(reverse=True)
    picked = [0.0]
    MIN_LEN = 10.0

    for _, t, _ in candidates:
        if len(picked) >= target:
            break
        if all(abs(t - p) >= MIN_LEN for p in picked) and dur - t >= MIN_LEN:
            picked.append(t)
    picked.sort()

    chapters = []
    for n, t in enumerate(picked):
        end = picked[n + 1] if n + 1 < len(picked) else dur
        text = " ".join(c[2] for c in cues if c[0] >= t and c[1] <= end)
        kw = list(extract_keywords(text))
        kw.sort(key=lambda w: -text.lower().count(w))
        title = " ".join(w.capitalize() for w in kw[:3]) or "Section"
        if n == 0 and not kw:
            title = "Introduction"
        chapters.append({
            "start": round(t, 2),
            "end": round(end, 2),
            "label": format_mmss(t),
            "draft_title": title,
            "duration": round(end - t, 2),
        })

    is_valid = (
        len(chapters) >= 3
        and chapters[0]["start"] == 0
        and all(c["duration"] >= MIN_LEN for c in chapters)
    )

    formatted_lines = [f"{c['label']} {c['draft_title']}" for c in chapters]
    formatted_text = "\n".join(formatted_lines)

    return {
        "valid": is_valid,
        "rules": {
            "first_is_00_00": bool(chapters and chapters[0]["start"] == 0),
            "at_least_3_chapters": len(chapters) >= 3,
            "all_min_10_seconds": all(c["duration"] >= MIN_LEN for c in chapters),
        },
        "chapters": chapters,
        "formatted_text": formatted_text,
    }


# --- 5. Audience Retention Export Diagnostic ---

def parse_retention_csv(
    csv_text_or_path: str | Path,
    transcript_cues: list[tuple[float, float, str]] | None = None,
    duration: float | None = None,
) -> dict[str, Any]:
    """Analyze a YouTube Studio audience retention CSV to diagnose hook leaks, cliffs, and slides."""
    rows: list[tuple[float, float]] = []
    if isinstance(csv_text_or_path, Path) or (isinstance(csv_text_or_path, str) and os.path.exists(csv_text_or_path)):
        lines = Path(csv_text_or_path).read_text(encoding="utf-8-sig", errors="replace").splitlines()
    else:
        lines = str(csv_text_or_path).strip().splitlines()

    for r in csv.reader(lines):
        nums = []
        for c in r:
            cleaned = c.strip().replace("%", "").replace(",", "")
            try:
                nums.append(float(cleaned))
            except ValueError:
                pass
        if len(nums) >= 2:
            rows.append((nums[0], nums[1]))

    if len(rows) < 8:
        return {
            "error": "Could not read at least 8 valid (timestamp, percentage) data points from CSV.",
            "points": len(rows),
        }

    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    pct_axis = max(xs) <= 100.5

    def at_seconds(x: float) -> float | None:
        if not pct_axis:
            return x
        if duration:
            return (x / 100.0) * duration
        return None

    start = ys[0] or 100.0
    cutoff = 30.0 if not pct_axis else ((30.0 / duration * 100) if duration else 10.0)
    hook_end = min((y for x, y in rows if x <= cutoff), default=start)
    hook_leak = start - hook_end

    drops = []
    for i in range(1, len(rows)):
        d = ys[i - 1] - ys[i]
        span = xs[i] - xs[i - 1] or 1.0
        drops.append((d / span, xs[i - 1], xs[i], d))

    drops.sort(reverse=True)
    cliffs = []
    for _, a1, b1, d in drops[:5]:
        if d > 0.8:
            sec = at_seconds(a1)
            cliffs.append({
                "from": round(a1, 2),
                "to": round(b1, 2),
                "lost": round(d, 2),
                "at_seconds": round(sec, 1) if sec is not None else None,
                "label": format_mmss(sec) if sec is not None else f"{a1:.1f}%",
            })

    mid = [d for d, x0, _, _ in [(r[0], r[1], r[2], r[3]) for r in drops] if x0 > cutoff]
    slide = sum(mid) / len(mid) if mid else 0.0

    # Spoken words correlation if transcript provided
    spoken_map: dict[str, str] = {}
    if transcript_cues:
        for c in cliffs:
            if c["at_seconds"] is not None:
                sec = c["at_seconds"]
                near = [q[2] for q in transcript_cues if q[0] <= sec + 4 and q[1] >= sec - 4]
                if near:
                    spoken_map[str(c["from"])] = " ".join(near)[:180]
                    c["spoken"] = " ".join(near)[:180]

    verdict = "healthy" if hook_leak < 25 else "leaking" if hook_leak < 40 else "severe"

    return {
        "points": len(rows),
        "start": round(start, 1),
        "end": round(ys[-1], 1),
        "hook_leak": round(hook_leak, 2),
        "hook_verdict": verdict,
        "cliffs": cliffs,
        "slide_rate": round(slide, 3),
        "advice": (
            "Hook is healthy (<25% lost). If reach is low, packaging (/yt-package) is your lever."
            if hook_leak < 25
            else "First 15-30s leaks significantly. Tighten the opening turn before altering the rest of the edit."
            if hook_leak < 40
            else "Severe hook dropoff (>40%). Replace the first sentence using a proven hook formula."
        ),
    }


# --- 6. Viral Swipe Outlier Ranker ---

def analyze_swipe_outliers(
    videos: list[dict[str, Any]],
    min_multiple: float = 1.5,
) -> dict[str, Any]:
    """Group collected niche videos by channel, determine median views, and identify outliers."""
    by_channel: dict[str, list[dict[str, Any]]] = {}
    for v in videos:
        ch = (v.get("channel") or "Unknown").strip()
        by_channel.setdefault(ch, []).append(v)

    outliers: list[dict[str, Any]] = []
    thin_channels: list[dict[str, Any]] = []

    for ch, vids in by_channel.items():
        if len(vids) < 4:
            thin_channels.append({"channel": ch, "count": len(vids)})
            continue
        views = [float(v.get("views", 0) or 0) for v in vids]
        med = statistics.median(views) if views else 0.0
        if med <= 0:
            continue

        for v in vids:
            v_views = float(v.get("views", 0) or 0)
            mult = v_views / med
            title = (v.get("title") or "").strip()
            formula_name, _, _ = classify_hook_formula(title)
            if mult >= min_multiple:
                outliers.append({
                    "channel": ch,
                    "title": title,
                    "views": int(v_views),
                    "median": int(med),
                    "multiple": round(mult, 2),
                    "formula": formula_name,
                    "url": v.get("url", ""),
                    "duration": v.get("duration", 0),
                })

    outliers.sort(key=lambda r: -r["multiple"])

    # Formula breakdown among outliers
    formula_counts: dict[str, int] = {}
    for r in outliers:
        f = r["formula"]
        formula_counts[f] = formula_counts.get(f, 0) + 1

    ranked_formulas = sorted(formula_counts.items(), key=lambda x: -x[1])

    return {
        "total_analyzed": len(videos),
        "channel_count": len(by_channel),
        "min_multiple": min_multiple,
        "outliers": outliers,
        "skipped_thin_channels": thin_channels,
        "top_formulas": [{"formula": f, "count": c} for f, c in ranked_formulas],
    }


# --- 7. Creator Voice Profile Manager ---

LOCAL_VOICE = CONFIG / "voice.md"


def get_voice_profile() -> str:
    paths = [
        LOCAL_VOICE,
        Path.home() / ".claude" / "youtube" / "voice.md",
        ROOT / "templates" / "voice.md",
    ]
    for p in paths:
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                pass
    return "# voice.md\n\nNo voice profile created yet."


def save_voice_profile(content: str) -> None:
    LOCAL_VOICE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_VOICE.write_text(content, encoding="utf-8")

    claude_yt = Path.home() / ".claude" / "youtube"
    try:
        claude_yt.mkdir(parents=True, exist_ok=True)
        (claude_yt / "voice.md").write_text(content, encoding="utf-8")
    except Exception as e:
        log.warning("Could not sync voice profile to ~/.claude/youtube: %s", e)
