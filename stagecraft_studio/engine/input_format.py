"""Detect a quicklook input format from the path. Unknown formats are refused."""

from __future__ import annotations

from pathlib import Path


class UnsupportedInput(Exception):
    """The path is not a format this quicklook launch can hand to the engine."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(reason)


_TEXT_FORMATS = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".txt": "txt",
}
_MATRIX_NAMES = frozenset({"matrix.mtx", "matrix.mtx.gz"})
_FEATURE_NAMES = frozenset({"features.tsv", "features.tsv.gz", "genes.tsv", "genes.tsv.gz"})
_BARCODE_NAMES = frozenset({"barcodes.tsv", "barcodes.tsv.gz"})
_SUPPORTED = "请改用 h5ad、10x MTX 目录，或 csv / tsv / txt 矩阵。"


def detect_input_format(path: Path) -> str:
    """Return the engine INPUT_FORMAT for a file or 10x directory."""
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_dir():
        return _mtx_directory(path)
    return _file_format(path)


def _file_format(path: Path) -> str:
    suffix = _data_suffix(path)
    if suffix == ".h5ad":
        return "h5ad"
    if suffix == ".h5":
        raise UnsupportedInput(path, f"不支持 10x h5。{_SUPPORTED}")
    mapped = _TEXT_FORMATS.get(suffix)
    if mapped is not None:
        return mapped
    raise UnsupportedInput(path, f"不支持这个输入。{_SUPPORTED}")


def _data_suffix(path: Path) -> str:
    name = path.name.casefold()
    if name.endswith(".gz"):
        inner = name[: -len(".gz")]
        inner_suffix = _suffix(inner)
        if inner_suffix in _TEXT_FORMATS:
            return inner_suffix
    return _suffix(name)


def _suffix(name: str) -> str:
    dot = name.rfind(".")
    if dot < 0:
        return ""
    return name[dot:]


def _mtx_directory(path: Path) -> str:
    names = {item.name.casefold() for item in path.iterdir() if item.is_file()}
    missing: list[str] = []
    if names.isdisjoint(_MATRIX_NAMES):
        missing.append("matrix.mtx")
    if names.isdisjoint(_FEATURE_NAMES):
        missing.append("features.tsv 或 genes.tsv")
    if names.isdisjoint(_BARCODE_NAMES):
        missing.append("barcodes.tsv")
    if missing:
        joined = "、".join(missing)
        raise UnsupportedInput(path, f"这个目录不是 10x MTX，缺少 {joined}。")
    return "10x_mtx"
