"""Read refused-job audit rows written by the review gates."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from stagecraft_studio.db.models import AuditEvent
from stagecraft_studio.db.store import session_factory


def rejected_audit(tmp_path: Path, rule_id: str) -> bool:
    with session_factory(tmp_path / "studio.sqlite")() as session:
        rows = session.scalars(select(AuditEvent)).all()
    return any(row.outcome == "REJECTED" and rule_id in row.detail_json for row in rows)
