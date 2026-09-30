"""Reject quicklook artifacts as formal-analysis inputs."""

from __future__ import annotations

import json
from pathlib import Path

QUICKLOOK_TIER = "quicklook"
TIER_FILENAME = "analysis_tier.json"


class FormalInputRejected(Exception):
    """A formal task tried to read a quicklook product."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def quicklook_not_formal(path: Path) -> None:
    """Raise when `path` is inside a directory marked analysis_tier quicklook."""
    start = path.resolve()
    cursor = start if start.is_dir() else start.parent
    while True:
        tier_path = cursor / TIER_FILENAME
        if tier_path.is_file():
            payload = _read_tier(tier_path)
            if payload.get("analysis_tier") == QUICKLOOK_TIER:
                raise FormalInputRejected(path, "QUICKLOOK_NOT_FORMAL")
        parent = cursor.parent
        if parent == cursor:
            return
        cursor = parent


def _read_tier(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FormalInputRejected(path, "QUICKLOOK_TIER_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise FormalInputRejected(path, "QUICKLOOK_TIER_UNREADABLE")
    return payload
