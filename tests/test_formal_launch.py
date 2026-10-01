"""Formal tasks use the startup engine path and named script arguments."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from stagecraft_studio.engine.formal import FormalPathRejected, UnsupportedFormalTask, formal_argv
from stagecraft_studio.engine.formal_args import SPECS
from stagecraft_studio.engine.formal_launch import _SCRIPTS, resolve_formal_launch
from stagecraft_studio.engine.registry import REGISTERED_TASKS, require_task
from stagecraft_studio.rules.quicklook import FormalInputRejected

_EXPECTED = {
    "formal_part1_load": {"--library-id", "--input", "--format", "--out"},
    "formal_part1_qc": {"--library-id", "--source", "--loaded", "--config", "--out"},
    "formal_part1_merge": {"--manifest", "--gene", "--out"},
    "formal_part1_grid": {"--common", "--gene", "--config", "--out"},
    "formal_part3_recluster": {
        "--input",
        "--barcodes",
        "--gene",
        "--lineage",
        "--seed",
        "--completed-rounds",
        "--out",
    },
    "formal_part2_survey": {"--input", "--gene", "--group", "--out"},
    "formal_part2_figures": {"--input", "--gene", "--group", "--colors", "--out"},
    "formal_part4_survey": {"--input", "--gene", "--group", "--out"},
    "formal_part4_figures": {"--input", "--gene", "--group", "--colors", "--out"},
    "formal_part5_prepare": {"--input", "--gene", "--group", "--arm", "--out"},
    "formal_stage_report": {"--stage"},
}


def test_formal_tasks_are_registered() -> None:
    for task_id in _EXPECTED:
        assert require_task(task_id) == task_id
        assert task_id in REGISTERED_TASKS


def test_each_task_uses_the_script_flags(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    for task_id, flags in _EXPECTED.items():
        argv = formal_argv(task_id, _fields(tmp_path, task_id), work_dir=tmp_path, launch=launch)
        assert Path(argv[1]).name == SPECS[task_id][0]
        assert flags <= set(argv)


def test_launch_stays_at_the_startup_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    python, scripts = _engine(tmp_path)
    monkeypatch.setenv("STAGECRAFT_FORMAL_PYTHON", str(python))
    monkeypatch.setenv("STAGECRAFT_FORMAL_SCRIPTS", str(scripts))
    launch = resolve_formal_launch()
    monkeypatch.setenv("STAGECRAFT_FORMAL_PYTHON", str(tmp_path / "other-python"))
    argv = formal_argv(
        "formal_part1_qc", _fields(tmp_path, "formal_part1_qc"), work_dir=tmp_path, launch=launch
    )
    assert argv[0] == str(python.resolve())
    assert argv[1] == str((scripts / "part1_qc.py").resolve())


def test_request_cannot_carry_an_engine_path(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    fields = {**_fields(tmp_path, "formal_part1_load"), "python": "python"}
    with pytest.raises(ValidationError):
        formal_argv("formal_part1_load", fields, work_dir=tmp_path, launch=launch)


def test_a_leading_hyphen_is_rejected(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    fields = _fields(tmp_path, "formal_part2_survey")
    fields["gene"] = "-GENE1"
    with pytest.raises(ValidationError):
        formal_argv("formal_part2_survey", fields, work_dir=tmp_path, launch=launch)


def test_a_path_outside_the_work_directory_is_rejected(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    outside = tmp_path / "outside"
    work = tmp_path / "work"
    work.mkdir()
    fields = _fields(work, "formal_part1_load")
    fields["input"] = outside / "counts.h5ad"
    with pytest.raises(FormalPathRejected):
        formal_argv("formal_part1_load", fields, work_dir=work, launch=launch)


def test_quicklook_directory_is_rejected_before_launch(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    folder = tmp_path / "quicklook"
    folder.mkdir()
    (folder / "analysis_tier.json").write_text(
        json.dumps({"analysis_tier": "quicklook"}), encoding="utf-8"
    )
    with pytest.raises(FormalInputRejected):
        formal_argv(
            "formal_part1_load",
            _fields(folder, "formal_part1_load"),
            work_dir=folder,
            launch=launch,
        )


def test_quicklook_task_is_not_a_formal_command(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    with pytest.raises(UnsupportedFormalTask):
        formal_argv("quicklook_run", {}, work_dir=tmp_path, launch=launch)


def test_part5_block_fallback_declared_flag(tmp_path: Path) -> None:
    launch = resolve_formal_launch(*_engine(tmp_path))
    fields = _fields(tmp_path, "formal_part5_prepare")
    fields["block_fallback_declared"] = True
    argv = formal_argv("formal_part5_prepare", fields, work_dir=tmp_path, launch=launch)
    assert "--block-fallback-declared" in argv


def _fields(root: Path, task_id: str) -> dict[str, object]:
    data = root / "counts.h5ad"
    data.write_bytes(b"formal")
    out = root / "out"
    common = {
        "library_id": "L1",
        "input": data,
        "format": "h5ad",
        "source": data,
        "loaded": data,
        "config": data,
        "manifest": data,
        "common": data,
        "barcodes": data,
        "colors": data,
        "stage": data,
        "gene": "GENE1",
        "group": "cell_type",
        "arm": "arm_a",
        "lineage": "lineage_a",
        "seed": 1,
        "completed_rounds": 0,
        "out": out,
    }
    model = SPECS[task_id][1]
    return {name: common[name] for name in model.model_fields if name in common}


def _engine(tmp_path: Path) -> tuple[Path, Path]:
    python = tmp_path / "python.exe"
    python.write_text("interpreter\n", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in _SCRIPTS:
        (scripts / name).write_text("# script\n", encoding="utf-8")
    return python, scripts
