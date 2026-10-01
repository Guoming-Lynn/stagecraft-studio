"""SQLite protocol freeze. A changed document blocks the old stage run."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from stagecraft_studio.db.models import AuditEvent, RuleResultRow
from stagecraft_studio.db.store import (
    continue_stage_run,
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.domain.protocol import ProtocolBlocked, content_hash, protocol_document

ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "project",
    "protocol_version",
    "stage_run",
    "job",
    "review_decision",
    "artifact",
    "rule_result",
    "audit_event",
}


def test_first_revision_creates_the_core_tables(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    _upgrade(database)
    factory = session_factory(database)
    with factory() as session:
        names = set(inspect(session.get_bind()).get_table_names())
    assert names >= TABLES


def test_changed_protocol_blocks_the_old_run(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    _upgrade(database)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts-v1")
    original = _document(harmony_keys=["dataset"])
    changed = _document(harmony_keys=["dataset", "library_id"])
    assert content_hash(original) != content_hash(changed)
    factory = session_factory(database)
    with factory() as session:
        project = create_project(session, "plaque")
        protocol = freeze_protocol(session, project.id, original)
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
        session.commit()
        run_id = run.id
        project_id = project.id
    with factory() as session:
        stored = session.get(type(run), run_id)
        assert stored is not None
        with pytest.raises(ProtocolBlocked, match="PROTOCOL_HASH_MATCH"):
            continue_stage_run(session, stored, changed, source)
        blocked = session.query(RuleResultRow).filter_by(stage_run_id=run_id).one()
        assert blocked.rule_id == "PROTOCOL_HASH_MATCH"
        assert blocked.rule_status == "BLOCK"
        rejected = (
            session.query(AuditEvent)
            .filter_by(project_id=project_id, action="continue_stage_run", outcome="rejected")
            .one()
        )
        assert "PROTOCOL_HASH_MATCH" in rejected.detail_json


def test_same_document_and_input_match(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    _upgrade(database)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts-v1")
    document = _document(harmony_keys=["dataset"])
    factory = session_factory(database)
    with factory() as session:
        project = create_project(session, "plaque")
        protocol = freeze_protocol(session, project.id, document)
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=source)
        session.commit()
        run_id = run.id
    with factory() as session:
        stored = session.get(type(run), run_id)
        assert stored is not None
        continue_stage_run(session, stored, document, source)
        session.commit()


def _document(harmony_keys: list[str]) -> dict[str, object]:
    return protocol_document(
        target_gene="STAT1",
        species="human",
        manifest=[{"library_id": "A", "dataset": "D1"}],
        qc={"loose_min_genes": 200, "expected_doublet_rate": 0.05},
        harmony_keys=harmony_keys,
    )


def _upgrade(database: Path) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "head")
