"""Write web/openapi.json from the FastAPI routes. Pass --check to compare."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from stagecraft_studio.api.app import create_app
from stagecraft_studio.engine.launch import EngineLaunch

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "openapi.json"


def build_schema() -> dict[str, object]:
    """Return the OpenAPI document. Paths do not depend on a real engine install."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        python = folder / "python"
        script = folder / "scripts" / "run_pipeline.py"
        script.parent.mkdir()
        python.write_text("", encoding="utf-8")
        script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        app = create_app(
            "token",
            port=8765,
            launch=EngineLaunch(python=python, script=script),
            state_path=folder / "runs.json",
            include_ui=False,
        )
        schema = app.openapi()
    if not isinstance(schema, dict):
        return {}
    return {str(key): value for key, value in schema.items()}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    schema = build_schema()
    if "--check" in args:
        if not TARGET.is_file():
            sys.stderr.write("缺少 web/openapi.json\n")
            return 1
        saved = json.loads(TARGET.read_text(encoding="utf-8"))
        if saved != schema:
            sys.stderr.write("web/openapi.json 和当前接口不一致\n")
            return 1
        return 0
    TARGET.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
