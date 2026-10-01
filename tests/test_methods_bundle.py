"""Methods text, reproduction zip, and run comparison stay on the server."""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.api.bundle import build_bundle
from stagecraft_studio.api.compare import compare_runs
from stagecraft_studio.api.copy import CLAIM_SCOPE
from stagecraft_studio.api.methods import methods_paragraph
from stagecraft_studio.api.steps import EngineIdentity
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.worker.runs import RunRecord

from tests.fakes import write_fake_engine

TOKEN = {
    "origin": "http://127.0.0.1:8765",
    "x-stagecraft-token": "secret-token",
}


def test_methods_paragraph_repeats_and_stays_cell_level() -> None:
    text = methods_paragraph(
        gene="IFITM3",
        seed="42",
        engine_name="scrna-target-engine",
        engine_version="0.1.0",
        engine_git="abc",
        stopped_after="phase03",
        enrichment_label="未运行，等本地基因集",
    )
    assert text == methods_paragraph(
        gene="IFITM3",
        seed="42",
        engine_name="scrna-target-engine",
        engine_version="0.1.0",
        engine_git="abc",
        stopped_after="phase03",
        enrichment_label="未运行，等本地基因集",
    )
    assert CLAIM_SCOPE in text
    assert "临时标签" in text
    assert "IFITM3" in text
    assert "42" in text
    assert "没有调用模型" in text


def test_bundle_keeps_launch_files_and_drops_data(tmp_path: Path) -> None:
    root = tmp_path / "out"
    root.mkdir()
    (root / "config.json").write_text('{"TARGET_GENE": "IFITM3"}\n', encoding="utf-8")
    (root / "matrix.h5ad").write_bytes(b"not-a-matrix")
    tables = root / "03_tables"
    tables.mkdir()
    (tables / "genes.csv").write_text("gene\nIFITM3\n", encoding="utf-8")
    scripts = tmp_path / "engine" / "scripts"
    scripts.mkdir(parents=True)
    (scripts.parent / "uv.lock").write_text("lock\n", encoding="utf-8")
    payload = build_bundle(
        root,
        "python run_pipeline.py",
        EngineIdentity("eng", "1", "abc", scripts),
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert names == {"config.json", "argv.txt", "engine.json", "uv.lock"}
        assert "IFITM3" in archive.read("config.json").decode("utf-8")
        engine = json.loads(archive.read("engine.json"))
        assert engine["lock"] == "uv.lock"
        assert engine["git"] == "abc"


def test_compare_shows_parameter_and_count_differences(tmp_path: Path) -> None:
    left = _record(tmp_path / "left", "a" * 16, gene="IFITM3", cells=10, clusters=3)
    right = _record(tmp_path / "right", "b" * 16, gene="CD3D", cells=12, clusters=3)
    view = compare_runs(left, right, EngineIdentity("eng", "1", "abc", tmp_path))
    assert view.cells_left == "10"
    assert view.cells_right == "12"
    assert view.clusters_left == "3"
    assert view.clusters_right == "3"
    gene = next(row for row in view.parameters if row.name == "TARGET_GENE")
    assert gene.left == "IFITM3"
    assert gene.right == "CD3D"
    assert gene.same is False
    assert view.figure_left == "未找到"


def test_compare_says_missing_without_a_cluster_report(tmp_path: Path) -> None:
    left = _record(tmp_path / "left", "c" * 16, gene="IFITM3", cells=None, clusters=None)
    right = _record(tmp_path / "right", "d" * 16, gene="IFITM3", cells=None, clusters=None)
    view = compare_runs(left, right, EngineIdentity("eng", "1", "abc", tmp_path))
    assert view.cells_left == "未找到"
    assert view.clusters_right == "未找到"


def test_run_page_includes_methods_and_bundle(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path / "bin")
    client = TestClient(
        create_app(
            "secret-token",
            port=8765,
            launch=EngineLaunch(python=Path(sys.executable), script=script),
        )
    )
    started = client.post(
        "/api/runs",
        json={"input_path": str(source), "gene": "IFITM3", "out": str(tmp_path / "project")},
        headers=TOKEN,
    )
    assert started.status_code == 201
    run_id = started.json()["run_id"]
    payload: dict[str, object] = {}
    for _ in range(40):
        payload = client.get(f"/api/runs/{run_id}").json()
        if payload.get("returncode") == 0:
            break
    text = payload["methods_text"]
    assert isinstance(text, str)
    assert "细胞水平" in text
    assert "IFITM3" in text
    assert "42" in text
    packed = client.get(f"/api/runs/{run_id}/bundle")
    assert packed.status_code == 200
    assert packed.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(packed.content)) as archive:
        assert "matrix.h5ad" not in archive.namelist()
        assert "config.json" in archive.namelist()
        assert "IFITM3" in archive.read("config.json").decode("utf-8")


def _record(
    root: Path,
    run_id: str,
    *,
    gene: str,
    cells: int | None,
    clusters: int | None,
) -> RunRecord:
    root.mkdir()
    (root / "config.json").write_text(
        json.dumps({"TARGET_GENE": gene, "RANDOM_SEED": 42}),
        encoding="utf-8",
    )
    if cells is not None and clusters is not None:
        logs = root / "99_logs"
        logs.mkdir()
        (logs / "02_global_report.json").write_text(
            json.dumps({"N_Cells": cells, "N_Clusters": clusters}),
            encoding="utf-8",
        )
    return RunRecord(
        run_id=run_id,
        output_root=root,
        status="succeeded",
        stopped_after="phase03",
        enrichment="not_run_until_local_gmt",
        command=("python", "run_pipeline.py"),
    )
