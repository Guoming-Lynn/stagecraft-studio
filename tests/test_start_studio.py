"""The double-click launcher only syncs, builds, serves, and opens the browser."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_uses_uv_and_pnpm() -> None:
    text = (ROOT / "scripts" / "start-studio.cmd").read_text(encoding="utf-8")
    assert text.count("uv sync --frozen") == 3
    assert "pnpm -C web build" in text
    assert "stagecraft_studio.engine.cli serve" in text
    assert "http://127.0.0.1:8765/" in text
    assert "python -c" not in text


def test_launcher_discovers_sibling_formal_engine_without_overriding_env() -> None:
    text = (ROOT / "scripts" / "start-studio.cmd").read_text(encoding="utf-8")
    assert 'set "FORMAL_ENGINE=%CD%\\..\\stagecraft-formal-engine"' in text
    assert (
        "if not defined STAGECRAFT_FORMAL_SCRIPTS "
        'set "STAGECRAFT_FORMAL_SCRIPTS=%FORMAL_ENGINE%\\scripts"' in text
    )
    assert (
        "if not defined STAGECRAFT_FORMAL_PYTHON "
        'set "STAGECRAFT_FORMAL_PYTHON=%FORMAL_ENGINE%\\.venv\\Scripts\\python.exe"' in text
    )
    assert 'if exist "%FORMAL_ENGINE%\\scripts\\part1_load.py" (' in text
    assert 'pushd "%FORMAL_ENGINE%"' in text
    assert text.index('pushd "%FORMAL_ENGINE%"') < text.index(
        'set "STAGECRAFT_FORMAL_PYTHON=%FORMAL_ENGINE%\\.venv\\Scripts\\python.exe"'
    )
    assert "未在同级目录找到正式分析引擎" in text


def test_root_launcher_delegates_to_script() -> None:
    text = (ROOT / "Start Studio.cmd").read_text(encoding="utf-8")
    assert 'call "%~dp0scripts\\start-studio.cmd"' in text
