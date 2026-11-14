"""Executable tests for DONOR_MAPPING_REQUIRED and QUICKLOOK_CLAIM_SCOPE."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from stagecraft_studio.api.bundle import build_bundle
from stagecraft_studio.api.copy import CLAIM_SCOPE, LEDE
from stagecraft_studio.api.methods import methods_paragraph
from stagecraft_studio.api.steps import EngineIdentity
from stagecraft_studio.db.models import AuditEvent, Job, RuleResultRow
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.rules.donor_mapping import (
    INDEPENDENCE_NOTE,
    evaluate_donor_audit,
    evaluate_donor_metadata_rows,
)
from stagecraft_studio.rules.evaluator import record_job_rules
from stagecraft_studio.rules.quicklook import (
    QuicklookClaimRejected,
    require_quicklook_claim_scope,
)

from tests.review_helpers import (
    TOKEN,
    client_with_run,
    cluster_row,
    complete_review_tables,
    resolution_body,
)


def _lock_synthetic_run(tmp_path: Path) -> tuple[object, int]:
    """Synthetic fixture driving a StageRun through Part 1 lock for gate tests."""
    client, run_id, digest = client_with_run(tmp_path)
    database = tmp_path / "studio.sqlite"

    assert (
        client.post(
            f"/api/stage-runs/{run_id}/resolution",
            headers=TOKEN,
            json=resolution_body(digest),
        ).status_code
        == 201
    )
    complete_review_tables(database, run_id)

    rows = [cluster_row("0", "KEEP"), cluster_row("1", "KEEP")]
    assert (
        client.post(
            f"/api/stage-runs/{run_id}/clusters",
            headers=TOKEN,
            json={"blinding": "NOT_APPLICABLE", "rows": rows},
        ).status_code
        == 201
    )
    named = [
        {**rows[0], "name": "Monocyte"},
        {**rows[1], "name": "T_cell"},
    ]
    assert (
        client.post(
            f"/api/stage-runs/{run_id}/clusters",
            headers=TOKEN,
            json={"blinding": "NOT_APPLICABLE", "rows": named},
        ).status_code
        == 201
    )
    lock_resp = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part1_lock"},
    )
    assert lock_resp.status_code == 201
    with session_factory(database)() as session:
        job = session.get(Job, lock_resp.json()["id"])
        assert job is not None
        job.job_status = "COMPLETED"
        session.commit()
    return client, run_id


def test_donor_mapping_required_blocks_unmapped_inference(tmp_path: Path) -> None:
    client, run_id = _lock_synthetic_run(tmp_path)
    database = tmp_path / "studio.sqlite"

    # 1. Missing-evidence case: library "A" has no protocol donor_id and no donor_audit
    denied_missing = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part5_prepare"},
    )
    assert denied_missing.status_code == 409
    assert denied_missing.json()["detail"]["rule_id"] == "DONOR_MAPPING_REQUIRED"

    with session_factory(database)() as session:
        block_rows = list(
            session.scalars(
                select(RuleResultRow).where(
                    RuleResultRow.stage_run_id == run_id,
                    RuleResultRow.rule_id == "DONOR_MAPPING_REQUIRED",
                )
            )
        )
        assert block_rows and block_rows[-1].rule_status == "BLOCK"
        audits = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "job_enqueue",
                    AuditEvent.outcome == "REJECTED",
                )
            )
        )
        assert any("DONOR_MAPPING_REQUIRED" in ev.detail_json for ev in audits)

    # Clear the unscoped block row to test library-scoped reject and pass transitions
    with session_factory(database)() as session:
        for row in session.scalars(
            select(RuleResultRow).where(RuleResultRow.rule_id == "DONOR_MAPPING_REQUIRED")
        ):
            session.delete(row)
        session.commit()

    # 2. Reject case: silent library_id fallback in donor_audit.json -> BLOCK
    bad_load_dir = tmp_path / "bad_load"
    bad_load_dir.mkdir()
    (bad_load_dir / "loaded.h5ad").write_text("stub", encoding="utf-8")
    (bad_load_dir / "donor_audit.json").write_text(
        json.dumps({"library_id": "A", "donor_source": "library_id", "donor_count": 1}),
        encoding="utf-8",
    )
    with session_factory(database)() as session:
        bad_job = Job(
            stage_run_id=run_id,
            task_id="formal_part1_load",
            job_status="RUNNING",
            payload_json=json.dumps({"fields": {"library_id": "A", "format": "h5ad"}}),
            created_at=datetime.now(timezone.utc),
        )
        session.add(bad_job)
        session.flush()
        recorded_bad = record_job_rules(session, bad_job, dest_dir=bad_load_dir)
        session.commit()
        donor_bad = [r for r in recorded_bad if r.rule_id == "DONOR_MAPPING_REQUIRED"]
        assert len(donor_bad) == 1
        assert donor_bad[0].rule_status == "BLOCK"

    denied_bad = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part5_prepare"},
    )
    assert denied_bad.status_code == 409
    assert denied_bad.json()["detail"]["rule_id"] == "DONOR_MAPPING_REQUIRED"

    # 3. Pass/Warn recovery case: clean donor_audit.json supersedes library "A" status
    with session_factory(database)() as session:
        for row in session.scalars(
            select(RuleResultRow).where(RuleResultRow.rule_id == "DONOR_MAPPING_REQUIRED")
        ):
            if "library_id" not in json.loads(row.detail_json):
                session.delete(row)
        good_dir = tmp_path / "good_load"
        good_dir.mkdir()
        (good_dir / "loaded.h5ad").write_text("stub", encoding="utf-8")
        (good_dir / "donor_audit.json").write_text(
            json.dumps({"library_id": "A", "donor_source": "obs_donor_id", "donor_count": 4}),
            encoding="utf-8",
        )
        good_job = Job(
            stage_run_id=run_id,
            task_id="formal_part1_load",
            job_status="RUNNING",
            payload_json=json.dumps({"fields": {"library_id": "A", "format": "h5ad"}}),
            created_at=datetime.now(timezone.utc),
        )
        session.add(good_job)
        session.flush()
        recorded_good = record_job_rules(session, good_job, dest_dir=good_dir)
        session.commit()
        donor_good = [r for r in recorded_good if r.rule_id == "DONOR_MAPPING_REQUIRED"]
        assert len(donor_good) == 1
        assert donor_good[0].rule_status == "PASS"
        assert INDEPENDENCE_NOTE in donor_good[0].detail_json

    allowed = client.post(
        f"/api/stage-runs/{run_id}/jobs",
        headers=TOKEN,
        json={"task_id": "formal_part5_prepare"},
    )
    assert allowed.status_code == 201


def test_donor_audit_and_part5_metadata_variants() -> None:
    warn_status, warn_detail = evaluate_donor_audit(
        {"donor_source": "obs_donor", "donor_count": 3},
        library_id="L1",
    )
    assert warn_status == "WARN"
    assert INDEPENDENCE_NOTE in str(warn_detail["note"])

    fail_status, _ = evaluate_donor_audit(
        None,
        library_id="L2",
        failure_reason="CountsError: 缺少供体信息; 规则 id: DONOR_ID_MISSING",
    )
    assert fail_status == "BLOCK"

    meta_block, _ = evaluate_donor_metadata_rows([{"dataset_donor_id": "D1_P1", "donor_id": "nan"}])
    assert meta_block == "BLOCK"

    meta_pass, meta_detail = evaluate_donor_metadata_rows(
        [
            {"dataset_donor_id": "D1_P1", "donor_id": "P1"},
            {"dataset_donor_id": "D1_P2", "donor_id": "P2"},
        ]
    )
    assert meta_pass == "PASS"
    assert meta_detail["n_donors"] == 2


def test_quicklook_claim_scope_rejects_missing_or_overclaimed_text(tmp_path: Path) -> None:
    # 1. Pass case on standard lede, deterministic methods, and reproduction bundle
    assert require_quicklook_claim_scope(LEDE) == LEDE
    paragraph = methods_paragraph(
        gene="IFITM3",
        seed="42",
        engine_name="scrna-target-engine",
        engine_version="0.1.0",
        engine_git="abc1234",
        stopped_after="phase03",
        enrichment_label="本地基因集",
    )
    assert CLAIM_SCOPE in paragraph

    out_root = tmp_path / "quicklook_out"
    out_root.mkdir()
    (out_root / "config.json").write_text('{"TARGET_GENE": "IFITM3"}\n', encoding="utf-8")
    bundle_bytes = build_bundle(
        out_root,
        "python run_pipeline.py",
        EngineIdentity("scrna-target-engine", "0.1.0", "abc1234", tmp_path),
        methods_text=paragraph,
    )
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as archive:
        engine_meta = json.loads(archive.read("engine.json"))
        assert engine_meta["analysis_tier"] == "quicklook"
        assert engine_meta["claim_scope"] == CLAIM_SCOPE

    # 2. Missing-evidence cases
    with pytest.raises(QuicklookClaimRejected) as missing_empty:
        require_quicklook_claim_scope("   ")
    assert missing_empty.value.rule_id == "QUICKLOOK_CLAIM_SCOPE"
    assert missing_empty.value.reason == "MISSING_CLAIM_SCOPE"

    with pytest.raises(QuicklookClaimRejected) as missing_scope:
        require_quicklook_claim_scope("细胞水平探索性分析，但删掉了后半句限制。")
    assert missing_scope.value.reason == "MISSING_CLAIM_SCOPE"

    # 3. Reject cases: overclaims smuggled after valid CLAIM_SCOPE (including clause boundaries)
    for suffix, expected_code in (
        ("。此外本结果已完成独立复制。", "OVERCLAIM:independent_replication"),
        ("，但可作为供体水平正式推断。", "OVERCLAIM:donor_level_inference"),
        ("。模型已完成校准。", "OVERCLAIM:calibrated_verdict"),
        (". Gene X causally drives activation.", "OVERCLAIM:causal_mechanism"),
    ):
        with pytest.raises(QuicklookClaimRejected) as exc_info:
            require_quicklook_claim_scope(CLAIM_SCOPE + suffix)
        assert exc_info.value.reason == expected_code

    with pytest.raises(QuicklookClaimRejected):
        build_bundle(
            out_root,
            "python run_pipeline.py",
            EngineIdentity("scrna-target-engine", "0.1.0", "abc1234", tmp_path),
            methods_text=CLAIM_SCOPE + "。本结果已完成外部验证。",
        )
