"""Server-side path to the quicklook engine. Requests cannot replace it."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class EngineConfigError(Exception):
    """The process was started without a usable engine path."""


class EngineLaunch(BaseModel):
    """Interpreter and pipeline script chosen when the process starts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    python: Path
    script: Path

    def inspect_script(self) -> Path:
        return self.script.parent / "inspect_obs.py"


def resolve_engine_launch(
    python: Path | None = None,
    script: Path | None = None,
) -> EngineLaunch:
    """Read the engine from startup arguments or the environment, then check it exists."""
    python_path = python if python is not None else _env_path("STAGECRAFT_QUICKLOOK_PYTHON")
    script_path = script if script is not None else _env_path("STAGECRAFT_QUICKLOOK_SCRIPT")
    if python_path is None or script_path is None:
        raise EngineConfigError("启动前要在参数或环境变量里给出引擎解释器和 run_pipeline.py。")
    if not python_path.is_file():
        raise EngineConfigError(f"找不到引擎解释器：{python_path}")
    if not script_path.is_file():
        raise EngineConfigError(f"找不到引擎脚本：{script_path}")
    return EngineLaunch(python=python_path.resolve(), script=script_path.resolve())


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw)
