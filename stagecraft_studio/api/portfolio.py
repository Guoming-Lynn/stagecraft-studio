"""Read the portfolio board manifest. Paths must stay inside the run directory."""

from __future__ import annotations

import json
from pathlib import Path

from stagecraft_studio.api.models import PortfolioTile, PortfolioView


def read_portfolio(root: Path) -> PortfolioView | None:
    """Return the board image and the clickable tiles, if a manifest exists."""
    folder = root / "06_portfolio"
    if not folder.is_dir():
        return None
    manifests = sorted(path for path in folder.glob("*.json") if path.is_file())
    if not manifests:
        return None
    manifest = manifests[-1]
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    image = _inside(root, manifest.with_suffix(".png").relative_to(root).as_posix())
    if image is None:
        return None
    tiles = _tiles(root, payload.get("sections"))
    return PortfolioView(
        image=image,
        width=_whole(payload.get("canvas_width_px")),
        height=_whole(payload.get("canvas_height_px")),
        tiles=tiles,
    )


def _tiles(root: Path, sections: object) -> list[PortfolioTile]:
    if not isinstance(sections, list):
        return []
    tiles: list[PortfolioTile] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        figures = section.get("figures")
        if not isinstance(figures, list):
            continue
        for figure in figures:
            tile = _tile(root, figure)
            if tile is not None:
                tiles.append(tile)
    return tiles


def _tile(root: Path, figure: object) -> PortfolioTile | None:
    if not isinstance(figure, dict):
        return None
    rel = _inside(root, _text(figure.get("relative_source")))
    if rel is None:
        return None
    width = _whole(figure.get("width"))
    height = _whole(figure.get("height"))
    if width <= 0 or height <= 0:
        return None
    table = _inside(root, _text(figure.get("table"))) or ""
    return PortfolioTile(
        rel=rel,
        table=table,
        x=_whole(figure.get("x")),
        y=_whole(figure.get("y")),
        width=width,
        height=height,
    )


def _inside(root: Path, rel: str) -> str | None:
    if not rel or ".." in Path(rel).parts:
        return None
    path = (root / rel).resolve()
    base = root.resolve()
    if not path.is_file() or not path.is_relative_to(base):
        return None
    return path.relative_to(base).as_posix()


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\\", "/").lstrip("/")


def _whole(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value
