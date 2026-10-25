"""IShowSpeed editorial profile; evidence is documented in SPEED_STUDIO.md."""
from .models import Preferences

BRIEF = """
DEDICATED ISHOWSPEED STREAM EDITOR. Select distinct, intelligible events, not generic advice.
Rank: a challenge with its result; unexpected reaction with its trigger; a fan encounter with a
payoff; football rivalry with actual context; a sincere emotional moment. Shouting alone is weak.
Use only events observed in THIS source. The creator profile is not evidence that an event occurred.
For 6-12s choose a single complete reaction/visual gag, 12-25s setup and payoff, 25-45s challenge,
45-60s only when the context earns it. These are options, not quotas. Never pad weak footage.
Open immediately before the trigger, keep the reveal and 0.5-1.5s of the real reaction when possible.
An athletic challenge must include its outcome. Keep other participants and the relevant action
visible. Do not cut a race so a loss looks like a win. Never manufacture dialogue or a reaction.
Retain anticipation when it is necessary; reject waiting rooms, ads, chat housekeeping and repeated
screams. Do not cut off physical action just because speech stopped. Avoid selecting nudity,
private information, serious injury or humiliation as entertainment. No fabricated stakes.
Write natural ENGLISH display hooks and Instagram captions, 3-8 words for the hook, preferably
under 55 characters. Name the specific tension; avoid generic 'Speed went crazy' on every clip.
Choose moment_type: reaction, challenge, fan_encounter, football, wholesome, or other.
payoff_time is the observed reveal/result in absolute source seconds, or null if unknown.
Keep transcript and quoted hook_text verbatim in the original language for verification.
For genuinely nonverbal visual moments use transcript="" and captions=[]; never invent speech.
Do not claim to have visual evidence when you only received text. Return fewer clips if necessary.
"""


def preset(base: Preferences, **overrides) -> Preferences:
    return Preferences.model_validate(base.model_dump() | {
        "editorial_profile": "ishowspeed", "text_mode": "english", "min_seconds": 6,
        "max_seconds": 60, "clipping_mode": "gemini_browser", "gemini_verify_captions": True,
        "layout": "square_hook", "style": "bold", "preserve_wide_groups": True,
        "trim_edges": False, "music_gain": .50, "sound_effects": True,
        "sfx_gain": .12, "reaction_zoom": True,
    } | overrides)


def instructions(prefs):
    from .project_rules import instructions as project_instructions
    from .display_text import language_brief
    from .prompts import get_prompt
    speed_prompt = get_prompt("speed_brief")
    return language_brief(prefs) + (speed_prompt if prefs.editorial_profile == "ishowspeed" else "") + project_instructions(prefs)


def score(ratings, prefs):
    if prefs.editorial_profile == "ishowspeed":
        return round(ratings.hook * .25 + ratings.payoff * .3 + ratings.standalone * .25
                     + ratings.emotion * .18 + ratings.usefulness * .02)
    return ratings.score()


def stream_signal(text):
    import re
    return min(8, len(re.findall(
        r"\b(race|won|lost|ronaldo|messi|goal|challenge|finish|fan|surprise|no way|thank you|finally)\b",
        text, re.I)))
