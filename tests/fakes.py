"""Stand-in engine programs. They record the interpreter and do not read a matrix."""

from __future__ import annotations

from pathlib import Path


def write_fake_engine(
    directory: Path,
    exit_code: int = 0,
    *,
    logs: bool = False,
    sleep_seconds: float = 0,
    report: str | None = None,
    resolution_note: str | None = None,
) -> Path:
    log_lines = ""
    if logs:
        log_lines = (
            "logs = out / '99_logs'\n"
            "logs.mkdir(parents=True, exist_ok=True)\n"
            "lines = [f'line-{index:02d}' for index in range(40)]\n"
            "lines.append('LOG-TAIL-OK')\n"
            "(logs / 'phase03.log').write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
        )
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "run_pipeline.py"
    script.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "config_path = Path(args[args.index('--config') + 1])\n"
        "config = json.loads(config_path.read_text(encoding='utf-8'))\n"
        "out = Path(config['OUTPUT_ROOT'])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'argv.json').write_text(json.dumps(args), encoding='utf-8')\n"
        "(out / 'argv0.txt').write_text(sys.executable, encoding='utf-8')\n"
        + log_lines
        + _report_lines(report, resolution_note)
        + (f"import time\ntime.sleep({sleep_seconds})\n" if sleep_seconds else "")
        + f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    return script


def _report_lines(kind: str | None, resolution_note: str | None = None) -> str:
    if kind not in {None, "pass", "reject", "rejected_input"}:
        return ""
    if kind is None and resolution_note is None:
        return ""
    quality = ""
    outcome = ""
    if kind == "pass":
        quality = '{"status": "pass", "bad_figures": []}'
        outcome = "completed_analysis"
    elif kind == "reject":
        quality = (
            '{"status": "reject", "bad_figures": [{"figure": "04_figures/volcano.png", '
            '"reasons": ["empty_violin", "no_significant_genes"]}]}'
        )
        outcome = "completed_analysis"
    elif kind == "rejected_input":
        quality = '{"status": "pass", "bad_figures": []}'
        outcome = "rejected_input"
    note = resolution_note
    if note is None and kind is not None:
        note = "分辨率由启发式自动选择"
    lines = "folder = out / '99_logs'\nfolder.mkdir(parents=True, exist_ok=True)\n"
    if kind is not None:
        lines += (
            f"(folder / 'pipeline_status.json').write_text("
            f"json.dumps({{'outcome': '{outcome}'}}), encoding='utf-8')\n"
            f"(folder / 'figure_quality_dataset_report.json').write_text("
            f"'{quality}', encoding='utf-8')\n"
        )
    if note is not None:
        lines += (
            "(folder / '02_global_report.json').write_text("
            f"json.dumps({{'resolution_note': {note!r}}}), encoding='utf-8')\n"
        )
    return lines


def write_fake_inspect(directory: Path) -> Path:
    script = directory / "inspect_obs.py"
    script.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "out = Path(args[args.index('--out') + 1])\n"
        "payload = {\n"
        "    'columns': [\n"
        "        {'name': 'group', 'values': ['Disease', 'Healthy']},\n"
        "        {'name': 'sample_id', 'values': ['S1']},\n"
        "    ],\n"
        "    'note': '',\n"
        "}\n"
        "out.write_text(json.dumps(payload), encoding='utf-8')\n"
        "marker = Path(__file__).with_name('inspect_argv0.txt')\n"
        "marker.write_text(sys.executable, encoding='utf-8')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    return script
