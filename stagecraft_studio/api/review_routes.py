"""Review gates over HTTP. The checks run here, not in the page."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import AuditEvent, Job, ProtocolVersion, StageRun
from stagecraft_studio.db.reviews import (
    annotation_evidence,
    carry_quicklook,
    enqueue,
    invalidate_downstream,
    review_center,
    submit_clusters,
    submit_resolution,
)
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.domain.protocol_form import FormError, document_from_form, form_fields
from stagecraft_studio.rules.gates import GateRejected

if TYPE_CHECKING:
    from stagecraft_studio.worker.jobs import FormalWorker


class ResolutionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str
    decided_on: str
    rationale: str
    evidence_hash: str
    resolution: str
    blinding: str


class ClusterRowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    decision: str
    rationale: str
    reviewer: str
    decided_on: str
    name: str = ""


class ClusterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blinding: str
    rows: list[ClusterRowBody]


class JobBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    reuse_umap: bool = False
    fields: dict[str, object] = Field(default_factory=dict)


class CarryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_path: str
    field_map: dict[str, str]
    target_gene: str


class LibraryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    library_id: str
    dataset: str


class FreezeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_gene: str
    species: str
    harmony_keys: list[str]
    loose_min_genes: int = 200
    data_path: str
    libraries: list[LibraryBody]


def build_review_router(
    *,
    token: str,
    origin: str,
    database: Path,
    formal_worker: FormalWorker | None = None,
) -> APIRouter:
    router = APIRouter()
    factory = session_factory(database)

    @router.post("/api/stage-runs/{run_id}/resolution", status_code=201)
    def resolution(request: Request, run_id: int, body: ResolutionBody) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                row = submit_resolution(session, run, **body.model_dump())
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return {"id": row.id, "evidence_hash": row.evidence_hash}

    @router.post("/api/stage-runs/{run_id}/clusters", status_code=201)
    def clusters(request: Request, run_id: int, body: ClusterBody) -> dict[str, int]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                row = submit_clusters(
                    session,
                    run,
                    rows=[item.model_dump() for item in body.rows],
                    blinding=body.blinding,
                )
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return {"id": row.id}

    @router.get("/api/stage-runs/{run_id}/review-evidence")
    def review_evidence(run_id: int) -> dict[str, object]:
        with factory() as session:
            run = _run(session, run_id)
            protocol = session.get(ProtocolVersion, run.protocol_id)
            if protocol is None:
                raise HTTPException(status_code=404, detail="没有协议")
            document = json.loads(protocol.document_json)
            target = document.get("target_gene") if isinstance(document, dict) else ""
            if not isinstance(target, str):
                target = ""
            return annotation_evidence(run, target)

    @router.post("/api/stage-runs/{run_id}/jobs", status_code=201)
    def jobs(request: Request, run_id: int, body: JobBody) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                job = enqueue(
                    session,
                    run,
                    task_id=body.task_id,
                    reuse_umap=body.reuse_umap,
                    fields=body.fields,
                )
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            payload = json.loads(job.payload_json)
            result = {"id": job.id, "task_id": job.task_id, **payload}
        if formal_worker is not None:
            formal_worker.wake()
        return result

    @router.get("/api/stage-runs/{run_id}/jobs")
    def stage_run_jobs(run_id: int) -> list[dict[str, object]]:
        with factory() as session:
            _run(session, run_id)
            rows = session.scalars(
                select(Job).where(Job.stage_run_id == run_id).order_by(Job.id.asc())
            ).all()
            return [
                {
                    "id": row.id,
                    "stage_run_id": row.stage_run_id,
                    "task_id": row.task_id,
                    "job_status": row.job_status,
                    "payload": json.loads(row.payload_json),
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

    @router.post("/api/jobs/{job_id}/cancel")
    def cancel_job(request: Request, job_id: int) -> dict[str, object]:
        _mutation(request, token, origin)
        if formal_worker is not None:
            res = formal_worker.cancel(job_id)
            if res.get("job_status") == "NOT_FOUND":
                raise HTTPException(status_code=404, detail="没有这个任务")
            if res.get("job_status") == "CONFLICT":
                raise HTTPException(
                    status_code=409,
                    detail=f"任务状态为 {res.get('current_status')}，不可取消",
                )
            return res
        with factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="没有这个任务")
            if job.job_status in {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}:
                raise HTTPException(
                    status_code=409,
                    detail=f"任务状态为 {job.job_status}，不可取消",
                )
            job.job_status = "CANCELLED"
            run = session.get(StageRun, job.stage_run_id)
            if run is not None:
                session.add(
                    AuditEvent(
                        project_id=run.project_id,
                        action="formal_job_cancel",
                        outcome="CANCELLED",
                        detail_json=json.dumps({"job_id": job.id, "task_id": job.task_id}),
                        created_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()
            return {"id": job.id, "job_status": job.job_status}

    @router.get("/api/stage-runs")
    def stage_runs() -> list[dict[str, object]]:
        with factory() as session:
            rows = session.scalars(select(StageRun)).all()
        return [{"id": row.id, "stage_status": row.stage_status} for row in rows]

    @router.get("/api/stage-runs/{run_id}/center")
    def center(run_id: int) -> dict[str, object]:
        with factory() as session:
            run = _run(session, run_id)
            protocol = session.get(ProtocolVersion, run.protocol_id)
            document = json.loads(protocol.document_json) if protocol is not None else {}
            target = document.get("target_gene") if isinstance(document, dict) else ""
            if not isinstance(target, str):
                target = ""
            return review_center(run, target)

    @router.post("/api/projects/from-quicklook", status_code=201)
    def from_quicklook(request: Request, body: CarryBody) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            try:
                carried = carry_quicklook(session, **body.model_dump())
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return carried

    @router.post("/api/stage-runs/{run_id}/invalidate")
    def invalidate(request: Request, run_id: int) -> dict[str, list[int]]:
        _mutation(request, token, origin)
        with factory() as session:
            _run(session, run_id)
            changed = invalidate_downstream(session, run_id)
            session.commit()
        return {"invalidated": changed}

    @router.get("/api/protocol/form")
    def protocol_form() -> dict[str, object]:
        return {"fields": form_fields()}

    @router.post("/api/protocol/freeze", status_code=201)
    def protocol_freeze(request: Request, body: FreezeBody) -> dict[str, object]:
        _mutation(request, token, origin)
        source = Path(body.data_path)
        if not source.is_file():
            raise HTTPException(status_code=400, detail={"rule_id": "PROTOCOL_FORM"})
        try:
            document = document_from_form(
                target_gene=body.target_gene,
                species=body.species,
                harmony_keys=body.harmony_keys,
                loose_min_genes=body.loose_min_genes,
                libraries=[row.model_dump() for row in body.libraries],
            )
        except FormError as exc:
            raise HTTPException(status_code=400, detail={"rule_id": exc.rule_id}) from exc
        with factory() as session:
            project_root = source.parent.resolve()
            project = create_project(session, body.target_gene.strip(), root_path=str(project_root))
            try:
                rel_data_path = source.resolve().relative_to(project_root).as_posix()
            except ValueError:
                rel_data_path = source.name
            document["data_path"] = rel_data_path
            protocol = freeze_protocol(session, project.id, document)
            run = open_stage_run(
                session,
                project_id=project.id,
                protocol=protocol,
                input_path=source,
            )
            session.commit()
            return {
                "project_id": project.id,
                "protocol_id": protocol.id,
                "content_hash": protocol.content_hash,
                "stage_run_id": run.id,
            }

    return router


def _mutation(request: Request, token: str, origin: str) -> None:
    if request.headers.get("x-stagecraft-token") != token:
        raise HTTPException(status_code=401, detail="缺少会话令牌")
    if request.headers.get("origin") != origin:
        raise HTTPException(status_code=403, detail="来源不被接受")


def _run(session: Session, run_id: int) -> StageRun:
    run = session.get(StageRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="没有这次运行")
    return run


def _raise(exc: GateRejected) -> None:
    raise HTTPException(status_code=exc.status_code, detail={"rule_id": exc.rule_id}) from exc
