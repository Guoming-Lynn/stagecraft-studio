"""Tests for formal_part1_lock task lifecycle, gating, and rules."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Job
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


def _setup(tmp_path: Path) -> tuple[TestClient, int, str]:
    db_path = tmp_path / "studio.sqlite"
    upgrade_database(db_path)
    factory = session_factory(db_path)
    with factory() as session:
        project = create_project(session, name="Lock Gate Test", root_path=str(tmp_path))
        doc = protocol_document(
            target_gene="STAT1",
            species="human",
            manifest=[{"library_id": "A", "dataset": "D1"}],
            qc={"loose_min_genes": 200},
            harmony_keys=["dataset"],
        )
        source = tmp_path / "counts.h5ad"
        source.write_bytes(b"counts-placeholder")
        protocol = freeze_protocol(session, project_id=project.id, document=doc)
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
        raw_evidence = json.dumps(
            {
                "overview": [
                    {
                        "resolution": "0.4",
                        "n_clusters": 2,
                        "min_cluster_size": 50,
                        "max_cluster_size": 150,
                    }
                ],
                "clusters": ["0", "1"],
                "clusters_by_resolution": {"0.4": ["0", "1"]},
                "genes": [{"gene": "STAT1", "expression": [1.5, 0.2]}],
            }
        )
        run.evidence_json = raw_evidence
        run.leiden_ids_json = json.dumps(["0", "1"])
        session.commit()
        run_id = run.id
        digest = evidence_digest(raw_evidence)

    app = create_app(
        "secret-token",
        port=8765,
        launch=LAUNCH,
        database=db_path,
    )
    return TestClient(app), run_id, digest


def test_lock_requires_resolution_and_clusters(tmp_path: Path) -> None:
    client, run_id, digest = _setup(tmp_path)

    # 1. Enqueue formal_part1_lock before resolution review -> rejected
    denied_res = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_lock"},
    )
    assert denied_res.status_code == 409
    assert denied_res.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"

    # Submit resolution review
    res_resp = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-02",
            "rationale": "Clear split",
            "evidence_hash": digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert res_resp.status_code == 201

    # 2. Enqueue formal_part1_lock before cluster review -> rejected
    denied_clu = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_lock"},
    )
    assert denied_clu.status_code == 409
    assert denied_clu.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"


def test_lock_rejects_delete_action(tmp_path: Path) -> None:
    client, run_id, digest = _setup(tmp_path)

    resolution = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-02",
            "rationale": "Clear split",
            "evidence_hash": digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert resolution.status_code == 201
    _complete_review_tables(tmp_path / "studio.sqlite", run_id)

    # Submit cluster review with DELETE
    clu_resp = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "rows": [
                {
                    "cluster": "0",
                    "decision": "DELETE",
                    "rationale": "Low quality doublet",
                    "reviewer": "Lin",
                    "decided_on": "2026-10-02",
                    "name": "",
                },
                {
                    "cluster": "1",
                    "decision": "KEEP",
                    "rationale": "Real cluster",
                    "reviewer": "Lin",
                    "decided_on": "2026-10-02",
                    "name": "",
                },
            ],
        },
    )
    assert clu_resp.status_code == 201

    # 3. Enqueue formal_part1_lock with DELETE in review -> rejected
    denied = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_lock"},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["rule_id"] == "DELETE_RECOMPUTE_REQUIRED"


def test_post_lock_tasks_require_completed_lock(tmp_path: Path) -> None:
    client, run_id, digest = _setup(tmp_path)

    resolution = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-02",
            "rationale": "Clear split",
            "evidence_hash": digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert resolution.status_code == 201
    _complete_review_tables(tmp_path / "studio.sqlite", run_id)
    cluster_rows = [
        {
            "cluster": cluster,
            "decision": "KEEP",
            "rationale": "Good",
            "reviewer": "Lin",
            "decided_on": "2026-10-02",
            "name": "",
        }
        for cluster in ("0", "1")
    ]
    reviewed = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "rows": cluster_rows,
        },
    )
    assert reviewed.status_code == 201
    named = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "rows": [
                {**cluster_rows[0], "name": "T_cell"},
                {**cluster_rows[1], "name": "B_cell"},
            ],
        },
    )
    assert named.status_code == 201

    # 4. Enqueue post-lock tasks before lock completed -> rejected
    for task in ["formal_part2_survey", "formal_part3_recluster", "formal_part5_prepare"]:
        denied = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN,
            json={"task_id": task},
        )
        assert denied.status_code == 409
        assert denied.json()["detail"]["rule_id"] == "LOCKED_ATLAS_REQUIRED"

    # 5. Enqueue formal_part1_lock -> succeeds
    enqueued = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_lock"},
    )
    assert enqueued.status_code == 201

    # Simulate formal_part1_lock completion
    factory = session_factory(tmp_path / "studio.sqlite")
    with factory() as session:
        job = session.get(Job, enqueued.json()["id"])
        assert job is not None
        job.job_status = "COMPLETED"
        session.commit()

    # 6. Post-lock tasks can now be enqueued
    allowed_p2 = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part2_survey"},
    )
    assert allowed_p2.status_code == 201


def _complete_review_tables(database: Path, run_id: int) -> None:
    with session_factory(database)() as session:
        job = session.scalar(
            select(Job)
            .where(Job.stage_run_id == run_id, Job.task_id == "formal_part1_review_tables")
            .order_by(Job.id.desc())
        )
        assert job is not None
        job.job_status = "COMPLETED"
        session.commit()
