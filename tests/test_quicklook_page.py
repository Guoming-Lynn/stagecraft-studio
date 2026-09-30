"""Local form posts a quicklook run and refuses a missing token."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.engine.cli import main
from stagecraft_studio.engine.launch import EngineConfigError, EngineLaunch, resolve_engine_launch

from tests.fakes import write_fake_engine, write_fake_inspect


def test_form_shows_server_engine_and_prefills_gmt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGECRAFT_QUICKLOOK_GMT", r"D:\sets\hallmark.gmt")
    launch = EngineLaunch(
        python=Path(r"D:\engines\python.exe"),
        script=Path(r"D:\engines\run_pipeline.py"),
    )
    response = TestClient(create_app("secret-token", port=8765, launch=launch)).get("/")
    assert response.status_code == 200
    assert r"D:\engines\python.exe" in response.text
    assert r"D:\engines\run_pipeline.py" in response.text
    assert 'name="python_path"' not in response.text
    assert 'name="script"' not in response.text
    assert 'value="D:\\sets\\hallmark.gmt"' in response.text
    assert "没有分组时不出 case/control 对比图" in response.text


def test_launch_requires_existing_engine_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("STAGECRAFT_QUICKLOOK_PYTHON", raising=False)
    monkeypatch.delenv("STAGECRAFT_QUICKLOOK_SCRIPT", raising=False)
    with pytest.raises(EngineConfigError):
        resolve_engine_launch()
    python = tmp_path / "python.exe"
    script = tmp_path / "run_pipeline.py"
    python.write_bytes(b"")
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    monkeypatch.setenv("STAGECRAFT_QUICKLOOK_PYTHON", str(python))
    monkeypatch.setenv("STAGECRAFT_QUICKLOOK_SCRIPT", str(script))
    launch = resolve_engine_launch()
    assert launch.python == python.resolve()
    assert launch.script == script.resolve()


def test_form_runs_quicklook_before_enrichment(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, logs=True)
    client = TestClient(_app(script))
    response = client.post(
        "/quicklook",
        data={
            "token": "secret-token",
            "input_path": str(source),
            "gene": "IFITM3",
            "group": "",
            "out": str(tmp_path / "project"),
        },
        headers={"origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 200
    assert 'data-returncode="0"' in response.text
    assert "探索性结果" in response.text
    assert "已完成" in response.text
    assert "quicklook" in response.text
    assert "未运行，等本地基因集" in response.text
    assert "LOG-TAIL-OK" in response.text
    assert "line-00" not in response.text
    output = tmp_path / "project"
    recorded = json.loads((output / "argv.json").read_text(encoding="utf-8"))
    assert recorded[recorded.index("--stop-after") + 1] == "phase03"
    argv0 = Path((output / "argv0.txt").read_text(encoding="utf-8"))
    assert argv0.resolve() == Path(sys.executable).resolve()


def test_post_cannot_choose_the_program(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path)
    client = TestClient(_app(script))
    response = client.post(
        "/quicklook",
        data={
            "token": "secret-token",
            "input_path": str(source),
            "gene": "IFITM3",
            "out": str(tmp_path / "project"),
            "python_path": r"C:\Windows\System32\cmd.exe",
            "script": r"C:\evil\run.py",
        },
        headers={"origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 422
    assert "不能在请求里指定" in response.text
    assert not (tmp_path / "project").exists()


def test_inspect_lists_columns_and_uses_server_python(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path)
    write_fake_inspect(tmp_path)
    client = TestClient(_app(script))
    response = client.post(
        "/quicklook/inspect",
        data={
            "token": "secret-token",
            "input_path": str(source),
            "gene": "IFITM3",
            "out": str(tmp_path / "project"),
        },
        headers={"origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 200
    assert 'value="group"' in response.text
    assert "group · Disease" in response.text
    assert "没有分组时不出 case/control 对比图" in response.text
    assert 'name="python_path"' not in response.text
    argv0 = Path((tmp_path / "inspect_argv0.txt").read_text(encoding="utf-8"))
    assert argv0.resolve() == Path(sys.executable).resolve()
    assert not (tmp_path / "project").exists()


def test_quicklook_cli_has_no_program_flags(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "quicklook",
                "--input",
                str(tmp_path / "counts.h5ad"),
                "--gene",
                "IFITM3",
                "--out",
                str(tmp_path / "project"),
                "--python",
                sys.executable,
            ]
        )


def test_post_without_token_is_rejected() -> None:
    client = TestClient(_app(Path("run_pipeline.py")))
    response = client.post(
        "/quicklook",
        data={
            "token": "nope",
            "input_path": "x",
            "gene": "IFITM3",
            "out": "y",
            "python_path": "python",
            "script": "run.py",
        },
        headers={"origin": "http://127.0.0.1:8765"},
    )
    assert response.status_code == 401


def test_post_from_other_origin_is_rejected() -> None:
    client = TestClient(_app(Path("run_pipeline.py")))
    response = client.post(
        "/quicklook",
        data={
            "token": "secret-token",
            "input_path": "x",
            "gene": "IFITM3",
            "out": "y",
        },
        headers={"origin": "http://evil.example"},
    )
    assert response.status_code == 403


def _app(script: Path) -> FastAPI:
    return create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path(sys.executable), script=script),
    )
