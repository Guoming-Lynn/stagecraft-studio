"""Chain test from Part 1 to Part 3 through Studio worker."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, AuditEvent, Job, StageRun
from stagecraft_studio.db.reviews import evidence_digest
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.engine.formal_contract import FORMAL_OUTPUT_CONTRACTS
from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.worker.jobs import FormalWorker

from tests.fakes import write_fake_formal_scripts

TOKEN_HEADERS = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"}
LAUNCH = EngineLaunch(python=Path(sys.executable), script=Path("run_pipeline.py"))


def _wait_for_jobs(db_path: Path, job_ids: list[int], timeout: float = 10.0) -> None:
    factory = session_factory(db_path)
    deadline = time.time() + timeout
    while time.time() < deadline:
        with factory() as session:
            jobs = [session.get(Job, jid) for jid in job_ids]
            if all(
                j is not None and j.job_status in {"COMPLETED", "FAILED", "CANCELLED"} for j in jobs
            ):
                return
        time.sleep(0.05)
    raise TimeoutError(f"Jobs did not finish within {timeout}s: {job_ids}")


def test_formal_chain_part1_to_part3_e2e(tmp_path: Path) -> None:
    db_path = tmp_path / "studio.sqlite"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)
    counts_file = project_root / "counts.h5ad"
    counts_file.write_bytes(b"counts-chain-synthetic-data")

    # Inputs required for Part 1 and Part 3
    qc_config = project_root / "qc_config.json"
    qc_config.write_text('{"min_genes": 200}\n', encoding="utf-8")
    manifest = project_root / "manifest.json"
    manifest.write_text('{"libraries": ["L1", "L2"]}\n', encoding="utf-8")
    grid_config = project_root / "grid_config.json"
    grid_config.write_text('{"resolutions": ["0.4", "0.8"]}\n', encoding="utf-8")
    barcodes_file = project_root / "barcodes.tsv"
    barcodes_file.write_text("barcode_1\nbarcode_2\n", encoding="utf-8")

    scripts_dir = tmp_path / "formal_scripts"
    write_fake_formal_scripts(scripts_dir)
    formal_launch = FormalLaunch(python=Path(sys.executable), scripts_dir=scripts_dir)

    worker = FormalWorker(database=db_path, launch=formal_launch)
    worker.start()

    app = create_app(
        "secret-token",
        port=8765,
        launch=LAUNCH,
        database=db_path,
        formal_worker=worker,
    )
    client = TestClient(app)

    try:
        # 1. Direct API call bypassing frontend - security and validation gates
        assert (
            client.post("/api/stage-runs/1/jobs", json={"task_id": "formal_part1_load"}).status_code
            == 401
        )
        bad_origin = client.post(
            "/api/stage-runs/1/jobs",
            headers={"origin": "http://evil.com", "x-stagecraft-token": "secret-token"},
            json={"task_id": "formal_part1_load"},
        )
        assert bad_origin.status_code == 403

        # 2. Freeze protocol via API
        freeze_resp = client.post(
            "/api/protocol/freeze",
            headers=TOKEN_HEADERS,
            json={
                "target_gene": "STAT1",
                "species": "human",
                "harmony_keys": ["dataset"],
                "loose_min_genes": 200,
                "data_path": str(counts_file),
                "libraries": [
                    {"library_id": "L1", "dataset": "D1"},
                    {"library_id": "L2", "dataset": "D2"},
                ],
            },
        )
        assert freeze_resp.status_code == 201
        run_id = freeze_resp.json()["stage_run_id"]
        assert run_id > 0

        # 3. Direct API call bypassing frontend: unknown task, non-formal task, extra fields
        bad_task = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_not_exist", "fields": {}},
        )
        assert bad_task.status_code == 422
        assert bad_task.json()["detail"]["rule_id"] == "TASK_NOT_REGISTERED"

        non_formal = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "quicklook_run", "fields": {}},
        )
        assert non_formal.status_code == 422
        assert non_formal.json()["detail"]["rule_id"] == "TASK_NOT_FORMAL"

        extra_fields = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_part1_load", "bogus": "value", "fields": {}},
        )
        assert extra_fields.status_code == 422

        recluster_fields = {
            "input": str(counts_file),
            "barcodes": str(barcodes_file),
            "gene": "STAT1",
            "lineage": "myeloid",
            "seed": 42,
            "completed_rounds": 1,
            "still_mixed": False,
            "out": str(project_root),
        }

        # 4. Enqueueing Part 3 recluster directly without review must be rejected
        unreviewed = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_part3_recluster", "fields": recluster_fields},
        )
        assert unreviewed.status_code == 409
        assert unreviewed.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"

        with factory() as session:
            audits = list(
                session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.action == "job_enqueue",
                        AuditEvent.outcome == "REJECTED",
                    )
                ).all()
            )
            assert len(audits) >= 3

        # 5. Enqueue Part 1 four tasks: load, qc, merge, grid
        j1 = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={
                "task_id": "formal_part1_load",
                "fields": {
                    "library_id": "L1",
                    "input": str(counts_file),
                    "format": "h5ad",
                    "out": str(project_root),
                },
            },
        )
        assert j1.status_code == 201
        job1_id = j1.json()["id"]

        j2 = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={
                "task_id": "formal_part1_qc",
                "fields": {
                    "library_id": "L1",
                    "source": str(project_root),
                    "loaded": str(counts_file),
                    "config": str(qc_config),
                    "out": str(project_root),
                },
            },
        )
        assert j2.status_code == 201
        job2_id = j2.json()["id"]

        j3 = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={
                "task_id": "formal_part1_merge",
                "fields": {"manifest": str(manifest), "gene": "STAT1", "out": str(project_root)},
            },
        )
        assert j3.status_code == 201
        job3_id = j3.json()["id"]

        j4 = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={
                "task_id": "formal_part1_grid",
                "fields": {
                    "common": str(counts_file),
                    "gene": "STAT1",
                    "config": str(grid_config),
                    "out": str(project_root),
                },
            },
        )
        assert j4.status_code == 201
        job4_id = j4.json()["id"]

        # Wait for Part 1 tasks to execute and complete
        part1_ids = [job1_id, job2_id, job3_id, job4_id]
        _wait_for_jobs(db_path, part1_ids)

        stage_dir = project_root / "analysis" / f"stage_{run_id}"
        with factory() as session:
            for jid in part1_ids:
                j = session.get(Job, jid)
                assert j is not None
                assert j.job_status == "COMPLETED"

                # Check artifacts
                artifacts = list(
                    session.scalars(select(Artifact).where(Artifact.job_id == jid)).all()
                )
                expected_files = FORMAL_OUTPUT_CONTRACTS[j.task_id]
                assert len(artifacts) == len(expected_files)
                for a in artifacts:
                    assert a.artifact_status == "VALID"
                    assert len(a.content_hash) == 64
                    disk_file = stage_dir / a.relative_path
                    assert disk_file.is_file()

        # 6. Simulate grid evidence and submit fixture human decisions
        evidence = {
            "overview": [
                {
                    "resolution": "0.4",
                    "n_clusters": 2,
                    "min_cluster_size": 50,
                    "max_cluster_size": 150,
                }
            ],
            "clusters": ["0", "1"],
            "genes": [{"gene": "STAT1", "expression": [1.5, 0.2]}],
        }
        raw_evidence = json.dumps(evidence)
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            run.evidence_json = raw_evidence
            run.leiden_ids_json = json.dumps(["0", "1"])
            session.commit()

        evidence_hash = evidence_digest(raw_evidence)

        # Still rejected before resolution review
        unreviewed_again = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_part3_recluster", "fields": recluster_fields},
        )
        assert unreviewed_again.status_code == 409
        assert unreviewed_again.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"

        # Submit resolution decision (fixture human decision)
        res_resp = client.post(
            f"/api/stage-runs/{run_id}/resolution",
            headers=TOKEN_HEADERS,
            json={
                "reviewer": "GuomingLin",
                "decided_on": "2026-10-01",
                "rationale": "FIXTURE_HUMAN_DECISION: separates clusters cleanly",
                "evidence_hash": evidence_hash,
                "resolution": "0.4",
                "blinding": "BLIND",
            },
        )
        assert res_resp.status_code == 201

        # Still rejected before cluster review
        before_clusters = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_part3_recluster", "fields": recluster_fields},
        )
        assert before_clusters.status_code == 409
        assert before_clusters.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"

        # Submit cluster review decision (fixture human decision)
        clu_resp = client.post(
            f"/api/stage-runs/{run_id}/clusters",
            headers=TOKEN_HEADERS,
            json={
                "blinding": "NOT_APPLICABLE",
                "rows": [
                    {
                        "cluster": "0",
                        "decision": "KEEP",
                        "rationale": "FIXTURE_HUMAN_DECISION: primary myeloid",
                        "reviewer": "GuomingLin",
                        "decided_on": "2026-10-01",
                        "name": "Myeloid_0",
                    },
                    {
                        "cluster": "1",
                        "decision": "KEEP",
                        "rationale": "FIXTURE_HUMAN_DECISION: primary lymphoid",
                        "reviewer": "GuomingLin",
                        "decided_on": "2026-10-01",
                        "name": "Lymphoid_1",
                    },
                ],
            },
        )
        assert clu_resp.status_code == 201

        # 7. Enqueue Part 3 recluster after reviews
        j5 = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN_HEADERS,
            json={"task_id": "formal_part3_recluster", "fields": recluster_fields},
        )
        assert j5.status_code == 201
        job5_id = j5.json()["id"]

        # Wait for Part 3 job to complete
        _wait_for_jobs(db_path, [job5_id])

        with factory() as session:
            j = session.get(Job, job5_id)
            assert j is not None
            assert j.job_status == "COMPLETED"

            artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job5_id)).all()
            )
            assert len(artifacts) == 1
            assert artifacts[0].artifact_status == "VALID"
            assert len(artifacts[0].content_hash) == 64
            assert (stage_dir / artifacts[0].relative_path).is_file()

        # 8. Query job list via API
        list_resp = client.get(f"/api/stage-runs/{run_id}/jobs")
        assert list_resp.status_code == 200
        jobs_data = list_resp.json()
        assert len(jobs_data) == 5
        assert [item["id"] for item in jobs_data] == [job1_id, job2_id, job3_id, job4_id, job5_id]
        assert all(item["job_status"] == "COMPLETED" for item in jobs_data)
        assert [item["task_id"] for item in jobs_data] == [
            "formal_part1_load",
            "formal_part1_qc",
            "formal_part1_merge",
            "formal_part1_grid",
            "formal_part3_recluster",
        ]
    finally:
        worker.stop()
