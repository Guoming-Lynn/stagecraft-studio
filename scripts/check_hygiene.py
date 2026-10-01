"""Repository hygiene checks for Stagecraft Studio.

AST checks live in hygiene_rules.py. This file walks the tree.
Regular expressions are not used.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import hygiene_rules
from hygiene_rules import ClassRecord, Violation

# 顶层额外路径只覆盖工具链。产品目录仍以任务书 9.3 节为准。
SPEC_TOP_LEVEL = frozenset(
    {
        "AGENTS.md",
        ".cursor",
        "README.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "stagecraft_studio",
        "web",
        "tests",
        "scripts",
        "docs",
    }
)
TOOLCHAIN_TOP_LEVEL = frozenset(
    {
        ".gitignore",
        ".gitattributes",
        ".python-version",
        ".pre-commit-config.yaml",
        ".github",
        "uv.lock",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
    }
)
ALLOWED_TOP_LEVEL = SPEC_TOP_LEVEL | TOOLCHAIN_TOP_LEVEL
DOCS_FILES = frozenset(
    {
        "architecture.md",
        "capability-map.md",
        "rule-coverage.md",
        "milestones.md",
        "install.md",
    }
)
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".ruff_cache",
        ".pytest_cache",
        ".mypy_cache",
        ".pnpm-store",
        "dist",
        "build",
        "htmlcov",
    }
)
MAX_FILE_BYTES = 1_000_000
MAX_FIXTURE_BYTES = 5_000_000
PYTHON_LINE_LIMIT = 400
REACT_LINE_LIMIT = 300


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    violations = check_root(root)
    for item in violations:
        _emit(item.render())
    return 1 if violations else 0


def check_root(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    classes: list[ClassRecord] = []
    violations.extend(_top_level(root))
    violations.extend(_docs(root))
    violations.extend(_only_file(root / ".cursor", "rules/studio.mdc", "CURSOR_EXTRA"))
    violations.extend(_only_file(root / ".github", "workflows/ci.yml", "GITHUB_EXTRA"))
    for path in _files(root):
        relative = path.relative_to(root).as_posix()
        violations.extend(_file_policy(path, relative))
        if path.suffix != ".py":
            continue
        source = _read(path)
        if source is None:
            violations.append(Violation(relative, "READ_ERROR", "file could not be read as utf-8"))
            continue
        violations.extend(
            hygiene_rules.length_violations(relative, source, PYTHON_LINE_LIMIT, "# hygiene:")
        )
        found, parsed = hygiene_rules.analyze_python(relative, source)
        violations.extend(found)
        classes.extend(parsed)
    violations.extend(hygiene_rules.abc_violations(classes))
    violations.extend(_fixtures(root))
    violations.sort(key=lambda item: (item.path, item.line, item.code))
    return violations


def _top_level(root: Path) -> list[Violation]:
    found: list[Violation] = []
    for child in root.iterdir():
        if _skipped(child.name):
            continue
        if hygiene_rules.forbidden_root_name(child.name):
            found.append(Violation(child.name, "ROOT_SCRIPT", "temporary root script is forbidden"))
            continue
        if child.name not in ALLOWED_TOP_LEVEL:
            found.append(Violation(child.name, "TOP_LEVEL", "path is outside the allowed root"))
    return found


def _docs(root: Path) -> list[Violation]:
    docs = root / "docs"
    if not docs.is_dir():
        return []
    found: list[Violation] = []
    for child in docs.iterdir():
        relative = child.relative_to(root).as_posix()
        if child.is_dir() or child.name not in DOCS_FILES:
            found.append(Violation(relative, "DOCS", "docs/ only allows the five named files"))
    return found


def _only_file(folder: Path, allowed: str, code: str) -> list[Violation]:
    if not folder.exists():
        return []
    found: list[Violation] = []
    for path in _files(folder):
        relative = path.relative_to(folder).as_posix()
        if relative != allowed:
            display = path.relative_to(folder.parent).as_posix()
            found.append(Violation(display, code, f"{folder.name} only allows {allowed}"))
    return found


def _file_policy(path: Path, relative: str) -> list[Violation]:
    found: list[Violation] = []
    if path.stat().st_size > MAX_FILE_BYTES:
        found.append(Violation(relative, "SIZE", "file exceeds 1 MB"))
    code = hygiene_rules.data_code(path.name)
    if code is not None:
        found.append(Violation(relative, code, "committed data, secret, log, or notebook"))
    if path.suffix in {".tsx", ".jsx"}:
        source = _read(path)
        if source is not None:
            found.extend(
                hygiene_rules.length_violations(relative, source, REACT_LINE_LIMIT, "// hygiene:")
            )
    return found


def _fixtures(root: Path) -> list[Violation]:
    folder = root / "tests" / "fixtures"
    if not folder.is_dir():
        return []
    total = sum(path.stat().st_size for path in _files(folder))
    if total > MAX_FIXTURE_BYTES:
        return [Violation("tests/fixtures", "FIXTURE_BUDGET", "fixtures exceed 5 MB")]
    return []


def _files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not _skipped(name)]
        for name in filenames:
            found.append(Path(dirpath) / name)
    return found


def _skipped(name: str) -> bool:
    return name in SKIP_DIRS or name.endswith(".egg-info")


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _emit(line: str) -> None:
    payload = (line + "\n").encode("utf-8")
    buffer = getattr(sys.stderr, "buffer", None)
    if buffer is None:
        sys.stderr.write(line + "\n")
        return
    buffer.write(payload)


if __name__ == "__main__":
    raise SystemExit(main())
