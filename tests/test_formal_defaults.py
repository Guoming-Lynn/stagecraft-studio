"""Protocol rows fill donor maps, merge manifests, and per-library publish paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from stagecraft_studio.engine.formal_args import SPECS
from stagecraft_studio.rules.gates import (
    get_target_gene,
    is_blinding_active,
    is_target_gene_artifact,
)
from stagecraft_studio.worker.formal_defaults import (
    ProtocolDefaultsError,
    enqueue_validation_defaults,
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


def test_load_qc_and_grid_defaults_fill_from_protocol(tmp_path: Path) -> None:
    work_dir = tmp_path / "project"
    work_dir.mkdir()
    raw = work_dir / "counts.h5ad"
    raw.write_bytes(b"h5ad")
    stage_dir = work_dir / "analysis" / "stage_1"
    tmp_dir = stage_dir / ".studio" / "tmp" / "1"
    tmp_dir.mkdir(parents=True)

    doc: dict[str, object] = {
        "target_gene": "STAT1",
        "species": "human",
        "harmony_keys": ["dataset"],
        "qc": {"loose_min_genes": 250},
        "data_path": "counts.h5ad",
        "manifest": [{"library_id": "L1", "dataset": "D1", "donor_id": "P1", "source_block": "S1"}],
    }

    load_fields: dict[str, object] = {"library_id": "L1"}
    fill_protocol_defaults(
        "formal_part1_load",
        load_fields,
        document=doc,
        stage_dir=stage_dir,
        tmp_dir=tmp_dir,
        work_dir=work_dir,
    )
    assert load_fields["input"] == raw.resolve()
    assert load_fields["format"] == "h5ad"

    qc_fields: dict[str, object] = {"library_id": "L1"}
    fill_protocol_defaults(
        "formal_part1_qc",
        qc_fields,
        document=doc,
        stage_dir=stage_dir,
        tmp_dir=tmp_dir,
        work_dir=work_dir,
    )
    assert qc_fields["source"] == raw.resolve()
    qc_cfg = json.loads(Path(str(qc_fields["config"])).read_text(encoding="utf-8"))
    assert qc_cfg["random_seed"] == 42
    assert qc_cfg["loose_min_genes"] == 250

    grid_fields: dict[str, object] = {}
    fill_protocol_defaults(
        "formal_part1_grid",
        grid_fields,
        document=doc,
        stage_dir=stage_dir,
        tmp_dir=tmp_dir,
        work_dir=work_dir,
    )
    assert grid_fields["gene"] == "STAT1"
    assert grid_fields["common"] == stage_dir / "formal_part1_merge" / "primary_common.h5ad"
    grid_cfg = json.loads(Path(str(grid_fields["config"])).read_text(encoding="utf-8"))
    assert grid_cfg == {"random_seed": 42, "harmony_keys": ["dataset"]}


def test_post_lock_defaults_and_part3_barcode_extraction(tmp_path: Path) -> None:
    stage_dir = tmp_path / "stage_1"
    lock_dir = stage_dir / "formal_part1_lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "cell_annotations.csv").write_text(
        "barcode,cluster,cell_type\ncell_1,0,Monocyte\ncell_2,1,T_cell\ncell_3,0,Monocyte\n",
        encoding="utf-8",
    )
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    doc: dict[str, object] = {"target_gene": "STAT1"}

    p2_fig: dict[str, object] = {}
    fill_protocol_defaults(
        "formal_part2_figures", p2_fig, document=doc, stage_dir=stage_dir, tmp_dir=tmp_dir
    )
    assert p2_fig["input"] == lock_dir / "locked_atlas.h5ad"
    assert p2_fig["colors"] == lock_dir / "colors.json"
    assert p2_fig["group"] == "cell_type"
    assert p2_fig["gene"] == "STAT1"

    p3_fields: dict[str, object] = {"lineage": "Monocyte"}
    fill_protocol_defaults(
        "formal_part3_recluster", p3_fields, document=doc, stage_dir=stage_dir, tmp_dir=tmp_dir
    )
    bc_lines = Path(str(p3_fields["barcodes"])).read_text(encoding="utf-8").splitlines()
    assert bc_lines == ["cell_1", "cell_3"]
    assert p3_fields["seed"] == 42
    assert p3_fields["completed_rounds"] == 0

    with pytest.raises(ProtocolDefaultsError, match="PART3_LINEAGE_EMPTY"):
        fill_protocol_defaults(
            "formal_part3_recluster",
            {"lineage": "NK_cell"},
            document=doc,
            stage_dir=stage_dir,
            tmp_dir=tmp_dir,
        )

    p5_fields: dict[str, object] = {"arm": "Monocyte"}
    fill_protocol_defaults(
        "formal_part5_prepare", p5_fields, document=doc, stage_dir=stage_dir, tmp_dir=tmp_dir
    )
    assert p5_fields["input"] == lock_dir / "locked_atlas.h5ad"
    assert p5_fields["group"] == "cell_type"
    assert p5_fields["gene"] == "STAT1"


def test_enqueue_validation_defaults_accepts_minimal_and_rejects_bad_tokens() -> None:
    _, load_model, _ = SPECS["formal_part1_load"]
    minimal_load: dict[str, object] = {"library_id": "L1"}
    enqueue_validation_defaults("formal_part1_load", minimal_load)
    load_model.model_validate(minimal_load)

    bad_load: dict[str, object] = {"library_id": "bad space"}
    enqueue_validation_defaults("formal_part1_load", bad_load)
    with pytest.raises(ValueError):
        load_model.model_validate(bad_load)
