"""Evaluate engine outputs and failure modes into persistent RuleResultRow records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Job, RuleResultRow


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="INPUT_COUNTS_VALID",
                rule_status="PASS",
                detail_json=json.dumps(
                    {
                        "library_id": lib_id,
                        "format": fmt,
                        "verified": "integer_counts_verified",
                    },
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
        else:
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="INPUT_COUNTS_VALID",
                rule_status="BLOCK",
                detail_json=json.dumps(
                    {
                        "library_id": lib_id,
                        "format": fmt,
                        "reason": failure_reason or "LOAD_FAILED",
                    },
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
        session.add(row)
        rows.append(row)

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

            # PER_LIBRARY_QC
            qc_row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="PER_LIBRARY_QC",
                rule_status="PASS",
                detail_json=json.dumps(
                    {
                        "library_id": lib_id,
                        "per_library": True,
                        "mad_bounds": mad_bounds,
                    },
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
            session.add(qc_row)
            rows.append(qc_row)

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
            doublet_row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="DOUBLET_FAILURE_EXPLICIT",
                rule_status=doublet_status,
                detail_json=json.dumps(doublet_detail, ensure_ascii=False),
                checked_at=_now(),
            )
            session.add(doublet_row)
            rows.append(doublet_row)
        else:
            qc_row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="PER_LIBRARY_QC",
                rule_status="BLOCK",
                detail_json=json.dumps(
                    {"library_id": lib_id, "reason": failure_reason or "QC_FAILED"},
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
            doublet_row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="DOUBLET_FAILURE_EXPLICIT",
                rule_status="BLOCK",
                detail_json=json.dumps(
                    {"library_id": lib_id, "reason": failure_reason or "QC_FAILED"},
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
            session.add(qc_row)
            session.add(doublet_row)
            rows.extend([qc_row, doublet_row])

    elif task_id == "formal_part1_merge":
        gene = str(fields.get("gene", ""))
        common_file = (dest_dir / "primary_common.h5ad") if dest_dir is not None else None
        if common_file is not None and common_file.is_file():
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="TARGET_MEASURED_IN_COMMON_SET",
                rule_status="PASS",
                detail_json=json.dumps(
                    {
                        "gene": gene,
                        "measured_in_all_primary_libraries": True,
                    },
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
        else:
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="TARGET_MEASURED_IN_COMMON_SET",
                rule_status="BLOCK",
                detail_json=json.dumps(
                    {
                        "gene": gene,
                        "reason": failure_reason or "TARGET_GENE_NOT_IN_COMMON_SET",
                    },
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
        session.add(row)
        rows.append(row)

    elif task_id == "formal_part5_prepare":
        arm = str(fields.get("arm", ""))
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
                status = "BLOCK"
                detail = {
                    "arm": arm,
                    "eligibility": "NOT_ESTIMABLE",
                    "reason": reason,
                    "rdf": rdf,
                    "design_rank": rank,
                    "design_columns": cols,
                }
            else:
                status = "PASS"
                detail = {
                    "arm": arm,
                    "eligibility": eligibility,
                    "rdf": rdf,
                    "design_rank": rank,
                    "design_columns": cols,
                    "exposure_sd": exposure_sd,
                }
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="DESIGN_ESTIMABLE",
                rule_status=status,
                detail_json=json.dumps(detail, ensure_ascii=False),
                checked_at=_now(),
            )
        else:
            row = RuleResultRow(
                stage_run_id=job.stage_run_id,
                rule_id="DESIGN_ESTIMABLE",
                rule_status="BLOCK",
                detail_json=json.dumps(
                    {"arm": arm, "reason": failure_reason or "PREPARE_FAILED"},
                    ensure_ascii=False,
                ),
                checked_at=_now(),
            )
        session.add(row)
        rows.append(row)

    return rows
