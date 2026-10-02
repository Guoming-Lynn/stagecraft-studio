"""Worker for queued formal analysis jobs.

Runs one job at a time in a background thread.
Outputs are staged in a temporary directory and published atomically
only when the child process exits 0 and satisfies the output contract.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from stagecraft_studio.db.models import (
    Artifact,
    AuditEvent,
    Job,
    Project,
    ProtocolVersion,
    StageRun,
)
from stagecraft_studio.db.store import continue_stage_run, session_factory
from stagecraft_studio.domain.protocol import ProtocolBlocked
from stagecraft_studio.engine.formal_args import (
    SPECS,
    FormalPathRejected,
    UnsupportedFormalTask,
    formal_argv,
)
from stagecraft_studio.engine.formal_contract import FORMAL_OUTPUT_CONTRACTS
from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.rules.evaluator import record_job_rules
from stagecraft_studio.rules.quicklook import FormalInputRejected
from stagecraft_studio.worker.process_tree import kill_tree, spawn


def stream_sha256(path: Path) -> str:
    """Compute sha256 checksum with streaming chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _atomic_publish(src: Path, dest: Path) -> None:
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FormalWorker:
    """Background worker executing one queued formal task at a time."""

    def __init__(self, database: Path, launch: FormalLaunch) -> None:
        self.database = database
        self.launch = launch
        self._factory: sessionmaker[Session] = session_factory(database)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_job_id: int | None = None
        self._current_process: subprocess.Popen[bytes] | None = None
        self._current_tmp_dir: Path | None = None

    def start(self) -> None:
        """Start the background worker thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._wake_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the worker to stop and wait for completion."""
        self._stop_event.set()
        self._wake_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def wake(self) -> None:
        """Wake up the worker immediately when a new job is queued."""
        self._wake_event.set()

    def recover(self) -> None:
        """Mark leftover RUNNING jobs INTERRUPTED and clean up their tmp directories."""
        with self._factory() as session:
            jobs = list(session.scalars(select(Job).where(Job.job_status == "RUNNING")).all())
            for job in jobs:
                job.job_status = "INTERRUPTED"
                payload = json.loads(job.payload_json) if job.payload_json else {}
                payload["interrupted_at"] = _now().isoformat()
                job.payload_json = json.dumps(payload)
                run = session.get(StageRun, job.stage_run_id)
                if run is not None:
                    stage_dir = self._resolve_stage_dir(session, run)
                    tmp_dir = stage_dir / ".studio" / "tmp" / str(job.id)
                    if tmp_dir.exists():
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    session.add(
                        AuditEvent(
                            project_id=run.project_id,
                            action="formal_job_recovery",
                            outcome="INTERRUPTED",
                            detail_json=json.dumps({"job_id": job.id, "reason": "server_restart"}),
                            created_at=_now(),
                        )
                    )
            session.commit()

    def cancel(self, job_id: int) -> dict[str, object]:
        """Cancel a running or queued job, killing process and removing tmp directory."""
        with self._factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return {"id": job_id, "job_status": "NOT_FOUND"}
            if job.job_status in {"COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED"}:
                return {"id": job.id, "job_status": "CONFLICT", "current_status": job.job_status}
            job.job_status = "CANCELLED"
            payload = json.loads(job.payload_json) if job.payload_json else {}
            payload["cancelled_at"] = _now().isoformat()
            job.payload_json = json.dumps(payload)
            run = session.get(StageRun, job.stage_run_id)
            if run is not None:
                stage_dir = self._resolve_stage_dir(session, run)
                disk_tmp = stage_dir / ".studio" / "tmp" / str(job_id)
                if disk_tmp.exists():
                    shutil.rmtree(disk_tmp, ignore_errors=True)
                session.add(
                    AuditEvent(
                        project_id=run.project_id,
                        action="formal_job_cancel",
                        outcome="CANCELLED",
                        detail_json=json.dumps({"job_id": job.id, "task_id": job.task_id}),
                        created_at=_now(),
                    )
                )
            session.commit()

        with self._lock:
            is_current = self._current_job_id == job_id
            proc = self._current_process if is_current else None
            tmp_dir = self._current_tmp_dir if is_current else None

        if proc is not None and proc.pid:
            kill_tree(proc.pid)
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=3.0)

        if tmp_dir is not None and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return {"id": job_id, "job_status": "CANCELLED"}

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            next_id = self._peek_next_job_id()
            if next_id is None:
                self._wake_event.wait(timeout=0.5)
                self._wake_event.clear()
                continue
            self._execute(next_id)

    def _peek_next_job_id(self) -> int | None:
        with self._factory() as session:
            job = session.scalars(
                select(Job).where(Job.job_status == "QUEUED").order_by(Job.id.asc()).limit(1)
            ).first()
            return job.id if job is not None else None

    def _resolve_stage_dir(self, session: Session, run: StageRun) -> Path:
        project = session.get(Project, run.project_id)
        if project and project.root_path:
            return Path(project.root_path) / "analysis" / f"stage_{run.id}"
        protocol = session.get(ProtocolVersion, run.protocol_id)
        if protocol and protocol.document_json:
            doc = json.loads(protocol.document_json)
            if isinstance(doc, dict) and "data_path" in doc:
                return Path(str(doc["data_path"])).parent / "analysis" / f"stage_{run.id}"
        return Path("analysis") / f"stage_{run.id}"

    def _execute(self, job_id: int) -> None:
        with self._factory() as session:
            job = session.get(Job, job_id)
            if job is None or job.job_status != "QUEUED":
                return
            run = session.get(StageRun, job.stage_run_id)
            if run is None:
                self._mark_failed(session, job, "STAGE_RUN_NOT_FOUND")
                return
            if run.invalidated or run.stage_status == "INVALIDATED":
                job.job_status = "CANCELLED"
                session.commit()
                return

            protocol = session.get(ProtocolVersion, run.protocol_id)
            if protocol is None:
                self._mark_failed(session, job, "PROTOCOL_NOT_FOUND")
                return

            document = json.loads(protocol.document_json) if protocol.document_json else {}
            data_path_str = str(document.get("data_path", "")).strip()
            data_path = Path(data_path_str) if data_path_str else None
            project = session.get(Project, run.project_id)
            if data_path and not data_path.is_absolute() and project and project.root_path:
                cand = Path(project.root_path) / data_path
                if cand.is_file():
                    data_path = cand
            if data_path is None or not data_path.is_file():
                self._mark_failed(session, job, "INPUT_FILE_NOT_FOUND")
                return

            try:
                continue_stage_run(session, run, document, data_path)
            except ProtocolBlocked:
                self._mark_failed(session, job, "PROTOCOL_HASH_MATCH")
                return

            job.job_status = "RUNNING"
            session.commit()
            stage_dir = self._resolve_stage_dir(session, run)
            work_dir = (
                Path(project.root_path).resolve()
                if (project and project.root_path)
                else stage_dir.resolve()
            )

        tmp_dir = stage_dir / ".studio" / "tmp" / str(job_id)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        with self._lock:
            self._current_job_id = job_id
            self._current_tmp_dir = tmp_dir

        try:
            self._run_job_process(job_id, stage_dir, tmp_dir, work_dir)
        finally:
            with self._lock:
                self._current_job_id = None
                self._current_process = None
                self._current_tmp_dir = None
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _run_job_process(self, job_id: int, stage_dir: Path, tmp_dir: Path, work_dir: Path) -> None:
        with self._factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            payload = json.loads(job.payload_json) if job.payload_json else {}
            fields = dict(payload.get("fields", {}))
            task_id = job.task_id

        if task_id == "formal_stage_report":
            fields.setdefault("stage", stage_dir)
            fields["out"] = tmp_dir / "REPORT.md"
        else:
            fields["out"] = tmp_dir

        path_keys: set[str] = {"out", "stage"}
        spec = SPECS.get(task_id)
        if spec is not None:
            path_keys |= {key for _, key, kind in spec[2] if kind == "path"}

        for k, v in list(fields.items()):
            if k in path_keys and isinstance(v, (str, Path)):
                pv = Path(v)
                if not pv.is_absolute():
                    cand_stage = (stage_dir / pv).resolve()
                    if cand_stage.is_relative_to(work_dir) and cand_stage.exists():
                        fields[k] = cand_stage
                    else:
                        cand_work = (work_dir / pv).resolve()
                        if cand_work.is_relative_to(work_dir):
                            fields[k] = cand_work

        try:
            argv = formal_argv(task_id, fields, work_dir=work_dir, launch=self.launch)
        except (FormalPathRejected, FormalInputRejected, UnsupportedFormalTask, ValueError) as exc:
            with self._factory() as session:
                job = session.get(Job, job_id)
                if job:
                    self._mark_failed(session, job, f"ARG_VALIDATION_FAILED: {exc}")
            return

        try:
            proc = spawn(argv, cwd=tmp_dir)
            with self._lock:
                self._current_process = proc
        except Exception as exc:
            with self._factory() as session:
                job = session.get(Job, job_id)
                if job:
                    self._mark_failed(session, job, f"SPAWN_FAILED: {exc}")
            return

        exit_code = proc.wait()

        with self._factory() as session:
            job = session.get(Job, job_id)
            if job is None or job.job_status == "CANCELLED":
                return

            if exit_code != 0:
                self._mark_failed(session, job, f"EXIT_CODE_{exit_code}")
                return

            contract = FORMAL_OUTPUT_CONTRACTS.get(task_id, ())
            missing = [fname for fname in contract if not (tmp_dir / fname).is_file()]
            if missing:
                self._mark_failed(session, job, "OUTPUT_CONTRACT_MISSING")
                return

            dest_dir = stage_dir / task_id
            _atomic_publish(tmp_dir, dest_dir)

            prior_job_ids = select(Job.id).where(
                Job.stage_run_id == job.stage_run_id,
                Job.task_id == job.task_id,
                Job.id != job.id,
            )
            session.execute(
                update(Artifact)
                .where(
                    Artifact.job_id.in_(prior_job_ids),
                    Artifact.artifact_status == "VALID",
                )
                .values(artifact_status="SUPERSEDED")
            )

            for fpath in sorted(dest_dir.rglob("*")):
                if fpath.is_file():
                    rel_path = fpath.relative_to(stage_dir).as_posix()
                    digest = stream_sha256(fpath)
                    session.add(
                        Artifact(
                            job_id=job.id,
                            relative_path=rel_path,
                            content_hash=digest,
                            artifact_status="VALID",
                        )
                    )

            record_job_rules(session, job, dest_dir=dest_dir)
            job.job_status = "COMPLETED"
            session.commit()

    def _mark_failed(self, session: Session, job: Job, reason: str) -> None:
        job.job_status = "FAILED"
        payload = json.loads(job.payload_json) if job.payload_json else {}
        payload["failure_reason"] = reason
        job.payload_json = json.dumps(payload)
        record_job_rules(session, job, dest_dir=None, failure_reason=reason)
        session.commit()
