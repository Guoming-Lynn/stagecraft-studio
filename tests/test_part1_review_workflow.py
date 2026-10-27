"""Part 1 review stops, table gates, and retained-count rounds."""

from __future__ import annotations

import json
from pathlib import Path

from stagecraft_studio.db.models import Job, StageRun
from stagecraft_studio.db.store import session_factory

from tests.review_helpers import (
    TOKEN,
    cluster_row,
    client_with_run,
    complete_review_tables,
    resolution_body,
)


def test_resolution_tables_cluster_decisions_then_separate_names(tmp_path: Path) -> None:
    client, run_id, digest = client_with_run(tmp_path)
    blocked = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={"blinding": "NOT_APPLICABLE", "round_index": 0, "rows": []},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["rule_id"] == "RESOLUTION_REVIEW_REQUIRED"

    selected = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json=resolution_body(digest),
    )
    assert selected.status_code == 201
    queued_tables = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={
            "task_id": "formal_part1_review_tables",
            "fields": {"round_index": 0, "resolution": "0.4"},
        },
    )
    assert queued_tables.status_code == 201
    assert queued_tables.json()["id"] == selected.json()["job_id"]

    premature = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 0,
            "rows": [cluster_row("0", "KEEP"), cluster_row("1", "KEEP")],
        },
    )
    assert premature.status_code == 409
    assert premature.json()["detail"]["rule_id"] == "REVIEW_TABLES_REQUIRED"

    complete_review_tables(tmp_path / "studio.sqlite", run_id)
    center = client.get(f"/api/stage-runs/{run_id}/center").json()
    assert center["review_state"] == "REVIEW_CLUSTERS"
    assert center["review_tables"]["available"] is True
    assert center["review_tables"]["qc"][0]["p5_total_counts"] == 500
    assert center["review_tables"]["qc"][0]["p95_total_counts"] == 1500
    assert "qc_flags" not in center["review_tables"]["qc"][0]
    assert center["review_tables"]["markers"][0]["gene"] == "LYZ"

    first = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 0,
            "rows": [cluster_row("0", "KEEP"), cluster_row("1", "KEEP")],
        },
    )
    assert first.status_code == 201
    assert first.json()["next_job_id"] == 0
    pending_names = client.get(f"/api/stage-runs/{run_id}/center").json()
    assert pending_names["review_state"] == "NAMES_PENDING"
    assert pending_names["selected_resolution"] == "0.4"

    named = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 0,
            "rows": [
                {**cluster_row("0", "KEEP"), "name": "Type 0"},
                {**cluster_row("1", "KEEP"), "name": "Type 1"},
            ],
        },
    )
    assert named.status_code == 201
    with session_factory(tmp_path / "studio.sqlite")() as session:
        lock = session.get(Job, named.json()["next_job_id"])
        assert lock is not None and lock.task_id == "formal_part1_lock"
    repeated = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 0,
            "rows": [
                {**cluster_row("0", "KEEP"), "name": "Type 0"},
                {**cluster_row("1", "KEEP"), "name": "Type 1"},
            ],
        },
    )
    assert repeated.status_code == 409
    assert repeated.json()["detail"]["rule_id"] == "PART1_NAMING_REQUIRED"


def test_delete_reclusters_before_next_resolution_and_naming(tmp_path: Path) -> None:
    client, run_id, digest = client_with_run(tmp_path)
    selected = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json=resolution_body(digest),
    )
    assert selected.status_code == 201
    complete_review_tables(tmp_path / "studio.sqlite", run_id)
    deleted = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 0,
            "rows": [cluster_row("0", "KEEP"), cluster_row("1", "DELETE")],
        },
    )
    assert deleted.status_code == 201
    with session_factory(tmp_path / "studio.sqlite")() as session:
        round_job = session.get(Job, deleted.json()["next_job_id"])
        assert round_job is not None and round_job.task_id == "formal_part1_round"
        assert json.loads(round_job.payload_json)["from_counts"] is True
        run = session.get(StageRun, run_id)
        assert run is not None
        evidence = json.loads(run.evidence_json)
        evidence.update(
            {
                "active_part1_round": 1,
                "active_grid_rel": "formal_part1_round_1",
                "overview": [{"resolution": "0.4", "n_clusters": 1}],
                "clusters_by_resolution": {"0.4": ["0"]},
                "clusters": ["0"],
            }
        )
        evidence.pop("active_resolution", None)
        evidence.pop("active_leiden_ids", None)
        run.evidence_json = json.dumps(evidence)
        run.leiden_ids_json = json.dumps(["0"])
        round_job.job_status = "COMPLETED"
        session.commit()

    center = client.get(f"/api/stage-runs/{run_id}/center").json()
    assert center["active_round"] == 1
    assert center["review_state"] == "CHOOSE_RESOLUTION"
    selected_round_two = client.post(
        f"/api/stage-runs/{run_id}/resolution",
        headers=TOKEN,
        json=resolution_body(center["evidence_hash"], round_index=1),
    )
    assert selected_round_two.status_code == 201
    complete_review_tables(tmp_path / "studio.sqlite", run_id, round_index=1)
    reviewed = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={"blinding": "NOT_APPLICABLE", "round_index": 1, "rows": [cluster_row("0", "KEEP")]},
    )
    assert reviewed.status_code == 201
    assert client.get(f"/api/stage-runs/{run_id}/center").json()["review_state"] == "NAMES_PENDING"
    named = client.post(
        f"/api/stage-runs/{run_id}/clusters",
        headers=TOKEN,
        json={
            "blinding": "NOT_APPLICABLE",
            "round_index": 1,
            "rows": [{**cluster_row("0", "KEEP"), "name": "Myeloid"}],
        },
    )
    assert named.status_code == 201
    with session_factory(tmp_path / "studio.sqlite")() as session:
        lock = session.get(Job, named.json()["next_job_id"])
        assert lock is not None and lock.task_id == "formal_part1_lock"
