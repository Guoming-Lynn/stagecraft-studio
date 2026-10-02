"""Test for worker cancel vs publish race condition."""

from __future__ import annotations

import sys
import time
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
        "(args.out / 'loaded.h5ad').write_bytes(b'loaded')\n"
        "(args.out / 'symbol_audit.csv').write_text('audit\\n', encoding='utf-8')\n"
        "(args.out / 'qc_record.json').write_text('{\"pass\": true}\\n', encoding='utf-8')\n"
    )
    for name in _SCRIPTS:
        (scripts_dir / name).write_text(body, encoding="utf-8")
    return FormalLaunch(python=Path(sys.executable), scripts_dir=scripts_dir)


def test_cancel_before_publish_does_not_publish(tmp_path: Path) -> None:
    db = tmp_path / "studio.sqlite"
    stage_root = tmp_path / "project"
    upgrade_database(db)
    factory = session_factory(db)
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
        project = create_project(session, "race_test_proj", root_path=str(stage_root))
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
    with factory() as session:
        run_obj = session.get(StageRun, run_id)
        assert run_obj is not None
        job = enqueue(session, run_obj, task_id="formal_part1_load", fields=fields)
        session.commit()
        job_id = job.id

    # Hook triggered right before publish acquires lock
    worker._before_publish_hook = lambda jid: worker.cancel(jid)

    worker.start()
    try:
        for _ in range(50):
            with factory() as session:
                j = session.get(Job, job_id)
                if j and j.job_status in {"COMPLETED", "FAILED", "CANCELLED"}:
                    break
            time.sleep(0.1)

        with factory() as session:
            final_job = session.get(Job, job_id)
            assert final_job is not None
            assert final_job.job_status == "CANCELLED"

            artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job_id)).all()
            )
            assert len(artifacts) == 0

        dest_dir = stage_root / "analysis" / f"stage_{run_id}" / "formal_part1_load"
        assert not dest_dir.exists()

        tmp_dir = stage_root / "analysis" / f"stage_{run_id}" / ".studio" / "tmp" / str(job_id)
        assert not tmp_dir.exists()
    finally:
        worker.stop()
