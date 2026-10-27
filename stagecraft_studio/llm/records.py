"""Assistant records contain hashes and references, never keys or raw conversation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.assistant_models import LLMCall, Proposal
from stagecraft_studio.db.models import AuditEvent, StageRun
from stagecraft_studio.llm.context import PROMPT_VERSION, digest
from stagecraft_studio.llm.schemas import CallStatus, CallView, ProposalInput, ProposalView


def record_call(
    session: Session,
    *,
    call_id: str,
    run_id: int | None,
    input_hash: str,
    sources: list[dict[str, object]],
    model: str,
    status: CallStatus,
    text: str,
    usage: dict[str, int] | None = None,
    proposal: ProposalInput | None = None,
) -> CallView:
    now = datetime.now(timezone.utc)
    row = LLMCall(
        id=call_id,
        stage_run_id=run_id,
        model=model,
        prompt_version=PROMPT_VERSION,
        input_hash=input_hash,
        sources_json=json.dumps(sources),
        status=status,
        result_json=json.dumps({"text_hash": digest(text), "usage": usage}),
        created_at=now,
    )
    session.add(row)
    session.flush()
    view = None
    if proposal is not None and status == "COMPLETED":
        saved = Proposal(
            call_id=call_id,
            stage_run_id=run_id,
            body_json=proposal.model_dump_json(),
            status="DRAFT",
            created_at=now,
        )
        session.add(saved)
        session.flush()
        view = proposal_view(saved)
    run = session.get(StageRun, run_id) if run_id is not None else None
    if run:
        session.add(
            AuditEvent(
                project_id=run.project_id,
                action="assistant_call",
                outcome=status,
                detail_json=json.dumps({"call_id": call_id, "input_hash": input_hash}),
                created_at=now,
            )
        )
    session.commit()
    return CallView(
        call_id=call_id,
        status=status,
        text=text,
        model=model,
        prompt_version=PROMPT_VERSION,
        input_hash=input_hash,
        sources=sources,
        created_at=now.isoformat(),
        usage=usage,
        proposal=view,
    )


def read_call(session: Session, row: LLMCall) -> CallView:
    proposal = session.scalar(select(Proposal).where(Proposal.call_id == row.id))
    result = json.loads(row.result_json)
    safe_status = (
        row.status if row.status in {"COMPLETED", "FAILED", "REJECTED", "CANCELLED"} else "FAILED"
    )
    return CallView(
        call_id=row.id,
        status=cast(CallStatus, safe_status),
        text="该调用已记录；原始回复不会持久化。",
        model=row.model,
        prompt_version=row.prompt_version,
        input_hash=row.input_hash,
        sources=json.loads(row.sources_json),
        created_at=row.created_at.isoformat(),
        usage=result.get("usage"),
        proposal=proposal_view(proposal) if proposal else None,
    )


def proposal_view(row: Proposal) -> ProposalView:
    value = ProposalInput.model_validate_json(row.body_json)
    return ProposalView(id=row.id, kind=value.kind, values=value.values, rationale=value.rationale)
