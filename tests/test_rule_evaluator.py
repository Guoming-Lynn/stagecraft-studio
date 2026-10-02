"""Test evaluation and recording of engine-enforced rules into RuleResultRow."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Job
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.rules.evaluator import record_job_rules


def _make_db(tmp_path: Path) -> tuple[Path, Session]:
    db_path = tmp_path / "test.db"
    upgrade_database(db_path)
    factory = session_factory(db_path)
    return db_path, factory()


def _make_job(
    session: Session,
    *,
    stage_run_id: int = 1,
    task_id: str,
    fields: dict[str, object],
) -> Job:
    job = Job(
        stage_run_id=stage_run_id,
        task_id=task_id,
        job_status="RUNNING",
        payload_json=json.dumps({"fields": fields}),
        created_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.commit()
    return job


def test_input_counts_valid_recorded_on_load(tmp_path: Path) -> None:
    _, session = _make_db(tmp_path)
    dest_dir = tmp_path / "stage_1" / "formal_part1_load"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "loaded.h5ad").write_text("dummy", encoding="utf-8")

    job = _make_job(
        session,
        task_id="formal_part1_load",
        fields={"library_id": "lib_01", "format": "h5ad"},
    )

    rows = record_job_rules(session, job, dest_dir=dest_dir)
    session.commit()

    assert len(rows) == 1
    assert rows[0].rule_id == "INPUT_COUNTS_VALID"
    assert rows[0].rule_status == "PASS"
    detail = json.loads(rows[0].detail_json)
    assert detail["library_id"] == "lib_01"
    assert detail["basis"] == "output_file_present"

    # Counter-example: dest_dir exists but loaded.h5ad is missing -> BLOCK
    missing_h5ad_dir = tmp_path / "stage_1" / "formal_part1_load_missing"
    missing_h5ad_dir.mkdir(parents=True, exist_ok=True)
    job_missing_h5ad = _make_job(
        session,
        task_id="formal_part1_load",
        fields={"library_id": "lib_01", "format": "h5ad"},
    )
    rows_missing = record_job_rules(session, job_missing_h5ad, dest_dir=missing_h5ad_dir)
    session.commit()
    assert len(rows_missing) == 1
    assert rows_missing[0].rule_status == "BLOCK"
    assert "LOAD_FAILED" in rows_missing[0].detail_json

    # Also test failure mode
    failed_job = _make_job(
        session,
        task_id="formal_part1_load",
        fields={"library_id": "lib_bad", "format": "h5ad"},
    )

    fail_rows = record_job_rules(
        session, failed_job, dest_dir=None, failure_reason="CountsError: 计数必须是整数样"
    )
    session.commit()

    assert len(fail_rows) == 1
    assert fail_rows[0].rule_id == "INPUT_COUNTS_VALID"
    assert fail_rows[0].rule_status == "BLOCK"
    assert "CountsError" in fail_rows[0].detail_json


def test_per_library_qc_recorded_on_qc(tmp_path: Path) -> None:
    _, session = _make_db(tmp_path)
    dest_dir = tmp_path / "stage_1" / "formal_part1_qc"
    dest_dir.mkdir(parents=True, exist_ok=True)
    qc_record = {
        "library_id": "lib_02",
        "scrublet_status": "ok",
        "in_primary_atlas": True,
        "n_singlets": 500,
        "mad_bounds": {"n_genes": [200, 2000], "total_counts": [500, 10000]},
    }
    (dest_dir / "qc_record.json").write_text(json.dumps(qc_record), encoding="utf-8")

    job = _make_job(
        session,
        task_id="formal_part1_qc",
        fields={"library_id": "lib_02"},
    )

    rows = record_job_rules(session, job, dest_dir=dest_dir)
    session.commit()

    qc_rows = [r for r in rows if r.rule_id == "PER_LIBRARY_QC"]
    assert len(qc_rows) == 1
    assert qc_rows[0].rule_status == "PASS"
    detail = json.loads(qc_rows[0].detail_json)
    assert detail["library_id"] == "lib_02"
    assert detail["per_library"] is True
    assert "n_genes" in detail["mad_bounds"]


def test_doublet_failure_explicit_recorded_on_qc(tmp_path: Path) -> None:
    _, session = _make_db(tmp_path)
    dest_dir = tmp_path / "stage_1" / "formal_part1_qc_fail"
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Case: Scrublet failed and library was explicitly excluded from primary atlas
    qc_record = {
        "library_id": "lib_failed",
        "scrublet_status": "failed",
        "in_primary_atlas": False,
        "n_singlets": 10,
    }
    (dest_dir / "qc_record.json").write_text(json.dumps(qc_record), encoding="utf-8")

    job = _make_job(
        session,
        task_id="formal_part1_qc",
        fields={"library_id": "lib_failed"},
    )

    rows = record_job_rules(session, job, dest_dir=dest_dir)
    session.commit()

    doublet_rows = [r for r in rows if r.rule_id == "DOUBLET_FAILURE_EXPLICIT"]
    assert len(doublet_rows) == 1
    assert doublet_rows[0].rule_status == "WARN"
    detail = json.loads(doublet_rows[0].detail_json)
    assert detail["in_primary_atlas"] is False
    assert "Doublet failure made explicit" in detail["note"]


def test_target_measured_in_common_set_recorded_on_merge(tmp_path: Path) -> None:
    _, session = _make_db(tmp_path)
    dest_dir = tmp_path / "stage_1" / "formal_part1_merge"
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "primary_common.h5ad").write_text("common", encoding="utf-8")
    presence_csv = (
        "dataset,gene,n_libraries_in_dataset,n_libraries_present,present_in_any,present_in_all,in_strict_common\n"
        "D1,CD3D,2,2,True,True,True\n"
        "D2,CD3D,1,1,True,True,True\n"
    )
    (dest_dir / "gene_presence_by_dataset.csv").write_text(presence_csv, encoding="utf-8")

    job = _make_job(
        session,
        task_id="formal_part1_merge",
        fields={"gene": "CD3D"},
    )

    rows = record_job_rules(session, job, dest_dir=dest_dir)
    session.commit()

    assert len(rows) == 1
    assert rows[0].rule_id == "TARGET_MEASURED_IN_COMMON_SET"
    assert rows[0].rule_status == "PASS"
    detail = json.loads(rows[0].detail_json)
    assert detail["gene"] == "CD3D"
    assert detail["basis"] == "gene_presence_by_dataset"
    assert detail["measured_in_all_primary_libraries"] is True
    assert set(detail["datasets_checked"]) == {"D1", "D2"}

    # Counter-example 1: gene_presence_by_dataset.csv missing -> BLOCK
    missing_csv_dir = tmp_path / "stage_1" / "merge_missing_csv"
    missing_csv_dir.mkdir(parents=True, exist_ok=True)
    (missing_csv_dir / "primary_common.h5ad").write_text("common", encoding="utf-8")
    job_no_csv = _make_job(
        session,
        task_id="formal_part1_merge",
        fields={"gene": "CD3D"},
    )
    rows_no_csv = record_job_rules(session, job_no_csv, dest_dir=missing_csv_dir)
    session.commit()
    assert len(rows_no_csv) == 1
    assert rows_no_csv[0].rule_status == "BLOCK"

    # Counter-example 2: gene not present in all libraries in one dataset -> BLOCK
    partial_dir = tmp_path / "stage_1" / "merge_partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    (partial_dir / "primary_common.h5ad").write_text("common", encoding="utf-8")
    partial_csv = (
        "dataset,gene,n_libraries_in_dataset,n_libraries_present,present_in_any,present_in_all,in_strict_common\n"
        "D1,CD3D,2,2,True,True,True\n"
        "D2,CD3D,2,1,True,False,False\n"
    )
    (partial_dir / "gene_presence_by_dataset.csv").write_text(partial_csv, encoding="utf-8")
    job_partial = _make_job(
        session,
        task_id="formal_part1_merge",
        fields={"gene": "CD3D"},
    )
    rows_partial = record_job_rules(session, job_partial, dest_dir=partial_dir)
    session.commit()
    assert len(rows_partial) == 1
    assert rows_partial[0].rule_status == "BLOCK"
    assert "not present in all libraries" in rows_partial[0].detail_json

    # Test failure mode when engine explicitly fails
    fail_job = _make_job(
        session,
        task_id="formal_part1_merge",
        fields={"gene": "MY_MISSING_GENE"},
    )

    fail_rows = record_job_rules(
        session, fail_job, dest_dir=None, failure_reason="MergeError: 目标基因不在 strict-common"
    )
    session.commit()

    assert len(fail_rows) == 1
    assert fail_rows[0].rule_id == "TARGET_MEASURED_IN_COMMON_SET"
    assert fail_rows[0].rule_status == "BLOCK"


def test_design_estimable_recorded_on_prepare(tmp_path: Path) -> None:
    _, session = _make_db(tmp_path)
    dest_dir = tmp_path / "stage_1" / "formal_part5_prepare"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Subtest 1: PASS case
    pass_verdict = {
        "eligibility": "formal",
        "rdf": 8,
        "design_rank": 4,
        "design_columns": 4,
        "exposure_sd": 0.85,
    }
    (dest_dir / "verdict.json").write_text(json.dumps(pass_verdict), encoding="utf-8")

    job_pass = _make_job(
        session,
        task_id="formal_part5_prepare",
        fields={"arm": "arm_tcell"},
    )

    rows_pass = record_job_rules(session, job_pass, dest_dir=dest_dir)
    session.commit()

    assert len(rows_pass) == 1
    assert rows_pass[0].rule_id == "DESIGN_ESTIMABLE"
    assert rows_pass[0].rule_status == "PASS"
    detail_pass = json.loads(rows_pass[0].detail_json)
    assert detail_pass["eligibility"] == "formal"
    assert detail_pass["rdf"] == 8

    # Subtest 2: NOT_ESTIMABLE case -> BLOCK
    block_verdict = {
        "eligibility": "NOT_ESTIMABLE",
        "reason": "rank-deficient design (rank 2 < 4 columns)",
        "rdf": 0,
        "design_rank": 2,
        "design_columns": 4,
    }
    (dest_dir / "verdict.json").write_text(json.dumps(block_verdict), encoding="utf-8")

    job_block = _make_job(
        session,
        task_id="formal_part5_prepare",
        fields={"arm": "arm_bad"},
    )

    rows_block = record_job_rules(session, job_block, dest_dir=dest_dir)
    session.commit()

    assert len(rows_block) == 1
    assert rows_block[0].rule_id == "DESIGN_ESTIMABLE"
    assert rows_block[0].rule_status == "BLOCK"
    detail_block = json.loads(rows_block[0].detail_json)
    assert detail_block["eligibility"] == "NOT_ESTIMABLE"
    assert "rank-deficient" in detail_block["reason"]
