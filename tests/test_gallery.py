"""Test formal analysis gallery aggregation and raw artifact serving."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.gallery import GalleryNotFound, get_stage_gallery
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, Job, RuleResultRow
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.engine.launch import EngineLaunch

LAUNCH = EngineLaunch(python=Path(sys.executable), script=Path("run_pipeline.py"))


def _setup_stage(tmp_path: Path):
    db_path = tmp_path / "test_studio.sqlite"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    data_file = tmp_path / "data.h5ad"
    data_file.write_text("dummy", encoding="utf-8")

    with factory() as session:
        project = create_project(session, "KRAS", root_path=str(tmp_path))
        protocol = freeze_protocol(
            session,
            project.id,
            {"target_gene": "KRAS", "data_path": "data.h5ad"},
        )
        run = open_stage_run(
            session, project_id=project.id, protocol=protocol, input_path=data_file
        )
        session.commit()
        run_id = run.id
        proj_id = project.id

    return db_path, factory, run_id, proj_id


def test_gallery_empty_run(tmp_path: Path):
    _, factory, run_id, _ = _setup_stage(tmp_path)
    with factory() as session:
        data = get_stage_gallery(session, run_id)
        assert data["run_id"] == run_id
        assert data["figures"] == []
        assert data["total_figures"] == 0
        assert data["available_count"] == 0
        assert data["not_estimable_count"] == 0
        sc = data["scientific_status"]
        assert sc["calibration_status"] == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"
        assert sc["associated"] is False


def test_gallery_with_figures_and_formats(tmp_path: Path):
    _, factory, run_id, _ = _setup_stage(tmp_path)
    with factory() as session:
        job1 = Job(
            stage_run_id=run_id,
            task_id="formal_part2_figures",
            job_status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )
        job2 = Job(
            stage_run_id=run_id,
            task_id="formal_part1_grid",
            job_status="COMPLETED",
            created_at=datetime.now(timezone.utc),
        )
        session.add_all([job1, job2])
        session.flush()

        session.add_all(
            [
                Artifact(
                    job_id=job1.id,
                    relative_path="formal_part2_figures/F02_01_KRAS_umap_counts.png",
                    content_hash="hash_p2_png",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job1.id,
                    relative_path="formal_part2_figures/F02_01_KRAS_umap_counts.svg",
                    content_hash="hash_p2_svg",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job1.id,
                    relative_path="formal_part2_figures/F02_01_KRAS_umap_counts.pdf",
                    content_hash="hash_p2_pdf",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job1.id,
                    relative_path="formal_part2_figures/F02_01_KRAS_umap_counts.parameters.json",
                    content_hash="hash_p2_json",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job1.id,
                    relative_path="formal_part2_figures/source_data/F02_01_KRAS_umap_counts.csv",
                    content_hash="hash_p2_csv",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job2.id,
                    relative_path="formal_part1_grid/leiden_resolution_overview.png",
                    content_hash="hash_p1_png",
                    artifact_status="VALID",
                ),
                Artifact(
                    job_id=job2.id,
                    relative_path="formal_part1_grid/Leiden_resolution_overview.csv",
                    content_hash="hash_p1_csv",
                    artifact_status="VALID",
                ),
            ]
        )
        session.commit()

        data = get_stage_gallery(session, run_id)
        assert data["total_figures"] == 2
        assert data["available_count"] == 2
        assert data["not_estimable_count"] == 0

        p2_item = next(f for f in data["figures"] if f["stage_part"] == "Part 2")
        assert p2_item["panel_id"] == "F02_01"
        assert p2_item["format_png"] == "formal_part2_figures/F02_01_KRAS_umap_counts.png"
        assert p2_item["format_svg"] == "formal_part2_figures/F02_01_KRAS_umap_counts.svg"
        assert p2_item["format_pdf"] == "formal_part2_figures/F02_01_KRAS_umap_counts.pdf"
        assert (
            p2_item["source_data"] == "formal_part2_figures/source_data/F02_01_KRAS_umap_counts.csv"
        )
        assert (
            p2_item["parameters"] == "formal_part2_figures/F02_01_KRAS_umap_counts.parameters.json"
        )
        assert p2_item["content_hash"] == "hash_p2_png"

        p1_item = next(f for f in data["figures"] if f["stage_part"] == "Part 1")
        assert p1_item["panel_id"] == "F01_grid"
        assert p1_item["format_png"] == "formal_part1_grid/leiden_resolution_overview.png"
        assert p1_item["source_data"] == "formal_part1_grid/Leiden_resolution_overview.csv"


def test_gallery_preserves_not_estimable_slots(tmp_path: Path):
    _, factory, run_id, _ = _setup_stage(tmp_path)
    with factory() as session:
        from stagecraft_studio.db.models import StageRun

        run = session.get(StageRun, run_id)
        assert run is not None
        run.evidence_json = json.dumps(
            {
                "verdict": {
                    "stopped": "NOT_ESTIMABLE",
                    "eligibility": "NOT_ESTIMABLE",
                    "arm": "Basal",
                    "reasons": ["LOW_N", "NO_EXPOSURE_RANGE"],
                },
                "part4": {
                    "stopped": "NO_PART4",
                    "reason": "LINEAGE_ROUND_LIMIT",
                },
            }
        )
        session.add(
            RuleResultRow(
                stage_run_id=run_id,
                rule_id="DESIGN_ESTIMABLE",
                rule_status="BLOCK",
                detail_json=json.dumps({"arm": "Luminal", "reason": "RANK_DEFICIENT"}),
                checked_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        data = get_stage_gallery(session, run_id)
        assert data["not_estimable_count"] >= 3
        not_est = [f for f in data["figures"] if f["status"] == "NOT_ESTIMABLE"]
        assert len(not_est) >= 3

        part5_basal = next(f for f in not_est if "Basal" in f["title"])
        assert "LOW_N" in part5_basal["reasons"]
        assert part5_basal["panel_id"] == "F05_NOT_ESTIMABLE"

        part4_stopped = next(f for f in not_est if "Part 4" in f["title"])
        assert "LINEAGE_ROUND_LIMIT" in part4_stopped["reasons"]

        part5_luminal = next(f for f in not_est if "Luminal" in f["title"])
        assert "RANK_DEFICIENT" in part5_luminal["reasons"]


def test_gallery_api_and_raw_artifact_serving(tmp_path: Path):
    db_path, factory, run_id, _ = _setup_stage(tmp_path)

    stage_dir = tmp_path / "analysis" / f"stage_{run_id}"
    p2_dir = stage_dir / "formal_part2_figures"
    p2_dir.mkdir(parents=True, exist_ok=True)
    img_file = p2_dir / "F02_01_KRAS_umap_counts.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfake_png_data")

    app = create_app(
        token="test-token",
        port=8765,
        launch=LAUNCH,
        include_ui=False,
        database=db_path,
    )
    client = TestClient(app)

    # 1. Gallery view
    res = client.get(f"/api/stage-runs/{run_id}/gallery")
    assert res.status_code == 200
    payload = res.json()
    assert payload["run_id"] == run_id
    assert "scientific_status" in payload
    assert payload["scientific_status"]["calibration_status"] == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"

    # 2. 404 for missing run
    res_404 = client.get("/api/stage-runs/99999/gallery")
    assert res_404.status_code == 404

    # 3. Serve raw artifact
    res_raw = client.get(
        f"/api/stage-runs/{run_id}/artifacts/raw?rel=formal_part2_figures/F02_01_KRAS_umap_counts.png"
    )
    assert res_raw.status_code == 200
    assert res_raw.headers["content-type"] == "image/png"
    assert res_raw.content == b"\x89PNG\r\n\x1a\nfake_png_data"

    # 4. Raw artifact 404
    res_missing = client.get(
        f"/api/stage-runs/{run_id}/artifacts/raw?rel=formal_part2_figures/not_there.png"
    )
    assert res_missing.status_code == 404

    # 5. Raw artifact 403 on traversal attempt
    res_escape = client.get(f"/api/stage-runs/{run_id}/artifacts/raw?rel=../../secret.txt")
    assert res_escape.status_code == 403


def test_gallery_not_found_exception(tmp_path: Path):
    _, factory, _, _ = _setup_stage(tmp_path)
    with factory() as session, pytest.raises(GalleryNotFound):
        get_stage_gallery(session, 99999)
