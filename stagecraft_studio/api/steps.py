"""Registered quicklook steps. Source is read by step id, never by a client path."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from stagecraft_studio.api.files import PathRejected
from stagecraft_studio.api.models import SourceView


@dataclass(frozen=True)
class EngineIdentity:
    name: str
    version: str
    git: str
    scripts: Path


@dataclass(frozen=True)
class StepSpec:
    step_id: str
    name: str
    script_name: str
    folders: tuple[str, ...]


STEP_SPECS: tuple[StepSpec, ...] = (
    StepSpec(
        "quicklook_qc",
        "质控与双细胞",
        "phase01_qc_scrublet.py",
        ("03_tables/01_qc", "04_figures/01_qc"),
    ),
    StepSpec(
        "quicklook_cluster",
        "全局聚类",
        "phase02_global_clustering.py",
        ("03_tables/02_global", "04_figures/02_global"),
    ),
    StepSpec(
        "quicklook_subtype",
        "亚群",
        "phase03_subclustering.py",
        ("03_tables/03_target", "04_figures/03_target"),
    ),
    StepSpec(
        "quicklook_deg",
        "差异与富集",
        "phase05_sensitivity_deg.py",
        ("03_tables/04_deg", "04_figures/04_deg"),
    ),
)
_BY_ID = {step.step_id: step for step in STEP_SPECS}


def engine_identity(script: Path) -> EngineIdentity:
    """Read the engine name and version from the package that owns run_pipeline.py."""
    scripts = script.resolve().parent
    root = scripts.parent if script.name == "run_pipeline.py" else scripts
    text = ""
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
    name = _toml_value(text, "name") or "quicklook-engine"
    version = _toml_value(text, "version")
    return EngineIdentity(name=name, version=version, git=_git_short(root), scripts=scripts)


def included_step_ids(stopped_after: str) -> tuple[str, ...]:
    ids = tuple(step.step_id for step in STEP_SPECS)
    if stopped_after == "phase04_sensitivity":
        return ids
    return ids[:3]


def step_state(run_status: str, included: bool) -> str:
    """Map one run status onto a step. Per-phase progress waits on engine events."""
    if not included:
        return "not_started"
    if run_status in {"running", "starting"}:
        return "running"
    if run_status == "succeeded":
        return "done"
    if run_status == "failed":
        return "failed"
    if run_status == "cancelled":
        return "cancelled"
    if run_status == "interrupted":
        return "interrupted"
    return "not_started"


def read_source(identity: EngineIdentity, step_id: str) -> SourceView:
    """Return one registered script. Unknown ids and paths outside scripts/ are refused."""
    step = _BY_ID.get(step_id)
    if step is None:
        raise PathRejected(404, "没有这个步骤")
    path = (identity.scripts / step.script_name).resolve()
    if not path.is_file() or not path.is_relative_to(identity.scripts.resolve()):
        raise PathRejected(404, "没有这个步骤的脚本")
    data = path.read_bytes()
    return SourceView(
        step_id=step.step_id,
        name=step.name,
        script_name=step.script_name,
        sha256=hashlib.sha256(data).hexdigest(),
        engine_version=identity.version,
        engine_git=identity.git,
        source=data.decode("utf-8", errors="replace"),
    )


def _toml_value(text: str, key: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        matched = stripped.startswith(f"{key} ") or stripped.startswith(f"{key}=")
        if not matched or "=" not in stripped:
            continue
        return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _git_short(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()
