from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROVIDERS = ("openai", "xai", "gemini", "chatgpt_browser", "heuristic")


def normalize_provider(value: str) -> str:
    provider = value.strip().lower()
    provider = {"grok": "xai", "google": "gemini", "chatgpt": "chatgpt_browser",
                "browser": "chatgpt_browser"}.get(provider, provider)
    if provider not in PROVIDERS:
        raise ValueError("Choose openai, xai (grok), gemini, chatgpt_browser, or heuristic")
    return provider


@dataclass(frozen=True)
class AISettings:
    provider: str
    key: str = field(repr=False)
    model: str
    base_url: str


@dataclass
class Config:
    data_dir: Path = Path("data")
    token: str = field(default="", repr=False)
    owners: set[int] = field(default_factory=set)
    provider: str = "openai"
    api_key: str = field(default="", repr=False)
    model: str = "gpt-4.1-mini"
    base_url: str | None = None
    xai_api_key: str = field(default="", repr=False)
    xai_model: str = "grok-4.6"
    gemini_api_key: str = field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"
    browser_timeout: int = 240
    browser_max_chars: int = 60000
    browser_headless: bool = False
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute: str = "int8"
    gpu_device_index: int = 0
    video_encoder: str = "libx264"
    ffmpeg_path: str = ""
    max_source_minutes: int = 120
    max_download_mb: int = 1500
    min_free_disk_mb: int = 3000
    max_active_jobs: int = 3
    retention_days: int = 7
    music_dir: Path = Path("music")
    allowed_hosts: tuple[str, ...] = ("youtube.com", "youtu.be", "vimeo.com", "twitch.tv")
    skip_image_qa: bool = True

    @classmethod
    def load(cls):
        load_dotenv()
        cfg = cls(
            data_dir=Path(os.getenv("DATA_DIR", "data")).resolve(),
            token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            owners={int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip()},
            provider=normalize_provider(os.getenv("AI_PROVIDER", "openai")),
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            xai_api_key=os.getenv("XAI_API_KEY", "").strip(),
            xai_model=os.getenv("XAI_MODEL", "grok-4.6").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
            browser_timeout=int(os.getenv("CHATGPT_BROWSER_TIMEOUT", "240")),
            browser_max_chars=int(os.getenv("CHATGPT_BROWSER_MAX_CHARS", "60000")),
            browser_headless=os.getenv("CHATGPT_BROWSER_HEADLESS", "false").lower() == "true",
            whisper_model=os.getenv("WHISPER_MODEL", "small"),
            whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
            whisper_compute=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            gpu_device_index=int(os.getenv("GPU_DEVICE_INDEX", "0")),
            video_encoder=os.getenv("VIDEO_ENCODER", "libx264").strip().lower(),
            ffmpeg_path=os.getenv("FFMPEG_PATH", ""),
            music_dir=Path(os.getenv("MUSIC_DIR", "music")).resolve(),
            allowed_hosts=tuple(x.strip().lower() for x in os.getenv(
                "ALLOWED_VIDEO_HOSTS", "youtube.com,youtu.be,vimeo.com,twitch.tv").split(",") if x.strip()),
            skip_image_qa=os.getenv("CLIPER_SKIP_IMAGE_QA", "true").lower() in ("1", "true", "yes"),
        )
        for attr in ("max_source_minutes", "max_download_mb", "min_free_disk_mb", "max_active_jobs",
                     "retention_days"):
            setattr(cfg, attr, int(os.getenv(attr.upper(), str(getattr(cfg, attr)))))
            if getattr(cfg, attr) < 1:
                raise ValueError(f"{attr.upper()} must be positive")
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        if cfg.browser_timeout < 10 or cfg.browser_max_chars < 8000:
            raise ValueError("CHATGPT_BROWSER_TIMEOUT must be >= 10; CHATGPT_BROWSER_MAX_CHARS must be >= 8000")
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(cfg.data_dir / "browsers" / "engines"))
        if cfg.whisper_device not in {"cpu", "cuda"}:
            raise ValueError("WHISPER_DEVICE must be cpu or cuda")
        if cfg.video_encoder not in {"libx264", "h264_nvenc"}:
            raise ValueError("VIDEO_ENCODER must be libx264 or h264_nvenc")
        if cfg.gpu_device_index < 0:
            raise ValueError("GPU_DEVICE_INDEX must be zero or greater")
        if cfg.whisper_device == "cuda":
            from .hardware import configure_cuda_paths
            configure_cuda_paths()
        os.environ.setdefault("HF_HOME", str(cfg.data_dir / "cache" / "huggingface"))
        return cfg

    def ffmpeg(self) -> str:
        if self.ffmpeg_path:
            path = shutil.which(self.ffmpeg_path)
            if not path:
                raise ValueError("FFMPEG_PATH does not point to an executable")
            return path
        if path := shutil.which("ffmpeg"):
            return path
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()

    def ai(self, provider: str | None = None, model: str | None = None) -> AISettings:
        selected = normalize_provider(provider or self.provider)
        key, default_model, base_url = {
            "openai": (self.api_key, self.model, self.base_url or "https://api.openai.com/v1"),
            "xai": (self.xai_api_key, self.xai_model, "https://api.x.ai/v1"),
            "gemini": (self.gemini_api_key, self.gemini_model,
                       "https://generativelanguage.googleapis.com/v1beta/openai/"),
            "heuristic": ("", "heuristic", ""),
            "chatgpt_browser": ("", "website-session", "https://chatgpt.com/"),
        }[selected]
        return AISettings(selected, key, model or default_model, base_url)

    def check_ai(self, provider: str | None = None, model: str | None = None):
        settings = self.ai(provider, model)
        if settings.provider not in {"heuristic", "chatgpt_browser"} and not settings.key:
            key_name = {"openai": "OPENAI_API_KEY", "xai": "XAI_API_KEY", "gemini": "GEMINI_API_KEY"}[settings.provider]
            raise ValueError(f"Set {key_name} in the local .env and restart the bot, or select heuristic.")
        if not settings.model.strip():
            raise ValueError(f"Configure a model for {settings.provider}")
        return settings

    def snapshot_ai(self, prefs):
        settings = self.ai(prefs.ai_provider, prefs.ai_model)
        return prefs.model_copy(update={"ai_provider": settings.provider, "ai_model": settings.model})

    def check_disk(self):
        if shutil.disk_usage(self.data_dir).free < self.min_free_disk_mb * 1024**2:
            raise ValueError("Not enough free disk space; clean old jobs or change DATA_DIR")
