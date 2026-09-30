"""Stand-in engine programs. They record the interpreter and do not read a matrix."""

from __future__ import annotations

from pathlib import Path


def write_fake_engine(directory: Path, exit_code: int = 0, *, logs: bool = False) -> Path:
    log_lines = ""
    if logs:
        log_lines = (
            "logs = out / '99_logs'\n"
            "logs.mkdir(parents=True, exist_ok=True)\n"
            "lines = [f'line-{index:02d}' for index in range(40)]\n"
            "lines.append('LOG-TAIL-OK')\n"
            "(logs / 'phase03.log').write_text('\\n'.join(lines) + '\\n', encoding='utf-8')\n"
        )
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
        + f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    return script


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
