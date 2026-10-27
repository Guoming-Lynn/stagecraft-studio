"""Fill formal task fields from the frozen protocol.

Per-library tasks publish under ``<task_id>/<library_id>`` so libraries do not
overwrite each other. Donor identity and source blocks come only from the
frozen protocol rows.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

PER_LIBRARY_TASKS = frozenset({"formal_part1_load", "formal_part1_qc"})


class ProtocolDefaultsError(ValueError):
    """The frozen protocol cannot supply what the task needs."""


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


def fill_protocol_defaults(
    task_id: str,
    fields: dict[str, object],
    *,
    document: dict[str, object],
    stage_dir: Path,
    tmp_dir: Path,
) -> None:
    """Mutate ``fields`` in place with protocol-derived inputs the caller left out."""
    rows = protocol_rows(document)
    if task_id == "formal_part1_load":
        row = _row_for(rows, str(fields.get("library_id", "")))
        fields.setdefault("dataset", row.get("dataset", ""))
        donor_id = row.get("donor_id", "").strip()
        if donor_id and not fields.get("donor_map"):
            path = tmp_dir / "donor_map.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["library_id", "donor_id"])
                writer.writerow([row["library_id"], donor_id])
            fields["donor_map"] = path
    elif task_id == "formal_part1_qc":
        library_id = str(fields.get("library_id", ""))
        _row_for(rows, library_id)
        fields.setdefault("loaded", stage_dir / "formal_part1_load" / library_id / "loaded.h5ad")
    elif task_id == "formal_part1_round":
        fields.setdefault("common", stage_dir / "formal_part1_merge" / "primary_common.h5ad")
    elif task_id == "formal_part1_review_tables":
        round_index = int(fields.get("round_index", 0))
        grid_rel = "formal_part1_grid" if round_index == 0 else f"formal_part1_round_{round_index}"
        fields.setdefault("grid", stage_dir / grid_rel / "all_resolutions.h5ad")
    elif task_id == "formal_part1_merge" and not fields.get("manifest"):
        fields["manifest"] = _write_manifest(rows, stage_dir, tmp_dir)


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
