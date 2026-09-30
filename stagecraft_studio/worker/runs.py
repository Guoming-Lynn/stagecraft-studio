"""One background quicklook at a time. The run id never carries a file path."""

from __future__ import annotations

import json
import secrets
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.engine.quicklook import (
    QuicklookRequest,
    prepare_quicklook,
    write_run_status,
)
from stagecraft_studio.worker.process_tree import kill_tree, spawn


class RunBusy(Exception):
    """A quicklook is already running."""

    def __init__(self) -> None:
        super().__init__("已有一次速览在运行。请等它结束或取消后再提交。")


@dataclass
class RunRecord:
    run_id: str
    output_root: Path
    status: str
    pid: int | None = None
    enrichment: str = ""
    stopped_after: str = ""
    command: tuple[str, ...] = ()
    process: subprocess.Popen[bytes] | None = None


class RunStore:
    """Server-side map from run id to output directory."""

    def __init__(self, state_path: Path) -> None:
        self._path = state_path
        self._lock = threading.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._load()

    def recover(self) -> None:
        """Mark leftover running records interrupted and stop any leftover pid."""
        with self._lock:
            for record in self._runs.values():
                if record.status not in {"running", "starting"}:
                    continue
                pid = record.pid
                record.status = "interrupted"
                record.pid = None
                record.process = None
                _mark(record, "interrupted", None)
                if pid is not None:
                    kill_tree(pid)
            self._save()

    def start(self, request: QuicklookRequest, launch: EngineLaunch) -> str:
        """Validate, write the config, and return as soon as the process is started."""
        with self._lock:
            if self._busy():
                raise RunBusy()
            run_id = secrets.token_hex(8)
            self._runs[run_id] = RunRecord(
                run_id=run_id,
                output_root=request.output_root,
                status="starting",
            )
            self._save()
        try:
            prepared = prepare_quicklook(request, python=launch.python, script=launch.script)
        except Exception:
            with self._lock:
                self._runs.pop(run_id, None)
                self._save()
            raise
        try:
            process = spawn(prepared.command)
        except OSError:
            with self._lock:
                record = self._runs[run_id]
                record.status = "failed"
                record.command = tuple(prepared.command)
                _mark(record, "failed", None)
                self._save()
            raise
        with self._lock:
            record = self._runs[run_id]
            record.output_root = request.output_root
            record.status = "running"
            record.pid = process.pid
            record.process = process
            record.command = tuple(prepared.command)
            record.enrichment = prepared.enrichment
            record.stopped_after = prepared.stopped_after
            self._save()
        threading.Thread(target=self._watch, args=(run_id,), daemon=True).start()
        return run_id

    def cancel(self, run_id: str) -> None:
        """Stop the process tree and record cancelled. Unknown ids do nothing."""
        with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status not in {"running", "starting"}:
                return
            record.status = "cancelled"
            pid = record.pid
            record.pid = None
            _mark(record, "cancelled", None)
            self._save()
        if pid is not None:
            kill_tree(pid)

    def get(self, run_id: str) -> RunRecord | None:
        """Return the record, finishing it first if the process has already exited."""
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            process = record.process
            if record.status == "running" and process is not None:
                code = process.poll()
                if code is not None:
                    self._finish(record, code)
            return record

    def _watch(self, run_id: str) -> None:
        with self._lock:
            process = self._runs[run_id].process
        if process is None:
            return
        code = process.wait()
        with self._lock:
            record = self._runs.get(run_id)
            if record is None or record.status != "running":
                return
            if isinstance(code, int):
                self._finish(record, code)

    def _finish(self, record: RunRecord, code: int) -> None:
        status = "succeeded" if code == 0 else "failed"
        record.status = status
        record.pid = None
        record.process = None
        _mark(record, status, code)
        self._save()

    def _busy(self) -> bool:
        return any(record.status in {"running", "starting"} for record in self._runs.values())

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        runs = payload.get("runs") if isinstance(payload, dict) else None
        if not isinstance(runs, dict):
            return
        for run_id, item in runs.items():
            if not isinstance(run_id, str) or not isinstance(item, dict):
                continue
            root = item.get("output_root")
            status = item.get("status")
            if not isinstance(root, str) or not isinstance(status, str):
                continue
            pid = item.get("pid")
            self._runs[run_id] = RunRecord(
                run_id=run_id,
                output_root=Path(root),
                status=status,
                pid=pid if isinstance(pid, int) else None,
                enrichment=_text(item.get("enrichment")),
                stopped_after=_text(item.get("stopped_after")),
                command=_command(item.get("command")),
            )

    def _save(self) -> None:
        payload = {
            "runs": {
                run_id: {
                    "output_root": str(record.output_root),
                    "status": record.status,
                    "pid": record.pid,
                    "enrichment": record.enrichment,
                    "stopped_after": record.stopped_after,
                    "command": list(record.command),
                }
                for run_id, record in self._runs.items()
            }
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(self._path)


def _mark(record: RunRecord, status: str, returncode: int | None) -> None:
    path = record.output_root / "run_status.json"
    enrichment = record.enrichment
    stopped_after = record.stopped_after
    if path.is_file():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = None
        if isinstance(current, dict):
            if not enrichment and isinstance(current.get("enrichment"), str):
                enrichment = current["enrichment"]
            if not stopped_after and isinstance(current.get("stopped_after"), str):
                stopped_after = current["stopped_after"]
    elif status == "interrupted":
        return
    write_run_status(
        record.output_root,
        status,
        returncode,
        enrichment=enrichment,
        stopped_after=stopped_after,
    )


def _text(value: object) -> str:
    if isinstance(value, str):
        return value
    return ""


def _command(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(part) for part in value)
