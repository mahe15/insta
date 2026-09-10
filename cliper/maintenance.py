from __future__ import annotations

import shutil
import time
import zipfile
from pathlib import Path

from .storage import Store


def cleanup(store: Store, days: int) -> int:
    cutoff = time.time() - days * 86400
    with store.connect() as db:
        rows = list(db.execute("SELECT id FROM jobs WHERE state IN ('complete','failed','cancelled') "
                               "AND updated < ?", (cutoff,)))
    removed = 0
    base = (store.root / "jobs").resolve()
    for row in rows:
        with store.connect() as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='publications'").fetchone():
                if db.execute("SELECT 1 FROM publications WHERE origin LIKE ? AND state NOT IN ('published','rejected')",
                              (row["id"] + ":%",)).fetchone():
                    continue
        directory = store.directory(row["id"])
        # Never delete user CLI source files, symlinks, or anything outside managed jobs.
        if directory.is_symlink() or directory.resolve().parent != base:
            continue
        if directory.exists():
            shutil.rmtree(directory)
        with store.connect() as db:
            db.execute("DELETE FROM jobs WHERE id=?", (row["id"],))
        removed += 1
    return removed


def export_metadata(directory: Path) -> Path:
    output = directory / "captions-and-edit-plans.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in [directory / "analysis.json", directory / "transcript.json",
                     *(directory / "clips").glob("*")]:
            if file.is_file() and file.suffix in {".json", ".ass", ".srt"}:
                archive.write(file, str(file.relative_to(directory)))
    return output
