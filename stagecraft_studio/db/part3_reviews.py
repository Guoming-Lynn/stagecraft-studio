"""Persist Part 3 compartment review decisions across the three stop points."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import ReviewDecision, StageRun
from stagecraft_studio.rules.gates import (
    GateRejected,
    canonical_resolution,
    cluster_set_hash,
    exposure_blinding,
    get_target_gene,
    part3_evidence_digest,
    require_blinding,
    require_date,
    require_hash,
    require_resolution,
    require_text,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _reject_if_closed(run: StageRun) -> None:
    if run.invalidated or run.stage_status == "INVALIDATED":
        raise GateRejected("LINEAR_INVALIDATION", 409)


def _get_latest_part3_review(session: Session, run_id: int, kind: str) -> ReviewDecision | None:
    rows = session.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.stage_run_id == run_id)
        .order_by(ReviewDecision.id.desc())
    )
    for row in rows:
        try:
            body = json.loads(row.body_json)
            if isinstance(body, dict) and body.get("kind") == kind:
                return row
        except (json.JSONDecodeError, OSError):
            continue
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
        body_json=json.dumps(body, ensure_ascii=False),
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def submit_part3_resolution(
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
    if digest != part3_evidence_digest(run.evidence_json or "{}"):
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    evidence = json.loads(run.evidence_json or "{}")
    overview = evidence.get("part3_overview") if isinstance(evidence, dict) else None
    if not isinstance(overview, list) or not overview:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)

    matched = [
        it
        for it in overview
        if isinstance(it, dict) and canonical_resolution(str(it.get("resolution", ""))) == chosen
    ]
    if not matched:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)

    clusters_map = (
        evidence.get("part3_clusters_by_resolution") if isinstance(evidence, dict) else None
    )
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

    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    body: dict[str, object] = {
        "kind": "part3_resolution",
        "resolution": chosen,
        "reviewer": reviewer_text,
        "decided_on": decided,
        "rationale": rationale_text,
        "blinding": recorded,
        "blinding_reason": reason,
        "leiden_ids": cluster_ids,
    }
    return _decision(session, run, digest, reviewer_text, body)


def submit_part3_clusters(
    session: Session,
    run: StageRun,
    *,
    rows: list[dict[str, str]],
    blinding: str,
) -> ReviewDecision:
    _reject_if_closed(run)
    res_decision = _get_latest_part3_review(session, run.id, "part3_resolution")
    if res_decision is None:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    res_body = json.loads(res_decision.body_json)
    leiden_ids = [str(x) for x in res_body.get("leiden_ids", [])]
    if not leiden_ids:
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)

    seen: list[str] = []
    cleaned: list[dict[str, str]] = []
    for r in rows:
        cid = require_text(r.get("cluster", ""), "REVIEW_CLUSTER_COMPLETE")
        decision = r.get("decision", "")
        if decision not in {"KEEP", "DELETE"}:
            raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
        rationale = require_text(r.get("rationale", ""), "REVIEW_CLUSTER_COMPLETE")
        reviewer = require_text(r.get("reviewer", ""), "REVIEW_CLUSTER_COMPLETE")
        decided_on = require_date(r.get("decided_on", ""), "REVIEW_CLUSTER_COMPLETE")
        name = r.get("name", "").strip()
        if name:
            raise GateRejected("PART3_NAMES_NOT_ALLOWED_AT_STOP2", 400)
        cleaned.append(
            {
                "cluster": cid,
                "decision": decision,
                "rationale": rationale,
                "reviewer": reviewer,
                "decided_on": decided_on,
            }
        )
        seen.append(cid)

    if set(seen) != set(leiden_ids) or len(seen) != len(leiden_ids):
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)

    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    digest = cluster_set_hash(leiden_ids)
    body: dict[str, object] = {
        "kind": "part3_clusters",
        "rows": cleaned,
        "blinding": recorded,
        "blinding_reason": reason,
    }
    reviewer = cleaned[0]["reviewer"]
    return _decision(session, run, digest, reviewer, body)


def submit_part3_names(
    session: Session,
    run: StageRun,
    *,
    rows: list[dict[str, str]],
    blinding: str,
) -> ReviewDecision:
    _reject_if_closed(run)
    clusters_decision = _get_latest_part3_review(session, run.id, "part3_clusters")
    if clusters_decision is None:
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
    c_body = json.loads(clusters_decision.body_json)
    c_rows = c_body.get("rows", [])
    if any(r.get("decision") == "DELETE" for r in c_rows):
        raise GateRejected("DELETE_RECOMPUTE_REQUIRED", 400)

    kept_ids = [str(r.get("cluster")) for r in c_rows if r.get("decision") == "KEEP"]
    if not kept_ids:
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)

    target_gene = get_target_gene(session, run).strip()
    seen: list[str] = []
    cleaned: list[dict[str, str]] = []
    for r in rows:
        cid = require_text(r.get("cluster", ""), "REVIEW_CLUSTER_COMPLETE")
        name = require_text(r.get("name", ""), "REVIEW_CLUSTER_COMPLETE")
        if target_gene and target_gene.casefold() in name.casefold():
            raise GateRejected("TARGET_GENE_IN_SUBTYPE_NAME", 400)
        rationale = require_text(r.get("rationale", ""), "REVIEW_CLUSTER_COMPLETE")
        reviewer = require_text(r.get("reviewer", ""), "REVIEW_CLUSTER_COMPLETE")
        decided_on = require_date(r.get("decided_on", ""), "REVIEW_CLUSTER_COMPLETE")
        cleaned.append(
            {
                "cluster": cid,
                "name": name,
                "rationale": rationale,
                "reviewer": reviewer,
                "decided_on": decided_on,
            }
        )
        seen.append(cid)

    if set(seen) != set(kept_ids) or len(seen) != len(kept_ids):
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)

    recorded, reason = exposure_blinding(require_blinding(blinding), run.quicklook_seen)
    digest = cluster_set_hash(kept_ids)
    body: dict[str, object] = {
        "kind": "part3_names",
        "rows": cleaned,
        "blinding": recorded,
        "blinding_reason": reason,
    }
    reviewer = cleaned[0]["reviewer"]
    return _decision(session, run, digest, reviewer, body)


def part3_review_center(session: Session, run: StageRun) -> dict[str, object]:
    target_gene = get_target_gene(session, run)
    payload = json.loads(run.evidence_json or "{}")
    if not isinstance(payload, dict):
        payload = {}
    overview = payload.get("part3_overview")
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
    res_dec = _get_latest_part3_review(session, run.id, "part3_resolution")
    clusters_dec = _get_latest_part3_review(session, run.id, "part3_clusters")
    names_dec = _get_latest_part3_review(session, run.id, "part3_names")

    res_body = json.loads(res_dec.body_json) if res_dec else None
    clusters_body = json.loads(clusters_dec.body_json) if clusters_dec else None
    names_body = json.loads(names_dec.body_json) if names_dec else None

    active_stop = "AWAITING_RECLUSTER"
    if overview:
        if res_body is None:
            active_stop = "STOP1_RESOLUTION"
        elif clusters_body is None:
            active_stop = "STOP2_CLUSTERS"
        else:
            has_del = any(
                r.get("decision") == "DELETE"
                for r in (clusters_body.get("rows") or [])
                if isinstance(r, dict)
            )
            if has_del:
                active_stop = "CLEANUP_REQUIRED"
            elif names_body is None:
                active_stop = "STOP3_NAMES"
            else:
                active_stop = "COMPLETED"

    digest = part3_evidence_digest(run.evidence_json or "{}")

    clusters: list[str] = []
    if res_body and isinstance(res_body.get("leiden_ids"), list):
        clusters = [str(x) for x in res_body["leiden_ids"]]
    elif resolutions:
        c_map = payload.get("part3_clusters_by_resolution")
        if isinstance(c_map, dict):
            default_res = "0.2" if "0.2" in c_map else (next(iter(c_map)) if c_map else None)
            if default_res and c_map.get(default_res):
                clusters = [str(x) for x in c_map[default_res]]

    return {
        "stage_run_id": run.id,
        "target_gene": target_gene,
        "resolutions": resolutions,
        "clusters": clusters,
        "evidence_hash": digest,
        "active_stop_point": active_stop,
        "quicklook_seen": run.quicklook_seen,
        "current_resolution": res_body,
        "current_clusters": clusters_body,
        "current_names": names_body,
    }
