"""Write docs/rule-coverage.md from the rule catalog. Pass --check to compare."""

from __future__ import annotations

import sys
from pathlib import Path

from stagecraft_studio.rules.catalog import render_coverage

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs" / "rule-coverage.md"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text = render_coverage()
    if "--check" in args:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != text:
            sys.stderr.write("docs/rule-coverage.md 和规则目录不一致\n")
            return 1
        return 0
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
