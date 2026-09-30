"""Reproduction zip. Config and locks only; matrices stay on disk."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from stagecraft_studio.api.copy import MISSING
from stagecraft_studio.api.steps import EngineIdentity

_LOCK_NAME = "uv.lock"


def build_bundle(root: Path, command_line: str, identity: EngineIdentity) -> bytes:
    """Pack the files needed to see how a run was launched. Data files are omitted."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("config.json", _config_text(root))
        archive.writestr("argv.txt", command_line)
        lock = _lock_path(identity)
        archive.writestr(
            "engine.json",
            json.dumps(
                {
                    "name": identity.name,
                    "version": identity.version,
                    "git": identity.git,
                    "lock": _LOCK_NAME if lock is not None else MISSING,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        if lock is not None:
            archive.write(lock, _LOCK_NAME)
    return buffer.getvalue()


def _config_text(root: Path) -> str:
    resolved = root / "99_logs" / "resolved_config.json"
    config = resolved if resolved.is_file() else root / "config.json"
    if not config.is_file():
        return json.dumps({"note": MISSING}, ensure_ascii=False)
    return config.read_text(encoding="utf-8")


def _lock_path(identity: EngineIdentity) -> Path | None:
    if identity.scripts.name != "scripts":
        return None
    candidate = identity.scripts.parent / _LOCK_NAME
    if candidate.is_file():
        return candidate
    return None
