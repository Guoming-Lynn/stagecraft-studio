"""Shared synthetic StageRun fixtures for HTTP review gate tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

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


def client_with_run(
    tmp_path: Path, *, quicklook_seen: bool = False
) -> tuple[TestClient, int, str]:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    evidence = {
        "genes": [{"gene": "STAT1", "expression": [1, 2]}, {"gene": "CD68", "expression": [3]}],
        "labels": {"group": "AS", "condition": "case"},
        "clusters": ["0", "1"],
        "overview": [
            {"resolution": "0.4", "n_clusters": 2, "min_cluster_size": 10, "max_cluster_size": 20},
            {"resolution": "0.2", "n_clusters": 2, "min_cluster_size": 10, "max_cluster_size": 20},
        ],
        "clusters_by_resolution": {"0.4": ["0", "1"], "0.2": ["0", "1"]},
    }
    raw = json.dumps(evidence)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    with session_factory(database)() as session:
        project = create_project(session, "plaque", root_path=str(tmp_path))
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
        run.evidence_json = raw
        run.leiden_ids_json = json.dumps(["0", "1"])
        run.quicklook_seen = quicklook_seen
        session.commit()
        run_id = run.id
    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    return TestClient(app), run_id, evidence_digest(raw)


def resolution_body(digest: str, *, round_index: int = 0) -> dict[str, str | int]:
    return {
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
        "rationale": "marker panel separates the monocyte cloud",
        "evidence_hash": digest,
        "resolution": "0.4",
        "blinding": "BLIND",
        "round_index": round_index,
    }


def cluster_row(cluster: str, decision: str) -> dict[str, str]:
    return {
        "cluster": cluster,
        "decision": decision,
        "rationale": "marker and QC",
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
    }


def complete_review_tables(
    database: Path, run_id: int, *, round_index: int = 0, resolution: str = "0.4"
) -> None:
    with session_factory(database)() as session:
        job = Job(
            stage_run_id=run_id,
            task_id="formal_part1_review_tables",
            job_status="COMPLETED",
            payload_json=json.dumps(
                {"fields": {"round_index": round_index, "resolution": resolution}}
            ),
            created_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()
    grid_rel = "formal_part1_grid" if round_index == 0 else f"formal_part1_round_{round_index}"
    table_root = database.parent / "analysis" / f"stage_{run_id}" / grid_rel / "review_tables"
    table_root.mkdir(parents=True, exist_ok=True)
    (table_root / "selected_tables.json").write_text(
        json.dumps({"round_index": round_index, "resolution": resolution}), encoding="utf-8"
    )
    (table_root / "selected_cluster_qc.csv").write_text(
        "cluster,n_cells,n_donors,n_datasets,n_libraries,p5_total_counts,p25_total_counts,median_total_counts,p75_total_counts,p95_total_counts,p5_n_genes,p25_n_genes,median_n_genes,p75_n_genes,p95_n_genes,p5_pct_mt,p25_pct_mt,median_pct_mt,p75_pct_mt,p95_pct_mt\n"
        "0,20,3,2,2,500,750,1000,1250,1500,200,300,400,500,600,1,3,5,7,9\n"
        "1,10,2,2,2,250,375,500,625,750,100,150,200,250,300,5,12,20,28,35\n",
        encoding="utf-8",
    )
    (table_root / "selected_top20_by_cluster.csv").write_text(
        "cluster,top20_markers\n0,LYZ;FCER1G\n1,CD3D;CD3E\n", encoding="utf-8"
    )
    (table_root / "selected_markers.csv").write_text(
        "cluster,rank,gene,logfoldchange,pct_in,pct_out,pct_delta,marker_quality,quality_basis\n"
        "0,1,LYZ,1.2,0.8,0.1,0.7,STRONG,thresholds\n"
        "1,1,CD3D,0.9,0.7,0.1,0.6,STRONG,thresholds\n",
        encoding="utf-8",
    )
