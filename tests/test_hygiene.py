"""Hygiene checker fixtures. Bad programs live in strings so this file stays clean."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_hygiene.py"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def place(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def test_repo_passes() -> None:
    result = run(ROOT)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("relative", "text", "code"),
    [
        ("scratch.py", "x = 1\n", "ROOT_SCRIPT"),
        ("debug.py", "x = 1\n", "ROOT_SCRIPT"),
        ("new_notes.py", "x = 1\n", "ROOT_SCRIPT"),
        ("notes.txt", "x\n", "TOP_LEVEL"),
        ("docs/NOTES.md", "x\n", "DOCS"),
        (".cursor/extra.md", "x\n", "CURSOR_EXTRA"),
        (".github/workflows/extra.yml", "x\n", "GITHUB_EXTRA"),
        ("stagecraft_studio/notes.ipynb", "{}\n", "NOTEBOOK"),
        ("stagecraft_studio/matrix.h5ad", "x\n", "DATA_FILE"),
        ("stagecraft_studio/.env", "TOKEN=1\n", "SECRET"),
        ("stagecraft_studio/run.log", "x\n", "LOG"),
        ("stagecraft_studio/long.py", "x = 1\n" * 401, "FILE_LENGTH"),
        ("stagecraft_studio/bad.py", "def bad(:\n", "SYNTAX"),
        (
            "stagecraft_studio/bad.py",
            "def bad() -> None:\n    eval('1')\n",
            "EVAL",
        ),
        (
            "stagecraft_studio/bad.py",
            "def bad() -> None:\n    exec('1')\n",
            "EXEC",
        ),
        (
            "stagecraft_studio/bad.py",
            "def bad() -> None:\n    print('x')\n",
            "PRINT",
        ),
        (
            "stagecraft_studio/bad.py",
            "import pickle\n\ndef bad(raw: bytes) -> None:\n    pickle.load(raw)\n",
            "PICKLE",
        ),
        (
            "stagecraft_studio/bad.py",
            "import sys\n\ndef bad() -> None:\n    sys.path.append('x')\n",
            "SYS_PATH",
        ),
        (
            "stagecraft_studio/bad.py",
            "import importlib\n\ndef bad(name: str) -> None:\n    importlib.import_module(name)\n",
            "DYNAMIC_IMPORT",
        ),
        (
            "stagecraft_studio/bad.py",
            "import subprocess\n\ndef bad() -> None:\n    subprocess.run(['python'], shell=True)\n",
            "SHELL",
        ),
        (
            "stagecraft_studio/bad.py",
            "def bad() -> None:\n    try:\n        x = 1\n    except:\n        x = 2\n",
            "BARE_EXCEPT",
        ),
        (
            "stagecraft_studio/bad.py",
            "def bad() -> None:\n    try:\n        x = 1\n    except Exception:\n        pass\n",
            "EXCEPT_PASS",
        ),
        ("stagecraft_studio/bad.py", "# x = 1\n", "COMMENTED_CODE"),
        ("stagecraft_studio/bad.py", "# TODO: later\n", "TODO"),
        (
            "stagecraft_studio/bad.py",
            "from abc import ABC\n\nclass Base(ABC):\n    pass\n\nclass Only(Base):\n    pass\n",
            "ABC",
        ),
    ],
)
def test_rejects(tmp_path: Path, relative: str, text: str, code: str) -> None:
    place(tmp_path, relative, text)
    result = run(tmp_path)
    assert result.returncode == 1
    assert code in result.stderr


def test_file_over_one_megabyte(tmp_path: Path) -> None:
    path = tmp_path / "stagecraft_studio" / "blob.txt"
    path.parent.mkdir()
    path.write_bytes(b"x" * 1_000_001)
    result = run(tmp_path)
    assert result.returncode == 1
    assert "SIZE" in result.stderr


def test_fixture_budget(tmp_path: Path) -> None:
    path = tmp_path / "tests" / "fixtures" / "blob.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * (5_000_001))
    result = run(tmp_path)
    assert result.returncode == 1
    assert "FIXTURE_BUDGET" in result.stderr


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        ("README.md", "ok\n"),
        (
            "stagecraft_studio/literal_import.py",
            "import importlib\n\ndef load() -> None:\n    importlib.import_module('json')\n",
        ),
        (
            "stagecraft_studio/safe_shell.py",
            "import subprocess\n\n"
            "def run() -> None:\n"
            "    subprocess.run(['python', '-c', '1'], shell=False)\n",
        ),
        ("stagecraft_studio/note.py", "# This is an explanation.\n"),
        ("stagecraft_studio/tracked.py", "# TODO(#1): tracked work\n"),
        (
            "stagecraft_studio/long.py",
            "# hygiene: generated table\n" + ("x = 1\n" * 400),
        ),
    ],
)
def test_allows(tmp_path: Path, relative: str, text: str) -> None:
    place(tmp_path, relative, text)
    result = run(tmp_path)
    assert result.returncode == 0, result.stderr
