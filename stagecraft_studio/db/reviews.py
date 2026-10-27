# hygiene: state machine module
"""Persist review decisions and refuse a queued job the gates do not allow."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import (
    Job,
    ProtocolVersion,
    ReviewDecision,
    RuleResultRow,
    StageRun,
)
from stagecraft_studio.db.store import _audit, create_project, open_stage_run
from stagecraft_studio.engine.formal_args import SPECS
from stagecraft_studio.engine.registry import UnsupportedTask, require_task
from stagecraft_studio.rules.gates import (
    POST_LOCK_TASKS,
    PRE_RESOLUTION,
    RESOLUTIONS,
    GateRejected,
    canonical_resolution,
    evidence_digest,
    exposure_blinding,
    filter_annotation_evidence,
    require_blinding,
    require_cluster_rows,
    require_date,
    require_hash,
    require_resolution,
    require_text,
)
from stagecraft_studio.rules.quicklook import saw_quicklook
from stagecraft_studio.rules.scientific_status import scientific_status


def submit_resolution(
    session: Session,
    run: StageRun,
    *,
    reviewer: str,
    decided_on: str,
    rationale: str,
    evidence_hash: str,
    resolution: str,
    blinding: str,
    round_index: int,
) -> ReviewDecision:
    _reject_if_closed(run)
    reviewer_text = require_text(reviewer, "RESOLUTION_REVIEW_REQUIRED")
    decided = require_date(decided_on, "RESOLUTION_REVIEW_REQUIRED")
    rationale_text = require_text(rationale, "RESOLUTION_REVIEW_REQUIRED")
    digest = require_hash(evidence_hash, "RESOLUTION_REVIEW_REQUIRED")
    chosen = require_resolution(resolution)
    evidence = _evidence(run)
    if round_index != _active_round(evidence):
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 409)
    if latest_review_for_round(session, run.id, "resolution", round_index) is not None:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 409)
    if latest_review_for_round(session, run.id, "clusters", round_index) is not None:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 409)
    if digest != evidence_digest(run.evidence_json):
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    overview = evidence.get("overview") if isinstance(evidence, dict) else None
    if not isinstance(overview, list) or not overview:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)

    matched = [
        it
        for it in overview
        if isinstance(it, dict) and canonical_resolution(str(it.get("resolution", ""))) == chosen
    ]
    if not matched:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)

    clusters_map = evidence.get("clusters_by_resolution") if isinstance(evidence, dict) else None
    if not isinstance(clusters_map, dict):
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    ids = clusters_map.get(chosen)
    if ids is None:
        for k, v in clusters_map.items():
            if canonical_resolution(k) == chosen:
                ids = v
                break
    if not ids:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    cluster_ids = [str(x) for x in ids]

    run.leiden_ids_json = json.dumps(cluster_ids)
    evidence["active_resolution"] = chosen
    evidence["active_leiden_ids"] = cluster_ids
    run.evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    body: dict[str, object] = {
        "kind": "resolution",
        "resolution": chosen,
        "reviewer": reviewer_text,
        "decided_on": decided,
        "rationale": rationale_text,
        "blinding": recorded,
        "blinding_reason": reason,
        "leiden_ids": cluster_ids,
        "round_index": round_index,
    }
    return _decision(session, run, digest, reviewer_text, body)


def submit_clusters(
    session: Session,
    run: StageRun,
    *,
    rows: list[dict[str, str]],
    blinding: str,
    round_index: int,
) -> ReviewDecision:
    _reject_if_closed(run)
    leiden_ids = _leiden_ids(run)
    resolution = latest_review_for_round(session, run.id, "resolution", round_index)
    if round_index != _active_round(_evidence(run)) or resolution is None:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 409)
    resolution_body = json.loads(resolution.body_json)
    selected_resolution = canonical_resolution(str(resolution_body.get("resolution", "")))
    if not _review_tables_completed(session, run.id, round_index, selected_resolution):
        raise GateRejected("REVIEW_TABLES_REQUIRED", 409)
    cleaned = require_cluster_rows(rows, leiden_ids)
    previous = latest_review_for_round(session, run.id, "clusters", round_index)
    named = all(bool(row["name"]) for row in cleaned)
    if previous is None and named:
        raise GateRejected("PART1_NAME_AFTER_CLUSTER_REVIEW", 409)
    if previous is not None:
        previous_body = json.loads(previous.body_json)
        if _rows_have_delete(previous_body) or not named:
            raise GateRejected("PART1_NAMING_REQUIRED", 409)
        if _rows_have_names(previous_body):
            raise GateRejected("PART1_NAMING_REQUIRED", 409)
    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    digest = _round_cluster_hash(leiden_ids, round_index, selected_resolution)
    body: dict[str, object] = {
        "kind": "clusters",
        "rows": cleaned,
        "round_index": round_index,
        "resolution": selected_resolution,
        "blinding": recorded,
        "blinding_reason": reason,
    }
    reviewer = cleaned[0]["reviewer"]
    return _decision(session, run, digest, reviewer, body)


def enqueue(
    session: Session,
    run: StageRun,
    *,
    task_id: str,
    reuse_umap: bool = False,
    fields: dict[str, object] | None = None,
) -> Job:
    _reject_if_closed(run)
    if not task_id.startswith("formal_"):
        _block(session, run, "TASK_NOT_FORMAL", 422)
    try:
        require_task(task_id)
    except UnsupportedTask:
        _block(session, run, "TASK_NOT_REGISTERED", 422)
    evidence = _evidence(run)
    current_round = _active_round(evidence)
    job_fields = dict(fields or {})
    if task_id == "formal_part1_review_tables":
        raw_round = job_fields.get("round_index", -1)
        requested_round = raw_round if isinstance(raw_round, int) else -1
        chosen = canonical_resolution(str(job_fields.get("resolution", "")))
        decision = latest_review_for_round(session, run.id, "resolution", requested_round)
        decision_body = json.loads(decision.body_json) if decision is not None else {}
        if requested_round != current_round or canonical_resolution(
            str(decision_body.get("resolution", ""))
        ) != chosen:
            _block(session, run, "RESOLUTION_REVIEW_REQUIRED")
        if latest_review_for_round(session, run.id, "clusters", requested_round) is not None:
            _block(session, run, "REVIEW_CLUSTER_COMPLETE")
        job_fields["resolution"] = chosen
        job_fields["round_index"] = requested_round
        existing = _latest_resolution_tables_job(
            session, run.id, requested_round, chosen
        )
        if existing is not None and existing.job_status in {"QUEUED", "RUNNING"}:
            return existing
    elif task_id == "formal_part1_round":
        raw_round = job_fields.get("round_index", -1)
        requested_round = raw_round if isinstance(raw_round, int) else -1
        cluster_decision = latest_review_for_round(session, run.id, "clusters", current_round)
        cluster_body = json.loads(cluster_decision.body_json) if cluster_decision else {}
        if (
            requested_round != current_round + 1
            or cluster_decision is None
            or not _rows_have_delete(cluster_body)
        ):
            _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
        job_fields["round_index"] = requested_round
        existing_round = _round_job(session, run.id, requested_round)
        if existing_round is not None and existing_round.job_status in {"QUEUED", "RUNNING"}:
            return existing_round
    elif task_id not in PRE_RESOLUTION:
        _require_current_resolution(session, run)
        _require_current_clusters(session, run)
    deleted = _has_delete(session, run)
    if deleted and task_id == "formal_part1_grid":
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if deleted and task_id == "formal_part1_grid" and reuse_umap:
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if (
        deleted
        and task_id not in PRE_RESOLUTION
        and task_id != "formal_part1_round"
        and not _recompute_after_review(session, run)
    ):
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if task_id == "formal_part1_lock":
        cluster = latest_review_for_round(session, run.id, "clusters", current_round)
        body = json.loads(cluster.body_json) if cluster is not None else {}
        if cluster is None or _rows_have_delete(body) or not _rows_have_names(body):
            _block(session, run, "PART1_NAMING_REQUIRED")
        if not _review_tables_completed(
            session,
            run.id,
            current_round,
            canonical_resolution(str(json.loads(cluster.body_json).get("resolution", ""))),
        ):
            _block(session, run, "REVIEW_TABLES_REQUIRED")
        existing_lock = _latest_task_job(session, run.id, task_id)
        if existing_lock is not None and existing_lock.job_status in {"QUEUED", "RUNNING"}:
            return existing_lock
    if task_id in POST_LOCK_TASKS:
        _require_locked_atlas(session, run)
    validate_task_fields = task_id in {
        "formal_part1_round",
        "formal_part1_review_tables",
    }
    if task_id in SPECS and (fields or validate_task_fields):
        _, model, _ = SPECS[task_id]
        check_fields = dict(job_fields)
        if task_id == "formal_part1_round":
            check_fields.update(
                common="placeholder_common",
                previous_grid="placeholder_grid",
                review="placeholder_review",
                config="placeholder_config",
                gene="GENE",
                out="placeholder_out",
            )
        if task_id == "formal_part1_review_tables":
            check_fields.update(
                grid="placeholder_grid",
                gene="GENE",
                out="placeholder_out",
            )
        if "out" not in check_fields:
            check_fields["out"] = "placeholder_out"
        if task_id == "formal_stage_report" and "stage" not in check_fields:
            check_fields["stage"] = "placeholder_stage"
        try:
            model.model_validate(check_fields)
        except Exception:
            _block(session, run, "ARG_VALIDATION_FAILED", 422)
    from_counts = task_id == "formal_part1_round"
    payload = {
        "task_id": task_id,
        "from_counts": from_counts,
        "reuse_umap": False if from_counts else reuse_umap,
        "fields": job_fields,
    }
    job = Job(
        stage_run_id=run.id,
        task_id=task_id,
        job_status="QUEUED",
        payload_json=json.dumps(payload),
        created_at=_now(),
    )
    session.add(job)
    session.flush()
    return job


def review_center(
    run: StageRun,
    target_gene: str,
    *,
    session: Session,
    stage_root: Path | None = None,
) -> dict[str, object]:
    payload = _evidence(run)
    round_index = _active_round(payload)
    resolution_review = latest_review_for_round(session, run.id, "resolution", round_index)
    resolution_body = json.loads(resolution_review.body_json) if resolution_review else {}
    selected_resolution = (
        canonical_resolution(str(resolution_body.get("resolution", "")))
        if resolution_body
        else ""
    )
    cluster_review = latest_review_for_round(session, run.id, "clusters", round_index)
    cluster_body = json.loads(cluster_review.body_json) if cluster_review else {}
    table_job = _review_tables_job(session, run.id, round_index, selected_resolution)
    next_round_job = _round_job(session, run.id, round_index + 1)
    tables_job = _latest_resolution_tables_job(session, run.id, round_index, selected_resolution)
    if cluster_review is not None and _rows_have_delete(cluster_body):
        review_state = "RECLUSTER_PENDING" if next_round_job is None else next_round_job.job_status
    elif selected_resolution and table_job is None:
        review_state = "TABLES_PENDING"
    elif selected_resolution and cluster_review is None:
        review_state = "REVIEW_CLUSTERS"
    elif cluster_review is not None and _rows_have_names(cluster_body):
        lock_job = _latest_task_job(session, run.id, "formal_part1_lock")
        review_state = lock_job.job_status if lock_job is not None else "COMPLETED"
    elif cluster_review is not None:
        review_state = "NAMES_PENDING"
    else:
        review_state = "CHOOSE_RESOLUTION"
    overview = payload.get("overview")
    resolutions = (
        [
            {
                "resolution": canonical_resolution(it.get("resolution", "")),
                "n_clusters": it.get("n_clusters"),
                "min_cluster_size": it.get("min_cluster_size"),
                "max_cluster_size": it.get("max_cluster_size"),
            }
            for it in overview
            if isinstance(it, dict)
        ]
        if isinstance(overview, list)
        else []
    )
    filtered = filter_annotation_evidence(payload, target_gene)
    return {
        "id": run.id,
        "stage_status": run.stage_status,
        "quicklook_seen": run.quicklook_seen,
        "evidence_hash": evidence_digest(run.evidence_json),
        "resolutions": resolutions,
        "clusters": payload.get("active_leiden_ids", []) if selected_resolution else [],
        "active_round": round_index,
        "selected_resolution": selected_resolution,
        "review_state": review_state,
        "cluster_decisions": cluster_body.get("rows", []),
        "round_job_status": next_round_job.job_status if next_round_job else "",
        "review_tables_job_status": tables_job.job_status if tables_job else "",
        "genes": filtered["genes"],
        "review_tables": review_tables(
            run,
            stage_root,
            round_index=round_index,
            resolution=selected_resolution,
            available=table_job is not None,
        ),
        "scientific_status": scientific_status(
            stage_status=run.stage_status, invalidated=run.invalidated, evidence=payload
        ),
    }


def review_tables(
    run: StageRun,
    stage_root: Path | None,
    *,
    round_index: int,
    resolution: str,
    available: bool,
) -> dict[str, object]:
    """Read the selected resolution's formal review table only."""
    base = {
        "available": False,
        "round_index": round_index,
        "resolution": resolution,
        "qc": [],
        "markers": [],
    }
    if not available or not resolution or stage_root is None:
        return base
    evidence = _evidence(run)
    relative = str(evidence.get("active_grid_rel", "formal_part1_grid"))
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        return base
    table_root = stage_root / relative / "review_tables"
    table_manifest = table_root / "selected_tables.json"
    if not table_manifest.is_file():
        return base
    try:
        manifest = json.loads(table_manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return base
    if (
        not isinstance(manifest, dict)
        or manifest.get("round_index") != round_index
        or canonical_resolution(str(manifest.get("resolution", ""))) != resolution
    ):
        return base
    qc_rows = _read_csv_rows(table_root / "selected_cluster_qc.csv")
    marker_rows = _read_csv_rows(table_root / "selected_markers.csv")
    # Older completed runs only have the compact worksheet. Keep it readable
    # for compatibility, while new runs use one gene per marker row.
    compact_rows = _read_csv_rows(table_root / "selected_top20_by_cluster.csv")
    if not marker_rows:
        marker_rows = _expand_compact_markers(compact_rows)
    for row in qc_rows:
        row.pop("qc_flags", None)
    return {**base, "available": bool(qc_rows or marker_rows), "qc": qc_rows, "markers": marker_rows}


def _read_csv_rows(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{str(k): _csv_value(v) for k, v in row.items()} for row in csv.DictReader(handle)]


def _csv_value(value: str | None) -> object:
    text = (value or "").strip()
    if not text:
        return ""
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    try:
        number = float(text)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def _expand_compact_markers(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    expanded: list[dict[str, object]] = []
    for row in rows:
        cluster = str(row.get("cluster", ""))
        genes = str(row.get("top20_markers", ""))
        for rank, gene in enumerate(genes.replace(";", ",").split(","), start=1):
            gene = gene.strip()
            if gene:
                expanded.append(
                    {
                        "cluster": cluster,
                        "rank": rank,
                        "gene": gene,
                        "marker_quality": "UNAVAILABLE",
                        "quality_basis": "旧版紧凑表未保存检出率和效应量",
                    }
                )
    return expanded


def carry_quicklook(
    session: Session,
    *,
    data_path: str,
    field_map: dict[str, str],
    target_gene: str,
) -> dict[str, object]:
    """Copy only the path, the field map, and the gene out of a quicklook."""
    path_text = data_path.strip()
    gene = target_gene.strip()
    if not path_text or not gene or not field_map:
        raise GateRejected("QUICKLOOK_LABELS_PROVISIONAL", 400)
    source = Path(path_text)
    root = source.parent.resolve()
    try:
        rel_path = source.resolve().relative_to(root).as_posix()
    except ValueError:
        rel_path = source.name
    carried = {"data_path": rel_path, "field_map": dict(field_map), "target_gene": gene}
    project = create_project(session, gene, root_path=str(root))
    encoded = json.dumps(carried, sort_keys=True)
    protocol = ProtocolVersion(
        project_id=project.id,
        document_json=encoded,
        content_hash=evidence_digest(encoded),
        status="carried",
        frozen_at=_now(),
    )
    session.add(protocol)
    session.flush()
    run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
    run.quicklook_seen = saw_quicklook(source)
    session.flush()
    return {
        "project_id": project.id,
        "stage_run_id": run.id,
        "quicklook_seen": run.quicklook_seen,
        "carried": carried,
    }


def annotation_evidence(run: StageRun, target_gene: str) -> dict[str, object]:
    payload = json.loads(run.evidence_json) if run.evidence_json else {}
    if not isinstance(payload, dict):
        payload = {}
    return filter_annotation_evidence(payload, target_gene)


def invalidate_downstream(session: Session, run_id: int) -> list[int]:
    rows = list(session.scalars(select(StageRun)))
    children: dict[int, list[StageRun]] = {}
    for row in rows:
        if row.upstream_id is not None:
            children.setdefault(row.upstream_id, []).append(row)
    changed: list[int] = []
    stack = list(children.get(run_id, []))
    while stack:
        current = stack.pop()
        if current.invalidated:
            stack.extend(children.get(current.id, []))
            continue
        current.invalidated = True
        current.stage_status = "INVALIDATED"
        changed.append(current.id)
        stack.extend(children.get(current.id, []))
    all_runs = [run_id, *changed]
    queued_jobs = session.scalars(
        select(Job).where(Job.stage_run_id.in_(all_runs), Job.job_status == "QUEUED")
    ).all()
    for qj in queued_jobs:
        qj.job_status = "CANCELLED"
    return changed


def _require_current_resolution(session: Session, run: StageRun) -> None:
    current = evidence_digest(run.evidence_json)
    round_index = _active_round(_evidence(run))
    decision = latest_review_for_round(session, run.id, "resolution", round_index)
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")
    body = json.loads(decision.body_json)
    res = canonical_resolution(str(body.get("resolution", ""))) if isinstance(body, dict) else ""
    if res not in RESOLUTIONS:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")


def _require_current_clusters(session: Session, run: StageRun) -> None:
    round_index = _active_round(_evidence(run))
    resolution = latest_review_for_round(session, run.id, "resolution", round_index)
    resolution_body = json.loads(resolution.body_json) if resolution is not None else {}
    chosen = canonical_resolution(str(resolution_body.get("resolution", "")))
    decision = latest_review_for_round(session, run.id, "clusters", round_index)
    current = _round_cluster_hash(_leiden_ids(run), round_index, chosen)
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "REVIEW_CLUSTER_COMPLETE")


def _has_delete(session: Session, run: StageRun) -> bool:
    decision = latest_review_for_round(
        session, run.id, "clusters", _active_round(_evidence(run))
    )
    if decision is None:
        return False
    body = json.loads(decision.body_json)
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return False
    return any(isinstance(row, dict) and row.get("decision") == "DELETE" for row in rows)


def _recompute_after_review(session: Session, run: StageRun) -> bool:
    review = latest_review(session, run.id, "clusters")
    if review is None:
        return False
    jobs = session.scalars(
        select(Job).where(Job.stage_run_id == run.id, Job.task_id == "formal_part1_grid")
    )
    for job in jobs:
        if job.created_at >= review.created_at and '"from_counts": true' in job.payload_json:
            return True
    return False


def latest_review(session: Session, run_id: int, kind: str) -> ReviewDecision | None:
    rows = session.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.stage_run_id == run_id)
        .order_by(ReviewDecision.id.desc())
    )
    for row in rows:
        body = json.loads(row.body_json)
        if isinstance(body, dict) and body.get("kind") == kind:
            return row
    return None


