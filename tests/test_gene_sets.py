"""Default Hallmark and GO Biological Process libraries stay on this machine."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.engine.gene_sets import _cache_dir, ensure_default_gmt, library_for_request
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.engine.quicklook import QuicklookRequest
from stagecraft_studio.worker.runs import RunStore

from tests.fakes import write_fake_engine


def test_default_libraries_are_combined_without_leaving_the_machine(tmp_path: Path) -> None:
    seen: list[str] = []

    def fetch(url: str) -> bytes:
        seen.append(url)
        if "go.bp" in url:
            return b"GOBP_WOUND_HEALING\tGO:0009611\tHK1,1\tIFITM3\n"
        if "h.all" in url or "mh.all" in url:
            return b"HALLMARK_HYPOXIA\thttps://example.test/hypoxia\tIFITM3\tVEGFA\n"
        raise AssertionError(url)

    path = ensure_default_gmt("human", fetch=fetch, cache=tmp_path)
    assert path.name == "human-2026.1.gmt"
    text = path.read_text(encoding="utf-8")
    assert "HALLMARK_HYPOXIA" in text
    assert "GOBP_WOUND_HEALING" in text
    assert "HK1\t" in text
    assert "HK1,1" not in text
    assert "KEGG" not in text
    assert all("kegg" not in url.casefold() and "enrichr" not in url.casefold() for url in seen)
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
    assert config["LOCAL_GMT"].endswith("mouse-2026.1.gmt")
    argv = json.loads((tmp_path / "project" / "argv.json").read_text(encoding="utf-8"))
    assert "--stop-after" not in argv
    sources_path = tmp_path / "project" / "parameter_sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8"))
    assert sources["LOCAL_GMT"] == "default"


def test_versioned_cache_lives_in_the_user_data_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STAGECRAFT_GENE_SET_CACHE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert _cache_dir() == tmp_path / "local" / "stagecraft-studio" / "gene-sets"


def test_offline_without_cache_asks_for_a_local_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("STAGECRAFT_GENE_SETS", raising=False)
    monkeypatch.setenv("STAGECRAFT_GENE_SET_CACHE", str(tmp_path / "empty-cache"))

    def offline(_url: str) -> bytes:
        raise OSError("offline")

    monkeypatch.setattr("stagecraft_studio.engine.gene_sets._fetch", offline)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path)
    client = TestClient(
        create_app(
            "secret-token",
            port=8765,
            launch=EngineLaunch(python=Path(sys.executable), script=script),
            state_path=tmp_path / "runs.json",
        )
    )
    response = client.post(
        "/api/runs",
        headers={"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"},
        json={"input_path": str(source), "gene": "IFITM3", "out": str(tmp_path / "project")},
    )
    assert response.status_code == 400
    detail = str(response.json()["detail"])
    assert "默认基因集没有下载成功" in detail
    assert "本地 GMT" in detail
    assert client.get("/api/runs").json() == []
    assert not (tmp_path / "project" / "config.json").exists()
    assert not (tmp_path / "project" / "argv.json").exists()
