"""Persist review decisions and refuse a queued job the gates do not allow."""

from __future__ import annotations

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
    cluster_set_hash,
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
) -> ReviewDecision:
    _reject_if_closed(run)
    reviewer_text = require_text(reviewer, "RESOLUTION_REVIEW_REQUIRED")
    decided = require_date(decided_on, "RESOLUTION_REVIEW_REQUIRED")
    rationale_text = require_text(rationale, "RESOLUTION_REVIEW_REQUIRED")
    digest = require_hash(evidence_hash, "RESOLUTION_REVIEW_REQUIRED")
    chosen = require_resolution(resolution)
    if digest != evidence_digest(run.evidence_json):
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    evidence = json.loads(run.evidence_json or "{}")
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
    }
    return _decision(session, run, digest, reviewer_text, body)


def submit_clusters(
    session: Session,
    run: StageRun,
    *,
    rows: list[dict[str, str]],
    blinding: str,
) -> ReviewDecision:
    _reject_if_closed(run)
    leiden_ids = _leiden_ids(run)
    cleaned = require_cluster_rows(rows, leiden_ids)
    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    digest = cluster_set_hash(leiden_ids)
    body: dict[str, object] = {
        "kind": "clusters",
        "rows": cleaned,
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
    if task_id not in PRE_RESOLUTION:
        _require_current_resolution(session, run)
        _require_current_clusters(session, run)
    deleted = _has_delete(session, run)
    if deleted and task_id == "formal_part1_grid" and reuse_umap:
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if deleted and task_id not in PRE_RESOLUTION and not _recompute_after_review(session, run):
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if task_id in POST_LOCK_TASKS:
        _require_locked_atlas(session, run)
    if task_id in SPECS and fields:
        _, model, _ = SPECS[task_id]
        check_fields = dict(fields)
        if "out" not in check_fields:
            check_fields["out"] = "placeholder_out"
        if task_id == "formal_stage_report" and "stage" not in check_fields:
            check_fields["stage"] = "placeholder_stage"
        try:
            model.model_validate(check_fields)
        except Exception:
            _block(session, run, "ARG_VALIDATION_FAILED", 422)
    from_counts = deleted and task_id == "formal_part1_grid"
    payload = {
        "task_id": task_id,
        "from_counts": from_counts,
        "reuse_umap": False if from_counts else reuse_umap,
        "fields": fields or {},
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


def review_center(run: StageRun, target_gene: str) -> dict[str, object]:
    payload = json.loads(run.evidence_json) if run.evidence_json else {}
    if not isinstance(payload, dict):
        payload = {}
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
        "clusters": filtered["clusters"],
        "genes": filtered["genes"],
        "scientific_status": scientific_status(
            stage_status=run.stage_status, invalidated=run.invalidated, evidence=payload
        ),
    }


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
    decision = latest_review(session, run.id, "resolution")
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")
    body = json.loads(decision.body_json)
    res = canonical_resolution(str(body.get("resolution", ""))) if isinstance(body, dict) else ""
    if res not in RESOLUTIONS:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")


def _require_current_clusters(session: Session, run: StageRun) -> None:
    decision = latest_review(session, run.id, "clusters")
    current = cluster_set_hash(_leiden_ids(run))
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "REVIEW_CLUSTER_COMPLETE")


def _has_delete(session: Session, run: StageRun) -> bool:
    decision = latest_review(session, run.id, "clusters")
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
