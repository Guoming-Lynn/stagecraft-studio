"""Test that resolution review is rejected when grid output is missing."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.reviews import evidence_digest
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.domain.protocol import protocol_document
from stagecraft_studio.engine.launch import EngineLaunch

TOKEN = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"}
LAUNCH = EngineLaunch(python=Path("python"), script=Path("run_pipeline.py"))


def test_resolution_review_rejected_without_grid_output(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    with session_factory(database)() as session:
        project = create_project(session, "plaque")
        protocol = freeze_protocol(
            session,
            project.id,
            protocol_document(
                target_gene="STAT1",
                species="human",
                manifest=[{"library_id": "A", "dataset": "D1"}],
                qc={"loose_min_genes": 200},
                harmony_keys=["dataset"],
            ),
        )
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
        run.evidence_json = json.dumps({"genes": []})
        session.commit()
        run_id = run.id
        empty_digest = evidence_digest(run.evidence_json)

    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    client = TestClient(app)

    res = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "marker panel separates the monocyte cloud",
            "evidence_hash": empty_digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
