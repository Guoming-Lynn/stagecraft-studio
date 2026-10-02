"""Tests verifying that re-running tasks marks prior Artifacts as SUPERSEDED."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, Job, StageRun
from stagecraft_studio.db.reviews import enqueue
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.engine.formal_launch import _SCRIPTS, FormalLaunch
from stagecraft_studio.worker.jobs import FormalWorker


def _setup_engine(root: Path) -> FormalLaunch:
    scripts_dir = root / "mock_scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    body = (
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
        "(args.out / 'loaded.h5ad').write_bytes(b'loaded_v1')\n"
        "(args.out / 'symbol_audit.csv').write_text('audit\\n', encoding='utf-8')\n"
    )
    for name in _SCRIPTS:
        (scripts_dir / name).write_text(body, encoding="utf-8")
    return FormalLaunch(python=Path(sys.executable), scripts_dir=scripts_dir)


def test_rerun_task_supersedes_prior_artifacts(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    upgrade_database(db)
    factory = session_factory(db)

    stage_root = tmp_path / "project"
    data_file = stage_root / "data" / "counts.h5ad"
    data_file.parent.mkdir(parents=True, exist_ok=True)
    data_file.write_bytes(b"counts-v1")

    doc = {
        "target_gene": "STAT1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "loose_min_genes": 200,
        "data_path": str(data_file),
        "libraries": [{"library_id": "L1", "dataset": "D1"}],
    }

    with factory() as session:
        project = create_project(session, "STAT1", root_path=str(stage_root))
        protocol = freeze_protocol(session, project.id, doc)
        run = open_stage_run(
            session, project_id=project.id, protocol=protocol, input_path=data_file
        )
        session.commit()
        run_id = run.id

    launch = _setup_engine(stage_root)
    worker = FormalWorker(database=db, launch=launch)

    fields = {
        "library_id": "L1",
        "input": str(data_file),
        "format": "h5ad",
        "out": str(stage_root),
    }

    import time

    worker.recover()
    worker.start()
    try:
        # 1. Enqueue Job 1
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job1 = enqueue(session, run, task_id="formal_part1_load", fields=fields)
            session.commit()
            job1_id = job1.id

        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job1_id)
                if j and j.job_status in {"COMPLETED", "FAILED"}:
                    break
            time.sleep(0.1)

        with factory() as session:
            j1 = session.get(Job, job1_id)
            assert j1 is not None and j1.job_status == "COMPLETED"
            arts1 = list(session.scalars(select(Artifact).where(Artifact.job_id == job1_id)).all())
            assert len(arts1) >= 2
            assert all(a.artifact_status == "VALID" for a in arts1)

        # 2. Enqueue Job 2 (rerun of same task formal_part1_load)
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job2 = enqueue(session, run, task_id="formal_part1_load", fields=fields)
            session.commit()
            job2_id = job2.id

        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job2_id)
                if j and j.job_status in {"COMPLETED", "FAILED"}:
                    break
            time.sleep(0.1)

        with factory() as session:
            j2 = session.get(Job, job2_id)
            assert j2 is not None and j2.job_status == "COMPLETED"

            # Check job 1 artifacts: must all be SUPERSEDED
            arts1_after = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job1_id)).all()
            )
            assert all(a.artifact_status == "SUPERSEDED" for a in arts1_after)

            # Check job 2 artifacts: must all be VALID
            arts2 = list(session.scalars(select(Artifact).where(Artifact.job_id == job2_id)).all())
            assert len(arts2) >= 2
            assert all(a.artifact_status == "VALID" for a in arts2)

            # Check that there are NO stale VALID artifacts for formal_part1_load from job 1
            valid_arts = list(
                session.scalars(
                    select(Artifact)
                    .join(Job, Artifact.job_id == Job.id)
                    .where(
                        Job.stage_run_id == run_id,
                        Job.task_id == "formal_part1_load",
                        Artifact.artifact_status == "VALID",
                    )
                ).all()
            )
            assert len(valid_arts) == len(arts2)
            assert all(a.job_id == job2_id for a in valid_arts)
    finally:
        worker.stop()