def latest_review_for_round(
    session: Session, run_id: int, kind: str, round_index: int
) -> ReviewDecision | None:
    rows = session.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.stage_run_id == run_id)
        .order_by(ReviewDecision.id.desc())
    )
    for row in rows:
        body = json.loads(row.body_json)
        if not isinstance(body, dict) or body.get("kind") != kind:
            continue
        if int(body.get("round_index", 0)) == round_index:
            return row
    return None


def _evidence(run: StageRun) -> dict[str, object]:
    payload = json.loads(run.evidence_json) if run.evidence_json else {}
    return payload if isinstance(payload, dict) else {}


def _active_round(payload: dict[str, object]) -> int:
    value = payload.get("active_part1_round", 0)
    return value if isinstance(value, int) and value >= 0 else 0


def _round_cluster_hash(ids: list[str], round_index: int, resolution: str) -> str:
    return evidence_digest(
        json.dumps(
            {"ids": sorted(ids), "round_index": round_index, "resolution": resolution},
            sort_keys=True,
        )
    )


def _rows_have_delete(body: dict[str, object]) -> bool:
    rows = body.get("rows")
    return isinstance(rows, list) and any(
        isinstance(row, dict) and row.get("decision") == "DELETE" for row in rows
    )


def _rows_have_names(body: dict[str, object]) -> bool:
    rows = body.get("rows")
    return isinstance(rows, list) and bool(rows) and all(
        isinstance(row, dict) and bool(str(row.get("name", "")).strip())
        for row in rows
    )


