"""Decide whether the built page is older than its sources."""

from __future__ import annotations

import sys
from pathlib import Path


def dist_is_stale(root: Path) -> bool:
    """True when dist is missing or older than web/src or the lockfile."""
    dist = root / "web" / "dist" / "index.html"
    if not dist.is_file():
        return True
    built = dist.stat().st_mtime
    lock = root / "pnpm-lock.yaml"
    if lock.is_file() and lock.stat().st_mtime > built:
        return True
    source = root / "web" / "src"
    if not source.is_dir():
        return False
    return any(path.is_file() and path.stat().st_mtime > built for path in source.rglob("*"))


def main(argv: list[str] | None = None) -> int:
    """Exit 1 when the page should be rebuilt. Exit 0 when dist is current."""
    del argv
    root = Path(__file__).resolve().parents[1]
    return 1 if dist_is_stale(root) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
