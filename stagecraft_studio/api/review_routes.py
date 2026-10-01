"""Review gates over HTTP. The checks run here, not in the page."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import ProtocolVersion, StageRun
from stagecraft_studio.db.reviews import (
    annotation_evidence,
    enqueue,
    invalidate_downstream,
    submit_clusters,
    submit_resolution,
)
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.rules.gates import GateRejected


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


class ClusterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blinding: str
    rows: list[ClusterRowBody]


class JobBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    reuse_umap: bool = False


def build_review_router(*, token: str, origin: str, database: Path) -> APIRouter:
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
                job = enqueue(session, run, task_id=body.task_id, reuse_umap=body.reuse_umap)
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            payload = json.loads(job.payload_json)
            return {"id": job.id, "task_id": job.task_id, **payload}

    @router.post("/api/stage-runs/{run_id}/invalidate")
    def invalidate(request: Request, run_id: int) -> dict[str, list[int]]:
        _mutation(request, token, origin)
        with factory() as session:
            _run(session, run_id)
            changed = invalidate_downstream(session, run_id)
            session.commit()
        return {"invalidated": changed}

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
