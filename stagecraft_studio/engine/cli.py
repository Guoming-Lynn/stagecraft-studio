"""Command line for the quicklook prototype."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from stagecraft_studio.api.app import serve
from stagecraft_studio.db.backup import BackupError, create_backup, restore_backup
from stagecraft_studio.engine.input_format import UnsupportedInput
from stagecraft_studio.engine.launch import EngineConfigError, resolve_engine_launch
from stagecraft_studio.engine.quicklook import OutputRejected, QuicklookRequest, run_quicklook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stagecraft-studio")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("quicklook")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--gene", required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--group", default=None)
    run.add_argument("--case", default=None)
    run.add_argument("--control", default=None)
    run.add_argument("--batch", default=None)
    run.add_argument("--gmt", type=Path, default=None)
    serve_command = sub.add_parser("serve")
    serve_command.add_argument("--port", type=int, default=8765)
    serve_command.add_argument("--python", type=Path, default=None)
    serve_command.add_argument("--script", type=Path, default=None)
    backup_command = sub.add_parser("backup")
    backup_command.add_argument("--database", type=Path, required=True)
    backup_command.add_argument("--out", type=Path, required=True)
    backup_command.add_argument("--overwrite", action="store_true")
    restore_command = sub.add_parser("restore")
    restore_command.add_argument("--backup", type=Path, required=True)
    restore_command.add_argument("--database", type=Path, required=True)
    restore_command.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "serve":
        if args.port <= 0:
            return 2
        try:
            serve(args.port, python=args.python, script=args.script)
        except EngineConfigError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        return 0
    if args.command == "backup":
        try:
            manifest = create_backup(args.database, args.out, overwrite=bool(args.overwrite))
        except BackupError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        sys.stdout.write(json.dumps(manifest, ensure_ascii=False) + "\n")
        return 0
    if args.command == "restore":
        try:
            restored = restore_backup(args.backup, args.database, overwrite=bool(args.overwrite))
        except BackupError as exc:
            sys.stderr.write(f"{exc}\n")
            return 2
        sys.stdout.write(json.dumps(restored, ensure_ascii=False) + "\n")
        return 0
    if args.command != "quicklook":
        return 2
    try:
        launch = resolve_engine_launch()
        request = QuicklookRequest(
            input_path=args.input,
            target_gene=args.gene,
            output_root=args.out,
            group_column=args.group,
            case_label=args.case,
            control_label=args.control,
            batch_column=args.batch,
            local_gmt=args.gmt,
        )
        result = run_quicklook(request, python=launch.python, script=launch.script)
    except (EngineConfigError, FileNotFoundError, UnsupportedInput, OutputRejected) as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(f"{result.returncode} {result.tier_path}\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
