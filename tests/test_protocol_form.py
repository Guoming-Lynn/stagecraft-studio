"""The research-design form is the schema. Extra fields and forbidden keys fail."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.domain.protocol_form import form_fields
from stagecraft_studio.engine.launch import EngineLaunch

TOKEN = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"}


def test_form_has_no_code_field(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/protocol/form")
    assert response.status_code == 200
    fields = response.json()["fields"]
    names = [field["name"] for field in fields]
    assert names == [field["name"] for field in form_fields()]
    assert all(field["kind"] != "code" for field in fields)
    harmony = next(field for field in fields if field["name"] == "harmony_keys")
    assert harmony["default"] == ["dataset"]
    assert "donor_id" in harmony["forbidden"]


def test_donor_is_not_a_harmony_key(tmp_path: Path) -> None:
    client = _client(tmp_path)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    body = _body(source)
    body["harmony_keys"] = ["dataset", "donor_id"]
    response = client.post("/api/protocol/freeze", headers=TOKEN, json=body)
    assert response.status_code == 400
    assert response.json()["detail"]["rule_id"] == "HARMONY_KEYS_ALLOWED"


def test_extra_field_is_rejected(tmp_path: Path) -> None:
    client = _client(tmp_path)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    body = _body(source)
    body["script"] = "print(1)"
    response = client.post("/api/protocol/freeze", headers=TOKEN, json=body)
    assert response.status_code == 422


def test_a_valid_form_freezes_a_hash(tmp_path: Path) -> None:
    client = _client(tmp_path)
    source = tmp_path / "counts.h5ad"
    source.write_bytes(b"counts")
    response = client.post("/api/protocol/freeze", headers=TOKEN, json=_body(source))
    assert response.status_code == 201
    payload = response.json()
    assert len(payload["content_hash"]) == 64
    assert payload["stage_run_id"] > 0


def _client(tmp_path: Path) -> TestClient:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    app = create_app(
        "secret-token",
        port=8765,
        launch=EngineLaunch(python=Path("python"), script=Path("run_pipeline.py")),
        database=database,
        include_ui=False,
    )
    return TestClient(app)


def _body(source: Path) -> dict[str, object]:
    return {
        "target_gene": "STAT1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "loose_min_genes": 200,
        "data_path": str(source),
        "libraries": [{"library_id": "A", "dataset": "D1"}],
    }
