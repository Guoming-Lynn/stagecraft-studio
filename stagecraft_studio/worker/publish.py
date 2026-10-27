"""Atomic publishing and checksum utilities for worker jobs."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Artifact, Job


def stream_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def atomic_publish(src: Path, dest: Path) -> None:
    """Publish src directory to dest atomically by staging replacement."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if dest.exists():
        timestamp = int(datetime.now(timezone.utc).timestamp() * 1000)
        backup = dest.parent / f".{dest.name}.old.{timestamp}"
        dest.rename(backup)
    try:
        os.replace(src, dest)
    except Exception:
        if backup is not None and backup.exists() and not dest.exists():
            backup.rename(dest)
        raise
    finally:
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def register_artifacts(session: Session, job: Job, stage_dir: Path, publish_rel: str) -> None:
    """Supersede earlier artifacts under the same folder, then record the new files."""
    prior_job_ids = select(Job.id).where(
        Job.stage_run_id == job.stage_run_id,
        Job.task_id == job.task_id,
    )
    session.execute(
        update(Artifact)
        .where(
            Artifact.job_id.in_(prior_job_ids),
            Artifact.artifact_status == "VALID",
            Artifact.relative_path.startswith(f"{publish_rel}/", autoescape=True),
        )
        .values(artifact_status="SUPERSEDED")
    )
    for fpath in sorted((stage_dir / publish_rel).rglob("*")):
        if fpath.is_file():
            session.add(
                Artifact(
                    job_id=job.id,
                    relative_path=fpath.relative_to(stage_dir).as_posix(),
                    content_hash=stream_sha256(fpath),
                    artifact_status="VALID",
                )
            )
