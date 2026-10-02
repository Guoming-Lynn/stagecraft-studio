"""Tests for Part 3 compartment review gates across the three stop points."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
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


def _setup_part3_run(tmp_path: Path, target_gene: str = "STAT1") -> tuple[TestClient, int]:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    with session_factory(database)() as session:
        project = create_project(session, target_gene)
        protocol = freeze_protocol(
            session,
            project.id,
            protocol_document(
                target_gene=target_gene,
                species="human",
                manifest=[{"library_id": "L1", "dataset": "D1"}],
                qc={"loose_min_genes": 200},
                harmony_keys=["dataset"],
            ),
        )
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
        run.evidence_json = json.dumps(
            {
                "part3_overview": [
                    {
                        "resolution": "0.2",
                        "n_clusters": 2,
                        "min_cluster_size": 50,
                        "max_cluster_size": 100,
                    },
                    {
                        "resolution": "0.4",
                        "n_clusters": 3,
                        "min_cluster_size": 30,
                        "max_cluster_size": 80,
                    },
                ],
                "part3_clusters_by_resolution": {"0.2": ["0", "1"], "0.4": ["0", "1", "2"]},
            }
        )
        session.commit()
        run_id = run.id

    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    return TestClient(app), run_id


def _post_res(client: TestClient, run_id: int, digest: str, res: str = "0.2"):
    return client.post(
        f"/api/stage-runs/{run_id}/part3/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "r",
            "evidence_hash": digest,
            "resolution": res,
            "blinding": "BLIND",
        },
    )


def _post_clusters(client: TestClient, run_id: int, rows: list[dict[str, str]]):
    return client.post(
        f"/api/stage-runs/{run_id}/part3/clusters",
        headers=TOKEN,
        json={"blinding": "BLIND", "rows": rows},
    )


def _post_names(client: TestClient, run_id: int, rows: list[dict[str, str]]):
    return client.post(
        f"/api/stage-runs/{run_id}/part3/names",
        headers=TOKEN,
        json={"blinding": "BLIND", "rows": rows},
    )


def _c_row(cid: str, dec: str = "KEEP", name: str = "") -> dict[str, str]:
    r = {
        "cluster": cid,
        "decision": dec,
        "rationale": "r",
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
    }
    if name:
        r["name"] = name
    return r


def _n_row(cid: str, name: str) -> dict[str, str]:
    return {
        "cluster": cid,
        "name": name,
        "rationale": "r",
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
    }


def test_part3_stop1_resolution_selection(tmp_path: Path) -> None:
    client, run_id = _setup_part3_run(tmp_path)
    center = client.get(f"/api/stage-runs/{run_id}/part3/center").json()
    assert center["active_stop_point"] == "STOP1_RESOLUTION"
    assert center["target_gene"] == "STAT1"
    digest = center["evidence_hash"]

    # Reject invalid hash and invalid resolution
    bad_hash = _post_res(client, run_id, "a" * 64, "0.2")
    assert (
        bad_hash.status_code == 400
        and bad_hash.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
    )
    bad_res = _post_res(client, run_id, digest, "0.8")
    assert (
        bad_res.status_code == 400
        and bad_res.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
    )

    # Valid Stop 1
    assert _post_res(client, run_id, digest, "0.2").status_code == 201
    center_after = client.get(f"/api/stage-runs/{run_id}/part3/center").json()
    assert center_after["active_stop_point"] == "STOP2_CLUSTERS"
    assert center_after["clusters"] == ["0", "1"]


def test_part3_stop2_clusters_rejects_names_and_requires_stop1(tmp_path: Path) -> None:
    client, run_id = _setup_part3_run(tmp_path)

    # Stop 2 before Stop 1 rejected
    no_stop1 = _post_clusters(client, run_id, [_c_row("0"), _c_row("1")])
    assert (
        no_stop1.status_code == 400
        and no_stop1.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
    )

    digest = client.get(f"/api/stage-runs/{run_id}/part3/center").json()["evidence_hash"]
    _post_res(client, run_id, digest, "0.2")

    # Stop 2 with name MUST be rejected
    has_name = _post_clusters(client, run_id, [_c_row("0", name="Monocyte"), _c_row("1")])
    assert (
        has_name.status_code == 400
        and has_name.json()["detail"]["rule_id"] == "PART3_NAMES_NOT_ALLOWED_AT_STOP2"
    )

    # Incomplete cluster list rejected
    inc = _post_clusters(client, run_id, [_c_row("0")])
    assert inc.status_code == 400 and inc.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"

    # Valid Stop 2
    assert _post_clusters(client, run_id, [_c_row("0"), _c_row("1")]).status_code == 201
    center_stop3 = client.get(f"/api/stage-runs/{run_id}/part3/center").json()
    assert center_stop3["active_stop_point"] == "STOP3_NAMES"


def test_part3_stop2_deletion_blocks_naming(tmp_path: Path) -> None:
    client, run_id = _setup_part3_run(tmp_path)
    digest = client.get(f"/api/stage-runs/{run_id}/part3/center").json()["evidence_hash"]
    _post_res(client, run_id, digest, "0.2")

    # Mark cluster 1 as DELETE
    _post_clusters(client, run_id, [_c_row("0", "KEEP"), _c_row("1", "DELETE")])
    center = client.get(f"/api/stage-runs/{run_id}/part3/center").json()
    assert center["active_stop_point"] == "CLEANUP_REQUIRED"

    # Stop 3 naming blocked
    naming = _post_names(client, run_id, [_n_row("0", "Classical_Monocytes")])
    assert (
        naming.status_code == 400
        and naming.json()["detail"]["rule_id"] == "DELETE_RECOMPUTE_REQUIRED"
    )


def test_part3_stop3_names_validation(tmp_path: Path) -> None:
    client, run_id = _setup_part3_run(tmp_path, target_gene="STAT1")
    digest = client.get(f"/api/stage-runs/{run_id}/part3/center").json()["evidence_hash"]
    _post_res(client, run_id, digest, "0.2")
    _post_clusters(client, run_id, [_c_row("0"), _c_row("1")])

    # Empty name rejected
    empty = _post_names(client, run_id, [_n_row("0", ""), _n_row("1", "Non_Classical_Monocytes")])
    assert (
        empty.status_code == 400 and empty.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"
    )

    # Name containing target gene STAT1 rejected
    tg = _post_names(
        client, run_id, [_n_row("0", "STAT1_High_Monocytes"), _n_row("1", "FCGR3A_Monocytes")]
    )
    assert tg.status_code == 400 and tg.json()["detail"]["rule_id"] == "TARGET_GENE_IN_SUBTYPE_NAME"

    # Valid naming succeeds
    ok = _post_names(
        client, run_id, [_n_row("0", "CD14_Monocytes"), _n_row("1", "FCGR3A_Monocytes")]
    )
    assert ok.status_code == 201

    center_final = client.get(f"/api/stage-runs/{run_id}/part3/center").json()
    assert center_final["active_stop_point"] == "COMPLETED"
    assert center_final["current_names"] is not None
