"""Local API posts a quicklook run and refuses a missing token."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.api.copy import CLAIM_SCOPE
from stagecraft_studio.engine.cli import main
from stagecraft_studio.engine.launch import EngineConfigError, EngineLaunch, resolve_engine_launch

from tests.fakes import write_fake_engine, write_fake_inspect

TOKEN = {
    "origin": "http://127.0.0.1:8765",
    "x-stagecraft-token": "secret-token",
}


def test_untrusted_host_does_not_receive_the_token() -> None:
    launch = EngineLaunch(
        python=Path(r"D:\engines\python.exe"),
        script=Path(r"D:\engines\run_pipeline.py"),
    )
    client = TestClient(
        create_app("secret-token", port=8765, launch=launch),
        base_url="http://evil.example",
    )
    response = client.get("/api/bootstrap")
    assert response.status_code == 400
    assert "secret-token" not in response.text


def test_bootstrap_shows_server_engine_and_gmt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STAGECRAFT_QUICKLOOK_GMT", r"D:\sets\hallmark.gmt")
    launch = EngineLaunch(
        python=Path(r"D:\engines\python.exe"),
        script=Path(r"D:\engines\run_pipeline.py"),
    )
    response = TestClient(create_app("secret-token", port=8765, launch=launch)).get(
        "/api/bootstrap"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["python"] == r"D:\engines\python.exe"
    assert body["script"] == r"D:\engines\run_pipeline.py"
    assert body["gmt"] == r"D:\sets\hallmark.gmt"
    assert body["group_note"] == "没有分组时不出 case/control 对比图"
    assert "python_path" not in body
    assert "token" in body


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
        "/api/runs",
        json=_body(source, tmp_path / "project"),
        headers=TOKEN,
    )
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    assert "project" not in response.text
    payload = _until(client, f"/api/runs/{run_id}", 0)
    assert payload["status_label"] == "已完成"
    assert payload["heading"] == "速览已跑到聚类"
    assert "quicklook" in payload["lede"]
    assert CLAIM_SCOPE in payload["lede"]
    assert CLAIM_SCOPE in payload["methods_text"]
    assert payload["enrichment_label"] == "未运行，等本地基因集"
    assert payload["figure_label"] == "未找到"
    assert payload["logs"][0]["text"].endswith("LOG-TAIL-OK")
    assert "line-00" not in payload["logs"][0]["text"]
    sources = {row["name"]: row["source_label"] for row in payload["parameters"]}
    assert sources["TARGET_GENE"] == "用户填写"
    assert sources["INPUT_FORMAT"] == "自动推断"
    assert sources["RANDOM_SEED"] == "默认"
    output = tmp_path / "project"
    recorded = json.loads((output / "argv.json").read_text(encoding="utf-8"))
    assert recorded[recorded.index("--stop-after") + 1] == "phase03"
    argv0 = Path((output / "argv0.txt").read_text(encoding="utf-8"))
    assert argv0.resolve() == Path(sys.executable).resolve()
    fetched = client.get(f"/api/runs/{run_id}")
    assert str(output) not in str(fetched.url)


def test_post_cannot_choose_the_program(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path)
    client = TestClient(_app(script))
    response = client.post(
        "/api/runs",
        json={
            **_body(source, tmp_path / "project"),
            "python_path": r"C:\Windows\System32\cmd.exe",
            "script": r"C:\evil\run.py",
        },
        headers=TOKEN,
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
        "/api/inspect",
        json=_body(source, tmp_path / "project"),
        headers=TOKEN,
    )
    assert response.status_code == 200
    body = response.json()
    columns = {item["name"]: item["values"] for item in body["columns"]}
    assert columns["group"] == ["Disease", "Healthy"]
    assert body["group_note"] == "没有分组时不出 case/control 对比图"
    assert "python_path" not in body
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
        "/api/runs",
        json={"input_path": "x", "gene": "IFITM3", "out": "y"},
        headers={"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "nope"},
    )
    assert response.status_code == 401


def test_post_from_other_origin_is_rejected() -> None:
    client = TestClient(_app(Path("run_pipeline.py")))
    response = client.post(
        "/api/runs",
        json={"input_path": "x", "gene": "IFITM3", "out": "y"},
        headers={"origin": "http://evil.example", "x-stagecraft-token": "secret-token"},
    )
    assert response.status_code == 403


def _body(source: Path, output: Path) -> dict[str, str]:
    return {"input_path": str(source), "gene": "IFITM3", "out": str(output)}


def _until(client: TestClient, url: str, returncode: int) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(40):
        payload = client.get(url).json()
        if payload.get("returncode") == returncode:
            return payload
        time.sleep(0.05)
    return payload


def _app(script: Path) -> FastAPI:
    return create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path(sys.executable), script=script),
    )
