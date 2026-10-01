"""Tests for the formal background worker."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, AuditEvent, Job, RuleResultRow, StageRun
from stagecraft_studio.db.reviews import enqueue
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.engine.formal_launch import _SCRIPTS, FormalLaunch
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.worker.jobs import FormalWorker

TOKEN = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"}
LAUNCH = EngineLaunch(python=Path("python"), script=Path("run_pipeline.py"))


def _setup_engine(root: Path, *, script_body: str | None = None) -> FormalLaunch:
    scripts_dir = root / "mock_scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    body = (
        script_body
        if script_body is not None
        else (
            "import argparse, pathlib\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--library-id')\n"
            "parser.add_argument('--input')\n"
            "parser.add_argument('--format')\n"
            "parser.add_argument('--source')\n"
            "parser.add_argument('--loaded')\n"
            "parser.add_argument('--config')\n"
            "parser.add_argument('--out', type=pathlib.Path, required=True)\n"
            "args, _ = parser.parse_known_args()\n"
            "args.out.mkdir(parents=True, exist_ok=True)\n"
            "(args.out / 'loaded.h5ad').write_bytes(b'loaded')\n"
            "(args.out / 'symbol_audit.csv').write_text('audit\\n', encoding='utf-8')\n"
            "(args.out / 'qc_record.json').write_text('{\"pass\": true}\\n', encoding='utf-8')\n"
        )
    )
    for name in _SCRIPTS:
        (scripts_dir / name).write_text(body, encoding="utf-8")
    return FormalLaunch(python=Path(sys.executable), scripts_dir=scripts_dir)


def _setup_run(
    db_path: Path, stage_root: Path
) -> tuple[int, int, Path, dict[str, object], FormalWorker]:
    upgrade_database(db_path)
    factory = session_factory(db_path)
    data_file = stage_root / "data" / "counts.h5ad"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_bytes(b"counts-v1")

    doc = {
        "target_gene": "GENE1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "loose_min_genes": 200,
        "data_path": str(data_file),
        "libraries": [{"library_id": "L1", "dataset": "D1"}],
    }
    with factory() as session:
        project = create_project(session, "test_proj", root_path=str(stage_root))
        protocol = freeze_protocol(session, project.id, doc)
        run = open_stage_run(
            session, project_id=project.id, protocol=protocol, input_path=data_file
        )
        session.commit()
        project_id = project.id
        run_id = run.id

    launch = _setup_engine(stage_root)
    worker = FormalWorker(database=db_path, launch=launch)
    return project_id, run_id, data_file, doc, worker


def test_queued_job_executes_and_registers_artifacts(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    _p_id, run_id, data_file, _doc, worker = _setup_run(db, stage_root)

    factory = session_factory(db)
    fields = {
        "library_id": "L1",
        "input": str(data_file),
        "format": "h5ad",
        "out": str(stage_root),
    }
    with factory() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        job = enqueue(session, run, task_id="formal_part1_load", fields=fields)
        session.commit()
        job_id = job.id

    worker.recover()
    worker.start()
    try:
        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job_id)
                if j and j.job_status in {"COMPLETED", "FAILED"}:
                    break
            time.sleep(0.1)

        with factory() as session:
            final_job = session.get(Job, job_id)
            assert final_job is not None
            assert final_job.job_status == "COMPLETED"

            artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job_id)).all()
            )
            assert len(artifacts) >= 2
            paths = {a.relative_path for a in artifacts}
            assert "formal_part1_load/loaded.h5ad" in paths
            assert "formal_part1_load/symbol_audit.csv" in paths
            for a in artifacts:
                assert a.artifact_status == "VALID"
                assert len(a.content_hash) == 64

        dest_dir = stage_root / "analysis" / f"stage_{run_id}" / "formal_part1_load"
        assert (dest_dir / "loaded.h5ad").is_file()
        assert (dest_dir / "symbol_audit.csv").is_file()
    finally:
        worker.stop()


def test_exit_zero_missing_contract_fails(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    _p_id, run_id, data_file, _doc, _ = _setup_run(db, stage_root)

    empty_launch = _setup_engine(stage_root, script_body="import sys\nsys.exit(0)\n")
    worker = FormalWorker(database=db, launch=empty_launch)

    factory = session_factory(db)
    fields = {
        "library_id": "L1",
        "input": str(data_file),
        "format": "h5ad",
        "out": str(stage_root),
    }
    with factory() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        job = enqueue(session, run, task_id="formal_part1_load", fields=fields)
        session.commit()
        job_id = job.id

    worker.start()
    try:
        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job_id)
                if j and j.job_status in {"COMPLETED", "FAILED"}:
                    break
            time.sleep(0.1)

        with factory() as session:
            final_job = session.get(Job, job_id)
            assert final_job is not None
            assert final_job.job_status == "FAILED"
            payload = json.loads(final_job.payload_json)
            assert payload.get("failure_reason") == "OUTPUT_CONTRACT_MISSING"

            artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job_id)).all()
            )
            assert len(artifacts) == 0

        dest_dir = stage_root / "analysis" / f"stage_{run_id}" / "formal_part1_load"
        assert not dest_dir.exists()
    finally:
        worker.stop()


def test_job_cancelled_kills_process_and_cleans_tmp(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    _p_id, run_id, data_file, _doc, _ = _setup_run(db, stage_root)

    sleep_body = "import time\ntime.sleep(15)\n"
    sleep_launch = _setup_engine(stage_root, script_body=sleep_body)
    worker = FormalWorker(database=db, launch=sleep_launch)

    factory = session_factory(db)
    fields = {
        "library_id": "L1",
        "input": str(data_file),
        "format": "h5ad",
        "out": str(stage_root),
    }
    with factory() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        job = enqueue(session, run, task_id="formal_part1_load", fields=fields)
        session.commit()
        job_id = job.id

    worker.start()
    try:
        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job_id)
                if j and j.job_status == "RUNNING":
                    break
            time.sleep(0.05)

        res = worker.cancel(job_id)
        assert res["job_status"] == "CANCELLED"

        with factory() as session:
            final_job = session.get(Job, job_id)
            assert final_job is not None
            assert final_job.job_status == "CANCELLED"

        tmp_dir = stage_root / "analysis" / f"stage_{run_id}" / ".studio" / "tmp" / str(job_id)
        assert not tmp_dir.exists()
        dest_dir = stage_root / "analysis" / f"stage_{run_id}" / "formal_part1_load"
        assert not dest_dir.exists()
    finally:
        worker.stop()


def test_startup_recovery_interrupted(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    project_id, run_id, _data_file, _doc, worker = _setup_run(db, stage_root)

    factory = session_factory(db)
    with factory() as session:
        job = Job(
            stage_run_id=run_id,
            task_id="formal_part1_load",
            job_status="RUNNING",
            payload_json=json.dumps({"fields": {}}),
            created_at=session.get(StageRun, run_id).created_at,  # type: ignore[union-attr]
        )
        session.add(job)
        session.commit()
        job_id = job.id

    tmp_dir = stage_root / "analysis" / f"stage_{run_id}" / ".studio" / "tmp" / str(job_id)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    (tmp_dir / "leftover.txt").write_text("leftover", encoding="utf-8")

    worker.recover()

    with factory() as session:
        recovered_job = session.get(Job, job_id)
        assert recovered_job is not None
        assert recovered_job.job_status == "INTERRUPTED"

        audits = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.action == "formal_job_recovery",
                )
            ).all()
        )
        assert len(audits) >= 1
        assert audits[0].outcome == "INTERRUPTED"

    assert not tmp_dir.exists()


def test_protocol_hash_change_blocks_job(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    _p_id, run_id, data_file, _doc, worker = _setup_run(db, stage_root)

    factory = session_factory(db)
    fields = {
        "library_id": "L1",
        "input": str(data_file),
        "format": "h5ad",
        "out": str(stage_root),
    }
    with factory() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        job = enqueue(session, run, task_id="formal_part1_load", fields=fields)
        session.commit()
        job_id = job.id

    # Alter data_file bytes to make input_hash mismatch
    data_file.write_bytes(b"corrupted-or-modified-after-freeze")

    worker.start()
    try:
        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job_id)
                if j and j.job_status in {"COMPLETED", "FAILED"}:
                    break
            time.sleep(0.05)

        with factory() as session:
            final_job = session.get(Job, job_id)
            assert final_job is not None
            assert final_job.job_status == "FAILED"
            payload = json.loads(final_job.payload_json)
            assert payload.get("failure_reason") == "PROTOCOL_HASH_MATCH"

            blocks = list(
                session.scalars(
                    select(RuleResultRow).where(
                        RuleResultRow.stage_run_id == run_id,
                        RuleResultRow.rule_id == "PROTOCOL_HASH_MATCH",
                    )
                ).all()
            )
            assert len(blocks) >= 1
            assert blocks[0].rule_status == "BLOCK"
    finally:
        worker.stop()


def test_api_jobs_and_cancellation(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    _p_id, run_id, data_file, _doc, _ = _setup_run(db, stage_root)

    sleep_body = "import time\ntime.sleep(15)\n"
    sleep_launch = _setup_engine(stage_root, script_body=sleep_body)
    worker = FormalWorker(database=db, launch=sleep_launch)
    worker.start()

    app = create_app(
        "secret-token",
        port=8765,
        launch=LAUNCH,
        state_path=tmp_path / "runs.json",
        include_ui=False,
        database=db,
        formal_worker=worker,
    )
    client = TestClient(app)

    try:
        post_resp = client.post(
            f"/api/stage-runs/{run_id}/jobs",
            headers=TOKEN,
            json={
                "task_id": "formal_part1_load",
                "reuse_umap": False,
                "fields": {
                    "library_id": "L1",
                    "input": str(data_file),
                    "format": "h5ad",
                    "out": str(stage_root),
                },
            },
        )
        assert post_resp.status_code == 201
        job_id = post_resp.json()["id"]

        list_resp = client.get(f"/api/stage-runs/{run_id}/jobs")
        assert list_resp.status_code == 200
        jobs_list = list_resp.json()
        assert len(jobs_list) >= 1
        assert any(item["id"] == job_id for item in jobs_list)

        cancel_resp = client.post(f"/api/jobs/{job_id}/cancel", headers=TOKEN)
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["job_status"] == "CANCELLED"
    finally:
        worker.stop()
