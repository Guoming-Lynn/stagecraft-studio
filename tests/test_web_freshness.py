"""The startup script rebuilds the page when sources are newer than dist."""

from __future__ import annotations

import os
from pathlib import Path

from stagecraft_studio.web_freshness import dist_is_stale


def test_missing_page_is_stale(tmp_path: Path) -> None:
    assert dist_is_stale(tmp_path)


def test_newer_source_or_lockfile_is_stale(tmp_path: Path) -> None:
    dist = _page(tmp_path)
    source = tmp_path / "web" / "src" / "main.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export {}\n", encoding="utf-8")
    lock = tmp_path / "pnpm-lock.yaml"
    lock.write_text("lock\n", encoding="utf-8")
    os.utime(dist, (10, 10))
    os.utime(source, (20, 20))
    os.utime(lock, (10, 10))
    assert dist_is_stale(tmp_path)
    os.utime(source, (10, 10))
    os.utime(lock, (20, 20))
    assert dist_is_stale(tmp_path)


def test_current_page_is_kept(tmp_path: Path) -> None:
    dist = _page(tmp_path)
    source = tmp_path / "web" / "src" / "main.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export {}\n", encoding="utf-8")
    lock = tmp_path / "pnpm-lock.yaml"
    lock.write_text("lock\n", encoding="utf-8")
    os.utime(source, (10, 10))
    os.utime(lock, (10, 10))
    os.utime(dist, (20, 20))
    assert not dist_is_stale(tmp_path)


def _page(root: Path) -> Path:
    dist = root / "web" / "dist" / "index.html"
    dist.parent.mkdir(parents=True)
    dist.write_text("<html></html>\n", encoding="utf-8")
    return dist
