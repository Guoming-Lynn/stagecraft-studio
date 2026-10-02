"""Part 3 compartment review routes. Enforces the 3 stop points over HTTP."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import StageRun
from stagecraft_studio.db.part3_reviews import (
    part3_review_center,
    submit_part3_clusters,
    submit_part3_names,
    submit_part3_resolution,
)
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.rules.gates import GateRejected


class Part3ResolutionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str
    decided_on: str
    rationale: str
    evidence_hash: str
    resolution: str
    blinding: str


class Part3ClusterRowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    decision: str
    rationale: str
    reviewer: str
    decided_on: str
    name: str = ""


class Part3ClusterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blinding: str
    rows: list[Part3ClusterRowBody]


class Part3NameRowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cluster: str
    name: str
    rationale: str
    reviewer: str
    decided_on: str


class Part3NameBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blinding: str
    rows: list[Part3NameRowBody]


def build_part3_router(
    *,
    token: str,
    origin: str,
    database: Path,
) -> APIRouter:
    router = APIRouter()
    factory = session_factory(database)

    @router.get("/api/stage-runs/{run_id}/part3/center")
    def part3_center(run_id: int) -> dict[str, object]:
        with factory() as session:
            run = _run(session, run_id)
            return part3_review_center(session, run)

    @router.post("/api/stage-runs/{run_id}/part3/resolution", status_code=201)
    def part3_resolution(
        request: Request, run_id: int, body: Part3ResolutionBody
    ) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                row = submit_part3_resolution(
                    session,
                    run,
                    reviewer=body.reviewer,
                    decided_on=body.decided_on,
                    rationale=body.rationale,
                    evidence_hash=body.evidence_hash,
                    resolution=body.resolution,
                    blinding=body.blinding,
                )
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return {"id": row.id}

    @router.post("/api/stage-runs/{run_id}/part3/clusters", status_code=201)
    def part3_clusters(request: Request, run_id: int, body: Part3ClusterBody) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                row = submit_part3_clusters(
                    session,
                    run,
                    rows=[item.model_dump() for item in body.rows],
                    blinding=body.blinding,
                )
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return {"id": row.id}

    @router.post("/api/stage-runs/{run_id}/part3/names", status_code=201)
    def part3_names(request: Request, run_id: int, body: Part3NameBody) -> dict[str, object]:
        _mutation(request, token, origin)
        with factory() as session:
            run = _run(session, run_id)
            try:
                row = submit_part3_names(
                    session,
                    run,
                    rows=[item.model_dump() for item in body.rows],
                    blinding=body.blinding,
                )
                session.commit()
            except GateRejected as exc:
                _raise(exc)
            return {"id": row.id}

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
