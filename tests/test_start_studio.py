"""The double-click launcher only syncs, builds, serves, and opens the browser."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_uses_uv_and_pnpm() -> None:
    text = (ROOT / "scripts" / "start-studio.cmd").read_text(encoding="utf-8")
    assert text.count("uv sync --frozen") == 2
    assert "pnpm -C web build" in text
    assert "stagecraft_studio.engine.cli serve" in text
    assert "http://127.0.0.1:8765/" in text
    assert "python -c" not in text
