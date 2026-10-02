"""Atomic publishing and checksum utilities for worker jobs."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def stream_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_publish(src: Path, dest: Path) -> None:
    """Publish src directory to dest atomically by staging replacement."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if dest.exists():
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        backup = dest.parent / f".{dest.name}.old.{timestamp}"
        dest.rename(backup)
    try:
        os.replace(src, dest)
    except Exception:
        if backup is not None and backup.exists() and not dest.exists():
            backup.rename(dest)
        raise
    finally:
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
