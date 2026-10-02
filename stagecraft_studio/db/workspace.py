"""Stage workspace view generator aggregating inputs, parameters, results, checks, and logs."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import (
    Artifact,
    Job,
    Project,
    ProtocolVersion,
    RuleResultRow,
    StageRun,
)
from stagecraft_studio.rules.scientific_status import scientific_status


class WorkspaceNotFound(Exception):
    """Stage run requested does not exist."""


def get_stage_workspace(session: Session, run_id: int) -> dict[str, object]:
    """Return the structured 5-tab workspace payload for a StageRun."""
    run = session.get(StageRun, run_id)
    if run is None:
        raise WorkspaceNotFound(f"Stage run {run_id} not found")

    project = session.get(Project, run.project_id)
    protocol = session.get(ProtocolVersion, run.protocol_id)

    doc: dict[str, object] = {}
    if protocol and protocol.document_json:
        try:
            doc = json.loads(protocol.document_json)
        except (json.JSONDecodeError, OSError):
            doc = {}

    inputs: dict[str, object] = {
        "project_id": project.id if project else None,
        "project_name": project.name if project else "",
        "root_path": project.root_path if project else "",
        "protocol_id": protocol.id if protocol else None,
        "protocol_hash": run.protocol_hash,
        "input_hash": run.input_hash,
        "target_gene": doc.get("target_gene", ""),
        "species": doc.get("species", ""),
        "data_path": doc.get("data_path", ""),
        "document": doc,
    }

    jobs = list(
        session.scalars(select(Job).where(Job.stage_run_id == run_id).order_by(Job.id.asc())).all()
    )

    parameters: list[dict[str, object]] = []
    logs: list[dict[str, object]] = []
    for j in jobs:
        payload = {}
        if j.payload_json:
            try:
                payload = json.loads(j.payload_json)
            except (json.JSONDecodeError, OSError):
                payload = {}
        parameters.append(
            {
                "job_id": j.id,
                "task_id": j.task_id,
                "job_status": j.job_status,
                "fields": payload.get("fields", {}),
            }
        )
        logs.append(
            {
                "id": j.id,
                "task_id": j.task_id,
                "job_status": j.job_status,
                "failure_reason": payload.get("failure_reason"),
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
        )

    artifacts = list(
        session.scalars(
            select(Artifact)
            .join(Job, Artifact.job_id == Job.id)
            .where(Job.stage_run_id == run_id, Artifact.artifact_status == "VALID")
            .order_by(Artifact.id.asc())
        ).all()
    )

    evidence: dict[str, object] = {}
    if run.evidence_json:
        try:
            evidence = json.loads(run.evidence_json)
        except (json.JSONDecodeError, OSError):
            evidence = {}

    sci = scientific_status(
        stage_status=run.stage_status,
        invalidated=run.invalidated,
        evidence=evidence,
    )

    results: dict[str, object] = {
        "scientific_status": sci,
        "evidence": evidence,
        "artifacts": [
            {
                "id": a.id,
                "job_id": a.job_id,
                "relative_path": a.relative_path,
                "content_hash": a.content_hash,
                "artifact_status": a.artifact_status,
            }
            for a in artifacts
        ],
    }

    rule_results = list(
        session.scalars(
            select(RuleResultRow)
            .where(RuleResultRow.stage_run_id == run_id)
            .order_by(RuleResultRow.id.asc())
        ).all()
    )

    checks: list[dict[str, object]] = []
    for r in rule_results:
        detail = {}
        if r.detail_json:
            try:
                detail = json.loads(r.detail_json)
            except (json.JSONDecodeError, OSError):
                detail = {}
        checks.append(
            {
                "id": r.id,
                "rule_id": r.rule_id,
                "rule_status": r.rule_status,
                "detail": detail,
                "checked_at": r.checked_at.isoformat() if r.checked_at else None,
            }
        )

    return {
        "id": run.id,
        "stage_status": run.stage_status,
        "invalidated": run.invalidated,
        "inputs": inputs,
        "parameters": parameters,
        "results": results,
        "checks": checks,
        "logs": logs,
    }
