from __future__ import annotations

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
    clipping_mode: Literal["audio_first", "gemini_browser"] = "audio_first"
    gemini_verify_captions: bool = True
    ai_provider: Literal["openai", "xai", "gemini", "chatgpt_browser", "heuristic"] | None = None
    ai_model: str | None = None
    clips: int = Field(default=5, ge=1, le=10)
    min_seconds: int = Field(default=30, ge=10, le=90)
    max_seconds: int = Field(default=60, ge=15, le=120)
    style: Literal["studio", "bold", "minimal"] = "studio"
    captions: bool = True
    reframe: Literal["auto", "blur", "center"] = "auto"
    language: str = "auto"
    width: Literal[360, 720, 1080] = 1080
    auto_render: bool = False
    layout: Literal["square_hook", "legacy"] = "square_hook"
    music: bool = True
    music_ducking: bool = True
    smart_crop: bool = True
    preserve_wide_groups: bool = False
    trim_edges: bool = True
    hook_style: Literal["auto", "curiosity", "contrast", "direct"] = "auto"
    auto_publish: bool = False
    instagram_account: str = "clips"
    f1_enabled: bool = True
    f2_enabled: bool = False
    active_feature: Literal["f1", "f2", "both"] = "f1"
    f2_auto_publish: bool = False
    selected_niche: str = "dark"
    enabled_niches: list[str] = Field(default_factory=lambda: ["dark", "men", "money", "tech", "finance"])

    @model_validator(mode="after")
    def lengths(self):
        if self.max_seconds < self.min_seconds:
            raise ValueError("Maximum length must be at least minimum length")
        return self


class Ratings(Model):
    hook: int = Field(ge=0, le=100)
    payoff: int = Field(ge=0, le=100)
    standalone: int = Field(ge=0, le=100)
    emotion: int = Field(ge=0, le=100)
    usefulness: int = Field(ge=0, le=100)

    def score(self) -> int:
        return round(self.hook * .25 + self.payoff * .25 + self.standalone * .25
                     + self.emotion * .1 + self.usefulness * .15)


class Proposal(Model):
    first_segment: int = Field(ge=0)
    last_segment: int = Field(ge=0)
    title: str = Field(max_length=90)
    reason: str = Field(max_length=500)
    hook_text: str = Field(max_length=150)
    ratings: Ratings
    music_category: Literal["cinematic_epic", "emotional_sad", "suspense_thriller", "energetic_hype", "chill_ambient"] = "chill_ambient"
    caption: str = Field(default="", max_length=1800)
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    hook_variants: list[str] = Field(default_factory=list, max_length=3)
    audience_value: str = Field(default="", max_length=300)


class Proposals(Model):
    clips: list[Proposal] = Field(max_length=30)


class Clip(Model):
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
    music_category: Literal["cinematic_epic", "emotional_sad", "suspense_thriller", "energetic_hype", "chill_ambient"] = "chill_ambient"
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list, max_length=5)
    hook_variants: list[str] = Field(default_factory=list, max_length=3)
    audience_value: str = ""
    editorial: dict = Field(default_factory=dict)


class Analysis(Model):
    title: str
    language: str
    duration: float
    method: str
    model: str | None = None
    clips: list[Clip]
