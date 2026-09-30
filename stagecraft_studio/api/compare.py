"""Side-by-side facts for two runs. Counts come from the engine report or stay missing."""

from __future__ import annotations

import json
from pathlib import Path

from stagecraft_studio.api.copy import MISSING
from stagecraft_studio.api.models import CompareRow, CompareView
from stagecraft_studio.api.steps import EngineIdentity
from stagecraft_studio.api.view import run_view
from stagecraft_studio.worker.runs import RunRecord


def compare_runs(left: RunRecord, right: RunRecord, identity: EngineIdentity) -> CompareView:
    """Pair parameter rows and the clustering counts each run actually wrote."""
    left_view = run_view(left, identity)
    right_view = run_view(right, identity)
    left_values = {row.name: row.value for row in left_view.parameters}
    right_values = {row.name: row.value for row in right_view.parameters}
    rows = [
        CompareRow(
            name=name,
            left=left_values.get(name, MISSING),
            right=right_values.get(name, MISSING),
            same=left_values.get(name, MISSING) == right_values.get(name, MISSING),
        )
        for name in sorted(set(left_values) | set(right_values))
    ]
    return CompareView(
        left_id=left.run_id,
        right_id=right.run_id,
        left_heading=left_view.heading,
        right_heading=right_view.heading,
        cells_left=_metric(left.output_root, "N_Cells"),
        cells_right=_metric(right.output_root, "N_Cells"),
        clusters_left=_metric(left.output_root, "N_Clusters"),
        clusters_right=_metric(right.output_root, "N_Clusters"),
        figure_left=left_view.figure_label,
        figure_right=right_view.figure_label,
        parameters=rows,
    )


def _metric(root: Path, key: str) -> str:
    report = _read(root / "99_logs" / "02_global_report.json")
    if report is None or key not in report:
        return MISSING
    value = report[key]
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return MISSING
    return str(value)


def _read(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict):
        return {str(key): value for key, value in payload.items()}
    return None
