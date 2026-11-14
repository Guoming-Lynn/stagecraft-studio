"""Evaluate engine outputs and failure modes into persistent RuleResultRow records."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Job, RuleResultRow
from stagecraft_studio.rules.donor_mapping import (
    evaluate_donor_audit,
    evaluate_donor_metadata_rows,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _add_row(
    session: Session,
    rows: list[RuleResultRow],
    run_id: int,
    rule_id: str,
    status: str,
    detail: dict[str, object],
) -> RuleResultRow:
    row = RuleResultRow(
        stage_run_id=run_id,
        rule_id=rule_id,
        rule_status=status,
        detail_json=json.dumps(detail, ensure_ascii=False),
        checked_at=_now(),
    )
    session.add(row)
    rows.append(row)
    return row


def record_job_rules(
    session: Session,
    job: Job,
    *,
    dest_dir: Path | None,
    failure_reason: str | None = None,
) -> list[RuleResultRow]:
    """Inspect output contract files or failure reason and append RuleResultRow."""
    rows: list[RuleResultRow] = []
    payload = json.loads(job.payload_json) if job.payload_json else {}
    fields = dict(payload.get("fields", {}))
    task_id = job.task_id

    if task_id == "formal_part1_load":
        lib_id = str(fields.get("library_id", ""))
        fmt = str(fields.get("format", ""))
        if dest_dir is not None and (dest_dir / "loaded.h5ad").is_file():
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "INPUT_COUNTS_VALID",
                "PASS",
                {"library_id": lib_id, "format": fmt, "basis": "output_file_present"},
            )
            audit_file = dest_dir / "donor_audit.json"
            if audit_file.is_file():
                try:
                    donor_audit: object = json.loads(audit_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    donor_audit = None
                d_status, d_detail = evaluate_donor_audit(donor_audit, library_id=lib_id)
                _add_row(
                    session,
                    rows,
                    job.stage_run_id,
                    "DONOR_MAPPING_REQUIRED",
                    d_status,
                    d_detail,
                )
        else:
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "INPUT_COUNTS_VALID",
                "BLOCK",
                {"library_id": lib_id, "format": fmt, "reason": failure_reason or "LOAD_FAILED"},
            )
            if failure_reason and (
                "DONOR_ID_MISSING" in failure_reason or "donor_map" in failure_reason
            ):
                d_status, d_detail = evaluate_donor_audit(
                    None, library_id=lib_id, failure_reason=failure_reason
                )
                _add_row(
                    session,
                    rows,
                    job.stage_run_id,
                    "DONOR_MAPPING_REQUIRED",
                    d_status,
                    d_detail,
                )

    elif task_id == "formal_part1_qc":
        lib_id = str(fields.get("library_id", ""))
        qc_file = (dest_dir / "qc_record.json") if dest_dir is not None else None
        if qc_file is not None and qc_file.is_file():
            try:
                qc_data = json.loads(qc_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                qc_data = {}
            if not isinstance(qc_data, dict):
                qc_data = {}
            lib_id = str(qc_data.get("library_id", lib_id))
            mad_bounds = qc_data.get("mad_bounds")
            scrublet_status = str(qc_data.get("scrublet_status", "ok"))
            in_primary = bool(qc_data.get("in_primary_atlas", False))
            n_singlets = qc_data.get("n_singlets")

            _add_row(
                session,
                rows,
                job.stage_run_id,
                "PER_LIBRARY_QC",
                "PASS",
                {"library_id": lib_id, "per_library": True, "mad_bounds": mad_bounds},
            )

            # DOUBLET_FAILURE_EXPLICIT
            if scrublet_status == "ok":
                doublet_status = "PASS"
                doublet_detail: dict[str, object] = {
                    "library_id": lib_id,
                    "scrublet_status": "ok",
                    "in_primary_atlas": True,
                    "n_singlets": n_singlets,
                }
            else:
                if not in_primary:
                    doublet_status = "WARN"
                    doublet_detail = {
                        "library_id": lib_id,
                        "scrublet_status": scrublet_status,
                        "in_primary_atlas": False,
                        "note": (
                            "Doublet failure made explicit, library excluded from primary atlas"
                        ),
                    }
                else:
                    doublet_status = "BLOCK"
                    doublet_detail = {
                        "library_id": lib_id,
                        "scrublet_status": scrublet_status,
                        "in_primary_atlas": True,
                        "error": "Scrublet failed but library remained in primary atlas",
                    }
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "DOUBLET_FAILURE_EXPLICIT",
                doublet_status,
                doublet_detail,
            )
        else:
            for rule in ("PER_LIBRARY_QC", "DOUBLET_FAILURE_EXPLICIT"):
                _add_row(
                    session,
                    rows,
                    job.stage_run_id,
                    rule,
                    "BLOCK",
                    {"library_id": lib_id, "reason": failure_reason or "QC_FAILED"},
                )

    elif task_id == "formal_part1_merge":
        gene = str(fields.get("gene", ""))
        presence_file = (
            (dest_dir / "gene_presence_by_dataset.csv") if dest_dir is not None else None
        )
        common_file = (dest_dir / "primary_common.h5ad") if dest_dir is not None else None

        is_valid = False
        failure_msg = failure_reason or "TARGET_GENE_NOT_IN_COMMON_SET"
        datasets_checked: list[str] = []

        if (
            presence_file is not None
            and presence_file.is_file()
            and common_file is not None
            and common_file.is_file()
        ):
            try:
                with presence_file.open(encoding="utf-8") as pf:
                    gene_rows = [
                        r
                        for r in csv.DictReader(pf)
                        if r.get("gene", "").strip().casefold() == gene.strip().casefold()
                    ]
                if gene_rows:
                    all_present = True
                    for r in gene_rows:
                        p_all = str(r.get("present_in_all", "")).casefold() == "true"
                        s_common = str(r.get("in_strict_common", "")).casefold() == "true"
                        try:
                            n_pres = int(r.get("n_libraries_present", 0))
                            n_total = int(r.get("n_libraries_in_dataset", 1))
                        except (ValueError, TypeError):
                            n_pres, n_total = 0, 1
                        if not (p_all or s_common or (n_total > 0 and n_pres == n_total)):
                            all_present = False
                            break
                        datasets_checked.append(str(r.get("dataset", "")))
                    if all_present and len(gene_rows) > 0:
                        is_valid = True
                    else:
                        failure_msg = f"Gene '{gene}' not present in all libraries across datasets"
                else:
                    failure_msg = f"Gene '{gene}' not found in gene_presence_by_dataset.csv"
            except Exception as exc:
                failure_msg = f"Failed to read gene_presence_by_dataset.csv: {exc}"

        _add_row(
            session,
            rows,
            job.stage_run_id,
            "TARGET_MEASURED_IN_COMMON_SET",
            "PASS" if is_valid else "BLOCK",
            (
                {
                    "gene": gene,
                    "basis": "gene_presence_by_dataset",
                    "measured_in_all_primary_libraries": True,
                    "datasets_checked": datasets_checked,
                }
                if is_valid
                else {"gene": gene, "reason": failure_msg}
            ),
        )

    elif task_id == "formal_part1_lock":
        lock_file = (dest_dir / "lock_record.json") if dest_dir is not None else None
        if lock_file is not None and lock_file.is_file():
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "REVIEW_CLUSTER_COMPLETE",
                "PASS",
                {"basis": "lock_record_present", "locked_atlas": True},
            )
        else:
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "REVIEW_CLUSTER_COMPLETE",
                "BLOCK",
                {"reason": failure_reason or "LOCK_FAILED"},
            )

    elif task_id == "formal_part5_prepare":
        arm = str(fields.get("arm", ""))
        meta_file = (dest_dir / "metadata.csv") if dest_dir is not None else None
        if meta_file is not None and meta_file.is_file():
            try:
                with meta_file.open(encoding="utf-8") as mf:
                    meta_rows = [
                        {str(k): str(v or "") for k, v in row.items() if k is not None}
                        for row in csv.DictReader(mf)
                    ]
                m_status, m_detail = evaluate_donor_metadata_rows(meta_rows)
            except OSError as exc:
                m_status = "BLOCK"
                m_detail = {"arm": arm, "reason": f"DONOR_METADATA_READ_FAILED: {exc}"}
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "DONOR_MAPPING_REQUIRED",
                m_status,
                {"arm": arm, **m_detail},
            )
        verdict_file = (dest_dir / "verdict.json") if dest_dir is not None else None
        if verdict_file is not None and verdict_file.is_file():
            try:
                verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                verdict = {}
            if not isinstance(verdict, dict):
                verdict = {}
            eligibility = str(verdict.get("eligibility", ""))
            reason = str(verdict.get("reason", ""))
            rdf = verdict.get("rdf")
            rank = verdict.get("design_rank")
            cols = verdict.get("design_columns")
            exposure_sd = verdict.get("exposure_sd")

            if eligibility == "NOT_ESTIMABLE":
                _add_row(
                    session,
                    rows,
                    job.stage_run_id,
                    "DESIGN_ESTIMABLE",
                    "BLOCK",
                    {
                        "arm": arm,
                        "eligibility": "NOT_ESTIMABLE",
                        "reason": reason,
                        "rdf": rdf,
                        "design_rank": rank,
                        "design_columns": cols,
                    },
                )
            else:
                _add_row(
                    session,
                    rows,
                    job.stage_run_id,
                    "DESIGN_ESTIMABLE",
                    "PASS",
                    {
                        "arm": arm,
                        "eligibility": eligibility,
                        "rdf": rdf,
                        "design_rank": rank,
                        "design_columns": cols,
                        "exposure_sd": exposure_sd,
                    },
                )
        else:
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "DESIGN_ESTIMABLE",
                "BLOCK",
                {"arm": arm, "reason": failure_reason or "PREPARE_FAILED"},
            )

    return rows
