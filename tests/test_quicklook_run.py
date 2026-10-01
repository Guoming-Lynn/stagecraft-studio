"""Quicklook task registration, subprocess launch, and formal-input refusal."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from stagecraft_studio.engine.quicklook import (
    OutputRejected,
    QuicklookRequest,
    run_quicklook,
)
from stagecraft_studio.engine.registry import UnsupportedTask, require_task
from stagecraft_studio.rules.quicklook import FormalInputRejected, quicklook_not_formal

from tests.fakes import write_fake_engine


def test_unknown_task_is_rejected() -> None:
    with pytest.raises(UnsupportedTask):
        require_task("run_shell")


def test_request_rejects_extra_fields(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    with pytest.raises(ValidationError):
        QuicklookRequest.model_validate(
            {
                "input_path": source,
                "target_gene": "IFITM3",
                "output_root": tmp_path / "out",
                "python_path": "python",
                "script": "run.py",
            }
        )


def test_successful_run_stops_before_enrichment(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    output = tmp_path / "project"
    script = write_fake_engine(tmp_path, exit_code=0)
    result = run_quicklook(
        QuicklookRequest(
            input_path=source, target_gene="IFITM3", output_root=output, group_column="group"
        ),
        python=Path(sys.executable),
        script=script,
    )
    assert result.returncode == 0
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config["QUICK_MODE"] is True
    assert config["GROUP_COLUMN"] == "group"
    assert config["INPUT_FORMAT"] == "h5ad"
    assert "enrichr" not in json.dumps(config).casefold()
    recorded = json.loads((output / "argv.json").read_text(encoding="utf-8"))
    assert "LOCAL_GMT" not in config
    assert recorded[recorded.index("--stop-after") + 1] == "phase03"
    argv0 = Path((output / "argv0.txt").read_text(encoding="utf-8"))
    assert argv0.resolve() == Path(sys.executable).resolve()
    status = json.loads((output / "run_status.json").read_text(encoding="utf-8"))
    assert status["enrichment"] == "not_run_until_local_gmt"
    assert status["stopped_after"] == "phase03"
    tier = json.loads(result.tier_path.read_text(encoding="utf-8"))
    assert tier["analysis_tier"] == "quicklook"
    assert tier["donor_level_inference"] is False
    assert "enrichment" not in tier
    with pytest.raises(FormalInputRejected):
        quicklook_not_formal(output / "config.json")


def test_group_labels_are_copied_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    output = tmp_path / "project"
    run_quicklook(
        QuicklookRequest(
            input_path=source,
            target_gene="IFITM3",
            output_root=output,
            group_column="condition",
            case_label="Disease",
            control_label="Healthy",
            batch_column="donor",
        ),
        python=Path(sys.executable),
        script=write_fake_engine(tmp_path),
    )
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config["GROUP_COLUMN"] == "condition"
    assert config["CASE_LABEL"] == "Disease"
    assert config["CONTROL_LABEL"] == "Healthy"
    assert config["BATCH_COLUMN"] == "donor"


def test_local_gmt_runs_through_enrichment_phase(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    gmt = tmp_path / "sets.gmt"
    gmt.write_text("SET\tdesc\tGENE1\n", encoding="utf-8")
    output = tmp_path / "project"
    result = run_quicklook(
        QuicklookRequest(
            input_path=source,
            target_gene="IFITM3",
            output_root=output,
            local_gmt=gmt,
        ),
        python=Path(sys.executable),
        script=write_fake_engine(tmp_path, exit_code=0),
    )
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    recorded = json.loads((output / "argv.json").read_text(encoding="utf-8"))
    assert config["LOCAL_GMT"] == str(gmt.resolve())
    assert "GROUP_COLUMN" not in config
    assert "CASE_LABEL" not in config
    assert "--stop-after" not in recorded
    status = json.loads((output / "run_status.json").read_text(encoding="utf-8"))
    tier = json.loads(result.tier_path.read_text(encoding="utf-8"))
    assert status["enrichment"] == "local_gmt"
    assert status["stopped_after"] == "phase04_sensitivity"
    assert "stopped_after" not in tier


def test_missing_gmt_file_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        run_quicklook(
            QuicklookRequest(
                input_path=source,
                target_gene="IFITM3",
                output_root=tmp_path / "project",
                local_gmt=tmp_path / "missing.gmt",
            ),
            python=Path(sys.executable),
            script=write_fake_engine(tmp_path, exit_code=0),
        )


def test_failed_run_stays_quicklook(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    output = tmp_path / "project"
    result = run_quicklook(
        QuicklookRequest(input_path=source, target_gene="IFITM3", output_root=output),
        python=Path(sys.executable),
        script=write_fake_engine(tmp_path, exit_code=7),
    )
    assert result.returncode == 7
    assert result.tier_path.is_file()
    (output / "partial.h5ad").write_bytes(b"x")
    with pytest.raises(FormalInputRejected, match="QUICKLOOK_NOT_FORMAL"):
        quicklook_not_formal(output / "partial.h5ad")
    status = json.loads((output / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["enrichment"] == "not_run_until_local_gmt"


def test_nonempty_output_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    output = tmp_path / "project"
    output.mkdir()
    (output / "already.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(OutputRejected, match="不是空的"):
        run_quicklook(
            QuicklookRequest(input_path=source, target_gene="IFITM3", output_root=output),
            python=Path(sys.executable),
            script=write_fake_engine(tmp_path),
        )
    assert (output / "already.txt").read_text(encoding="utf-8") == "keep"
    assert not (output / "analysis_tier.json").exists()
    assert not (output / "config.json").exists()


def test_tenx_h5_is_passed_to_the_engine(tmp_path: Path) -> None:
    source = tmp_path / "matrix.h5"
    source.write_bytes(b"x")
    output = tmp_path / "project"
    script = write_fake_engine(tmp_path)
    result = run_quicklook(
        QuicklookRequest(input_path=source, target_gene="IFITM3", output_root=output),
        python=Path(sys.executable),
        script=script,
    )
    assert result.returncode == 0
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config["INPUT_FORMAT"] == "h5"
