"""Environment rows come from the server, including the fail text."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from stagecraft_studio.api.environment import _missing_r_packages, environment_report


def test_environment_report_separates_pass_and_fail() -> None:
    report = environment_report(
        python_version="3.11.15",
        r_version=None,
        engine_version="0.1.0",
        engine_name="scrna-target-engine",
        memory_bytes=1024,
        disk_free_bytes=20 * 1024**3,
    )
    by_name = {item.name: item for item in report.checks}
    assert by_name["python"].label == "通过"
    assert by_name["engine"].detail == "scrna-target-engine 0.1.0"
    assert by_name["r"].label == "不通过"
    assert "Rscript" in by_name["r"].fix
    assert by_name["memory"].label == "不通过"
    assert "8 GB" in by_name["memory"].fix
    assert by_name["disk"].label == "通过"


def test_environment_report_flags_missing_r_packages() -> None:
    report = environment_report(
        python_version="3.10.19",
        r_version="R scripting front-end version 4.5.0",
        engine_version="0.1.0",
        engine_name="stagecraft-formal",
        memory_bytes=16 * 1024**3,
        disk_free_bytes=20 * 1024**3,
        missing_r_packages=("limma", "DESeq2"),
    )
    by_name = {item.name: item for item in report.checks}
    assert by_name["r"].status == "fail"
    assert by_name["r"].label == "不通过"
    assert "limma" in by_name["r"].detail
    assert "DESeq2" in by_name["r"].fix


def test_missing_r_packages_parses_probe_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="edgeR,DESeq2,ignored_pkg\n", stderr="")

    monkeypatch.setattr("stagecraft_studio.api.environment.subprocess.run", _fake_run)
    assert _missing_r_packages("Rscript") == ("edgeR", "DESeq2")

    monkeypatch.undo()
    assert _missing_r_packages(str(Path(sys.executable).parent / "definitely-missing-rscript")) == (
        "jsonlite",
        "Matrix",
        "limma",
        "edgeR",
        "DESeq2",
    )
