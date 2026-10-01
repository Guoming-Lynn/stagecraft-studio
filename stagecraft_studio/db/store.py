"""Write protocol versions and block an old run whose hash no longer matches."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stagecraft_studio.db.models import (
    AuditEvent,
    Project,
    ProtocolVersion,
    RuleResultRow,
    StageRun,
)
from stagecraft_studio.domain.protocol import (
    JsonValue,
    ProtocolBlocked,
    content_hash,
    file_sha256,
    protocol_hash_match,
)

ENGINE_VERSION = "0.0.0"
RULE_VERSION = "g4"


def session_factory(database: Path) -> sessionmaker[Session]:
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    return sessionmaker(bind=engine)


def create_project(session: Session, name: str) -> Project:
    row = Project(name=name, created_at=_now())
    session.add(row)
    session.flush()
    return row


def freeze_protocol(
    session: Session, project_id: int, document: dict[str, JsonValue]
) -> ProtocolVersion:
    row = ProtocolVersion(
        project_id=project_id,
        document_json=json.dumps(document, sort_keys=True),
        content_hash=content_hash(document),
        status="frozen",
        frozen_at=_now(),
    )
    session.add(row)
    session.flush()
    _audit(session, project_id, "freeze_protocol", "recorded", row.content_hash)
    return row


def open_stage_run(
    session: Session,
    *,
    project_id: int,
    protocol: ProtocolVersion,
    input_path: Path,
) -> StageRun:
    row = StageRun(
        project_id=project_id,
        protocol_id=protocol.id,
        protocol_hash=protocol.content_hash,
        input_hash=file_sha256(input_path),
        engine_version=ENGINE_VERSION,
        rule_version=RULE_VERSION,
        stage_status="READY",
        created_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def continue_stage_run(
    session: Session,
    run: StageRun,
    document: dict[str, JsonValue],
    input_path: Path,
) -> None:
    """Block the stored run when the protocol document or the input bytes changed."""
    try:
        protocol_hash_match(
            stored_protocol_hash=run.protocol_hash,
            stored_input_hash=run.input_hash,
            protocol_hash=content_hash(document),
            input_hash=file_sha256(input_path),
        )
    except ProtocolBlocked:
        session.add(
            RuleResultRow(
                stage_run_id=run.id,
                rule_id="PROTOCOL_HASH_MATCH",
                rule_status="BLOCK",
                detail_json=json.dumps({"run_id": run.id}),
                checked_at=_now(),
            )
        )
        _audit(session, run.project_id, "continue_stage_run", "rejected", "PROTOCOL_HASH_MATCH")
        session.commit()
        raise
    _audit(session, run.project_id, "continue_stage_run", "recorded", run.protocol_hash)


def _audit(session: Session, project_id: int, action: str, outcome: str, detail: str) -> None:
    session.add(
        AuditEvent(
            project_id=project_id,
            action=action,
            outcome=outcome,
            detail_json=json.dumps({"detail": detail}),
            created_at=_now(),
        )
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)
