"""Named arguments for formal scripts. Paths have to stay inside the work directory."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict

from stagecraft_studio.engine.formal_launch import FormalLaunch
from stagecraft_studio.engine.registry import require_task
from stagecraft_studio.rules.quicklook import quicklook_not_formal

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_Format = Literal["h5ad", "10x_mtx", "10x_h5"]
_Model = Literal["limma_voom", "edger_ql", "deseq2"]


def _token(value: str) -> str:
    if _TOKEN.fullmatch(value) is None:
        raise ValueError("名字只能用字母、数字、点、下划线和连字符，并且不能以连字符开头")
    return value


def _optional_token(value: str) -> str:
    return value if value == "" else _token(value)


Token = Annotated[str, AfterValidator(_token)]
OptionalToken = Annotated[str, AfterValidator(_optional_token)]


class FormalPathRejected(Exception):
    """A path resolved outside the stage work directory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(str(path))


class UnsupportedFormalTask(Exception):
    """A registered task that does not call the formal engine."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(task_id)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoadArgs(_Args):
    library_id: Token
    input: Path
    format: _Format
    out: Path
    donor_map: Path | None = None
    dataset: OptionalToken = ""


class QcArgs(_Args):
    library_id: Token
    source: Path
    config: Path
    out: Path
    loaded: Path | None = None


class MergeArgs(_Args):
    gene: Token
    out: Path
    manifest: Path | None = None


class GridArgs(_Args):
    common: Path
    gene: Token
    config: Path
    out: Path


class Part1RoundArgs(_Args):
    common: Path
    previous_grid: Path
    review: Path
    config: Path
    gene: Token
    round_index: int
    out: Path


class ReviewTableArgs(_Args):
    grid: Path
    resolution: str
    round_index: int
    gene: Token
    out: Path
    lineage_genes: str = ""


class LockArgs(_Args):
    common: Path
    grid: Path
    review: Path
    gene: Token
    out: Path


class ReclusterArgs(_Args):
    input: Path
    barcodes: Path
    gene: Token
    lineage: Token
    seed: int
    completed_rounds: int
    still_mixed: bool = False
    out: Path


class SurveyArgs(_Args):
    input: Path
    gene: Token
    group: Token
    out: Path


class FigureArgs(SurveyArgs):
    colors: Path


class Part4SurveyArgs(SurveyArgs):
    lineage_stopped: bool = False


class Part4FigureArgs(FigureArgs):
    lineage_stopped: bool = False


class PrepareArgs(_Args):
    input: Path
    gene: Token
    group: Token
    arm: Token
    out: Path
    part4_flag: OptionalToken = ""
    model: _Model | Literal[""] = ""
    single_source_declared: bool = False
    block_fallback_declared: bool = False
    audit_flags: Path | None = None
    verdict_table: Path | None = None


class ReportArgs(_Args):
    stage: Path
    out: Path | None = None


# flag, field, kind. kind is value, path, optional, or switch.
_Arg = tuple[str, str, str]


def _spec(
    script: str, model: type[_Args], argv: tuple[_Arg, ...]
) -> tuple[str, type[_Args], tuple[_Arg, ...]]:
    return script, model, argv


_PATH = "path"
_VALUE = "value"
_OPTIONAL = "optional"
_SWITCH = "switch"

SPECS: dict[str, tuple[str, type[_Args], tuple[_Arg, ...]]] = {
    "formal_part1_load": _spec(
        "part1_load.py",
        LoadArgs,
        (
            ("--library-id", "library_id", _VALUE),
            ("--input", "input", _PATH),
            ("--format", "format", _VALUE),
            ("--out", "out", _PATH),
            ("--donor-map", "donor_map", _OPTIONAL),
            ("--dataset", "dataset", _OPTIONAL),
        ),
    ),
    "formal_part1_qc": _spec(
        "part1_qc.py",
        QcArgs,
        (
            ("--library-id", "library_id", _VALUE),
            ("--source", "source", _PATH),
            ("--loaded", "loaded", _OPTIONAL),
            ("--config", "config", _PATH),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part1_merge": _spec(
        "part1_merge.py",
        MergeArgs,
        (
            ("--manifest", "manifest", _OPTIONAL),
            ("--gene", "gene", _VALUE),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part1_grid": _spec(
        "part1_resolution_grid.py",
        GridArgs,
        (
            ("--common", "common", _PATH),
            ("--gene", "gene", _VALUE),
            ("--config", "config", _PATH),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part1_round": _spec(
        "part1_round.py",
        Part1RoundArgs,
        (
            ("--common", "common", _PATH),
            ("--previous-grid", "previous_grid", _PATH),
            ("--review", "review", _PATH),
            ("--config", "config", _PATH),
            ("--gene", "gene", _VALUE),
            ("--round-index", "round_index", _VALUE),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part1_review_tables": _spec(
        "cluster_review_tables.py",
        ReviewTableArgs,
        (
            ("--input", "grid", _PATH),
            ("--resolution", "resolution", _VALUE),
            ("--round-index", "round_index", _VALUE),
            ("--gene", "gene", _VALUE),
            ("--lineage-genes", "lineage_genes", _OPTIONAL),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part1_lock": _spec(
        "part1_lock.py",
        LockArgs,
        (
            ("--common", "common", _PATH),
            ("--grid", "grid", _PATH),
            ("--review", "review", _PATH),
            ("--gene", "gene", _VALUE),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part3_recluster": _spec(
        "part3_recluster.py",
        ReclusterArgs,
        (
            ("--input", "input", _PATH),
            ("--barcodes", "barcodes", _PATH),
            ("--gene", "gene", _VALUE),
            ("--lineage", "lineage", _VALUE),
            ("--seed", "seed", _VALUE),
            ("--completed-rounds", "completed_rounds", _VALUE),
            ("--still-mixed", "still_mixed", _SWITCH),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part2_survey": _spec(
        "part2_survey.py",
        SurveyArgs,
        (
            ("--input", "input", _PATH),
            ("--gene", "gene", _VALUE),
            ("--group", "group", _VALUE),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part2_figures": _spec(
        "part2_figures.py",
        FigureArgs,
        (
            ("--input", "input", _PATH),
            ("--gene", "gene", _VALUE),
            ("--group", "group", _VALUE),
            ("--colors", "colors", _PATH),
            ("--out", "out", _PATH),
        ),
    ),
    "formal_part4_survey": _spec(
        "part4_survey.py",
        Part4SurveyArgs,
        (
            ("--input", "input", _PATH),
            ("--gene", "gene", _VALUE),
            ("--group", "group", _VALUE),
            ("--out", "out", _PATH),
            ("--lineage-stopped", "lineage_stopped", _SWITCH),
        ),
    ),
    "formal_part4_figures": _spec(
        "part4_figures.py",
        Part4FigureArgs,
        (
            ("--input", "input", _PATH),
            ("--gene", "gene", _VALUE),
            ("--group", "group", _VALUE),
            ("--colors", "colors", _PATH),
            ("--out", "out", _PATH),
            ("--lineage-stopped", "lineage_stopped", _SWITCH),
        ),
    ),
    "formal_part5_prepare": _spec(
        "part5_prepare.py",
        PrepareArgs,
        (
            ("--input", "input", _PATH),
            ("--gene", "gene", _VALUE),
            ("--group", "group", _VALUE),
            ("--arm", "arm", _VALUE),
            ("--out", "out", _PATH),
            ("--part4-flag", "part4_flag", _OPTIONAL),
            ("--model", "model", _OPTIONAL),
            ("--single-source-declared", "single_source_declared", _SWITCH),
            ("--block-fallback-declared", "block_fallback_declared", _SWITCH),
            ("--audit-flags", "audit_flags", _OPTIONAL),
            ("--verdict-table", "verdict_table", _OPTIONAL),
        ),
    ),
    "formal_stage_report": _spec(
        "stage_report.py",
        ReportArgs,
        (("--stage", "stage", _PATH), ("--out", "out", _OPTIONAL)),
    ),
}


def formal_argv(
    task_id: str,
    fields: Mapping[str, object],
    *,
    work_dir: Path,
    launch: FormalLaunch,
) -> list[str]:
    """Validate fields, keep every path inside work_dir, and return a command array."""
    checked = require_task(task_id)
    spec = SPECS.get(checked)
    if spec is None:
        raise UnsupportedFormalTask(checked)
    script, model, argv_spec = spec
    data = model.model_validate(fields).model_dump()
    argv = [str(launch.python.resolve()), str(launch.script(script).resolve())]
    for flag, key, kind in argv_spec:
        value = data[key]
        if kind == _SWITCH:
            if value:
                argv.append(flag)
            continue
        if kind == _OPTIONAL and (value is None or value == ""):
            continue
        if isinstance(value, Path):
            resolved = _inside(value, work_dir)
            quicklook_not_formal(resolved)
            argv.extend((flag, str(resolved)))
            continue
        argv.extend((flag, str(value)))
    return argv


def _inside(path: object, work_dir: Path) -> Path:
    if not isinstance(path, Path):
        raise FormalPathRejected(work_dir)
    resolved = path.resolve()
    if not resolved.is_relative_to(work_dir.resolve()):
        raise FormalPathRejected(resolved)
    return resolved
