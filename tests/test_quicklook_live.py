"""Background quicklook and the three result statuses."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.worker.process_tree import pid_alive
from stagecraft_studio.worker.runs import RunStore

from tests.fakes import write_fake_engine

ORIGIN = {"origin": "http://127.0.0.1:8765"}


def test_submit_opens_a_running_page_and_cancel_stops_the_process(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=20, logs=True)
    state = tmp_path / "runs.json"
    client = TestClient(_app(script, state))
    started = time.perf_counter()
    response = client.post(
        "/quicklook",
        data=_form(source, tmp_path / "project"),
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert time.perf_counter() - started < 2
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/runs/" in location
    assert "project" not in location
    try:
        text = _until(client, location, "运行中")
        assert 'http-equiv="refresh"' in text
        assert "取消" in text
        assert "速览正在跑到聚类" in text
        pid = _pid(state)
        cancelled = client.post(
            f"{location}/cancel",
            data={"token": "secret-token"},
            headers=ORIGIN,
        )
        assert cancelled.status_code == 200
        assert "已取消" in cancelled.text
        assert "速览已取消" in cancelled.text
        deadline = time.perf_counter() + 3
        while pid_alive(pid) and time.perf_counter() < deadline:
            time.sleep(0.1)
        assert not pid_alive(pid)
    finally:
        client.post(f"{location}/cancel", data={"token": "secret-token"}, headers=ORIGIN)


def test_running_page_becomes_succeeded(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=1)
    client = TestClient(_app(script, tmp_path / "runs.json"))
    response = client.post(
        "/quicklook",
        data=_form(source, tmp_path / "project"),
        headers=ORIGIN,
        follow_redirects=False,
    )
    location = response.headers["location"]
    running = client.get(location).text
    assert "运行中" in running
    finished = _until(client, location, 'data-returncode="0"')
    assert "已完成" in finished
    assert "速览已跑到聚类" in finished


def test_second_quicklook_is_rejected_while_one_is_running(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=20)
    state = tmp_path / "runs.json"
    client = TestClient(_app(script, state))
    first = client.post(
        "/quicklook",
        data=_form(source, tmp_path / "one"),
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert first.status_code == 303
    try:
        second = client.post(
            "/quicklook",
            data=_form(source, tmp_path / "two"),
            headers=ORIGIN,
        )
        assert second.status_code == 409
        assert "已有一次速览在运行" in second.text
        assert not (tmp_path / "two" / "config.json").exists()
    finally:
        client.post(
            f"{first.headers['location']}/cancel",
            data={"token": "secret-token"},
            headers=ORIGIN,
        )


def test_finished_page_keeps_pass_reject_and_rejected_input_apart(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    passed = _finished_text(
        tmp_path / "pass",
        source,
        write_fake_engine(tmp_path / "bin-pass", report="pass"),
        'data-returncode="0"',
    )
    assert "速览已跑到聚类" in passed
    assert "已完成" in passed
    assert "分析已完成" in passed
    assert "通过" in passed
    assert "未通过" not in passed
    assert "该面板没有细胞数超过 100 的类别" not in passed

    rejected = _finished_text(
        tmp_path / "reject",
        source,
        write_fake_engine(tmp_path / "bin-reject", report="reject"),
        'data-returncode="0"',
    )
    assert "已完成" in rejected
    assert "分析已完成" in rejected
    assert "未通过" in rejected
    assert "04_figures/volcano.png" in rejected
    assert "该面板没有细胞数超过 100 的类别" in rejected
    assert "差异分析没有显著基因" in rejected

    refused = _finished_text(
        tmp_path / "refused",
        source,
        write_fake_engine(tmp_path / "bin-refused", exit_code=3, report="rejected_input"),
        'data-returncode="3"',
    )
    assert "未完成" in refused
    assert "输入被拒绝" in refused
    assert "已完成" not in refused


def _finished_text(output: Path, source: Path, script: Path, marker: str) -> str:
    state = output.parent / f"{output.name}-runs.json"
    client = TestClient(_app(script, state))
    response = client.post(
        "/quicklook",
        data=_form(source, output),
        headers=ORIGIN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    return _until(client, response.headers["location"], marker)


def test_startup_marks_a_leftover_run_interrupted(tmp_path: Path) -> None:
    output = tmp_path / "project"
    output.mkdir()
    (output / "run_status.json").write_text(
        json.dumps(
            {
                "task_id": "quicklook_run",
                "status": "running",
                "returncode": None,
                "enrichment": "not_run_until_local_gmt",
                "stopped_after": "phase03",
            }
        ),
        encoding="utf-8",
    )
    state = tmp_path / "runs.json"
    state.write_text(
        json.dumps(
            {
                "runs": {
                    "abc123abc123abcd": {
                        "output_root": str(output),
                        "status": "running",
                        "pid": None,
                        "enrichment": "not_run_until_local_gmt",
                        "stopped_after": "phase03",
                        "command": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    RunStore(state).recover()
    saved = json.loads((output / "run_status.json").read_text(encoding="utf-8"))
    assert saved["status"] == "interrupted"


def _form(source: Path, output: Path) -> dict[str, str]:
    return {
        "token": "secret-token",
        "input_path": str(source),
        "gene": "IFITM3",
        "out": str(output),
    }


def _app(script: Path, state: Path) -> object:
    return create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path(sys.executable), script=script),
        state_path=state,
    )


def _until(client: TestClient, url: str, marker: str) -> str:
    text = ""
    for _ in range(80):
        text = client.get(url).text
        if marker in text:
            return text
        time.sleep(0.05)
    return text


def _pid(state: Path) -> int:
    payload = json.loads(state.read_text(encoding="utf-8"))
    runs = payload["runs"]
    assert isinstance(runs, dict)
    for item in runs.values():
        assert isinstance(item, dict)
        pid = item.get("pid")
        if isinstance(pid, int):
            return pid
    raise AssertionError(payload)
