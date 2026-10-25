from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Word(Model):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class Segment(Model):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    text: str
    words: list[Word] = Field(default_factory=list)


class Transcript(Model):
    language: str
    duration: float = Field(gt=0)
    segments: list[Segment]
    coverage: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def timestamps(self):
        last = -1.0
        for s in self.segments:
            if s.start < last or s.end <= s.start or s.end > self.duration + 1:
                raise ValueError("Transcript segments must have ordered, valid timestamps")
            last = s.start
            previous_word = s.start - 0.2
            for w in s.words:
                if (w.start < previous_word or w.end <= w.start or w.start < s.start - 0.2
                        or w.end > s.end + 0.2):
                    raise ValueError("Word timestamps must be ordered and inside their segment")
                previous_word = w.start
        return self


class Preferences(Model):
    project_rules: str = Field(default="", max_length=2000)
    description_suffix: str = Field(default="", max_length=500)
    overlay_text: str = Field(default="", max_length=80)
    editorial_profile: Literal["standard", "ishowspeed"] = "standard"
    text_mode: Literal["romanized", "english", "source"] = "romanized"
    sound_effects: bool = True
    sfx_gain: float = Field(default=.12, ge=0, le=.25)
    reaction_zoom: bool = True
    scan_minutes: int = Field(default=24, ge=6, le=1440)
    focus_times: list[float] = Field(default_factory=list, max_length=12)
    music_gain: float = Field(default=.50, ge=0, le=1.0)
    music_normalize: bool = True
    clipping_mode: Literal["audio_first", "gemini_browser"] = "audio_first"
    gemini_verify_captions: bool = True
    ai_provider: Literal["openai", "xai", "gemini", "chatgpt_browser", "heuristic"] | None = None
    ai_model: str | None = None
    clips: int = Field(default=5, ge=1, le=10)
    min_seconds: int = Field(default=30, ge=6, le=90)
    max_seconds: int = Field(default=60, ge=6, le=120)
    style: Literal["studio", "bold", "minimal"] = "studio"
    captions: bool = True
    reframe: Literal["auto", "blur", "center"] = "auto"
    language: str = "auto"
    width: Literal[360, 720, 1080] = 1080
    fps: Literal[30, 60] = 60
    color_grade: Literal["off", "natural", "vivid"] = "natural"
    export_quality: Literal["high", "compact"] = "high"
    auto_render: bool = False
    layout: Literal["square_hook", "legacy"] = "square_hook"
    music: bool = True
    music_ducking: bool = True
    music_override: str | None = Field(default=None, description="Force all clips to use this music category (e.g. 'phonk')")
    music_folder: str | None = Field(default=None, description="Specific folder or category to select music from")
    music_track: str | None = Field(default=None, description="Specific song file or track path to use for clips")
    smart_crop: bool = True
    preserve_wide_groups: bool = False
    trim_edges: bool = True
    hook_style: Literal["auto", "curiosity", "contrast", "direct"] = "auto"
    auto_publish: bool = False
    instagram_account: str = "clips"
    youtube_auto_publish: bool = False
    youtube_account: str = "main"
    f1_enabled: bool = True
    f2_enabled: bool = False
    active_feature: Literal["f1", "f2", "both"] = "f1"
    f2_auto_publish: bool = False
    f2_skip_image_qa: bool = False
    selected_niche: str = "dark"
    enabled_niches: list[str] = Field(default_factory=lambda: ["dark", "men", "money", "tech", "finance"])

    @model_validator(mode="after")
    def lengths(self):
        import re
        self.project_rules = self.project_rules.strip()
        self.description_suffix = self.description_suffix.strip()
        self.overlay_text = " ".join(self.overlay_text.split())
        if len(set(t.casefold() for t in re.findall(r"#(\w+)", self.description_suffix))) > 5:
            raise ValueError("Use at most five required hashtags in the description text")
        if self.editorial_profile == "ishowspeed":
            self.text_mode = "english"
            if self.min_seconds > 60 or self.max_seconds > 60:
                raise ValueError("IShowSpeed clips must be between 6 and 60 seconds")
        if any(not math.isfinite(t) or t < 0 for t in self.focus_times):
            raise ValueError("Focus timestamps must be finite nonnegative seconds")
        if self.max_seconds < self.min_seconds:
            raise ValueError("Maximum length must be at least minimum length")
        return self


