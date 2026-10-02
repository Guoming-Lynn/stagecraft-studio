"""Evaluate engine outputs and failure modes into persistent RuleResultRow records."""

from __future__ import annotations

import contextlib
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Job, RuleResultRow, StageRun
from stagecraft_studio.rules.gates import canonical_resolution


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
        else:
            _add_row(
                session,
                rows,
                job.stage_run_id,
                "INPUT_COUNTS_VALID",
                "BLOCK",
                {"library_id": lib_id, "format": fmt, "reason": failure_reason or "LOAD_FAILED"},
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


def record_job_evidence(
    session: Session,
    job: Job,
    *,
    dest_dir: Path | None,
) -> None:
    """Store published records from Part 2, Part 4, and Part 5 into StageRun.evidence_json."""
    if dest_dir is None:
        return
    run = session.get(StageRun, job.stage_run_id)
    if run is None:
        return
    evidence = json.loads(run.evidence_json) if run.evidence_json else {}
    task_id = job.task_id

    if task_id == "formal_part5_prepare":
        vpath = dest_dir / "verdict.json"
        if vpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["verdict"] = json.loads(vpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part4_survey":
        rpath = dest_dir / "part4_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part4"] = json.loads(rpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part2_survey":
        rpath = dest_dir / "part2_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part2"] = json.loads(rpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part1_lock":
        lpath = dest_dir / "lock_record.json"
        if lpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["lock"] = json.loads(lpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part1_grid":
        gpath = dest_dir / "grid_record.json"
        if gpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["grid"] = json.loads(gpath.read_text(encoding="utf-8"))
        overview, res_map = _parse_grid_tables(dest_dir)
        if overview is not None:
            evidence["overview"] = overview
        if res_map is not None:
            evidence["clusters_by_resolution"] = res_map
            default_res = "0.2" if "0.2" in res_map else (next(iter(res_map)) if res_map else None)
            if default_res and res_map.get(default_res):
                evidence["clusters"] = list(res_map[default_res])
    elif task_id == "formal_part3_recluster":
        rpath = dest_dir / "part3_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part3"] = json.loads(rpath.read_text(encoding="utf-8"))
        overview, res_map = _parse_grid_tables(dest_dir)
        if overview is not None:
            evidence["part3_overview"] = overview
        if res_map is not None:
            evidence["part3_clusters_by_resolution"] = res_map

    run.evidence_json = json.dumps(evidence, ensure_ascii=False)


def _parse_grid_tables(
    dest_dir: Path,
) -> tuple[list[dict[str, object]] | None, dict[str, list[str]] | None]:
    overview: list[dict[str, object]] | None = None
    res_map: dict[str, list[str]] | None = None
    opath = dest_dir / "Leiden_resolution_overview.csv"
    if opath.is_file():
        with contextlib.suppress(OSError), opath.open("r", encoding="utf-8") as f:
            rows: list[dict[str, object]] = []
            for r in csv.DictReader(f):
                row: dict[str, object] = dict(r)
                if row.get("resolution"):
                    row["resolution"] = canonical_resolution(row["resolution"])
                for k in ("n_clusters", "min_cluster_size", "max_cluster_size"):
                    if row.get(k) is not None:
                        with contextlib.suppress(ValueError):
                            row[k] = int(str(row[k]))
                if row.get("median_cluster_size") is not None:
                    with contextlib.suppress(ValueError):
                        row["median_cluster_size"] = float(str(row["median_cluster_size"]))
                rows.append(row)
            overview = rows
    cpath = dest_dir / "cluster_by_dataset.csv"
    if cpath.is_file():
        with contextlib.suppress(OSError), cpath.open("r", encoding="utf-8") as f:
            res_map = {}
            for crow in csv.DictReader(f):
                res_val = canonical_resolution(crow.get("resolution", ""))
                cid = str(crow.get("cluster", ""))
                if res_val and cid:
                    res_map.setdefault(res_val, [])
                    if cid not in res_map[res_val]:
                        res_map[res_val].append(cid)
    return overview, res_map