def _review_tables_job(
    session: Session, run_id: int, round_index: int, resolution: str
) -> Job | None:
    jobs = session.scalars(
        select(Job)
        .where(Job.stage_run_id == run_id, Job.task_id == "formal_part1_review_tables")
        .order_by(Job.id.desc())
    )
    for job in jobs:
        payload = json.loads(job.payload_json) if job.payload_json else {}
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        if (
            isinstance(fields, dict)
            and fields.get("round_index") == round_index
            and fields.get("resolution") == resolution
            and job.job_status == "COMPLETED"
        ):
            return job
    return None


def _review_tables_completed(
    session: Session, run_id: int, round_index: int, resolution: str
) -> bool:
    return _review_tables_job(session, run_id, round_index, resolution) is not None


def _round_job(session: Session, run_id: int, round_index: int) -> Job | None:
    jobs = session.scalars(
        select(Job)
        .where(Job.stage_run_id == run_id, Job.task_id == "formal_part1_round")
        .order_by(Job.id.desc())
    )
    for job in jobs:
        payload = json.loads(job.payload_json) if job.payload_json else {}
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        if isinstance(fields, dict) and fields.get("round_index") == round_index:
            return job
    return None


def _latest_task_job(session: Session, run_id: int, task_id: str) -> Job | None:
    return session.scalars(
        select(Job)
        .where(Job.stage_run_id == run_id, Job.task_id == task_id)
        .order_by(Job.id.desc())
    ).first()


