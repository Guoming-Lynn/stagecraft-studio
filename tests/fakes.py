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


def write_fake_formal_scripts(directory: Path) -> Path:
    from stagecraft_studio.engine.formal_args import SPECS
    from stagecraft_studio.engine.formal_contract import FORMAL_OUTPUT_CONTRACTS

    directory.mkdir(parents=True, exist_ok=True)
    for task_id, (script_name, _model, _argv) in SPECS.items():
        contract_files = list(FORMAL_OUTPUT_CONTRACTS.get(task_id, ()))
        script_path = directory / script_name
        if script_name == "stage_report.py":
            code = (
                "import argparse\n"
                "import pathlib\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--stage', type=pathlib.Path, required=False)\n"
                "parser.add_argument('--out', type=pathlib.Path, required=False)\n"
                "args, _ = parser.parse_known_args()\n"
                "if args.out:\n"
                "    args.out.parent.mkdir(parents=True, exist_ok=True)\n"
                "    args.out.write_text('# Formal Stage Report\\n', encoding='utf-8')\n"
            )
        elif script_name == "cluster_review_tables.py":
            code = (
                "import argparse, json, pathlib\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--out', type=pathlib.Path)\n"
                "parser.add_argument('--resolution', default='0.4')\n"
                "parser.add_argument('--round-index', type=int, default=0)\n"
                "args, _ = parser.parse_known_args()\n"
                "args.out.mkdir(parents=True, exist_ok=True)\n"
                "(args.out / 'review_table.json').write_text('{}\\n', encoding='utf-8')\n"
                "(args.out / 'selected_tables.json').write_text(json.dumps({"
                "'resolution': args.resolution, 'round_index': args.round_index}), encoding='utf-8')\n"
                "(args.out / 'selected_cluster_qc.csv').write_text("
                "'cluster,n_cells,n_donors,n_datasets,n_libraries,p5_total_counts,p25_total_counts,median_total_counts,p75_total_counts,p95_total_counts,p5_n_genes,p25_n_genes,median_n_genes,p75_n_genes,p95_n_genes,p5_pct_mt,p25_pct_mt,median_pct_mt,p75_pct_mt,p95_pct_mt\\n'"
                "+ '0,20,3,2,2,500,750,1000,1250,1500,200,300,400,500,600,1,3,5,7,9\\n'"
                "+ '1,10,2,2,2,250,375,500,625,750,100,150,200,250,300,5,12,20,28,35\\n', encoding='utf-8')\n"
                "(args.out / 'selected_top20_by_cluster.csv').write_text("
                "'cluster,top20_markers\\n0,LYZ;FCER1G\\n1,CD3D;CD3E\\n', encoding='utf-8')\n"
                "(args.out / 'selected_markers.csv').write_text("
                "'cluster,rank,gene,logfoldchange,pct_in,pct_out,pct_delta,marker_quality,quality_basis\\n'"
                "+ '0,1,LYZ,1.2,0.8,0.1,0.7,STRONG,thresholds\\n'"
                "+ '1,1,CD3D,0.9,0.7,0.1,0.6,STRONG,thresholds\\n', encoding='utf-8')\n"
            )
        else:
            code = (
                "import argparse\n"
                "import pathlib\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('--out', type=pathlib.Path, required=False)\n"
                "args, _ = parser.parse_known_args()\n"
                "if args.out:\n"
                "    args.out.mkdir(parents=True, exist_ok=True)\n"
                f"    for fname in {contract_files!r}:\n"
                "        content = '{}\\n' if fname.endswith('.json') else 'contract-file\\n'\n"
                "        (args.out / fname).write_text(content, encoding='utf-8')\n"
            )
        script_path.write_text(code, encoding="utf-8")
    return directory
