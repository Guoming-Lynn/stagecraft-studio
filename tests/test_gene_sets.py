"""Default Hallmark, KEGG, and GO Biological Process libraries stay on this machine."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from stagecraft_studio.engine.gene_sets import ensure_default_gmt, library_for_request
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.engine.quicklook import QuicklookRequest
from stagecraft_studio.worker.runs import RunStore

from tests.fakes import write_fake_engine


def test_default_libraries_are_combined_without_leaving_the_machine(tmp_path: Path) -> None:
    def fetch(url: str) -> bytes:
        if "kegg_legacy" in url:
            return b"KEGG_GLYCOLYSIS\tdesc\tHK1,1\tGAPDH\n"
        if "Hallmark" in url or "h.all" in url or "mh.all" in url:
            return b"HALLMARK_HYPOXIA\thttps://example.test/hypoxia\tIFITM3\tVEGFA\n"
        return b"GOBP_WOUND_HEALING\tGO:0009611\tIFITM3\n"

    path = ensure_default_gmt("human", fetch=fetch, cache=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "HALLMARK_HYPOXIA" in text
    assert "KEGG_GLYCOLYSIS" in text
    assert "HK1\t" in text
    assert "HK1,1" not in text
    assert "GOBP_WOUND_HEALING" in text
    def offline(_url: str) -> bytes:
        raise OSError("no")

    again = ensure_default_gmt("human", fetch=offline, cache=tmp_path)
    assert again == path


def test_an_imported_gmt_is_not_replaced(tmp_path: Path) -> None:
    imported = tmp_path / "mine.gmt"
    imported.write_text("MINE\tdesc\tGENE1\n", encoding="utf-8")
    assert library_for_request(imported, "human") == imported


def test_empty_gmt_uses_the_downloaded_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STAGECRAFT_GENE_SETS", raising=False)
    monkeypatch.setenv("STAGECRAFT_GENE_SET_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(
        "stagecraft_studio.engine.gene_sets._fetch",
        lambda _url: b"HALLMARK_HYPOXIA\tdesc\tIFITM3\n",
    )
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, logs=True)
    store = RunStore(tmp_path / "runs.json")
    run_id = store.start(
        QuicklookRequest(
            input_path=source,
            target_gene="IFITM3",
            output_root=tmp_path / "project",
            organism="mouse",
        ),
        EngineLaunch(python=Path(__import__("sys").executable), script=script),
    )
    assert run_id
    deadline = time.monotonic() + 2
    argv_path = tmp_path / "project" / "argv.json"
    while not argv_path.is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    config = json.loads((tmp_path / "project" / "config.json").read_text(encoding="utf-8"))
    assert config["LOCAL_GMT"].endswith("mouse.gmt")
    argv = json.loads((tmp_path / "project" / "argv.json").read_text(encoding="utf-8"))
    assert "--stop-after" not in argv
    sources_path = tmp_path / "project" / "parameter_sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    assert sources["LOCAL_GMT"] == "default"
