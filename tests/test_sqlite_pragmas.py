"""Test SQLite WAL mode and busy_timeout pragmas."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import Project
from stagecraft_studio.db.store import create_project, session_factory


def test_session_factory_enables_wal_and_busy_timeout(tmp_path: Path) -> None:
    db = tmp_path / "test_pragmas.sqlite"
    upgrade_database(db)

    factory = session_factory(db)
    with factory() as session:
        journal_mode = session.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = session.execute(text("PRAGMA busy_timeout")).scalar()

        assert str(journal_mode).lower() == "wal"
        assert int(busy_timeout) == 5000


def test_concurrent_sessions_do_not_lock(tmp_path: Path) -> None:
    db = tmp_path / "test_concurrent.sqlite"
    upgrade_database(db)

    factory = session_factory(db)
    # Open session 1 and write
    with factory() as session1:
        p1 = create_project(session1, "proj1")
        session1.commit()
        assert p1.id is not None

        # Open session 2 while session 1 is active, and write
        with factory() as session2:
            p2 = create_project(session2, "proj2")
            session2.commit()
            assert p2.id is not None

        # Verify session 1 can read data written by session 2
        projs = list(session1.query(Project).all())
        assert len(projs) == 2
