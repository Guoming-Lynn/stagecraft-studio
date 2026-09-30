"""One-click synthetic quicklook. The matrix is written by the engine script."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.engine.quicklook import QuicklookRequest
from stagecraft_studio.worker.runs import RunStore

DEMO_SOURCE = "合成矩阵，由 write_demo_h5ad.py 用种子 42 生成。不是策展数据，不能当作正式分析。"


class DemoFailed(Exception):
    """The demo matrix was not written."""


def start_demo(store: RunStore, launch: EngineLaunch) -> tuple[str, str]:
    """Write a new synthetic h5ad and start quicklook in a fresh output directory."""
    script = launch.demo_script()
    if not script.is_file():
        raise DemoFailed("引擎里没有 write_demo_h5ad.py。")
    folder = Path(tempfile.gettempdir()) / "stagecraft-studio" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    data = folder / "demo.h5ad"
    try:
        completed = subprocess.run(
            [str(launch.python), str(script), "--out", str(data)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DemoFailed("演示数据没有写成。") from exc
    if completed.returncode != 0 or not data.is_file():
        detail = completed.stderr.strip() or completed.stdout.strip() or "演示数据没有写成。"
        raise DemoFailed(detail)
    info = _info(completed.stdout)
    output = folder / "runs" / _fresh_name(folder / "runs")
    request = QuicklookRequest(
        input_path=data,
        target_gene=info["gene"],
        output_root=output,
        group_column=info["group"],
        case_label=info["case"],
        control_label=info["control"],
        batch_column=info["batch"],
    )
    return store.start(request, launch), info["source"]


def _fresh_name(parent: Path) -> str:
    parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while (parent / f"run-{index}").exists():
        index += 1
    return f"run-{index}"


def _info(stdout: str) -> dict[str, str]:
    payload: object
    try:
        payload = json.loads(stdout.strip() or "{}")
    except json.JSONDecodeError as exc:
        raise DemoFailed("演示脚本没有返回说明。") from exc
    if not isinstance(payload, dict):
        raise DemoFailed("演示脚本没有返回说明。")
    source = payload.get("source")
    return {
        "source": source if isinstance(source, str) and source else DEMO_SOURCE,
        "gene": _text(payload.get("gene"), "IFITM3"),
        "group": _text(payload.get("group"), "group"),
        "case": _text(payload.get("case"), "Disease"),
        "control": _text(payload.get("control"), "Healthy"),
        "batch": _text(payload.get("batch"), "sample_id"),
    }


def _text(value: object, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default
