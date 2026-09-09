import os
from pathlib import Path

import pytest

from cliper.config import Config
from cliper.models import Clip, Ratings, Segment, Transcript, Word

engines_dir = Path(__file__).resolve().parent.parent / "data" / "browsers" / "engines"
if engines_dir.exists():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(engines_dir))


@pytest.fixture
def cfg(tmp_path):
    return Config(data_dir=tmp_path, provider="heuristic", min_free_disk_mb=1)


@pytest.fixture
def transcript():
    texts = ["Why did my first project fail?", "I tried building everything before testing demand.",
             "One conversation changed the entire plan.", "Now I test the smallest useful idea first.",
             "A tomato plant needs space to grow.", "Too much water can drown the roots.",
             "Check the soil before watering again.", "The leaves recover when the roots can breathe."]
    segments = []
    for i, text in enumerate(texts):
        tokens = text.split()
        step = 4 / len(tokens)
        words = [Word(start=i * 5 + j * step, end=i * 5 + (j + 1) * step, text=t)
                 for j, t in enumerate(tokens)]
        segments.append(Segment(start=i * 5, end=i * 5 + 4, text=text, words=words))
    return Transcript(language="en", duration=40, segments=segments)


@pytest.fixture
def clip():
    ratings = Ratings(hook=80, payoff=75, standalone=90, emotion=60, usefulness=85)
    return Clip(id=1, start=0, end=19, title="Test demand before building", reason="Complete useful lesson",
                hook_text="Why did my first project fail?", score=ratings.score(), ratings=ratings,
                text="A complete useful lesson with a clear opening and payoff.", selection_method="test")
