"""Formal Part 1 commands. The engine path comes from startup, not the request."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.engine.registry import require_task
from stagecraft_studio.rules.quicklook import quicklook_not_formal

_TASK_SCRIPTS = {
    "formal_part1_load": "part1_load.py",
    "formal_part1_qc": "part1_qc.py",
    "formal_part1_merge": "part1_merge.py",
    "formal_part1_grid": "part1_resolution_grid.py",
}


class FormalRequest(BaseModel):
    """Task id and input path. Python and the engine directory are not fields."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    input_path: Path


def formal_command(request: FormalRequest, launch: FormalLaunch) -> list[str]:
    """Reject a quicklook directory, then build argv from the startup launch."""
    task_id = require_task(request.task_id)
    script_name = _TASK_SCRIPTS.get(task_id)
    if script_name is None:
        raise UnsupportedFormalTask(task_id)
    quicklook_not_formal(request.input_path)
    return [str(launch.python), str(launch.script(script_name)), str(request.input_path)]


class UnsupportedFormalTask(Exception):
    """A registered task that is not one of the formal Part 1 entry points."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(task_id)
