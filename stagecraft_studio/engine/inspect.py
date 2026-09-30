"""Read obs column names through the engine. The matrix stays on disk."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from stagecraft_studio.engine.registry import require_task


class InspectFailed(Exception):
    """The inspect script did not return column names."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class InspectColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    values: list[str]


class InspectResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[InspectColumn]
    note: str = ""


class InspectRequest(BaseModel):
    """Only the input path. The script path comes from the server launch config."""

    model_config = ConfigDict(extra="forbid")

    input_path: Path


def run_inspect(request: InspectRequest, *, python: Path, script: Path) -> InspectResult:
    """Run the registered inspect task and return column names with a few values."""
    require_task("quicklook_inspect")
    if not request.input_path.exists():
        raise FileNotFoundError(request.input_path)
    if not python.is_file() or not script.is_file():
        raise FileNotFoundError(python if not python.is_file() else script)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "inspect.json"
        completed = subprocess.run(
            [str(python), str(script), "--input", str(request.input_path), "--out", str(out)],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0 or not out.is_file():
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise InspectFailed(detail or "检查输入没有返回列信息")
        return _parse_inspect(out.read_text(encoding="utf-8"))


def _parse_inspect(text: str) -> InspectResult:
    try:
        payload = json.loads(text)
        return InspectResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise InspectFailed("检查输入没有返回列信息") from exc
