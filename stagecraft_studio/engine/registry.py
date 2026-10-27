"""Registered task identifiers. Unknown ids are rejected."""

from __future__ import annotations

REGISTERED_TASKS = frozenset(
    {
        "quicklook_run",
        "quicklook_inspect",
        "formal_part1_load",
        "formal_part1_qc",
        "formal_part1_merge",
        "formal_part1_grid",
        "formal_part1_round",
        "formal_part1_review_tables",
        "formal_part1_lock",
        "formal_part2_survey",
        "formal_part2_figures",
        "formal_part3_recluster",
        "formal_part4_survey",
        "formal_part4_figures",
        "formal_part5_prepare",
        "formal_stage_report",
    }
)


# Tasks whose published outputs show target-gene results. Hidden until cluster review is done.
TARGET_EXPOSING_TASKS = frozenset(
    {
        "formal_part2_survey",
        "formal_part2_figures",
        "formal_part4_survey",
        "formal_part4_figures",
        "formal_part5_prepare",
        "formal_stage_report",
    }
)


class UnsupportedTask(Exception):
    """The worker received a task id that is not registered."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(task_id)


def require_task(task_id: str) -> str:
    if task_id not in REGISTERED_TASKS:
        raise UnsupportedTask(task_id)
    return task_id
