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

TOKEN = {
    "origin": "http://127.0.0.1:8765",
    "x-stagecraft-token": "secret-token",
}


def test_submit_opens_a_running_page_and_cancel_stops_the_process(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=20, logs=True)
    state = tmp_path / "runs.json"
    client = TestClient(_app(script, state))
    started = time.perf_counter()
    response = client.post("/api/runs", json=_body(source, tmp_path / "project"), headers=TOKEN)
    assert time.perf_counter() - started < 2
    assert response.status_code == 201
    run_id = response.json()["run_id"]
    assert "project" not in str(response.url)
    url = f"/api/runs/{run_id}"
    try:
        running = _until_label(client, url, "运行中")
        assert running["heading"] == "速览正在跑到聚类"
        assert running["can_cancel"] is True
        pid = _pid(state)
        cancelled = client.post(f"{url}/cancel", headers=TOKEN)
        assert cancelled.status_code == 200
        body = cancelled.json()
        assert body["status_label"] == "已取消"
        assert body["heading"].startswith("速览已取消")
        deadline = time.perf_counter() + 3
        while pid_alive(pid) and time.perf_counter() < deadline:
            time.sleep(0.1)
        assert not pid_alive(pid)
    finally:
        client.post(f"{url}/cancel", headers=TOKEN)


def test_running_page_becomes_succeeded(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=1)
    client = TestClient(_app(script, tmp_path / "runs.json"))
    response = client.post("/api/runs", json=_body(source, tmp_path / "project"), headers=TOKEN)
    run_id = response.json()["run_id"]
    url = f"/api/runs/{run_id}"
    running = client.get(url).json()
    assert running["status_label"] == "运行中"
    finished = _until_code(client, url, 0)
    assert finished["status_label"] == "已完成"
    assert finished["heading"] == "速览已跑到聚类"
    assert finished["resolution_note"] == ""


def test_resolution_note_is_read_from_the_phase02_report(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, report="pass", resolution_note="from-the-engine-report")
    body = _finished(tmp_path / "noted", source, script, 0)
    assert body["resolution_note"] == "from-the-engine-report"


def test_second_quicklook_is_rejected_while_one_is_running(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=20)
    state = tmp_path / "runs.json"
    client = TestClient(_app(script, state))
    first = client.post("/api/runs", json=_body(source, tmp_path / "one"), headers=TOKEN)
    assert first.status_code == 201
    try:
        second = client.post("/api/runs", json=_body(source, tmp_path / "two"), headers=TOKEN)
        assert second.status_code == 409
        assert "已有一次速览在运行" in second.text
        assert not (tmp_path / "two" / "config.json").exists()
    finally:
        client.post(f"/api/runs/{first.json()['run_id']}/cancel", headers=TOKEN)


def test_finished_page_keeps_pass_reject_and_rejected_input_apart(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    passed = _finished(
        tmp_path / "pass", source, write_fake_engine(tmp_path / "bin-pass", report="pass"), 0
    )
    assert passed["heading"] == "速览已跑到聚类"
    assert passed["status_label"] == "已完成"
    assert passed["pipeline_label"] == "分析已完成"
    assert passed["figure_label"] == "通过"
    assert passed["resolution_note"] == "分辨率由启发式自动选择"
    assert passed["figure_label"] != "未通过"
    joined = json.dumps(passed, ensure_ascii=False)
    assert "该面板没有细胞数超过 100 的类别" not in joined

    rejected = _finished(
        tmp_path / "reject",
        source,
        write_fake_engine(tmp_path / "bin-reject", report="reject"),
        0,
    )
    assert rejected["status_label"] == "已完成"
    assert rejected["pipeline_label"] == "分析已完成"
    assert rejected["figure_label"] == "未通过"
    images = rejected["images"]
    assert isinstance(images, list)
    assert images[0]["rel"] == "04_figures/volcano.png"
    reasons = " ".join(item["text"] for item in images[0]["reasons"])
    assert "该面板没有细胞数超过 100 的类别" in reasons
    assert "差异分析没有显著基因" in reasons

    refused = _finished(
        tmp_path / "refused",
        source,
        write_fake_engine(tmp_path / "bin-refused", exit_code=3, report="rejected_input"),
        3,
    )
    assert refused["status_label"] == "未完成"
    assert refused["pipeline_label"] == "输入被拒绝"
    assert "已完成" not in json.dumps(refused, ensure_ascii=False)


def test_events_stream_one_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"x")
    script = write_fake_engine(tmp_path, sleep_seconds=1)
    client = TestClient(_app(script, tmp_path / "runs.json"))
    started = client.post("/api/runs", json=_body(source, tmp_path / "project"), headers=TOKEN)
    url = f"/api/runs/{started.json()['run_id']}/events"
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("data: ")
    client.post(f"/api/runs/{started.json()['run_id']}/cancel", headers=TOKEN)


def _finished(output: Path, source: Path, script: Path, code: int) -> dict[str, object]:
    state = output.parent / f"{output.name}-runs.json"
    client = TestClient(_app(script, state))
    response = client.post("/api/runs", json=_body(source, output), headers=TOKEN)
    assert response.status_code == 201
    return _until_code(client, f"/api/runs/{response.json()['run_id']}", code)


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


def _body(source: Path, output: Path) -> dict[str, str]:
    return {"input_path": str(source), "gene": "IFITM3", "out": str(output)}


def _app(script: Path, state: Path) -> object:
    return create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path(sys.executable), script=script),
        state_path=state,
    )


def _until_code(client: TestClient, url: str, returncode: int) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(80):
        payload = client.get(url).json()
        if payload.get("returncode") == returncode:
            return payload
        time.sleep(0.05)
    return payload


def _until_label(client: TestClient, url: str, label: str) -> dict[str, object]:
    payload: dict[str, object] = {}
    for _ in range(80):
        payload = client.get(url).json()
        if payload.get("status_label") == label:
            return payload
        time.sleep(0.05)
    return payload


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
