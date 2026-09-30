"""Registered task identifiers. Unknown ids are rejected."""

from __future__ import annotations

REGISTERED_TASKS = frozenset({"quicklook_run", "quicklook_inspect"})


class UnsupportedTask(Exception):
    """The worker received a task id that is not registered."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(task_id)


def require_task(task_id: str) -> str:
    if task_id not in REGISTERED_TASKS:
        raise UnsupportedTask(task_id)
    return task_id
