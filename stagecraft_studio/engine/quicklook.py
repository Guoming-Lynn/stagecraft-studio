"""Launch the quicklook engine as a fixed subprocess.

How far the run goes is decided by quicklook_scope. A local GMT file is
required before the enrichment phase. The online enrichment entry point is
not used.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from stagecraft_studio.engine.gene_sets import library_for_request
from stagecraft_studio.engine.input_format import detect_input_format
from stagecraft_studio.engine.quicklook_scope import engine_argv, plan_scope
from stagecraft_studio.engine.registry import require_task
from stagecraft_studio.rules.quicklook import QUICKLOOK_TIER, TIER_FILENAME


class OutputRejected(Exception):
    """The output directory already has files, so this run will not overwrite them."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(reason)


class QuicklookRequest(BaseModel):
    """User fields plus the output directory. The engine program is not a field."""

    model_config = ConfigDict(extra="forbid")

    input_path: Path
    target_gene: str
    output_root: Path
    group_column: str | None = None
    case_label: str | None = None
    control_label: str | None = None
    batch_column: str | None = None
    local_gmt: Path | None = None
    organism: Literal["human", "mouse"] = "human"
    random_seed: int = Field(default=42, ge=0)

    @field_validator("group_column", "case_label", "control_label", "batch_column")
    @classmethod
    def blank_is_missing(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value

    @field_validator("target_gene")
    @classmethod
    def one_symbol(cls, value: str) -> str:
        text = value.strip()
        if not text or any(character.isspace() for character in text):
            raise ValueError("target_gene must be one symbol")
        if "/" in text or "\\" in text:
            raise ValueError("target_gene must be one symbol")
        return text


class QuicklookResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    returncode: int
    config_path: Path
    tier_path: Path


_USER_KEYS = frozenset(
    {
        "TARGET_GENE",
        "INPUT_PATH",
        "OUTPUT_ROOT",
        "GROUP_COLUMN",
        "CASE_LABEL",
        "CONTROL_LABEL",
        "BATCH_COLUMN",
        "LOCAL_GMT",
    }
)


def parameter_sources(config: dict[str, object], *, downloaded_gmt: bool = False) -> dict[str, str]:
    """Record where each written config value came from."""
    sources: dict[str, str] = {}
    for key in config:
        if key == "INPUT_FORMAT":
            sources[key] = "inferred"
        elif key == "LOCAL_GMT" and downloaded_gmt:
            sources[key] = "default"
        elif key in _USER_KEYS:
            sources[key] = "user"
        else:
            sources[key] = "default"
    return sources


def engine_config(
    request: QuicklookRequest,
    gmt_path: Path | None,
    input_format: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "TARGET_GENE": request.target_gene,
        "INPUT_PATH": str(request.input_path.resolve()),
        "INPUT_FORMAT": input_format,
        "OUTPUT_ROOT": str(request.output_root.resolve()),
        "QUICK_MODE": True,
        "RANDOM_SEED": request.random_seed,
        "FILTER_LOW_INFORMATION_FIGURES": True,
        "BUILD_PORTFOLIO": True,
    }
    _put(payload, "GROUP_COLUMN", request.group_column)
    _put(payload, "CASE_LABEL", request.case_label)
    _put(payload, "CONTROL_LABEL", request.control_label)
    _put(payload, "BATCH_COLUMN", request.batch_column)
    if gmt_path is not None:
        payload["LOCAL_GMT"] = str(gmt_path)
    return payload


def _put(payload: dict[str, object], key: str, value: str | None) -> None:
    if value is not None:
        payload[key] = value


def require_empty_output(path: Path) -> None:
    """Refuse an existing file or a directory that already contains anything."""
    if path.exists() and not path.is_dir():
        raise OutputRejected(path, "输出路径已经存在，而且不是目录。请换一个新目录。")
    if path.is_dir() and any(path.iterdir()):
        raise OutputRejected(path, "输出目录不是空的。请换一个空目录，以免覆盖已有文件。")


@dataclass(frozen=True)
class PreparedQuicklook:
    command: list[str]
    config_path: Path
    tier_path: Path
    enrichment: str
    stopped_after: str


def prepare_quicklook(
    request: QuicklookRequest,
    *,
    python: Path,
    script: Path,
) -> PreparedQuicklook:
    """Write config and the quicklook marker, then return the command array."""
    require_task("quicklook_run")
    if not python.is_file() or not script.is_file():
        raise FileNotFoundError(python if not python.is_file() else script)
    input_format = detect_input_format(request.input_path)
    chosen = library_for_request(request.local_gmt, request.organism)
    scope = plan_scope(chosen)
    require_empty_output(request.output_root)
    request.output_root.mkdir(parents=True, exist_ok=True)
    config_path = request.output_root / "config.json"
    config = engine_config(request, scope.gmt_path, input_format)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    downloaded = request.local_gmt is None and chosen is not None
    (request.output_root / "parameter_sources.json").write_text(
        json.dumps(parameter_sources(config, downloaded_gmt=downloaded), indent=2),
        encoding="utf-8",
    )
    tier_path = _write_tier(request.output_root)
    write_run_status(
        request.output_root,
        "running",
        None,
        enrichment=scope.enrichment,
        stopped_after=scope.stopped_after,
    )
    return PreparedQuicklook(
        command=engine_argv(python, script, config_path, scope),
        config_path=config_path,
        tier_path=tier_path,
        enrichment=scope.enrichment,
        stopped_after=scope.stopped_after,
    )


def run_quicklook(
    request: QuicklookRequest,
    *,
    python: Path,
    script: Path,
) -> QuicklookResult:
    """Run the registered quicklook task and wait. The HTTP form does not use this."""
    prepared = prepare_quicklook(request, python=python, script=script)
    completed = subprocess.run(prepared.command, check=False)
    status = "succeeded" if completed.returncode == 0 else "failed"
    write_run_status(
        request.output_root,
        status,
        completed.returncode,
        enrichment=prepared.enrichment,
        stopped_after=prepared.stopped_after,
    )
    return QuicklookResult(
        returncode=completed.returncode,
        config_path=prepared.config_path,
        tier_path=prepared.tier_path,
    )


def _write_tier(output_root: Path) -> Path:
    """Mark the directory as quicklook before the engine starts. Never remove it."""
    tier_path = output_root / TIER_FILENAME
    tier_path.write_text(
        json.dumps(
            {
                "analysis_tier": QUICKLOOK_TIER,
                "labels_provisional": True,
                "donor_level_inference": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tier_path


def write_run_status(
    output_root: Path,
    status: str,
    returncode: int | None,
    *,
    enrichment: str,
    stopped_after: str,
) -> None:
    (output_root / "run_status.json").write_text(
        json.dumps(
            {
                "task_id": "quicklook_run",
                "status": status,
                "returncode": returncode,
                "enrichment": enrichment,
                "stopped_after": stopped_after,
            }
        ),
        encoding="utf-8",
    )
