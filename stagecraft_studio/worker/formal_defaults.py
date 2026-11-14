"""Fill formal task fields from the frozen protocol and stage artifacts.

Per-library tasks publish under ``<task_id>/<library_id>`` so libraries do not
overwrite each other. Donor identity and source blocks come only from the
frozen protocol rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

PER_LIBRARY_TASKS = frozenset({"formal_part1_load", "formal_part1_qc"})

_ENQUEUE_PLACEHOLDERS: dict[str, dict[str, object]] = {
    "formal_part1_load": {"input": "placeholder_input", "format": "h5ad"},
    "formal_part1_qc": {"source": "placeholder_source", "config": "placeholder_config"},
    "formal_part1_merge": {"gene": "GENE"},
    "formal_part1_grid": {
        "common": "placeholder_common",
        "gene": "GENE",
        "config": "placeholder_config",
    },
    "formal_part1_round": {
        "common": "placeholder_common",
        "previous_grid": "placeholder_grid",
        "review": "placeholder_review",
        "config": "placeholder_config",
        "gene": "GENE",
    },
    "formal_part1_review_tables": {"grid": "placeholder_grid", "gene": "GENE"},
    "formal_part1_lock": {
        "common": "placeholder_common",
        "grid": "placeholder_grid",
        "review": "placeholder_review",
        "gene": "GENE",
    },
    "formal_part2_survey": {
        "input": "placeholder_input",
        "gene": "GENE",
        "group": "cell_type",
    },
    "formal_part2_figures": {
        "input": "placeholder_input",
        "gene": "GENE",
        "group": "cell_type",
        "colors": "placeholder_colors",
    },
    "formal_part3_recluster": {
        "input": "placeholder_input",
        "barcodes": "placeholder_barcodes",
        "gene": "GENE",
        "seed": 42,
        "completed_rounds": 0,
    },
    "formal_part4_survey": {
        "input": "placeholder_input",
        "gene": "GENE",
        "group": "cell_type",
    },
    "formal_part4_figures": {
        "input": "placeholder_input",
        "gene": "GENE",
        "group": "cell_type",
        "colors": "placeholder_colors",
    },
    "formal_part5_prepare": {
        "input": "placeholder_input",
        "gene": "GENE",
        "group": "cell_type",
    },
    "formal_stage_report": {"stage": "placeholder_stage"},
}


class ProtocolDefaultsError(ValueError):
    """The frozen protocol or stage artifacts cannot supply what the task needs."""


def enqueue_validation_defaults(task_id: str, check_fields: dict[str, object]) -> None:
    """Populate worker-supplied placeholders so Pydantic validates caller-provided fields."""
    placeholders = _ENQUEUE_PLACEHOLDERS.get(task_id, {})
    for key, placeholder in placeholders.items():
        if check_fields.get(key) in (None, ""):
            check_fields[key] = placeholder
    if check_fields.get("out") in (None, "") and task_id != "formal_stage_report":
        check_fields["out"] = "placeholder_out"


def protocol_rows(document: dict[str, object]) -> list[dict[str, str]]:
    raw = document.get("manifest") or document.get("libraries") or []
    rows: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                rows.append({str(k): str(v) for k, v in item.items() if v is not None})
    return rows


def publish_subpath(task_id: str, fields: dict[str, object]) -> str:
    if task_id in PER_LIBRARY_TASKS:
        library_id = str(fields.get("library_id", "")).strip()
        if not library_id:
            raise ProtocolDefaultsError("LIBRARY_ID_REQUIRED")
        return f"{task_id}/{library_id}"
    return task_id


def _row_for(rows: list[dict[str, str]], library_id: str) -> dict[str, str]:
    for row in rows:
        if row.get("library_id") == library_id:
            return row
    raise ProtocolDefaultsError(f"LIBRARY_NOT_IN_PROTOCOL: {library_id}")


def _is_missing(fields: dict[str, object], key: str) -> bool:
    val = fields.get(key)
    return val is None or (isinstance(val, str) and not val.strip())


def _target_gene(document: dict[str, object]) -> str:
    gene = str(document.get("target_gene", "")).strip()
    if not gene:
        raise ProtocolDefaultsError("TARGET_GENE_MISSING")
    return gene


def _harmony_keys(document: dict[str, object]) -> list[str]:
    raw = document.get("harmony_keys")
    if isinstance(raw, list):
        keys = [str(item).strip() for item in raw if str(item).strip()]
        if keys:
            return keys
    return ["dataset"]


def _resolve_candidate(raw: str, work_dir: Path | None) -> Path:
    path = Path(raw)
    if not path.is_absolute() and work_dir is not None:
        return (work_dir / path).resolve()
    return path


def _infer_load_format(path: Path) -> str:
    if path.exists() and path.is_dir():
        return "10x_mtx"
    suffix = path.name.casefold()
    if suffix.endswith(".h5"):
        return "10x_h5"
    return "h5ad"


def write_default_grid_config(document: dict[str, object], tmp_dir: Path) -> Path:
    path = tmp_dir / "grid_config.json"
    payload = {"random_seed": 42, "harmony_keys": _harmony_keys(document)}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def fill_protocol_defaults(
    task_id: str,
    fields: dict[str, object],
    *,
    document: dict[str, object],
    stage_dir: Path,
    tmp_dir: Path,
    work_dir: Path | None = None,
) -> None:
    """Mutate ``fields`` in place with protocol-derived inputs the caller left out."""
    rows = protocol_rows(document)
    if task_id == "formal_part1_load":
        row = _row_for(rows, str(fields.get("library_id", "")))
        if _is_missing(fields, "dataset"):
            fields["dataset"] = row.get("dataset", "")
        raw_input = (
            str(fields.get("input", "")).strip()
            or row.get("input", "").strip()
            or row.get("path", "").strip()
            or str(document.get("data_path", "")).strip()
        )
        if _is_missing(fields, "input") and raw_input:
            fields["input"] = _resolve_candidate(raw_input, work_dir)
        if _is_missing(fields, "format") and not _is_missing(fields, "input"):
            in_val = fields["input"]
            cand = in_val if isinstance(in_val, Path) else _resolve_candidate(str(in_val), work_dir)
            fields["format"] = _infer_load_format(cand)
        donor_id = row.get("donor_id", "").strip()
        if donor_id and _is_missing(fields, "donor_map"):
            path = tmp_dir / "donor_map.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["library_id", "donor_id"])
                writer.writerow([row["library_id"], donor_id])
            fields["donor_map"] = path
    elif task_id == "formal_part1_qc":
        library_id = str(fields.get("library_id", ""))
        row = _row_for(rows, library_id)
        loaded_path = stage_dir / "formal_part1_load" / library_id / "loaded.h5ad"
        if _is_missing(fields, "loaded"):
            fields["loaded"] = loaded_path
        if _is_missing(fields, "source"):
            raw_source = (
                row.get("input", "").strip()
                or row.get("path", "").strip()
                or str(document.get("data_path", "")).strip()
            )
            cand_source = _resolve_candidate(raw_source, work_dir) if raw_source else None
            fields["source"] = (
                cand_source if cand_source is not None and cand_source.is_file() else loaded_path
            )
        if _is_missing(fields, "config"):
            qc_doc = document.get("qc")
            loose = qc_doc.get("loose_min_genes", 200) if isinstance(qc_doc, dict) else 200
            cfg_path = tmp_dir / "qc_config.json"
            cfg_path.write_text(
                json.dumps(
                    {
                        "random_seed": 42,
                        "species": document.get("species", "human"),
                        "loose_min_genes": loose,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            fields["config"] = cfg_path
    elif task_id == "formal_part1_merge":
        if _is_missing(fields, "gene") and document.get("target_gene"):
            fields["gene"] = _target_gene(document)
        if _is_missing(fields, "manifest"):
            fields["manifest"] = _write_manifest(rows, stage_dir, tmp_dir)
    elif task_id == "formal_part1_grid":
        if _is_missing(fields, "common"):
            fields["common"] = stage_dir / "formal_part1_merge" / "primary_common.h5ad"
        if _is_missing(fields, "gene"):
            fields["gene"] = _target_gene(document)
        if _is_missing(fields, "config"):
            fields["config"] = write_default_grid_config(document, tmp_dir)
    elif task_id == "formal_part1_round":
        if _is_missing(fields, "common"):
            fields["common"] = stage_dir / "formal_part1_merge" / "primary_common.h5ad"
    elif task_id == "formal_part1_review_tables":
        raw_round = fields.get("round_index", 0)
        round_index = int(raw_round) if isinstance(raw_round, (int, str)) else 0
        grid_rel = "formal_part1_grid" if round_index == 0 else f"formal_part1_round_{round_index}"
        if _is_missing(fields, "grid"):
            fields["grid"] = stage_dir / grid_rel / "all_resolutions.h5ad"
    elif task_id in {"formal_part2_survey", "formal_part2_figures"}:
        _fill_locked_defaults(fields, document=document, stage_dir=stage_dir)
        if task_id == "formal_part2_figures" and _is_missing(fields, "colors"):
            fields["colors"] = stage_dir / "formal_part1_lock" / "colors.json"
    elif task_id == "formal_part3_recluster":
        if _is_missing(fields, "input"):
            fields["input"] = stage_dir / "formal_part1_lock" / "locked_atlas.h5ad"
        if _is_missing(fields, "gene"):
            fields["gene"] = _target_gene(document)
        if _is_missing(fields, "seed"):
            fields["seed"] = 42
        if _is_missing(fields, "completed_rounds"):
            fields["completed_rounds"] = 0
        if _is_missing(fields, "barcodes"):
            fields["barcodes"] = _write_lineage_barcodes(
                str(fields.get("lineage", "")).strip(), stage_dir, tmp_dir
            )
    elif task_id in {"formal_part4_survey", "formal_part4_figures"}:
        if _is_missing(fields, "input"):
            comp = stage_dir / "formal_part3_recluster" / "compartment_counts.h5ad"
            fields["input"] = (
                comp if comp.is_file() else stage_dir / "formal_part1_lock" / "locked_atlas.h5ad"
            )
        _fill_locked_defaults(fields, document=document, stage_dir=stage_dir)
        if task_id == "formal_part4_figures" and _is_missing(fields, "colors"):
            fields["colors"] = stage_dir / "formal_part1_lock" / "colors.json"
    elif task_id == "formal_part5_prepare":
        _fill_locked_defaults(fields, document=document, stage_dir=stage_dir)


def _fill_locked_defaults(
    fields: dict[str, object], *, document: dict[str, object], stage_dir: Path
) -> None:
    if _is_missing(fields, "input"):
        fields["input"] = stage_dir / "formal_part1_lock" / "locked_atlas.h5ad"
    if _is_missing(fields, "gene"):
        fields["gene"] = _target_gene(document)
    if _is_missing(fields, "group"):
        fields["group"] = "cell_type"


def _write_lineage_barcodes(lineage: str, stage_dir: Path, tmp_dir: Path) -> Path:
    if not lineage:
        raise ProtocolDefaultsError("LINEAGE_REQUIRED")
    annotations = stage_dir / "formal_part1_lock" / "cell_annotations.csv"
    if not annotations.is_file():
        raise ProtocolDefaultsError(f"PART3_BARCODES_NOT_FOUND: {lineage}")
    matched: list[str] = []
    with annotations.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            bc = str(row.get("barcode", "")).strip()
            if not bc:
                continue
            if row.get("cell_type") == lineage or row.get("cluster") == lineage:
                matched.append(bc)
    if not matched:
        raise ProtocolDefaultsError(f"PART3_LINEAGE_EMPTY: {lineage}")
    out_path = tmp_dir / "lineage_barcodes.txt"
    out_path.write_text("\n".join(matched) + "\n", encoding="utf-8")
    return out_path


def _write_manifest(rows: list[dict[str, str]], stage_dir: Path, tmp_dir: Path) -> Path:
    if not rows:
        raise ProtocolDefaultsError("PROTOCOL_HAS_NO_LIBRARIES")
    entries: list[dict[str, object]] = []
    excluded: list[str] = []
    for row in rows:
        library_id = row["library_id"]
        qc_dir = stage_dir / "formal_part1_qc" / library_id
        record_path = qc_dir / "qc_record.json"
        if not record_path.is_file():
            raise ProtocolDefaultsError(f"QC_NOT_RUN: {library_id}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        clean = qc_dir / "clean.h5ad"
        if not record.get("in_primary_atlas") or not clean.is_file():
            excluded.append(library_id)
            continue
        entries.append(
            {
                "library_id": library_id,
                "dataset": row["dataset"],
                "source_block": row.get("source_block") or row["dataset"],
                "include_in_primary_atlas": True,
                "path": str(clean),
            }
        )
    path = tmp_dir / "merge_manifest.json"
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (tmp_dir / "merge_excluded_libraries.json").write_text(
        json.dumps(excluded, ensure_ascii=False), encoding="utf-8"
    )
    return path
