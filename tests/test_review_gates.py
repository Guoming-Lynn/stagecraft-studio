"""Review gates over HTTP. The page is not part of these checks."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import StageRun
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


def test_resolution_is_required_before_a_later_job(tmp_path: Path) -> None:
    client, run_id, digest = _client(tmp_path)
    denied = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_annotate", "reuse_umap": False},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
    missing = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={
            "reviewer": "Lin",
            "decided_on": "2026-10-01",
            "rationale": "",
            "evidence_hash": digest,
            "resolution": "0.4",
            "blinding": "BLIND",
        },
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"
    extra = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json={**_resolution(digest), "skip_review": True},
    )
    assert extra.status_code == 422
    assert (
        client.post(
            f"/api/stage-runs/{run_id}/resolution", headers=TOKEN, json=_resolution(digest)
        ).status_code
        == 201
    )
    _clusters(client, run_id)
    queued = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_annotate", "reuse_umap": False},
    )
    assert queued.status_code == 201


def test_review_requires_a_blinding_value(tmp_path: Path) -> None:
    client, run_id, digest = _client(tmp_path)
    body = _resolution(digest)
    body["blinding"] = "SECRET"
    response = client.post(f"/api/stage-runs/{run_id}/resolution", headers=TOKEN, json=body)
    assert response.status_code == 400
    assert response.json()["detail"]["rule_id"] == "REVIEW_BLINDING_RECORDED"
    anonymous = client.post(f"/api/stage-runs/{run_id}/resolution", json=_resolution(digest))
    assert anonymous.status_code == 401


def test_quicklook_exposure_forces_unblinded(tmp_path: Path) -> None:
    client, run_id, digest = _client(tmp_path, quicklook_seen=True)
    response = client.post(
        f"/api/stage-runs/{run_id}/resolution", headers=TOKEN, json=_resolution(digest)
    )
    assert response.status_code == 201
    with session_factory(tmp_path / "studio.sqlite")() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        from stagecraft_studio.db.models import ReviewDecision

        decision = session.get(ReviewDecision, response.json()["id"])
        assert decision is not None
        body = json.loads(decision.body_json)
    assert body["blinding"] == "UNBLINDED_WITH_REASON"
    assert "速览" in body["blinding_reason"]


def test_old_cluster_review_does_not_apply_to_new_ids(tmp_path: Path) -> None:
    client, run_id, digest = _client(tmp_path)
    assert (
        client.post(
            f"/api/stage-runs/{run_id}/resolution", headers=TOKEN, json=_resolution(digest)
        ).status_code
        == 201
    )
    partial = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={"blinding": "NOT_APPLICABLE", "rows": [_row("0", "KEEP")]},
    )
    assert partial.status_code == 400
    assert partial.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"
    assert _clusters(client, run_id).status_code == 201
    with session_factory(tmp_path / "studio.sqlite")() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        run.leiden_ids_json = json.dumps(["0", "1", "2"])
        session.commit()
    again = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_annotate", "reuse_umap": False},
    )
    assert again.status_code == 409
    assert again.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"


def test_delete_cannot_reuse_the_old_umap(tmp_path: Path) -> None:
    client, run_id, digest = _client(tmp_path)
    client.post(f"/api/stage-runs/{run_id}/resolution", headers=TOKEN, json=_resolution(digest))
    rows = [_row("0", "KEEP"), _row("1", "DELETE")]
    assert (
        client.post(
            f"/api/stage-runs/{run_id}/clusters",
            headers=TOKEN,
            json={"blinding": "NOT_APPLICABLE", "rows": rows},
        ).status_code
        == 201
    )
    blocked = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_grid", "reuse_umap": True},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["rule_id"] == "DELETE_RECOMPUTE_REQUIRED"
    early = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_annotate", "reuse_umap": False},
    )
    assert early.status_code == 409
    assert early.json()["detail"]["rule_id"] == "DELETE_RECOMPUTE_REQUIRED"
    recomputed = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_grid", "reuse_umap": False},
    )
    assert recomputed.status_code == 201
    assert recomputed.json()["from_counts"] is True
    assert recomputed.json()["reuse_umap"] is False


def test_upstream_change_invalidates_downstream(tmp_path: Path) -> None:
    client, parent_id, digest = _client(tmp_path)
    with session_factory(tmp_path / "studio.sqlite")() as session:
        parent = session.get(StageRun, parent_id)
        assert parent is not None
        child = StageRun(
            project_id=parent.project_id,
            protocol_id=parent.protocol_id,
            protocol_hash=parent.protocol_hash,
            input_hash=parent.input_hash,
            engine_version=parent.engine_version,
            rule_version=parent.rule_version,
            stage_status="READY",
            created_at=parent.created_at,
            evidence_json=parent.evidence_json,
            leiden_ids_json=parent.leiden_ids_json,
            upstream_id=parent.id,
        )
        kept = parent.protocol_hash
        session.add(child)
        session.commit()
        child_id = child.id
    response = client.post(f"/api/stage-runs/{parent_id}/invalidate", headers=TOKEN)
    assert response.status_code == 200
    assert child_id in response.json()["invalidated"]
    denied = client.post(
        f"/api/stage-runs/{child_id}/resolution", headers=TOKEN, json=_resolution(digest)
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["rule_id"] == "LINEAR_INVALIDATION"
    with session_factory(tmp_path / "studio.sqlite")() as session:
        child = session.get(StageRun, child_id)
        parent = session.get(StageRun, parent_id)
        assert child is not None and parent is not None
        assert child.stage_status == "INVALIDATED"
        assert child.protocol_hash == kept
        assert parent.stage_status == "READY"


def test_annotation_evidence_hides_the_target_gene_and_groups(tmp_path: Path) -> None:
    client, run_id, _digest = _client(tmp_path)
    response = client.get(f"/api/stage-runs/{run_id}/review-evidence?include_target=1")
    assert response.status_code == 200
    body = response.json()
    assert body["genes"] == [{"gene": "CD68", "expression": [3]}]
    assert "labels" not in body
    assert "group" not in json.dumps(body)
    assert "STAT1" not in json.dumps(body)


def test_quicklook_carry_omits_labels_and_resolution(tmp_path: Path) -> None:
    folder = tmp_path / "quick"
    folder.mkdir()
    source = folder / "counts.h5ad"
    source.write_bytes(b"counts")
    (folder / "analysis_tier.json").write_text(
        json.dumps({"analysis_tier": "quicklook", "labels": ["macrophage"], "resolution": "0.4"}),
        encoding="utf-8",
    )
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    client = TestClient(create_app("secret-token", port=8765, launch=LAUNCH, database=database))
    rejected = client.post(
        "/api/projects/from-quicklook",
        headers=TOKEN,
        json={
            "data_path": str(source),
            "field_map": {"sample": "library_id"},
            "target_gene": "STAT1",
            "resolution": "0.4",
            "labels": ["macrophage"],
        },
    )
    assert rejected.status_code == 422
    accepted = client.post(
        "/api/projects/from-quicklook",
        headers=TOKEN,
        json={
            "data_path": str(source),
            "field_map": {"sample": "library_id"},
            "target_gene": "STAT1",
        },
    )
    assert accepted.status_code == 201
    body = accepted.json()
    assert set(body["carried"]) == {"data_path", "field_map", "target_gene"}
    assert body["quicklook_seen"] is True
    assert "resolution" not in body["carried"]
    assert "labels" not in body["carried"]


def test_names_are_refused_while_a_cluster_is_deleted(tmp_path: Path) -> None:
    client, run_id, _digest = _client(tmp_path)
    named = _row("0", "KEEP")
    named["name"] = "monocyte"
    deleted = _row("1", "DELETE")
    response = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={"blinding": "NOT_APPLICABLE", "rows": [named, deleted]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["rule_id"] == "REVIEW_CLUSTER_COMPLETE"


def test_a_stored_pass_does_not_raise_the_ceiling(tmp_path: Path) -> None:
    client, run_id, _digest = _client(tmp_path)
    with session_factory(tmp_path / "studio.sqlite")() as session:
        run = session.get(StageRun, run_id)
        assert run is not None
        evidence = json.loads(run.evidence_json)
        evidence["verdict"] = {
            "stopped": "FITTED",
            "fitted": True,
            "model": "edger_ql",
            "claims_limma": True,
            "associated": True,
            "holdout": "not_run",
            "calibration_status": "FROZEN_PASS",
        }
        run.evidence_json = json.dumps(evidence)
        session.commit()
    center = client.get(f"/api/stage-runs/{run_id}/center")
    assert center.status_code == 200
    status = center.json()["scientific_status"]
    assert status["calibration_status"] == "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"
    assert status["associated"] is False
    assert status["claims_limma"] is False
    assert status["lodo_is_replication"] is False
    assert status["forecast_is_not_a_verdict"] is True
    assert "NOT_ESTIMABLE 不表示效应不存在。" in status["limits"]
    forged = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_grid", "scientific_status": "FROZEN_PASS"},
    )
    assert forged.status_code == 422


def test_rule_coverage_matches_the_catalog() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_rule_coverage.py"), "--check"],
        check=False,
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def _client(tmp_path: Path, *, quicklook_seen: bool = False) -> tuple[TestClient, int, str]:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    evidence = {
        "genes": [
            {"gene": "STAT1", "expression": [1, 2]},
            {"gene": "CD68", "expression": [3]},
        ],
        "labels": {"group": "AS", "condition": "case"},
        "clusters": ["0", "1"],
    }
    raw = json.dumps(evidence)
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
        run.evidence_json = raw
        run.leiden_ids_json = json.dumps(["0", "1"])
        run.quicklook_seen = quicklook_seen
        session.commit()
        run_id = run.id
    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    return TestClient(app), run_id, evidence_digest(raw)


def _resolution(digest: str) -> dict[str, str]:
    return {
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
        "rationale": "marker panel separates the monocyte cloud",
        "evidence_hash": digest,
        "resolution": "0.4",
        "blinding": "BLIND",
    }


def _row(cluster: str, decision: str) -> dict[str, str]:
    return {
        "cluster": cluster,
        "decision": decision,
        "rationale": "marker and QC",
        "reviewer": "Lin",
        "decided_on": "2026-10-01",
    }


def _clusters(client: TestClient, run_id: int):
    return client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={"blinding": "NOT_APPLICABLE", "rows": [_row("0", "KEEP"), _row("1", "KEEP")]},
    )
