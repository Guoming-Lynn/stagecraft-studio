"""The demo button starts quicklook on a matrix the engine script writes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.engine.launch import EngineLaunch

from tests.fakes import write_fake_engine

TOKEN = {
    "origin": "http://127.0.0.1:8765",
    "x-stagecraft-token": "secret-token",
}


def test_demo_uses_the_script_source_and_server_output(tmp_path: Path) -> None:
    script = write_fake_engine(tmp_path)
    (tmp_path / "write_demo_h5ad.py").write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "out = Path(args[args.index('--out') + 1])\n"
        "out.write_bytes(b'h5ad')\n"
        "sys.stdout.write(json.dumps({\n"
        "    'source': (\n"
        "        '合成矩阵，由 write_demo_h5ad.py 用种子 42 生成。'\n"
        "        '不是策展数据，不能当作正式分析。'\n"
        "    ),\n"
        "    'gene': 'IFITM3',\n"
        "    'group': 'group',\n"
        "    'case': 'Disease',\n"
        "    'control': 'Healthy',\n"
        "    'batch': 'sample_id',\n"
        "}) + '\\n')\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    state = tmp_path / "runs.json"
    client = TestClient(
        create_app(
            "secret-token",
            port=8765,
            launch=EngineLaunch(python=Path(sys.executable), script=script),
            state_path=state,
        )
    )
    response = client.post("/api/demo", headers=TOKEN)
    assert response.status_code == 201
    body = response.json()
    assert "合成矩阵" in body["source"]
    assert "策展" in body["source"]
    saved = json.loads(state.read_text(encoding="utf-8"))
    output = Path(next(iter(saved["runs"].values()))["output_root"])
    config = json.loads((output / "config.json").read_text(encoding="utf-8"))
    assert config["TARGET_GENE"] == "IFITM3"
    assert config["CASE_LABEL"] == "Disease"
    assert config["CONTROL_LABEL"] == "Healthy"
    assert "GSE167363" not in body["source"]
