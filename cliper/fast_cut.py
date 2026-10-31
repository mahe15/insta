"""Sequential video slicing into fixed-duration parts with 4:3 framing and header markers."""
from __future__ import annotations

import math

from .models import Clip, Ratings


def generate_fast_cut_clips(
    duration: float,
    chunk_duration: float = 90.0,
    skip_intro: bool = False,
    skip_seconds: float = 180.0,
    title_prefix: str = "Part",
) -> list[Clip]:
    """Slice a video of given duration into sequential parts.

    - Default chunk duration is 90 seconds (configurable e.g. 15-600s).
    - If skip_intro is True, begins slicing from skip_seconds (default 180s = 3 min).
    - Each clip receives a title and hook_text of 'Part 1', 'Part 2', etc.
    - Slices that are shorter than 5 seconds at the very end are merged into the last part.
    """
    if duration <= 0:
        raise ValueError("Video duration must be greater than 0")

    start_offset = skip_seconds if skip_intro else 0.0
    if start_offset >= duration:
        raise ValueError(
            f"Skip intro duration ({start_offset:.0f}s / {start_offset/60:.1f}m) "
            f"meets or exceeds total video duration ({duration:.0f}s / {duration/60:.1f}m)"
        )

    chunk_duration = max(5.0, float(chunk_duration))
    clips: list[Clip] = []
    current = start_offset
    part_num = 1

    while current < duration:
        end = min(duration, current + chunk_duration)
        # If the remaining piece after this chunk would be tiny (< 5 seconds), extend this chunk to the end
        if duration - end < 5.0:
            end = duration

        clip_start = round(current, 3)
        clip_end = round(end, 3)
        clip_len = round(clip_end - clip_start, 1)

        title = f"{title_prefix} {part_num}"
        hook = f"{title_prefix} {part_num}"
        ratings = Ratings(hook=90, payoff=90, standalone=90, emotion=90, usefulness=90)

        clip = Clip(
            moment_type="other",
            payoff_time=round(clip_start + (clip_end - clip_start) / 2, 3),
            id=part_num,
            start=clip_start,
            end=clip_end,
            title=title,
            reason=f"Sequential Fast Cut {title} ({clip_len}s)",
            hook_text=hook,
            score=90,
            ratings=ratings,
            text=f"{title} ({clip_len}s)",
            selection_method="fast_cut",
            music_category="chill_ambient",
            caption=f"{title} · Watch till the end!",
            hashtags=["shorts", "viral", "fyp", f"part{part_num}", "fastcut"],
            hook_variants=[title],
            audience_value=f"Continuous part {part_num} of source video.",
            editorial={
                "fast_cut": True,
                "part": part_num,
                "duration": clip_len,
                "skip_intro_applied": skip_intro,
            },
        )
        clips.append(clip)
        part_num += 1
        current = end
        if end >= duration:
            break

    return clips
