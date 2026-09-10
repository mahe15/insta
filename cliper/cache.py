"""Versioned cache identities for derived media; never depend on preferences alone."""
import hashlib
import json
from pathlib import Path

RENDER_VERSION = "square-studio-v3"
CAROUSEL_VERSION = "carousel-studio-v3"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_identity(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "missing": True}
    stat = path.stat()
    return {"path": str(path.resolve()), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def export_identity(reference, transcript, clip, prefs, cfg):
    inventory = []
    if prefs.music and cfg.music_dir.exists():
        inventory = [file_identity(p) for p in sorted(cfg.music_dir.glob("*/*")) if p.is_file() and not p.is_symlink()]
    return digest({"version": RENDER_VERSION, "source": reference, "source_file": file_identity(reference["path"]),
                   "transcript": transcript.model_dump(), "clip": clip.model_dump(), "preferences": prefs.model_dump(),
                   "encoder": cfg.video_encoder, "gpu": cfg.gpu_device_index, "music": inventory})
