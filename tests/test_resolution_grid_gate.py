"""Test that resolution review is rejected when grid output is missing."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import ReviewDecision, StageRun
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


def test_resolution_review_rejected_without_clusters_by_resolution(tmp_path: Path) -> None:
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
        # overview is present, but clusters_by_resolution is missing
        run.evidence_json = json.dumps(
            {
                "overview": [
                    {
                        "resolution": "0.4",
                        "n_clusters": 2,
                        "min_cluster_size": 10,
                        "max_cluster_size": 20,
                    }
                ]
            }
        )
        session.commit()
        run_id = run.id
        digest = evidence_digest(run.evidence_json)

    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    client = TestClient(app)

    res = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "testing rejection when cluster map is missing",
            "evidence_hash": digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert res.status_code == 400
    assert res.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"


def test_resolution_normalized_canonical_string_match(tmp_path: Path) -> None:
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
        run.evidence_json = json.dumps(
            {
                "overview": [
                    {
                        "resolution": "0.2",
                        "n_clusters": 2,
                        "min_cluster_size": 10,
                        "max_cluster_size": 20,
                    }
                ],
                "clusters_by_resolution": {
                    "0.2": ["0", "1"],
                },
            }
        )
        session.commit()
        run_id = run.id
        digest = evidence_digest(run.evidence_json)

    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    client = TestClient(app)

    # Submit "0.20" which normalizes to canonical "0.2"
    res = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "normalized canonical match",
            "evidence_hash": digest,
            "resolution": "0.20",
            "blinding": "BLIND",
        },
    )
    assert res.status_code == 201
    dec_id = res.json()["id"]
    with session_factory(database)() as session:
        stored_run = session.get(StageRun, run_id)
        assert stored_run is not None
        assert json.loads(stored_run.leiden_ids_json) == ["0", "1"]
        dec = session.get(ReviewDecision, dec_id)
        assert dec is not None
        body = json.loads(dec.body_json)
        assert body["resolution"] == "0.2"
        assert body["leiden_ids"] == ["0", "1"]

    # Invalid resolution "0.25" is rejected
    invalid_res = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "invalid resolution",
            "evidence_hash": digest,
            "resolution": "0.25",
            "blinding": "BLIND",
        },
    )
    assert invalid_res.status_code == 400
    assert invalid_res.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
