"""Atomic WAL-safe SQLite backup and verified restore for Studio state."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_NAME = "studio.sqlite"
MANIFEST_NAME = "backup_manifest.json"
_ALLOWED_ARCHIVE_NAMES = frozenset({SNAPSHOT_NAME, MANIFEST_NAME})
_AUDITED_TABLES: tuple[str, ...] = (
    "project",
    "protocol_version",
    "stage_run",
    "job",
    "review_decision",
    "artifact",
    "rule_result",
    "audit_event",
)


class BackupError(RuntimeError):
    """Backup or restore could not complete safely."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_sqlite(path: Path) -> tuple[str, dict[str, int]]:
    with contextlib.closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or str(integrity[0]).lower() != "ok":
            raise BackupError("SQLITE_INTEGRITY_FAILED")
        tables = {
            str(row[0])
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "alembic_version" not in tables:
            raise BackupError("NOT_A_STUDIO_DATABASE")
        rev_row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        revision = str(rev_row[0]) if rev_row and rev_row[0] else ""
        if not revision:
            raise BackupError("ALEMBIC_REVISION_MISSING")
        counts: dict[str, int] = {}
        for table in _AUDITED_TABLES:
            if table not in tables:
                raise BackupError(f"MISSING_STUDIO_TABLE:{table}")
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row else 0
    return revision, counts


def create_backup(
    database: Path,
    archive_path: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    """Create a verified zip archive containing a consistent SQLite snapshot and manifest."""
    if not database.is_file():
        raise BackupError(f"DATABASE_NOT_FOUND: {database}")
    if archive_path.exists() and not overwrite:
        raise BackupError(f"ARCHIVE_ALREADY_EXISTS: {archive_path}")

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=archive_path.parent) as tmp_str:
        tmp_dir = Path(tmp_str)
        snapshot = tmp_dir / SNAPSHOT_NAME
        try:
            with (
                contextlib.closing(sqlite3.connect(str(database))) as src,
                contextlib.closing(sqlite3.connect(str(snapshot))) as dst,
            ):
                src.backup(dst)
        except sqlite3.Error as exc:
            raise BackupError(f"SQLITE_BACKUP_FAILED: {exc}") from exc

        revision, counts = _inspect_sqlite(snapshot)
        sha256 = _sha256_file(snapshot)
        manifest: dict[str, object] = {
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "alembic_revision": revision,
            "sqlite_sha256": sha256,
            "table_counts": counts,
            "excludes_matrices_and_credentials": True,
        }
        staged_zip = tmp_dir / "staged_backup.zip"
        with zipfile.ZipFile(staged_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(snapshot, SNAPSHOT_NAME)
            zf.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        staged_zip.replace(archive_path)
    return manifest


def restore_backup(
    archive_path: Path,
    target_database: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    """Verify a backup archive before atomically replacing or creating target_database."""
    if not archive_path.is_file():
        raise BackupError(f"BACKUP_ARCHIVE_NOT_FOUND: {archive_path}")
    if target_database.exists() and not overwrite:
        raise BackupError(f"TARGET_DATABASE_EXISTS: {target_database}")

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            names = set(zf.namelist())
            if names != _ALLOWED_ARCHIVE_NAMES:
                raise BackupError("INVALID_BACKUP_ARCHIVE_CONTENTS")
            manifest_raw = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
            if not isinstance(manifest_raw, dict):
                raise BackupError("INVALID_BACKUP_MANIFEST")
            sqlite_bytes = zf.read(SNAPSHOT_NAME)
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackupError(f"CORRUPT_BACKUP_ARCHIVE: {exc}") from exc

    expected_hash = str(manifest_raw.get("sqlite_sha256", "")).strip().casefold()
    actual_hash = hashlib.sha256(sqlite_bytes).hexdigest()
    if not expected_hash or actual_hash != expected_hash:
        raise BackupError("BACKUP_CHECKSUM_MISMATCH")

    target_database.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target_database.parent) as tmp_str:
        staged_db = Path(tmp_str) / SNAPSHOT_NAME
        staged_db.write_bytes(sqlite_bytes)
        try:
            revision, counts = _inspect_sqlite(staged_db)
        except sqlite3.Error as exc:
            raise BackupError(f"SQLITE_RESTORE_INVALID: {exc}") from exc
        if revision != str(manifest_raw.get("alembic_revision", "")):
            raise BackupError("BACKUP_REVISION_MISMATCH")
        expected_counts = manifest_raw.get("table_counts")
        if not isinstance(expected_counts, dict) or counts != expected_counts:
            raise BackupError("BACKUP_ROW_COUNT_MISMATCH")

        if overwrite:
            for suffix in ("-wal", "-shm"):
                sidecar = Path(f"{target_database}{suffix}")
                if sidecar.exists():
                    sidecar.unlink()
        staged_db.replace(target_database)

    return {
        "alembic_revision": revision,
        "sqlite_sha256": actual_hash,
        "table_counts": counts,
    }
