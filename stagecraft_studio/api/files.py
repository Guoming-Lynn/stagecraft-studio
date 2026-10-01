"""Run-directory file access. The relative path cannot leave that directory."""

from __future__ import annotations

import csv
import os
import subprocess
from pathlib import Path

from stagecraft_studio.api.models import FilePreview, TablePage, TreeEntry

TEXT_LIMIT = 2_000_000
_TEXT_SUFFIXES = {".log", ".json", ".csv", ".tsv", ".txt", ".md", ".svg"}
_MEDIA_SUFFIXES = {".png", ".svg"}
_TABLE_SUFFIXES = {".csv", ".tsv"}


class PathRejected(Exception):
    """The requested relative path is missing or not inside the run directory."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


def resolve_inside(root: Path, rel: str) -> Path:
    """Resolve rel under root. Absolute paths, drives, and links that escape are refused."""
    if not rel or not rel.strip():
        raise PathRejected(422, "缺少相对路径")
    # "C:/..." has no drive on Linux, so it would be looked up as a missing relative file.
    normalized = rel.replace("\\", "/")
    if len(normalized) >= 2 and normalized[0].isalpha() and normalized[1] == ":":
        raise PathRejected(403, "路径不能超出这次运行的目录")
    candidate_rel = Path(rel)
    if candidate_rel.drive or candidate_rel.is_absolute() or rel.startswith("\\\\"):
        raise PathRejected(403, "路径不能超出这次运行的目录")
    root_resolved = root.resolve()
    candidate = (root_resolved / candidate_rel).resolve()
    if not candidate.is_relative_to(root_resolved):
        raise PathRejected(403, "路径不能超出这次运行的目录")
    return candidate


def list_tree(root: Path) -> list[TreeEntry]:
    """List files under the run directory without following links that leave it."""
    root_resolved = root.resolve()
    if not root_resolved.is_dir():
        return []
    entries: list[TreeEntry] = []
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        current = Path(dirpath)
        if _outside(root_resolved, current):
            dirnames.clear()
            continue
        kept: list[str] = []
        for name in list(dirnames):
            child = current / name
            if _outside(root_resolved, child):
                continue
            kept.append(name)
            entries.append(
                TreeEntry(rel=child.relative_to(root_resolved).as_posix(), kind="dir", size=0)
            )
        dirnames[:] = kept
        for name in filenames:
            path = current / name
            if _outside(root_resolved, path):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            entries.append(
                TreeEntry(
                    rel=path.relative_to(root_resolved).as_posix(),
                    kind="file",
                    size=size,
                )
            )
    return entries


def preview_text(root: Path, rel: str) -> FilePreview:
    """Return at most 2 MB of text. Longer files are marked truncated."""
    path = _file(root, rel, _TEXT_SUFFIXES, "这个文件不能作为文本预览")
    with path.open("rb") as handle:
        chunk = handle.read(TEXT_LIMIT + 1)
    truncated = len(chunk) > TEXT_LIMIT
    text = chunk[:TEXT_LIMIT].decode("utf-8", errors="replace")
    try:
        size = path.stat().st_size
    except OSError:
        size = len(chunk)
    return FilePreview(
        rel=path.relative_to(root.resolve()).as_posix(),
        text=text,
        truncated=truncated,
        note="已截断" if truncated else "",
        size=size,
    )


def media_file(root: Path, rel: str) -> Path:
    """Return a PNG or SVG that stays inside the run directory."""
    return _file(root, rel, _MEDIA_SUFFIXES, "这个文件不是图片")


def preview_table(
    root: Path,
    rel: str,
    offset: int,
    limit: int,
    *,
    query: str = "",
    sort: str = "",
    descending: bool = False,
) -> TablePage:
    """Return one page after filtering and sorting. The whole table is not sent."""
    path = _file(root, rel, _TABLE_SUFFIXES, "这个文件不是表格")
    delimiter = "\t" if path.suffix.casefold() == ".tsv" else ","
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            columns = [str(item) for item in next(reader)]
        except StopIteration:
            columns = []
        # ponytail: sort/filter holds the matching rows in memory; stream if a table exceeds RAM
        matched = [_row(row) for row in reader if _matches(row, query)]
    index = columns.index(sort) if sort in columns else -1
    if index >= 0:
        matched.sort(key=lambda row: _sort_key(row, index), reverse=descending)
    page = matched[offset : offset + limit]
    return TablePage(
        rel=path.relative_to(root.resolve()).as_posix(),
        columns=columns,
        rows=page,
        offset=offset,
        limit=limit,
        total=len(matched),
    )


def reveal_command(path: Path) -> list[str]:
    """Open a directory in the system file browser. The argument is that directory only."""
    if os.name == "nt":
        return ["explorer", str(path)]
    return ["xdg-open", str(path)]


def reveal(path: Path) -> None:
    subprocess.run(reveal_command(path), check=False)


def _file(root: Path, rel: str, suffixes: set[str], wrong_type: str) -> Path:
    path = resolve_inside(root, rel)
    if path.is_dir():
        raise PathRejected(400, "这是目录")
    if not path.is_file():
        raise PathRejected(404, "没有这个文件")
    if path.suffix.casefold() not in suffixes:
        raise PathRejected(415, wrong_type)
    return path


def _row(row: list[str]) -> list[str]:
    return [str(item) for item in row]


def _matches(row: list[str], query: str) -> bool:
    needle = query.casefold().strip()
    if not needle:
        return True
    return any(needle in str(item).casefold() for item in row)


def _sort_key(row: list[str], index: int) -> tuple[int, float, str]:
    cell = row[index] if index < len(row) else ""
    try:
        return (0, float(cell), "")
    except ValueError:
        return (1, 0.0, cell.casefold())


def _outside(root: Path, path: Path) -> bool:
    try:
        return not path.resolve().is_relative_to(root)
    except OSError:
        return True
