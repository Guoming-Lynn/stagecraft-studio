"""The formal queue accepts only registered formal task ids."""

from __future__ import annotations

from pathlib import Path

from tests.audit_rows import rejected_audit
from tests.test_review_gates import TOKEN, _client


def test_an_unknown_formal_task_is_refused_and_audited(tmp_path: Path) -> None:
    client, run_id, _digest = _client(tmp_path)
    response = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_not_a_task", "reuse_umap": False},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["rule_id"] == "TASK_NOT_REGISTERED"
    assert rejected_audit(tmp_path, "TASK_NOT_REGISTERED")


def test_a_quicklook_task_cannot_enter_the_formal_queue(tmp_path: Path) -> None:
    client, run_id, _digest = _client(tmp_path)
    response = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "quicklook_run", "reuse_umap": False},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["rule_id"] == "TASK_NOT_FORMAL"
    assert rejected_audit(tmp_path, "TASK_NOT_FORMAL")