def _latest_resolution_tables_job(
    session: Session, run_id: int, round_index: int, resolution: str
) -> Job | None:
    jobs = session.scalars(
        select(Job)
        .where(Job.stage_run_id == run_id, Job.task_id == "formal_part1_review_tables")
        .order_by(Job.id.desc())
    )
    for job in jobs:
        payload = json.loads(job.payload_json) if job.payload_json else {}
        fields = payload.get("fields", {}) if isinstance(payload, dict) else {}
        if (
            isinstance(fields, dict)
            and fields.get("round_index") == round_index
            and fields.get("resolution") == resolution
        ):
            return job
    return None


def _decision(
    session: Session, run: StageRun, digest: str, reviewer: str, body: dict[str, object]
) -> ReviewDecision:
    row = ReviewDecision(
        stage_run_id=run.id,
        evidence_hash=digest,
        reviewer=reviewer,
        body_json=json.dumps(body),
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def _block(session: Session, run: StageRun, rule_id: str, status_code: int = 409) -> NoReturn:
    row = RuleResultRow(
        stage_run_id=run.id,
        rule_id=rule_id,
        rule_status="BLOCK",
        detail_json=json.dumps({"run_id": run.id}),
        checked_at=_now(),
    )
    session.add(row)
    _audit(session, run.project_id, "job_enqueue", "REJECTED", rule_id)
    session.commit()
    raise GateRejected(rule_id, status_code)


def _reject_if_closed(run: StageRun) -> None:
    if run.invalidated or run.stage_status == "INVALIDATED":
        raise GateRejected("LINEAR_INVALIDATION", 409)


def _leiden_ids(run: StageRun) -> list[str]:
    payload = json.loads(run.leiden_ids_json or "[]")
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, str)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _require_locked_atlas(session: Session, run: StageRun) -> None:
    completed = session.scalar(
        select(Job.id).where(
            Job.stage_run_id == run.id,
            Job.task_id == "formal_part1_lock",
            Job.job_status == "COMPLETED",
        )
    )
    if completed is None:
        _block(session, run, "LOCKED_ATLAS_REQUIRED")
