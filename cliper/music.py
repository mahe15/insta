from __future__ import annotations

import random
from pathlib import Path

CATEGORIES = {
    "cinematic_epic": "Cinematic - Epic",
    "emotional_sad": "Emotional - Sad",
    "suspense_thriller": "Suspense - Thriller",
    "energetic_hype": "Energetic - Hype",
    "chill_ambient": "Chill - Ambient",
    "phonk": "Phonk",
}


AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def folders(root: Path):
    for name in CATEGORIES.values():
        (root / name).mkdir(parents=True, exist_ok=True)


def get_categories(root: Path) -> dict[str, str]:
    import re
    folders(root)
    result = dict(CATEGORIES)
    if root.exists():
        for p in sorted(root.iterdir()):
            if p.is_dir() and not p.is_symlink() and p.name not in CATEGORIES.values() and not p.name.startswith("."):
                slug = re.sub(r"[^\w]+", "_", p.name.strip().lower()).strip("_") or p.name.lower()
                if slug not in result:
                    result[slug] = p.name
    return result


def resolve_category_folder(root: Path, category: str | None) -> Path | None:
    if not category:
        return None
    cat = str(category).strip()
    if not cat:
        return None

    # Exact key in CATEGORIES
    if cat in CATEGORIES:
        return root / CATEGORIES[cat]

    all_cats = get_categories(root)
    if cat in all_cats:
        return root / all_cats[cat]

    # Direct folder in root
    candidate = root / cat
    if candidate.is_dir():
        return candidate

    cat_norm = cat.lower().replace("-", "_").replace(" ", "_")
    for k, v in all_cats.items():
        v_norm = v.lower().replace("-", "_").replace(" ", "_")
        if cat_norm in (k.lower(), v_norm):
            return root / v

    # Common aliases
    if cat_norm in {"chill", "ambient", "chill_ambient"}:
        return root / CATEGORIES["chill_ambient"]
    if cat_norm in {"phonk"}:
        return root / CATEGORIES["phonk"]
    if cat_norm in {"epic", "cinematic", "cinematic_epic"}:
        return root / CATEGORIES["cinematic_epic"]
    if cat_norm in {"sad", "emotional", "emotional_sad"}:
        return root / CATEGORIES["emotional_sad"]
    if cat_norm in {"hype", "energetic", "energetic_hype"}:
        return root / CATEGORIES["energetic_hype"]
    if cat_norm in {"suspense", "thriller", "suspense_thriller"}:
        return root / CATEGORIES["suspense_thriller"]

    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and not d.is_symlink():
                d_norm = d.name.lower().replace("-", "_").replace(" ", "_")
                if cat_norm in d_norm or d_norm in cat_norm:
                    return d

    return None


def resolve_track(root: Path, track_name_or_path: str | None) -> Path | None:
    if not track_name_or_path:
        return None
    val = str(track_name_or_path).strip()
    if not val:
        return None

    p = Path(val)
    if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
        return p.resolve()
    candidate = root / val
    if candidate.is_file() and candidate.suffix.lower() in AUDIO_EXTENSIONS:
        return candidate.resolve()

    target_name = p.name.lower()
    if root.exists():
        for track in root.glob("*/*"):
            if track.is_file() and not track.is_symlink() and track.suffix.lower() in AUDIO_EXTENSIONS:
                if track.name.lower() == target_name:
                    return track.resolve()

        for track in root.glob("*/*"):
            if track.is_file() and not track.is_symlink() and track.suffix.lower() in AUDIO_EXTENSIONS:
                if target_name in track.name.lower():
                    return track.resolve()

    return None


def choose(root: Path, category: str | None = None) -> Path | None:
    folders(root)
    if category:
        directory = resolve_category_folder(root, category)
        if directory and directory.is_dir():
            tracks = [p for p in directory.iterdir() if p.is_file() and not p.is_symlink()
                      and p.suffix.lower() in AUDIO_EXTENSIONS]
            if tracks:
                return random.choice(tracks).resolve()

    all_tracks = [p for p in root.glob("*/*") if p.is_file() and not p.is_symlink()
                  and p.suffix.lower() in AUDIO_EXTENSIONS]
    return random.choice(all_tracks).resolve() if all_tracks else None
