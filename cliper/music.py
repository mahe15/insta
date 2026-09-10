from __future__ import annotations

import random
from pathlib import Path

CATEGORIES = {
    "cinematic_epic": "Cinematic - Epic",
    "emotional_sad": "Emotional - Sad",
    "suspense_thriller": "Suspense - Thriller",
    "energetic_hype": "Energetic - Hype",
    "chill_ambient": "Chill - Ambient",
}


def folders(root: Path):
    for name in CATEGORIES.values():
        (root / name).mkdir(parents=True, exist_ok=True)


def choose(root: Path, category: str) -> Path | None:
    folders(root)
    directory = root / CATEGORIES[category]
    tracks = [p for p in directory.iterdir() if p.is_file() and not p.is_symlink()
              and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}]
    return random.choice(tracks).resolve() if tracks else None
