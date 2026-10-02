"""Formal-engine paths are fixed when the process starts."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from stagecraft_studio.engine.launch import EngineConfigError

_SCRIPTS = (
    "part1_load.py",
    "part1_qc.py",
    "part1_merge.py",
    "part1_resolution_grid.py",
    "part1_lock.py",
    "part2_figures.py",
    "part2_survey.py",
    "part3_recluster.py",
    "part4_figures.py",
    "part4_survey.py",
    "part5_prepare.py",
    "stage_report.py",
)


class FormalLaunch(BaseModel):
    """Interpreter and formal-engine scripts directory chosen at startup."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    python: Path
    scripts_dir: Path

    def script(self, name: str) -> Path:
        if name not in _SCRIPTS:
            raise EngineConfigError(f"正式引擎没有这个脚本：{name}")
        return self.scripts_dir / name


def resolve_formal_launch(
    python: Path | None = None,
    scripts_dir: Path | None = None,
) -> FormalLaunch:
    """Read the formal engine from startup arguments or the environment."""
    python_path = python if python is not None else _env_path("STAGECRAFT_FORMAL_PYTHON")
    scripts_path = scripts_dir
    if scripts_path is None:
        scripts_path = _env_path("STAGECRAFT_FORMAL_SCRIPTS")
    if python_path is None or scripts_path is None:
        raise EngineConfigError("启动前要给出正式引擎的解释器和脚本目录。")
    if not python_path.is_file():
        raise EngineConfigError(f"找不到正式引擎解释器：{python_path}")
    if not scripts_path.is_dir():
        raise EngineConfigError(f"找不到正式引擎脚本目录：{scripts_path}")
    launch = FormalLaunch(python=python_path.resolve(), scripts_dir=scripts_path.resolve())
    missing = [name for name in _SCRIPTS if not launch.script(name).is_file()]
    if missing:
        raise EngineConfigError(f"正式引擎脚本目录缺少：{', '.join(missing)}")
    return launch


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw)
