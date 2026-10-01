"""Formal tasks use the startup engine path and refuse quicklook directories."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from stagecraft_studio.engine.formal import FormalRequest, UnsupportedFormalTask, formal_command
from stagecraft_studio.engine.formal_launch import resolve_formal_launch
from stagecraft_studio.engine.registry import require_task
from stagecraft_studio.rules.quicklook import FormalInputRejected

_SCRIPTS = (
    "part1_load.py",
    "part1_qc.py",
    "part1_merge.py",
    "part1_resolution_grid.py",
)


def test_formal_tasks_are_registered() -> None:
    for task_id in (
        "formal_part1_load",
        "formal_part1_qc",
        "formal_part1_merge",
        "formal_part1_grid",
    ):
        assert require_task(task_id) == task_id


def test_launch_stays_at_the_startup_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    python, scripts = _engine(tmp_path)
    monkeypatch.setenv("STAGECRAFT_FORMAL_PYTHON", str(python))
    monkeypatch.setenv("STAGECRAFT_FORMAL_SCRIPTS", str(scripts))
    launch = resolve_formal_launch()
    monkeypatch.setenv("STAGECRAFT_FORMAL_PYTHON", str(tmp_path / "other-python"))
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"formal")
    argv = formal_command(FormalRequest(task_id="formal_part1_qc", input_path=source), launch)
    assert argv[0] == str(python.resolve())
    assert argv[1] == str((scripts / "part1_qc.py").resolve())
    assert argv[2] == str(source)


def test_request_cannot_carry_an_engine_path(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        FormalRequest.model_validate(
            {
                "task_id": "formal_part1_load",
                "input_path": tmp_path / "counts.h5ad",
                "python": "python",
                "scripts_dir": "scripts",
            }
        )


def test_quicklook_directory_is_rejected_before_launch(tmp_path: Path) -> None:
    python, scripts = _engine(tmp_path)
    launch = resolve_formal_launch(python, scripts)
    folder = tmp_path / "quicklook"
    folder.mkdir()
    (folder / "analysis_tier.json").write_text(
        json.dumps({"analysis_tier": "quicklook"}), encoding="utf-8"
    )
    source = folder / "counts.h5ad"
    source.write_bytes(b"quick")
    with pytest.raises(FormalInputRejected):
        formal_command(FormalRequest(task_id="formal_part1_load", input_path=source), launch)


def test_quicklook_task_is_not_a_formal_command(tmp_path: Path) -> None:
    python, scripts = _engine(tmp_path)
    launch = resolve_formal_launch(python, scripts)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"formal")
    with pytest.raises(UnsupportedFormalTask):
        formal_command(FormalRequest(task_id="quicklook_run", input_path=source), launch)


def _engine(tmp_path: Path) -> tuple[Path, Path]:
    python = tmp_path / "python.exe"
    python.write_text("interpreter\n", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in _SCRIPTS:
        (scripts / name).write_text("# script\n", encoding="utf-8")
    return python, scripts
