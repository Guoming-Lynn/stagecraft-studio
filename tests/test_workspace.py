"""Test Stage Workspace 5-tab view aggregation and API endpoint."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, Job, RuleResultRow
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.db.workspace import WorkspaceNotFound, get_stage_workspace
from stagecraft_studio.engine.launch import EngineLaunch

LAUNCH = EngineLaunch(python=Path(sys.executable), script=Path("run_pipeline.py"))


def test_get_stage_workspace_aggregates_all_tabs(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    data_file = tmp_path / "counts.h5ad"
    data_file.write_text("dummy", encoding="utf-8")

    doc = {
        "target_gene": "STAT1",
        "species": "human",
        "data_path": str(data_file),
        "harmony_keys": ["dataset"],
    }

    with factory() as session:
        proj = create_project(session, "test_proj")
        proto = freeze_protocol(session, proj.id, doc)
        run = open_stage_run(session, project_id=proj.id, protocol=proto, input_path=data_file)
        run.evidence_json = json.dumps(
            {
                "verdict": {
                    "stopped": "FROZEN_PASS",
                    "target_gene": "STAT1",
                    "associated": True,
                    "holdout": "source_block_recorded",
                    "fitted": True,
                    "model": "limma_voom",
                    "claims_limma": True,
                }
            }
        )
        session.commit()
        run_id = run.id

        job = Job(
            stage_run_id=run_id,
            task_id="formal_part1_load",
            job_status="COMPLETED",
            payload_json=json.dumps({"fields": {"library_id": "L1", "format": "h5ad"}}),
            created_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()

        art = Artifact(
            job_id=job.id,
            relative_path="formal_part1_load/loaded.h5ad",
            content_hash="abc123hash",
            artifact_status="VALID",
        )
        session.add(art)

        rule = RuleResultRow(
            stage_run_id=run_id,
            rule_id="INPUT_COUNTS_VALID",
            rule_status="PASS",
            detail_json=json.dumps({"library_id": "L1", "verified": True}),
            checked_at=datetime.now(timezone.utc),
        )
        session.add(rule)
        session.commit()

        ws = get_stage_workspace(session, run_id)

    # 1. Inputs
    assert ws["id"] == run_id
    assert ws["inputs"]["target_gene"] == "STAT1"
    assert ws["inputs"]["species"] == "human"

    # 2. Parameters
    assert len(ws["parameters"]) == 1
    assert ws["parameters"][0]["task_id"] == "formal_part1_load"
    assert ws["parameters"][0]["fields"]["library_id"] == "L1"

    # 3. Results
    assert ws["results"]["scientific_status"]["scientific_status"] == "FROZEN_PASS"
    assert ws["results"]["scientific_status"]["associated"] is True
    assert ws["results"]["scientific_status"]["claims_limma"] is True
    assert len(ws["results"]["artifacts"]) == 1
    assert ws["results"]["artifacts"][0]["relative_path"] == "formal_part1_load/loaded.h5ad"

    # 4. Checks
    assert len(ws["checks"]) == 1
    assert ws["checks"][0]["rule_id"] == "INPUT_COUNTS_VALID"
    assert ws["checks"][0]["rule_status"] == "PASS"

    # 5. Logs
    assert len(ws["logs"]) == 1
    assert ws["logs"][0]["task_id"] == "formal_part1_load"
    assert ws["logs"][0]["job_status"] == "COMPLETED"


def test_get_stage_workspace_not_found(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    upgrade_database(db_path)
    factory = session_factory(db_path)
    with factory() as session, pytest.raises(WorkspaceNotFound):
        get_stage_workspace(session, 99999)


def test_workspace_api_endpoint(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    data_file = tmp_path / "counts.h5ad"
    data_file.write_text("dummy", encoding="utf-8")

    doc = {"target_gene": "STAT1", "species": "human", "data_path": str(data_file)}
    with factory() as session:
        proj = create_project(session, "test_proj")
        proto = freeze_protocol(session, proj.id, doc)
        run = open_stage_run(session, project_id=proj.id, protocol=proto, input_path=data_file)
        session.commit()
        run_id = run.id

    app = create_app("test-token", port=8765, launch=LAUNCH, database=db_path)
    client = TestClient(app)

    res = client.get(f"/api/stage-runs/{run_id}/workspace")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == run_id
    assert "inputs" in data
    assert "parameters" in data
    assert "results" in data
    assert "checks" in data
    assert "logs" in data

    res404 = client.get("/api/stage-runs/99999/workspace")
    assert res404.status_code == 404
