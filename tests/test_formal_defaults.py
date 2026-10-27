"""Protocol rows fill donor maps, merge manifests, and per-library publish paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from stagecraft_studio.rules.gates import (
    get_target_gene,
    is_blinding_active,
    is_target_gene_artifact,
)
from stagecraft_studio.worker.formal_defaults import (
    ProtocolDefaultsError,
    fill_protocol_defaults,
    publish_subpath,
)


def test_publish_subpath_is_per_library_for_load_and_qc() -> None:
    assert publish_subpath("formal_part1_load", {"library_id": "L2"}) == "formal_part1_load/L2"
    assert publish_subpath("formal_part1_merge", {"library_id": "L2"}) == "formal_part1_merge"


def test_load_writes_donor_map_from_the_protocol(tmp_path: Path) -> None:
    fields: dict[str, object] = {"library_id": "L2"}
    document = {
        "target_gene": "CD14",
        "libraries": [
            {"library_id": "L1", "dataset": "D1", "donor_id": "P1", "source_block": "S1"},
            {"library_id": "L2", "dataset": "D2", "donor_id": "P2", "source_block": "S2"},
        ],
    }
    fill_protocol_defaults(
        "formal_part1_load", fields, document=document, stage_dir=tmp_path, tmp_dir=tmp_path
    )
    assert fields["dataset"] == "D2"
    path = Path(str(fields["donor_map"]))
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text == "library_id,donor_id\nL2,P2\n"


def test_merge_manifest_uses_protocol_source_blocks(tmp_path: Path) -> None:
    qc = tmp_path / "formal_part1_qc" / "L1"
    qc.mkdir(parents=True)
    (qc / "qc_record.json").write_text('{"in_primary_atlas": true}', encoding="utf-8")
    (qc / "clean.h5ad").write_bytes(b"clean")
    fields: dict[str, object] = {}
    document = {
        "libraries": [{"library_id": "L1", "dataset": "D1", "source_block": "BLOCK_X"}],
    }
    fill_protocol_defaults(
        "formal_part1_merge", fields, document=document, stage_dir=tmp_path, tmp_dir=tmp_path
    )
    manifest = json.loads(Path(str(fields["manifest"])).read_text(encoding="utf-8"))
    assert manifest == [
        {
            "library_id": "L1",
            "dataset": "D1",
            "source_block": "BLOCK_X",
            "include_in_primary_atlas": True,
            "path": str(qc / "clean.h5ad"),
        }
    ]


def test_merge_requires_qc(tmp_path: Path) -> None:
    fields: dict[str, object] = {}
    with pytest.raises(ProtocolDefaultsError, match="QC_NOT_RUN"):
        fill_protocol_defaults(
            "formal_part1_merge",
            fields,
            document={"libraries": [{"library_id": "L1", "dataset": "D1"}]},
            stage_dir=tmp_path,
            tmp_dir=tmp_path,
        )


def test_target_exposing_tasks_are_hidden_by_task_id() -> None:
    assert is_target_gene_artifact("formal_part2_figures/umap.png")
    assert not is_target_gene_artifact("formal_part1_grid/umap.png")
    assert is_target_gene_artifact("formal_part1_grid/CD14_umap.png", "CD14")


class _Run:
    def __init__(self) -> None:
        self.id = 1
        self.protocol_id = 1
        self.leiden_ids_json = '["0", "1"]'


def test_blinding_lifts_after_matching_cluster_review() -> None:
    from stagecraft_studio.rules.gates import cluster_set_hash

    class _Session:
        def get(self, _model, _id):
            return None

        def scalars(self, _stmt):
            return [
                type(
                    "Row",
                    (),
                    {
                        "body_json": json.dumps({"kind": "clusters", "blinding": "BLIND"}),
                        "evidence_hash": cluster_set_hash(["0", "1"]),
                    },
                )()
            ]

    assert is_blinding_active(_Session(), _Run()) is False  # type: ignore[arg-type]


def test_get_target_gene_reads_the_protocol_only() -> None:
    class _Protocol:
        document_json = json.dumps({"target_gene": "CD14"})

    class _Session:
        def get(self, model, _id):
            name = getattr(model, "__name__", "")
            return _Protocol() if name == "ProtocolVersion" else type("P", (), {"name": "KRAS"})()

    assert get_target_gene(_Session(), _Run()) == "CD14"  # type: ignore[arg-type]
