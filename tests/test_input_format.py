"""One accepted format, plus one format the engine must not guess."""

from __future__ import annotations

from pathlib import Path

import pytest
from stagecraft_studio.engine.input_format import UnsupportedInput, detect_input_format


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("counts.h5ad", "h5ad"),
        ("filtered_feature_bc_matrix.h5", "h5"),
        ("counts.csv", "csv"),
        ("counts.csv.gz", "csv"),
        ("counts.tsv", "tsv"),
        ("counts.tsv.gz", "tsv"),
        ("counts.txt", "txt"),
        ("counts.txt.gz", "txt"),
    ],
)
def test_supported_file_formats(tmp_path: Path, name: str, expected: str) -> None:
    path = tmp_path / name
    path.write_bytes(b"x")
    assert detect_input_format(path) == expected


def test_10x_mtx_directory(tmp_path: Path) -> None:
    compressed = tmp_path / "gz"
    compressed.mkdir()
    for name in ("matrix.mtx.gz", "features.tsv.gz", "barcodes.tsv.gz"):
        (compressed / name).write_bytes(b"x")
    genes = tmp_path / "genes"
    genes.mkdir()
    for name in ("matrix.mtx", "genes.tsv", "barcodes.tsv"):
        (genes / name).write_bytes(b"x")
    assert detect_input_format(compressed) == "10x_mtx"
    assert detect_input_format(genes) == "10x_mtx"


def test_unknown_suffix_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "counts.loom"
    path.write_bytes(b"x")
    with pytest.raises(UnsupportedInput, match="不支持这个输入"):
        detect_input_format(path)
