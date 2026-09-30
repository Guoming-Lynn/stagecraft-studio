"""File routes stay inside the run directory recorded for that run id."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.api.files import reveal_command
from stagecraft_studio.engine.launch import EngineLaunch

RUN_ID = "abc123abc123abcd"
TOKEN = {
    "origin": "http://127.0.0.1:8765",
    "x-stagecraft-token": "secret-token",
}


def test_relative_path_cannot_escape_the_run(tmp_path: Path) -> None:
    output = tmp_path / "project"
    output.mkdir()
    (output / "note.txt").write_text("inside", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET-PARENT", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("SECRET-OUTSIDE", encoding="utf-8")
    link = _link_outside(output, outside)
    client = TestClient(_app(tmp_path, output))
    inside = client.get(f"/api/runs/{RUN_ID}/file", params={"rel": "note.txt"})
    assert inside.status_code == 200
    assert inside.json()["text"] == "inside"
    assert str(output) not in str(inside.url)
    for rel in ("../secret.txt", str(secret), "C:/Windows/win.ini", link):
        response = client.get(f"/api/runs/{RUN_ID}/file", params={"rel": rel})
        assert response.status_code == 403
        assert "SECRET-PARENT" not in response.text
        assert "SECRET-OUTSIDE" not in response.text


def test_text_preview_truncates_after_two_megabytes(tmp_path: Path) -> None:
    output = tmp_path / "project"
    output.mkdir()
    (output / "big.txt").write_bytes(b"a" * (2_000_000 + 25))
    client = TestClient(_app(tmp_path, output))
    body = client.get(f"/api/runs/{RUN_ID}/file", params={"rel": "big.txt"}).json()
    assert body["truncated"] is True
    assert body["note"] == "已截断"
    assert len(body["text"]) == 2_000_000


def test_table_pages_and_rejects_a_limit_over_500(tmp_path: Path) -> None:
    output = tmp_path / "project"
    output.mkdir()
    (output / "genes.csv").write_text("gene,score\nA,1\nB,2\nC,3\n", encoding="utf-8")
    client = TestClient(_app(tmp_path, output))
    page = client.get(
        f"/api/runs/{RUN_ID}/table",
        params={"rel": "genes.csv", "offset": 1, "limit": 1},
    )
    assert page.status_code == 200
    body = page.json()
    assert body["rows"] == [["B", "2"]]
    assert body["total"] == 3
    found = client.get(
        f"/api/runs/{RUN_ID}/table",
        params={"rel": "genes.csv", "q": "B"},
    )
    assert found.json()["rows"] == [["B", "2"]]
    ordered = client.get(
        f"/api/runs/{RUN_ID}/table",
        params={"rel": "genes.csv", "sort": "score", "desc": True},
    )
    assert ordered.json()["rows"][0] == ["C", "3"]
    too_many = client.get(
        f"/api/runs/{RUN_ID}/table",
        params={"rel": "genes.csv", "limit": 501},
    )
    assert too_many.status_code == 422


def test_tree_lists_only_names_inside_the_run(tmp_path: Path) -> None:
    output = tmp_path / "project"
    (output / "04_figures").mkdir(parents=True)
    (output / "04_figures" / "plot.png").write_bytes(b"png")
    client = TestClient(_app(tmp_path, output))
    response = client.get(f"/api/runs/{RUN_ID}/tree")
    rels = {item["rel"] for item in response.json()}
    assert "04_figures/plot.png" in rels
    assert str(output) not in response.text


def test_step_source_comes_from_the_registry(tmp_path: Path) -> None:
    script = tmp_path / "run_pipeline.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    phase = tmp_path / "phase01_qc_scrublet.py"
    phase.write_text("def run():\n    return 1\n", encoding="utf-8")
    client = TestClient(_app(tmp_path, tmp_path / "empty", script=script))
    response = client.get("/api/steps/quicklook_qc/source")
    assert response.status_code == 200
    body = response.json()
    assert "def run" in body["source"]
    assert body["sha256"] == hashlib.sha256(phase.read_bytes()).hexdigest()
    assert body["script_name"] == "phase01_qc_scrublet.py"
    missing = client.get("/api/steps/not-a-step/source")
    assert missing.status_code == 404


def test_reveal_opens_only_the_recorded_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "project"
    output.mkdir()
    opened: list[Path] = []
    monkeypatch.setattr("stagecraft_studio.api.routes.reveal", opened.append)
    client = TestClient(_app(tmp_path, output))
    response = client.post(f"/api/runs/{RUN_ID}/reveal", headers=TOKEN)
    assert response.status_code == 200
    assert opened == [output]
    assert reveal_command(output) == (
        ["explorer", str(output)] if os.name == "nt" else ["xdg-open", str(output)]
    )


def _link_outside(output: Path, outside: Path) -> str:
    link = output / "joined"
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            os.symlink(outside, link, target_is_directory=True)
    else:
        os.symlink(outside, link, target_is_directory=True)
    return "joined/secret.txt"


def _app(folder: Path, output: Path, script: Path | None = None) -> FastAPI:
    output.mkdir(parents=True, exist_ok=True)
    state = folder / "runs.json"
    state.write_text(
        json.dumps(
            {
                "runs": {
                    RUN_ID: {
                        "output_root": str(output),
                        "status": "succeeded",
                        "pid": None,
                        "enrichment": "not_run_until_local_gmt",
                        "stopped_after": "phase03",
                        "command": [sys.executable, "run_pipeline.py"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    program = script or (folder / "run_pipeline.py")
    if not program.exists():
        program.write_text("raise SystemExit(0)\n", encoding="utf-8")
    return create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path(sys.executable), script=program),
        state_path=state,
    )
