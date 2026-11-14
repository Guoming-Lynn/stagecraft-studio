"""End-to-end tests for WAL-safe SQLite backup and verified restore."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import select
from stagecraft_studio.db.backup import (
    MANIFEST_NAME,
    SNAPSHOT_NAME,
    BackupError,
    create_backup,
    restore_backup,
)
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.models import AuditEvent, ProtocolVersion, ReviewDecision, StageRun
from stagecraft_studio.db.reviews import evidence_digest, submit_resolution
from stagecraft_studio.db.store import (
    create_project,
    freeze_protocol,
    open_stage_run,
    session_factory,
)
from stagecraft_studio.domain.protocol import protocol_document
from stagecraft_studio.engine.cli import main as studio_cli


def _populate_studio_db(db_path: Path, work_dir: Path) -> tuple[str, str]:
    upgrade_database(db_path)
    counts = work_dir / "synthetic.h5ad"
    counts.write_bytes(b"synthetic-matrix-bytes")
    factory = session_factory(db_path)
    with factory() as session:
        project = create_project(session, "backup-drill", root_path=str(work_dir))
        protocol = freeze_protocol(
            session,
            project.id,
            protocol_document(
                target_gene="STAT1",
                species="human",
                manifest=[{"library_id": "L1", "dataset": "D1", "donor_id": "P1"}],
                qc={"loose_min_genes": 200},
                harmony_keys=["dataset"],
            ),
        )
        run = open_stage_run(session, project_id=project.id, protocol=protocol, input_path=counts)
        evidence_text = json.dumps(
            {
                "overview": [
                    {
                        "resolution": "0.4",
                        "n_clusters": 2,
                        "min_cluster_size": 20,
                        "max_cluster_size": 40,
                    }
                ],
                "clusters_by_resolution": {"0.4": ["0", "1"]},
            }
        )
        run.evidence_json = evidence_text
        digest = evidence_digest(evidence_text)
        decision = submit_resolution(
            session,
            run,
            reviewer="Lin",
            decided_on="2026-10-28",
            rationale="Synthetic backup drill fixture",
            evidence_hash=digest,
            resolution="0.4",
            blinding="BLIND",
            round_index=0,
        )
        session.commit()
        return protocol.content_hash, decision.evidence_hash


def test_cli_backup_and_restore_preserves_frozen_state_and_omits_matrices(tmp_path: Path) -> None:
    source_db = tmp_path / "live" / "studio.sqlite"
    source_db.parent.mkdir()
    proto_hash, review_hash = _populate_studio_db(source_db, source_db.parent)
    archive = tmp_path / "backups" / "studio-backup.zip"

    # Keep a live WAL session open during backup to exercise online snapshot consistency
    live_factory = session_factory(source_db)
    with live_factory() as open_session:
        assert open_session.scalar(select(StageRun.id)) == 1
        rc_backup = studio_cli(["backup", "--database", str(source_db), "--out", str(archive)])
        assert rc_backup == 0

    with zipfile.ZipFile(archive, "r") as zf:
        assert set(zf.namelist()) == {SNAPSHOT_NAME, MANIFEST_NAME}
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        assert manifest["excludes_matrices_and_credentials"] is True
        assert manifest["table_counts"]["protocol_version"] == 1
        assert manifest["table_counts"]["review_decision"] == 1

    restored_db = tmp_path / "restored" / "studio.sqlite"
    rc_restore = studio_cli(["restore", "--backup", str(archive), "--database", str(restored_db)])
    assert rc_restore == 0

    # Refuses to overwrite an existing database unless --overwrite is passed
    rc_refused = studio_cli(["restore", "--backup", str(archive), "--database", str(restored_db)])
    assert rc_refused == 2

    with session_factory(restored_db)() as restored_session:
        proto = restored_session.scalar(select(ProtocolVersion))
        decision = restored_session.scalar(select(ReviewDecision))
        audits = list(restored_session.scalars(select(AuditEvent)))
        assert proto is not None and proto.content_hash == proto_hash
        assert decision is not None and decision.evidence_hash == review_hash
        assert len(audits) >= 1


def test_restore_rejects_tampered_checksum_and_unexpected_members(tmp_path: Path) -> None:
    source_db = tmp_path / "src" / "studio.sqlite"
    source_db.parent.mkdir()
    _populate_studio_db(source_db, source_db.parent)
    clean_zip = tmp_path / "clean.zip"
    create_backup(source_db, clean_zip)

    # 1. Tamper sqlite bytes -> checksum mismatch leaves existing target untouched
    tampered_zip = tmp_path / "tampered.zip"
    with (
        zipfile.ZipFile(clean_zip, "r") as src_zf,
        zipfile.ZipFile(tampered_zip, "w") as dst_zf,
    ):
        raw_sqlite = bytearray(src_zf.read(SNAPSHOT_NAME))
        raw_sqlite[-1] ^= 0xFF
        dst_zf.writestr(SNAPSHOT_NAME, bytes(raw_sqlite))
        dst_zf.writestr(MANIFEST_NAME, src_zf.read(MANIFEST_NAME))

    existing_target = tmp_path / "protected.sqlite"
    existing_target.write_bytes(b"keep-me-safe")
    with pytest.raises(BackupError, match="BACKUP_CHECKSUM_MISMATCH"):
        restore_backup(tampered_zip, existing_target, overwrite=True)
    assert existing_target.read_bytes() == b"keep-me-safe"

    # 2. Extra unexpected entry in zip -> rejected before reading sqlite
    extra_zip = tmp_path / "extra.zip"
    with (
        zipfile.ZipFile(clean_zip, "r") as src_zf,
        zipfile.ZipFile(extra_zip, "w") as dst_zf,
    ):
        dst_zf.writestr(SNAPSHOT_NAME, src_zf.read(SNAPSHOT_NAME))
        dst_zf.writestr(MANIFEST_NAME, src_zf.read(MANIFEST_NAME))
        dst_zf.writestr("../evil.txt", "nope")

    with pytest.raises(BackupError, match="INVALID_BACKUP_ARCHIVE_CONTENTS"):
        restore_backup(extra_zip, tmp_path / "never_created.sqlite")
    assert not (tmp_path / "never_created.sqlite").exists()
