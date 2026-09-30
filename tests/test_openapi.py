"""The committed OpenAPI document matches the routes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_openapi_file_matches_the_app() -> None:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_openapi.py"), "--check"],
        check=False,
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
