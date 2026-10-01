"""Persist review decisions and refuse a queued job the gates do not allow."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Job, ReviewDecision, RuleResultRow, StageRun
from stagecraft_studio.rules.gates import (
    PRE_RESOLUTION,
    GateRejected,
    cluster_set_hash,
    exposure_blinding,
    filter_annotation_evidence,
    require_blinding,
    require_cluster_rows,
    require_date,
    require_hash,
    require_resolution,
    require_text,
)
from stagecraft_studio.rules.scientific_status import scientific_status


def evidence_digest(evidence_json: str) -> str:
    from hashlib import sha256

    return sha256(evidence_json.encode("utf-8")).hexdigest()


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
    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    body: dict[str, object] = {
        "kind": "resolution",
        "resolution": chosen,
        "reviewer": reviewer_text,
        "decided_on": decided,
        "rationale": rationale_text,
        "blinding": recorded,
        "blinding_reason": reason,
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
    reuse_umap: bool,
) -> Job:
    _reject_if_closed(run)
    if task_id not in PRE_RESOLUTION:
        _require_current_resolution(session, run)
        _require_current_clusters(session, run)
    deleted = _has_delete(session, run)
    if deleted and task_id == "formal_part1_grid" and reuse_umap:
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    if deleted and task_id not in PRE_RESOLUTION and not _recompute_after_review(session, run):
        _block(session, run, "DELETE_RECOMPUTE_REQUIRED")
    from_counts = deleted and task_id == "formal_part1_grid"
    payload = {
        "task_id": task_id,
        "from_counts": from_counts,
        "reuse_umap": False if from_counts else reuse_umap,
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
    resolutions: list[dict[str, object]] = []
    if isinstance(overview, list):
        for item in overview:
            if not isinstance(item, dict):
                continue
            resolutions.append(
                {
                    "resolution": item.get("resolution"),
                    "n_clusters": item.get("n_clusters"),
                    "min_cluster_size": item.get("min_cluster_size"),
                    "max_cluster_size": item.get("max_cluster_size"),
                }
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
            stage_status=run.stage_status,
            invalidated=run.invalidated,
            evidence=payload,
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
    carried = {"data_path": path_text, "field_map": dict(field_map), "target_gene": gene}
    from stagecraft_studio.db.models import ProtocolVersion
    from stagecraft_studio.db.store import create_project, open_stage_run

    project = create_project(session, gene)
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
    source = Path(path_text)
    run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
    run.quicklook_seen = _saw_quicklook(source)
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
    return changed


def _require_current_resolution(session: Session, run: StageRun) -> None:
    current = evidence_digest(run.evidence_json)
    decision = _latest(session, run.id, "resolution")
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")
    body = json.loads(decision.body_json)
    if not isinstance(body, dict) or body.get("resolution") not in {
        "0.2",
        "0.3",
        "0.4",
        "0.5",
        "0.6",
        "0.8",
        "1.0",
        "1.2",
        "1.5",
    }:
        _block(session, run, "RESOLUTION_REVIEW_REQUIRED")


def _require_current_clusters(session: Session, run: StageRun) -> None:
    decision = _latest(session, run.id, "clusters")
    current = cluster_set_hash(_leiden_ids(run))
    if decision is None or decision.evidence_hash != current:
        _block(session, run, "REVIEW_CLUSTER_COMPLETE")


def _has_delete(session: Session, run: StageRun) -> bool:
    decision = _latest(session, run.id, "clusters")
    if decision is None:
        return False
    body = json.loads(decision.body_json)
    rows = body.get("rows") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return False
    return any(isinstance(row, dict) and row.get("decision") == "DELETE" for row in rows)


def _recompute_after_review(session: Session, run: StageRun) -> bool:
    review = _latest(session, run.id, "clusters")
    if review is None:
        return False
    jobs = session.scalars(
        select(Job).where(Job.stage_run_id == run.id, Job.task_id == "formal_part1_grid")
    )
    for job in jobs:
        if job.created_at >= review.created_at and '"from_counts": true' in job.payload_json:
            return True
    return False


def _latest(session: Session, run_id: int, kind: str) -> ReviewDecision | None:
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
    session: Session,
    run: StageRun,
    digest: str,
    reviewer: str,
    body: dict[str, object],
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


def _block(session: Session, run: StageRun, rule_id: str) -> NoReturn:
    session.add(
        RuleResultRow(
            stage_run_id=run.id,
            rule_id=rule_id,
            rule_status="BLOCK",
            detail_json=json.dumps({"run_id": run.id}),
            checked_at=_now(),
        )
    )
    session.commit()
    raise GateRejected(rule_id, 409)


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


def _saw_quicklook(path: Path) -> bool:
    cursor = path.resolve()
    if cursor.is_file():
        cursor = cursor.parent
    while True:
        tier = cursor / "analysis_tier.json"
        if tier.is_file():
            payload = json.loads(tier.read_text(encoding="utf-8"))
            return isinstance(payload, dict) and payload.get("analysis_tier") == "quicklook"
        if cursor.parent == cursor:
            return False
        cursor = cursor.parent
