"""Assemble the run payload the page displays. It does not decide whether a run may start."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Literal

from stagecraft_studio.api.copy import (
    ENGINE_STATUS,
    ENRICHMENT,
    FIGURE_DATASET_FAIL,
    FIGURE_FAIL,
    FIGURE_PASS,
    LEDE,
    MISSING,
    PHASES,
    SOURCE_LABELS,
    STEP_STATUS,
)
from stagecraft_studio.api.files import PathRejected, resolve_inside
from stagecraft_studio.api.models import (
    ArtifactView,
    ImageView,
    LogView,
    ParameterRow,
    ReasonView,
    RunListItem,
    RunView,
    StepView,
)
from stagecraft_studio.api.steps import (
    STEP_SPECS,
    EngineIdentity,
    included_step_ids,
    step_state,
)
from stagecraft_studio.rules.figure_copy import figure_reason, outcome_label
from stagecraft_studio.worker.runs import RunRecord


def run_view(record: RunRecord, identity: EngineIdentity) -> RunView:
    """Build one run, including the three statuses the result page keeps apart."""
    root = record.output_root
    status_file = _read(root / "run_status.json")
    pipeline = _read(root / "99_logs" / "pipeline_status.json")
    quality = _read(root / "99_logs" / "figure_quality_dataset_report.json")
    enrichment = record.enrichment or _text(status_file, "enrichment")
    stopped_after = record.stopped_after or _text(status_file, "stopped_after")
    figure_status, figure_label = _figure_status(quality)
    config_text, parameters = _parameters(root)
    bad = _bad_figures(quality)
    return RunView(
        run_id=record.run_id,
        task_id=_text(status_file, "task_id") or "quicklook_run",
        status=record.status,
        status_label=ENGINE_STATUS.get(record.status, record.status),
        heading=_heading(record.status, stopped_after),
        lede=LEDE,
        can_cancel=record.status in {"running", "starting"},
        returncode=_returncode(status_file),
        enrichment=enrichment,
        enrichment_label=ENRICHMENT.get(enrichment, enrichment or MISSING),
        stopped_after=stopped_after,
        output_root=str(root),
        engine_name=identity.name,
        engine_version=identity.version,
        engine_git=identity.git,
        command=list(record.command),
        command_line=_quote(record.command),
        config_text=config_text,
        parameters=parameters,
        logs=_logs(root),
        pipeline_outcome=_text(pipeline, "outcome"),
        pipeline_label=_outcome(pipeline),
        figure_status=figure_status,
        figure_label=figure_label,
        images=_images(root, bad, quality is not None and figure_status == "pass"),
    )


def run_item(record: RunRecord) -> RunListItem:
    view = run_view(record, EngineIdentity("", "", "", record.output_root))
    return RunListItem(
        run_id=view.run_id,
        task_id=view.task_id,
        status=view.status,
        status_label=view.status_label,
        heading=view.heading,
        returncode=view.returncode,
        enrichment=view.enrichment,
        stopped_after=view.stopped_after,
    )


def step_views(record: RunRecord) -> list[StepView]:
    """Planned steps share the run status until the engine reports each phase."""
    root = record.output_root
    quality = _read(root / "99_logs" / "figure_quality_dataset_report.json")
    bad = set(_bad_figures(quality))
    known = quality is not None
    included = set(included_step_ids(record.stopped_after))
    views: list[StepView] = []
    for step in STEP_SPECS:
        state = step_state(record.status, step.step_id in included)
        views.append(
            StepView(
                step_id=step.step_id,
                name=step.name,
                status=state,
                status_label=STEP_STATUS.get(state, state),
                script_name=step.script_name,
                artifacts=_artifacts(root, step.folders, bad, known),
            )
        )
    return views


def _heading(status: str, stopped_after: str) -> str:
    phase = PHASES.get(stopped_after, stopped_after or "这一阶段")
    if status in {"running", "starting"}:
        return f"速览正在跑到{phase}"
    if status == "succeeded":
        return f"速览已跑到{phase}"
    if status == "cancelled":
        return f"速览已取消，当时计划跑到{phase}"
    return f"速览没有跑完，当时计划跑到{phase}"


def _quote(command: tuple[str, ...]) -> str:
    if not command:
        return ""
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return " ".join(shlex.quote(part) for part in command)


def _parameters(root: Path) -> tuple[str, list[ParameterRow]]:
    config = _read(_config_path(root))
    sources = _read(root / "parameter_sources.json") or {}
    if config is None:
        return "", []
    rows: list[ParameterRow] = []
    for key, value in config.items():
        source = sources.get(key)
        code = source if isinstance(source, str) and source else "未记录"
        rows.append(
            ParameterRow(
                name=key,
                value=_show(value),
                source=code,
                source_label=SOURCE_LABELS.get(code, code),
            )
        )
    return json.dumps(config, indent=2, ensure_ascii=False), rows


def _config_path(root: Path) -> Path:
    resolved = root / "99_logs" / "resolved_config.json"
    if resolved.is_file():
        return resolved
    return root / "config.json"


def _logs(root: Path) -> list[LogView]:
    folder = root / "99_logs"
    if not folder.is_dir():
        return []
    found: list[LogView] = []
    for path in sorted(folder.glob("*.log"))[:8]:
        try:
            rel = path.relative_to(root).as_posix()
            safe = resolve_inside(root, rel)
        except (ValueError, PathRejected):
            continue
        with safe.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 65536))
            chunk = handle.read(65536)
        lines = chunk.decode("utf-8", errors="replace").splitlines()[-30:]
        found.append(LogView(name=safe.name, text="\n".join(lines)))
    return found


def _images(root: Path, bad: dict[str, list[str]], dataset_passed: bool) -> list[ImageView]:
    rels = set(bad)
    figures = root / "04_figures"
    if figures.is_dir():
        for path in figures.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in {".png", ".svg"}:
                continue
            try:
                rel = path.relative_to(root).as_posix()
                resolve_inside(root, rel)
            except (ValueError, PathRejected):
                continue
            rels.add(rel)
    views: list[ImageView] = []
    for rel in sorted(rels):
        codes = bad.get(rel, [])
        failed = rel in bad
        if failed:
            label = FIGURE_FAIL
            passed = False
        elif dataset_passed:
            label = FIGURE_PASS
            passed = True
        else:
            label = MISSING
            passed = False
        step_id, step_name = _step_for(rel)
        views.append(
            ImageView(
                rel=rel,
                step_id=step_id,
                step_name=step_name,
                passed=passed,
                label=label,
                reasons=[_reason(code) for code in codes],
            )
        )
    return views


def _artifacts(
    root: Path, folders: tuple[str, ...], bad: set[str], known: bool
) -> list[ArtifactView]:
    found: list[ArtifactView] = []
    for folder in folders:
        base = root.joinpath(*folder.split("/"))
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root).as_posix()
                resolve_inside(root, rel)
                size = path.stat().st_size
            except (ValueError, PathRejected, OSError):
                continue
            quality_status: Literal["pass", "fail", "missing"]
            if rel in bad:
                label = FIGURE_FAIL
                quality_status = "fail"
            elif known:
                label = FIGURE_PASS
                quality_status = "pass"
            else:
                label = MISSING
                quality_status = "missing"
            found.append(
                ArtifactView(
                    rel=rel,
                    size=size,
                    quality_label=label,
                    quality_status=quality_status,
                )
            )
    return found


def _step_for(rel: str) -> tuple[str, str]:
    for step in STEP_SPECS:
        if any(rel == folder or rel.startswith(f"{folder}/") for folder in step.folders):
            return step.step_id, step.name
    return "", ""


def _reason(code: str) -> ReasonView:
    copy = figure_reason(code)
    return ReasonView(code=code, text=copy.text, suggestion=copy.suggestion)


def _bad_figures(report: dict[str, object] | None) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    if report is None:
        return found
    raw = report.get("bad_figures")
    if not isinstance(raw, list):
        return found
    for item in raw:
        if not isinstance(item, dict):
            continue
        figure = item.get("figure")
        reasons = item.get("reasons")
        if not isinstance(figure, str) or not figure:
            continue
        codes = [str(code) for code in reasons] if isinstance(reasons, list) else []
        found[figure.replace("\\", "/")] = codes
    return found


def _figure_status(report: dict[str, object] | None) -> tuple[str, str]:
    if report is None:
        return "", MISSING
    status = report.get("status")
    if status == "pass":
        return "pass", FIGURE_PASS
    if status == "reject":
        return "reject", FIGURE_DATASET_FAIL
    if isinstance(status, str) and status:
        return status, status
    return "", MISSING


def _outcome(pipeline: dict[str, object] | None) -> str:
    if pipeline is None:
        return MISSING
    outcome = pipeline.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        return MISSING
    return outcome_label(outcome)


def _returncode(payload: dict[str, object] | None) -> int | None:
    if payload is None:
        return None
    value = payload.get("returncode")
    if isinstance(value, int):
        return value
    return None


def _read(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key): value for key, value in payload.items()}


def _text(payload: dict[str, object] | None, key: str) -> str:
    if payload is None:
        return ""
    value = payload.get(key)
    if isinstance(value, str):
        return value
    return ""


def _show(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
