"""End-to-end real formal engine pipeline test without fakes.

Executes Part 1 (load -> QC -> merge -> grid) -> reviews -> Part 3 (recluster) ->
Part 2 (survey and figures) -> Part 4 (survey and figures) -> Part 5 (prepare) ->
formal stage report using FormalWorker and real formal engine scripts.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Artifact, Job, StageRun
from stagecraft_studio.db.reviews import evidence_digest
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.worker.jobs import FormalWorker

TOKEN = "secret-real-pipeline-token"
HEADERS = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": TOKEN}
LAUNCH = EngineLaunch(python=Path(os.sys.executable), script=Path("run_pipeline.py"))


def _find_formal_engine() -> tuple[Path, Path] | None:
    scripts_env = os.environ.get("STAGECRAFT_FORMAL_SCRIPTS")
    python_env = os.environ.get("STAGECRAFT_FORMAL_PYTHON")
    if not scripts_env or not python_env:
        return None
    s_dir, p_path = Path(scripts_env), Path(python_env)
    return (p_path, s_dir) if (s_dir.is_dir() and p_path.is_file()) else None


def _make_synth(
    python: Path, path: Path, *, seed: int, prefix: str, dataset: str, donor: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "import anndata as ad, numpy as np, pandas as pd, sys\n"
        "out, s, pre, ds, dn = sys.argv[1], int(sys.argv[2]), sys.argv[3], "
        "sys.argv[4], sys.argv[5]\n"
        "genes = ['STAT1'] + [f'G{i}' for i in range(339)]\n"
        "counts = np.random.default_rng(s).integers("
        "0, 10, size=(240, len(genes)), dtype=np.int64)\n"
        "obs = pd.DataFrame(index=[f'{pre}_{i}' for i in range(240)])\n"
        "obs['dataset'], obs['donor_id'] = ds, dn\n"
        "ad.AnnData(X=counts, obs=obs, var=pd.DataFrame(index=genes)).write_h5ad(out)\n"
    )
    subprocess.run(
        [str(python), "-c", body, str(path), str(seed), prefix, dataset, donor], check=True
    )


def _wait(factory: object, job_id: int, max_s: float = 60.0) -> None:
    deadline = time.time() + max_s
    while time.time() < deadline:
        with factory() as session:  # type: ignore[operator]
            job = session.get(Job, job_id)
            if job and job.job_status in {"COMPLETED", "FAILED"}:
                assert job.job_status == "COMPLETED", f"Job {job_id} failed: {job.payload_json}"
                return
        time.sleep(0.3)
    raise TimeoutError(f"Job {job_id} did not finish within {max_s}s")


def _task(
    client: TestClient, fac: object, run_id: int, task: str, fields: dict[str, object]
) -> int:
    resp = client.post(
        f"/api/stage-runs/{run_id}/jobs", headers=HEADERS, json={"task_id": task, "fields": fields}
    )
    assert resp.status_code == 201, f"Enqueue {task} failed: {resp.text}"
    jid = int(resp.json()["id"])
    _wait(fac, jid)
    return jid


def test_real_formal_engine_pipeline_end_to_end(tmp_path: Path) -> None:
    engine = _find_formal_engine()
    if engine is None:
        pytest.skip("STAGECRAFT_FORMAL_SCRIPTS / PYTHON missing; skipping real pipeline test")
    py, scripts = engine

    root = tmp_path / "project"
    root.mkdir(parents=True, exist_ok=True)
    raw1, raw2 = root / "raw" / "lib1.h5ad", root / "raw" / "lib2.h5ad"
    _make_synth(py, raw1, seed=42, prefix="c1", dataset="D1", donor="donor_1")
    _make_synth(py, raw2, seed=43, prefix="c2", dataset="D2", donor="donor_2")

    db_path = tmp_path / "studio.sqlite"
    upgrade_database(db_path)
    factory = session_factory(db_path)

    doc = {
        "target_gene": "STAT1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "loose_min_genes": 200,
        "data_path": "raw/lib1.h5ad",
        "libraries": [
            {"library_id": "L1", "dataset": "D1"},
            {"library_id": "L2", "dataset": "D2"},
        ],
    }

    with factory() as session:
        proj = create_project(session, "STAT1", root_path=str(root))
        proto = freeze_protocol(session, proj.id, doc)
        run = open_stage_run(session, project_id=proj.id, protocol=proto, input_path=raw1)
        session.commit()
        run_id = run.id

    launch = FormalLaunch(python=py, scripts_dir=scripts)
    worker = FormalWorker(database=db_path, launch=launch)
    worker.start()

    app = create_app(TOKEN, port=8765, launch=LAUNCH, database=db_path, formal_worker=worker)
    client = TestClient(app)
    stage_dir = root / "analysis" / f"stage_{run_id}"

    try:
        # Step 1: formal_part1_load
        p1_l1 = {"library_id": "L1", "input": str(raw1), "format": "h5ad", "out": str(root)}
        p1_l2 = {"library_id": "L2", "input": str(raw2), "format": "h5ad", "out": str(root)}
        _task(client, factory, run_id, "formal_part1_load", p1_l1)
        _task(client, factory, run_id, "formal_part1_load", p1_l2)

        # Step 2: formal_part1_qc
        qc_cfg = root / "qc_config.json"
        qc_cfg.write_text(json.dumps({"random_seed": 42}), encoding="utf-8")
        loaded_l1 = stage_dir / "formal_part1_load" / "loaded.h5ad"
        p1_qc = {
            "library_id": "L1",
            "source": str(raw1),
            "loaded": str(loaded_l1),
            "config": str(qc_cfg),
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part1_qc", p1_qc)
        clean_l1 = stage_dir / "formal_part1_qc" / "clean.h5ad"
        assert clean_l1.is_file()

        # Step 3: formal_part1_merge
        mfile = root / "manifest.json"
        manifest_data = [
            {
                "library_id": "L1",
                "dataset": "D1",
                "include_in_primary_atlas": True,
                "path": str(clean_l1),
            }
        ]
        mfile.write_text(json.dumps(manifest_data), encoding="utf-8")
        p1_merge = {"manifest": str(mfile), "gene": "STAT1", "out": str(root)}
        _task(client, factory, run_id, "formal_part1_merge", p1_merge)
        primary = stage_dir / "formal_part1_merge" / "primary_common.h5ad"
        assert primary.is_file()

        # Step 4: formal_part1_grid
        gcfg = root / "grid_config.json"
        gcfg.write_text(json.dumps({"random_seed": 42}), encoding="utf-8")
        p1_grid = {"common": str(primary), "gene": "STAT1", "config": str(gcfg), "out": str(root)}
        _task(client, factory, run_id, "formal_part1_grid", p1_grid)

        # Step 5: Reviews
        with factory() as session:
            run_db = session.get(StageRun, run_id)
            assert run_db is not None
            e_hash = evidence_digest(run_db.evidence_json)

        r_body = {
            "reviewer": "Lin",
            "decided_on": "2026-10-02",
            "rationale": "DECISION",
            "evidence_hash": e_hash,
            "resolution": "0.2",
            "blinding": "BLIND",
        }
        assert (
            client.post(
                f"/api/stage-runs/{run_id}/resolution", headers=HEADERS, json=r_body
            ).status_code
            == 201
        )

        with factory() as session:
            run_db = session.get(StageRun, run_id)
            assert run_db is not None
            real_clusters = json.loads(run_db.leiden_ids_json or "[]")
            assert len(real_clusters) >= 1
            assert "0" in real_clusters

        c_rows = [
            {
                "cluster": c,
                "decision": "KEEP",
                "rationale": f"c{c}",
                "reviewer": "Lin",
                "decided_on": "2026-10-02",
                "name": f"c{c}",
            }
            for c in real_clusters
        ]
        assert (
            client.post(
                f"/api/stage-runs/{run_id}/clusters",
                headers=HEADERS,
                json={"blinding": "NOT_APPLICABLE", "rows": c_rows},
            ).status_code
            == 201
        )

        # Step 5b: formal_part1_lock
        rev_file = root / "cluster_review.json"
        rev_data = {
            "resolution": "0.2",
            "rows": c_rows,
        }
        rev_file.write_text(json.dumps(rev_data), encoding="utf-8")
        grid_out = stage_dir / "formal_part1_grid"
        p1_lock = {
            "common": str(primary),
            "grid": str(grid_out),
            "review": str(rev_file),
            "gene": "STAT1",
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part1_lock", p1_lock)
        locked = stage_dir / "formal_part1_lock" / "locked_atlas.h5ad"
        assert locked.is_file()
        assert (stage_dir / "formal_part1_lock" / "celltype_colors.yaml").is_file()
        assert (stage_dir / "formal_part1_lock" / "cluster_mapping.csv").is_file()
        assert (stage_dir / "formal_part1_lock" / "lock_record.json").is_file()

        # Step 6: Part 3
        bc_file = root / "barcodes.txt"
        bc_cmd = (
            "import anndata as ad, sys; "
            "sys.stdout.write('\\n'.join(ad.read_h5ad(sys.argv[1]).obs_names[:60]))"
        )
        bc_res = subprocess.run(
            [str(py), "-c", bc_cmd, str(primary)], capture_output=True, text=True, check=True
        )
        bc_file.write_text(bc_res.stdout + "\n", encoding="utf-8")
        p3_f = {
            "input": str(primary),
            "barcodes": str(bc_file),
            "gene": "STAT1",
            "lineage": "myeloid",
            "seed": 42,
            "completed_rounds": 0,
            "still_mixed": False,
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part3_recluster", p3_f)
        comp_h5ad = stage_dir / "formal_part3_recluster" / "compartment_counts.h5ad"
        assert comp_h5ad.is_file()

        # Step 7: Part 2
        colors = stage_dir / "formal_part1_lock" / "colors.json"
        p2_s = {"input": str(locked), "gene": "STAT1", "group": "cell_type", "out": str(root)}
        _task(client, factory, run_id, "formal_part2_survey", p2_s)
        assert (stage_dir / "formal_part2_survey" / "part2_record.json").is_file()

        p2_f = {
            "input": str(locked),
            "gene": "STAT1",
            "group": "cell_type",
            "colors": str(colors),
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part2_figures", p2_f)
        assert (stage_dir / "formal_part2_figures" / "part2_figure_record.json").is_file()

        # Step 8: Part 4
        p4_s = {
            "input": str(comp_h5ad),
            "gene": "STAT1",
            "group": "dataset",
            "lineage_stopped": False,
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part4_survey", p4_s)
        assert (stage_dir / "formal_part4_survey" / "part4_record.json").is_file()

        p4_f = {
            "input": str(comp_h5ad),
            "gene": "STAT1",
            "group": "dataset",
            "colors": str(colors),
            "lineage_stopped": False,
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part4_figures", p4_f)
        assert (stage_dir / "formal_part4_figures" / "part4_figure_record.json").is_file()

        # Step 9: Part 5
        p5_f = {
            "input": str(locked),
            "gene": "STAT1",
            "group": "cell_type",
            "arm": "c0",
            "single_source_declared": True,
            "out": str(root),
        }
        _task(client, factory, run_id, "formal_part5_prepare", p5_f)
        v_file = stage_dir / "formal_part5_prepare" / "verdict.json"
        assert v_file.is_file()
        v_data = json.loads(v_file.read_text(encoding="utf-8"))
        assert v_data["calibration_status"] == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"

        # Step 10: Report
        _task(
            client,
            factory,
            run_id,
            "formal_stage_report",
            {"stage": str(stage_dir), "out": str(root)},
        )
        rep_file = stage_dir / "formal_stage_report" / "REPORT.md"
        assert rep_file.is_file()
        rep_text = rep_file.read_text(encoding="utf-8")
        assert "# Stage report" in rep_text
        assert "NOT_ESTABLISHED_FOR_THIS_ANALYSIS" in rep_text

        # Step 11: APIs
        ws = client.get(f"/api/stage-runs/{run_id}/workspace")
        assert ws.status_code == 200
        assert {"inputs", "parameters", "results", "checks", "logs"}.issubset(ws.json().keys())

        gal = client.get(f"/api/stage-runs/{run_id}/gallery")
        assert gal.status_code == 200
        assert (
            gal.json()["scientific_status"]["calibration_status"]
            == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"
        )

        # Step 12: DB Artifacts
        with factory() as session:
            q = (
                select(Artifact)
                .join(Job, Artifact.job_id == Job.id)
                .where(Job.stage_run_id == run_id)
            )
            arts = list(session.scalars(q).all())
            valid_arts = [a for a in arts if a.artifact_status == "VALID"]
            assert len(valid_arts) >= 20
            assert any(a.artifact_status == "SUPERSEDED" for a in arts)
            assert all(len(a.content_hash) == 64 for a in arts)

    finally:
        worker.stop()