class Ratings(Model):
    hook: int = Field(ge=0, le=100)
    payoff: int = Field(ge=0, le=100)
    standalone: int = Field(ge=0, le=100)
    emotion: int = Field(ge=0, le=100)
    usefulness: int = Field(ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def _normalize_ratings(cls, data):
        if not isinstance(data, dict):
            return data
        res = dict(data)
        allowed = {"hook", "payoff", "standalone", "emotion", "usefulness"}
        filtered = {k: v for k, v in res.items() if k in allowed}
        vals = [v for v in filtered.values() if isinstance(v, (int, float))]
        is_small_scale = vals and max(vals) <= 10.0 and any(0 < v < 10.0 for v in vals)
        for k in allowed:
            if k in filtered:
                val = filtered[k]
                try:
                    f = float(val)
                except (ValueError, TypeError):
                    filtered[k] = 80
                    continue
                if math.isnan(f) or math.isinf(f):
                    raise ValueError("Ratings cannot be NaN or infinite")
                if is_small_scale:
                    f *= 10.0
                filtered[k] = max(0, min(100, int(round(f))))
            else:
                filtered[k] = 80
        return filtered

    def score(self) -> int:
        return round(self.hook * .25 + self.payoff * .25 + self.standalone * .25
                     + self.emotion * .1 + self.usefulness * .15)


class Proposal(Model):
    moment_type: Literal["reaction", "challenge", "fan_encounter", "football", "wholesome", "other"] = "other"
    payoff_time: float | None = Field(default=None, ge=0)
    first_segment: int = Field(ge=0)
    last_segment: int = Field(ge=0)
    title: str = Field(max_length=120)
    reason: str = Field(max_length=1000)
    hook_text: str = Field(max_length=500)
    ratings: Ratings = Field(default_factory=lambda: Ratings(hook=80, payoff=80, standalone=80, emotion=80, usefulness=80))
    music_category: str = "chill_ambient"
    caption: str = Field(default="", max_length=1800)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    hook_variants: list[str] = Field(default_factory=list, max_length=3)
    audience_value: str = Field(default="", max_length=300)

    @model_validator(mode="before")
    @classmethod
    def _sanitize_proposal(cls, data):
        if not isinstance(data, dict):
            return data
        res = dict(data)
        ratings_val = res.get("ratings")
        if not isinstance(ratings_val, (dict, Ratings)):
            flattened = {k: res[k] for k in ("hook", "payoff", "standalone", "emotion", "usefulness") if k in res}
            if flattened:
                res["ratings"] = flattened
            elif ratings_val is None or "ratings" not in res:
                res["ratings"] = {"hook": 80, "payoff": 80, "standalone": 80, "emotion": 80, "usefulness": 80}
        cat = str(res.get("music_category", "")).strip()
        from .music import CATEGORIES
        valid_cats = set(CATEGORIES.keys()) | {v.lower().replace(" - ", "_").replace(" ", "_") for v in CATEGORIES.values()}
        cat_norm = cat.lower().replace("-", "_").replace(" ", "_")
        if cat_norm in valid_cats or cat in CATEGORIES:
            res["music_category"] = cat_norm if cat_norm in valid_cats else cat
        else:
            res["music_category"] = "chill_ambient"
        for field, max_len in [("title", 120), ("reason", 1000), ("hook_text", 500),
                               ("caption", 1800), ("audience_value", 300)]:
            if isinstance(res.get(field), str) and len(res[field]) > max_len:
                res[field] = res[field][:max_len]
        if isinstance(res.get("hashtags"), list) and len(res["hashtags"]) > 5:
            res["hashtags"] = res["hashtags"][:5]
        if isinstance(res.get("hook_variants"), list) and len(res["hook_variants"]) > 3:
            res["hook_variants"] = res["hook_variants"][:3]
        allowed = {"first_segment", "last_segment", "title", "reason", "hook_text",
                   "ratings", "music_category", "caption", "hashtags", "hook_variants", "audience_value", "moment_type", "payoff_time"}
        return {k: v for k, v in res.items() if k in allowed}



class Proposals(Model):
    clips: list[Proposal] = Field(max_length=30)

    @model_validator(mode="before")
    @classmethod
    def _sanitize_clips(cls, data):
        if not isinstance(data, dict):
            return data
        raw_clips = data.get("clips")
        if not isinstance(raw_clips, list):
            return data
        valid = []
        for c in raw_clips:
            if isinstance(c, Proposal):
                valid.append(c)
            elif isinstance(c, dict):
                try:
                    valid.append(Proposal.model_validate(c))
                except Exception:
                    continue
        if valid:
            res = dict(data)
            res["clips"] = valid
            return res
        return data


class Clip(Model):
    moment_type: Literal["reaction", "challenge", "fan_encounter", "football", "wholesome", "other"] = "other"
    payoff_time: float | None = Field(default=None, ge=0)
    id: int
    start: float
    end: float
    title: str
    reason: str
    hook_text: str
    score: int
    ratings: Ratings
    text: str
    selection_method: str
    music_category: str = "chill_ambient"
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    hook_variants: list[str] = Field(default_factory=list, max_length=3)
    audience_value: str = ""
    editorial: dict = Field(default_factory=dict)


class Analysis(Model):
    coverage: dict = Field(default_factory=dict)
    title: str
    language: str
    duration: float
    method: str
    model: str | None = None
    clips: list[Clip]
