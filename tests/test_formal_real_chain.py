"""Integration test using the real formal engine without fakes.

Executes Part 1 load -> QC -> merge -> resolution grid using FormalWorker
with the real python interpreter and scripts from stagecraft-formal-engine.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
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
from stagecraft_studio.engine.formal_contract import FORMAL_OUTPUT_CONTRACTS
from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.worker.jobs import FormalWorker


def _find_formal_engine() -> tuple[Path, Path] | None:
    scripts_env = os.environ.get("STAGECRAFT_FORMAL_SCRIPTS")
    python_env = os.environ.get("STAGECRAFT_FORMAL_PYTHON")
    if not scripts_env or not python_env:
        return None
    scripts_dir = Path(scripts_env)
    python_path = Path(python_env)
    if not scripts_dir.is_dir() or not python_path.is_file():
        return None
    return python_path, scripts_dir


def _make_synthetic_library(python: Path, path: Path, *, seed: int, prefix: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    code = (
        "import anndata as ad, numpy as np, pandas as pd, sys\n"
        "out_path = sys.argv[1]\n"
        "seed = int(sys.argv[2])\n"
        "prefix = sys.argv[3]\n"
        "genes = ['STAT1'] + [f'G{i}' for i in range(339)]\n"
        "rng = np.random.default_rng(seed)\n"
        "counts = rng.integers(0, 10, size=(240, len(genes)), dtype=np.int64)\n"
        "barcodes = [f'{prefix}_{i}' for i in range(240)]\n"
        "obs = pd.DataFrame(index=barcodes)\n"
        "obs['dataset'] = 'D1'\n"
        "obs['donor_id'] = 'donor_1'\n"
        "adata = ad.AnnData(X=counts.copy(), obs=obs, var=pd.DataFrame(index=genes))\n"
        "adata.write_h5ad(out_path)\n"
    )
    subprocess.run(
        [str(python), "-c", code, str(path), str(seed), prefix],
        check=True,
        capture_output=True,
    )


def test_real_formal_engine_chain_part1(tmp_path: Path) -> None:
    engine = _find_formal_engine()
    if engine is None:
        pytest.skip(
            "STAGECRAFT_FORMAL_SCRIPTS and STAGECRAFT_FORMAL_PYTHON not set or invalid; "
            "skipping real formal engine test (expected in CI)"
        )
    python_path, scripts_dir = engine

    stage_root = tmp_path / "project"
    stage_root.mkdir(parents=True, exist_ok=True)
    raw_h5ad = stage_root / "raw" / "lib1.h5ad"
    _make_synthetic_library(python_path, raw_h5ad, seed=42, prefix="cell")

    db_path = tmp_path / "studio.sqlite"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    doc = {
        "target_gene": "STAT1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "loose_min_genes": 200,
        "data_path": "raw/lib1.h5ad",
        "libraries": [{"library_id": "L1", "dataset": "D1"}],
    }

    with factory() as session:
        project = create_project(session, "STAT1", root_path=str(stage_root))
        protocol = freeze_protocol(session, project.id, doc)
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=raw_h5ad)
        session.commit()
        run_id = run.id

    launch = FormalLaunch(python=python_path, scripts_dir=scripts_dir)
    worker = FormalWorker(database=db_path, launch=launch)
    worker.start()

    stage_dir = stage_root / "analysis" / f"stage_{run_id}"

    try:
        # 1. Enqueue and execute formal_part1_load
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job1 = enqueue(
                session,
                run,
                task_id="formal_part1_load",
                fields={
                    "library_id": "L1",
                    "input": str(raw_h5ad),
                    "format": "h5ad",
                    "out": str(stage_root),
                },
            )
            session.commit()
            job1_id = job1.id

        _wait_for_job(factory, job1_id)
        loaded_h5ad = stage_dir / "formal_part1_load" / "loaded.h5ad"
        assert loaded_h5ad.is_file()
        assert (stage_dir / "formal_part1_load" / "symbol_audit.csv").is_file()

        # 2. Enqueue and execute formal_part1_qc
        qc_cfg = stage_root / "qc_config.json"
        qc_cfg.write_text(json.dumps({"random_seed": 42}), encoding="utf-8")
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job2 = enqueue(
                session,
                run,
                task_id="formal_part1_qc",
                fields={
                    "library_id": "L1",
                    "source": str(raw_h5ad),
                    "loaded": str(loaded_h5ad),
                    "config": str(qc_cfg),
                    "out": str(stage_root),
                },
            )
            session.commit()
            job2_id = job2.id

        _wait_for_job(factory, job2_id)
        assert (stage_dir / "formal_part1_qc" / "qc_record.json").is_file()
        clean_h5ad = stage_dir / "formal_part1_qc" / "clean.h5ad"
        assert clean_h5ad.is_file()

        # 3. Enqueue and execute formal_part1_merge
        manifest_file = stage_root / "merge_manifest.json"
        manifest_file.write_text(
            json.dumps(
                [
                    {
                        "library_id": "L1",
                        "dataset": "D1",
                        "include_in_primary_atlas": True,
                        "path": str(clean_h5ad),
                    }
                ]
            ),
            encoding="utf-8",
        )
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job3 = enqueue(
                session,
                run,
                task_id="formal_part1_merge",
                fields={
                    "manifest": str(manifest_file),
                    "gene": "STAT1",
                    "out": str(stage_root),
                },
            )
            session.commit()
            job3_id = job3.id

        _wait_for_job(factory, job3_id)
        primary_common = stage_dir / "formal_part1_merge" / "primary_common.h5ad"
        assert primary_common.is_file()
        for fname in FORMAL_OUTPUT_CONTRACTS["formal_part1_merge"]:
            assert (stage_dir / "formal_part1_merge" / fname).is_file()

        # 4. Enqueue and execute formal_part1_grid
        grid_cfg = stage_root / "grid_config.json"
        grid_cfg.write_text(json.dumps({"random_seed": 42}), encoding="utf-8")
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job4 = enqueue(
                session,
                run,
                task_id="formal_part1_grid",
                fields={
                    "common": str(primary_common),
                    "gene": "STAT1",
                    "config": str(grid_cfg),
                    "out": str(stage_root),
                },
            )
            session.commit()
            job4_id = job4.id

        _wait_for_job(factory, job4_id)
        for fname in FORMAL_OUTPUT_CONTRACTS["formal_part1_grid"]:
            assert (stage_dir / "formal_part1_grid" / fname).is_file()

        # Verify artifacts recorded in database
        with factory() as session:
            artifacts4 = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job4_id)).all()
            )
            assert len(artifacts4) >= 5
            contract_rel = {
                f"formal_part1_grid/{fname}"
                for fname in FORMAL_OUTPUT_CONTRACTS["formal_part1_grid"]
            }
            recorded_rel = {a.relative_path for a in artifacts4}
            assert contract_rel.issubset(recorded_rel)
            assert all(a.artifact_status == "VALID" for a in artifacts4)

        # 5. Rerun formal_part1_grid to verify old artifacts become SUPERSEDED
        with factory() as session:
            run = session.get(StageRun, run_id)
            assert run is not None
            job5 = enqueue(
                session,
                run,
                task_id="formal_part1_grid",
                fields={
                    "common": str(primary_common),
                    "gene": "STAT1",
                    "config": str(grid_cfg),
                    "out": str(stage_root),
                },
            )
            session.commit()
            job5_id = job5.id

        _wait_for_job(factory, job5_id)

        with factory() as session:
            old_artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job4_id)).all()
            )
            new_artifacts = list(
                session.scalars(select(Artifact).where(Artifact.job_id == job5_id)).all()
            )
            assert len(old_artifacts) == len(artifacts4)
            assert all(a.artifact_status == "SUPERSEDED" for a in old_artifacts)
            assert len(new_artifacts) == len(artifacts4)
            assert all(a.artifact_status == "VALID" for a in new_artifacts)

    finally:
        worker.stop()


def _wait_for_job(factory: object, job_id: int, max_seconds: float = 60.0) -> None:
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        with factory() as session:  # type: ignore[operator]
            job = session.get(Job, job_id)
            if job and job.job_status in {"COMPLETED", "FAILED"}:
                assert job.job_status == "COMPLETED", f"Job failed: {job.payload_json}"
                return
        time.sleep(0.2)
    raise TimeoutError(f"Job {job_id} did not finish within {max_seconds}s")
