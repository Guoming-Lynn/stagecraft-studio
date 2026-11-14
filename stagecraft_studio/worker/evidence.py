"""Hydrate StageRun.evidence_json from published formal task outputs."""

from __future__ import annotations

import contextlib
import csv
import json
from pathlib import Path

from sqlalchemy.orm import Session

from stagecraft_studio.db.models import Job, StageRun
from stagecraft_studio.rules.gates import canonical_resolution


def record_job_evidence(
    session: Session,
    job: Job,
    *,
    dest_dir: Path | None,
) -> None:
    """Store published records from Part 1–5 into StageRun.evidence_json."""
    if dest_dir is None:
        return
    run = session.get(StageRun, job.stage_run_id)
    if run is None:
        return
    evidence = json.loads(run.evidence_json) if run.evidence_json else {}
    task_id = job.task_id

    if task_id == "formal_part5_prepare":
        vpath = dest_dir / "verdict.json"
        if vpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["verdict"] = json.loads(vpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part4_survey":
        rpath = dest_dir / "part4_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part4"] = json.loads(rpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part2_survey":
        rpath = dest_dir / "part2_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part2"] = json.loads(rpath.read_text(encoding="utf-8"))
    elif task_id == "formal_part1_lock":
        lpath = dest_dir / "lock_record.json"
        if lpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["lock"] = json.loads(lpath.read_text(encoding="utf-8"))
    elif task_id in {"formal_part1_grid", "formal_part1_round"}:
        gpath = dest_dir / "grid_record.json"
        if gpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["grid"] = json.loads(gpath.read_text(encoding="utf-8"))
        overview, res_map = _parse_grid_tables(dest_dir)
        if overview is not None:
            evidence["overview"] = overview
        if res_map is not None:
            evidence["clusters_by_resolution"] = res_map
            selected = evidence.get("active_resolution")
            if isinstance(selected, str) and res_map.get(selected):
                evidence["clusters"] = list(res_map[selected])
        if task_id == "formal_part1_grid":
            evidence["active_part1_round"] = 0
            evidence["active_grid_rel"] = "formal_part1_grid"
        else:
            record_path = dest_dir / "round_record.json"
            with contextlib.suppress(json.JSONDecodeError, OSError):
                record = json.loads(record_path.read_text(encoding="utf-8"))
                evidence["active_part1_round"] = record["round_index"]
                evidence["active_grid_rel"] = f"formal_part1_round_{record['round_index']}"
                evidence["clusters"] = []
                evidence.pop("active_resolution", None)
                evidence.pop("active_leiden_ids", None)
    elif task_id == "formal_part1_review_tables":
        evidence["review_tables_run"] = int(json.loads(job.payload_json)["fields"]["round_index"])
    elif task_id == "formal_part3_recluster":
        rpath = dest_dir / "part3_record.json"
        if rpath.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                evidence["part3"] = json.loads(rpath.read_text(encoding="utf-8"))
        overview, res_map = _parse_grid_tables(dest_dir)
        if overview is not None:
            evidence["part3_overview"] = overview
        if res_map is not None:
            evidence["part3_clusters_by_resolution"] = res_map

    run.evidence_json = json.dumps(evidence, ensure_ascii=False)


def _parse_grid_tables(
    dest_dir: Path,
) -> tuple[list[dict[str, object]] | None, dict[str, list[str]] | None]:
    overview: list[dict[str, object]] | None = None
    res_map: dict[str, list[str]] | None = None
    opath = dest_dir / "Leiden_resolution_overview.csv"
    if opath.is_file():
        with contextlib.suppress(OSError), opath.open("r", encoding="utf-8") as f:
            rows: list[dict[str, object]] = []
            for r in csv.DictReader(f):
                row: dict[str, object] = dict(r)
                if row.get("resolution"):
                    row["resolution"] = canonical_resolution(row["resolution"])
                for k in ("n_clusters", "min_cluster_size", "max_cluster_size"):
                    if row.get(k) is not None:
                        with contextlib.suppress(ValueError):
                            row[k] = int(str(row[k]))
                if row.get("median_cluster_size") is not None:
                    with contextlib.suppress(ValueError):
                        row["median_cluster_size"] = float(str(row["median_cluster_size"]))
                rows.append(row)
            overview = rows
    cpath = dest_dir / "cluster_by_dataset.csv"
    if cpath.is_file():
        with contextlib.suppress(OSError), cpath.open("r", encoding="utf-8") as f:
            res_map = {}
            for crow in csv.DictReader(f):
                res_val = canonical_resolution(crow.get("resolution", ""))
                cid = str(crow.get("cluster", ""))
                if res_val and cid:
                    res_map.setdefault(res_val, [])
                    if cid not in res_map[res_val]:
                        res_map[res_val].append(cid)
    return overview, res_map
