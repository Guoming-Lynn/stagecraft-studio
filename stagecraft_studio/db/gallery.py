"""Formal analysis gallery aggregation.

Collects image artifacts (PNG, SVG), publication PDFs, parameter sidecars,
and source data CSVs. Explicitly preserves NOT_ESTIMABLE slots so that
failed or inestimable arms are never hidden.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.api.files import PathRejected, resolve_inside
from stagecraft_studio.db.models import (
    Artifact,
    Job,
    Project,
    ProtocolVersion,
    RuleResultRow,
    StageRun,
)
from stagecraft_studio.rules.gates import (
    get_target_gene,
    is_blinding_active,
    is_target_gene_artifact,
)
from stagecraft_studio.rules.scientific_status import scientific_status


class GalleryNotFound(Exception):
    """The requested stage run was not found."""


class ArtifactAccessDenied(Exception):
    """Access to raw artifact was denied."""

    def __init__(self, detail: str = "ACCESS_DENIED", status_code: int = 403) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class ScientificStatusView(BaseModel):
    calibration_status: str
    associated: bool
    evidence_ceiling: str
    reasons: list[str] = Field(default_factory=list)


class GalleryFigureItem(BaseModel):
    id: str
    task_id: str
    title: str
    stage_part: str
    panel_id: str
    status: str  # "AVAILABLE" | "NOT_ESTIMABLE" | "STOPPED"
    format_png: str | None = None
    format_svg: str | None = None
    format_pdf: str | None = None
    source_data: str | None = None
    parameters: str | None = None
    caption: str = ""
    reasons: list[str] = Field(default_factory=list)
    content_hash: str = ""


class StageGalleryView(BaseModel):
    run_id: int
    project_id: int
    scientific_status: ScientificStatusView
    figures: list[GalleryFigureItem]
    total_figures: int
    available_count: int
    not_estimable_count: int


def resolve_stage_dir(session: Session, run: StageRun) -> Path:
    project = session.get(Project, run.project_id)
    if project and project.root_path:
        return Path(project.root_path) / "analysis" / f"stage_{run.id}"
    protocol = session.get(ProtocolVersion, run.protocol_id)
    if protocol and protocol.document_json:
        try:
            doc = json.loads(protocol.document_json)
            if isinstance(doc, dict) and "data_path" in doc:
                return Path(str(doc["data_path"])).parent / "analysis" / f"stage_{run.id}"
        except (json.JSONDecodeError, OSError):
            pass
    return Path("analysis") / f"stage_{run.id}"


def get_stage_gallery(session: Session, run_id: int) -> dict[str, Any]:
    run = session.get(StageRun, run_id)
    if run is None:
        raise GalleryNotFound(f"Stage run {run_id} not found")

    artifacts = list(
        session.scalars(
            select(Artifact)
            .join(Job, Artifact.job_id == Job.id)
            .where(Job.stage_run_id == run_id, Artifact.artifact_status == "VALID")
            .order_by(Artifact.id.asc())
        ).all()
    )

    evidence: dict[str, Any] = {}
    if run.evidence_json:
        try:
            evidence = json.loads(run.evidence_json)
        except (json.JSONDecodeError, OSError):
            evidence = {}

    raw_sc = scientific_status(
        stage_status=run.stage_status,
        invalidated=run.invalidated,
        evidence=evidence,
    )
    raw_reasons = raw_sc.get("reasons", [])
    reasons_list = [str(r) for r in raw_reasons] if isinstance(raw_reasons, list) else []
    sc_view = ScientificStatusView(
        calibration_status="NOT_ESTABLISHED_FOR_THIS_ANALYSIS",
        associated=False,
        evidence_ceiling=str(raw_sc.get("evidence_ceiling", "descriptive")),
        reasons=reasons_list,
    )

    artifact_by_path = {a.relative_path: a for a in artifacts}
    figure_stems: dict[str, dict[str, Any]] = {}

    for a in artifacts:
        p = Path(a.relative_path)
        suf = p.suffix.casefold()
        if suf in {".png", ".svg"}:
            stem_key = p.with_suffix("").as_posix()
            if stem_key not in figure_stems:
                task_id = p.parts[0] if len(p.parts) > 1 else ""
                figure_stems[stem_key] = {
                    "task_id": task_id,
                    "stem": stem_key,
                    "name": p.stem,
                    "path_obj": p,
                }

    figure_items: list[GalleryFigureItem] = []

    for stem_key, meta in sorted(figure_stems.items()):
        p = meta["path_obj"]
        name = meta["name"]
        task_id = meta["task_id"]

        png_path = f"{stem_key}.png" if f"{stem_key}.png" in artifact_by_path else None
        svg_path = f"{stem_key}.svg" if f"{stem_key}.svg" in artifact_by_path else None
        pdf_path = f"{stem_key}.pdf" if f"{stem_key}.pdf" in artifact_by_path else None
        param_path = (
            f"{stem_key}.parameters.json"
            if f"{stem_key}.parameters.json" in artifact_by_path
            else None
        )

        parent_dir = p.parent.as_posix() if str(p.parent) != "." else ""
        source_cand1 = (
            f"{parent_dir}/source_data/{name}.csv" if parent_dir else f"source_data/{name}.csv"
        )
        source_cand2 = f"{parent_dir}/{name}.csv" if parent_dir else f"{name}.csv"
        source_cand3 = f"{task_id}/Leiden_resolution_overview.csv"

        source_path = None
        if source_cand1 in artifact_by_path:
            source_path = source_cand1
        elif source_cand2 in artifact_by_path:
            source_path = source_cand2
        elif source_cand3 in artifact_by_path:
            source_path = source_cand3

        stage_part = "Other"
        panel_id = name
        title = name.replace("_", " ")
        caption = "Figure artifact generated by pipeline."

        if name.startswith("F02_") or task_id == "formal_part2_figures":
            stage_part = "Part 2"
            panel_id = name[:6] if len(name) >= 6 else name
            title = f"{panel_id}: {name[7:].replace('_', ' ')}" if len(name) > 7 else name
            caption = "Part 2 single-cell target survey on locked UMAP coordinates."
        elif name.startswith("F04_") or task_id == "formal_part4_figures":
            stage_part = "Part 4"
            panel_id = name[:6] if len(name) >= 6 else name
            title = f"{panel_id}: {name[7:].replace('_', ' ')}" if len(name) > 7 else name
            caption = "Part 4 identifiability check: sd ≈ 0 cannot identify a Part 5 slope."
        elif task_id == "formal_part1_grid" or "grid" in name.lower():
            stage_part = "Part 1"
            panel_id = "F01_grid"
            title = "Leiden Resolution Overview"
            caption = "Part 1 cluster resolution scan and metric evaluation."

        primary_artifact = artifact_by_path.get(png_path or svg_path or "")
        content_hash = primary_artifact.content_hash if primary_artifact else ""

        figure_items.append(
            GalleryFigureItem(
                id=stem_key,
                task_id=task_id,
                title=title,
                stage_part=stage_part,
                panel_id=panel_id,
                status="AVAILABLE",
                format_png=png_path,
                format_svg=svg_path,
                format_pdf=pdf_path,
                source_data=source_path,
                parameters=param_path,
                caption=caption,
                content_hash=content_hash,
            )
        )

    figure_items.extend(_collect_not_estimable(session, run.id, evidence, artifact_by_path))

    if is_blinding_active(session, run):
        target_gene = get_target_gene(session, run)
        figure_items = [
            f
            for f in figure_items
            if not (
                f.stage_part in {"Part 2", "Part 4", "Part 5"}
                or is_target_gene_artifact(f.id, target_gene)
                or (f.format_png and is_target_gene_artifact(f.format_png, target_gene))
                or (f.format_svg and is_target_gene_artifact(f.format_svg, target_gene))
            )
        ]

    total_count = len(figure_items)
    avail_count = sum(1 for f in figure_items if f.status == "AVAILABLE")
    not_est_count = sum(1 for f in figure_items if f.status == "NOT_ESTIMABLE")

    view = StageGalleryView(
        run_id=run.id,
        project_id=run.project_id,
        scientific_status=sc_view,
        figures=figure_items,
        total_figures=total_count,
        available_count=avail_count,
        not_estimable_count=not_est_count,
    )
    return view.model_dump()


def _collect_not_estimable(
    session: Session,
    run_id: int,
    evidence: dict[str, Any],
    artifact_by_path: dict[str, Artifact],
) -> list[GalleryFigureItem]:
    items: list[GalleryFigureItem] = []
    part4 = evidence.get("part4")
    if isinstance(part4, dict) and str(part4.get("stopped", "")) == "NO_PART4":
        reason = str(part4.get("reason", "LINEAGE_ROUND_LIMIT"))
        items.append(
            GalleryFigureItem(
                id=f"not_estimable_part4_{reason}",
                task_id="formal_part4_figures",
                title=f"Part 4 Identifiability: STOPPED ({reason})",
                stage_part="Part 4",
                panel_id="F04_STOPPED",
                status="NOT_ESTIMABLE",
                caption=f"Part 4 stopped due to {reason}. Preserved per scientific specification.",
                reasons=[reason],
            )
        )

    verdict = evidence.get("verdict")
    if isinstance(verdict, dict):
        v_stop = str(verdict.get("stopped", ""))
        v_elig = str(verdict.get("eligibility", ""))
        arm = str(verdict.get("arm", "default"))
        if v_stop == "NOT_ESTIMABLE" or v_elig == "NOT_ESTIMABLE":
            reasons = [str(r) for r in verdict.get("reasons", [])] or ["NOT_ESTIMABLE"]
            elig_csv = (
                "formal_part5_prepare/eligibility.csv"
                if "formal_part5_prepare/eligibility.csv" in artifact_by_path
                else None
            )
            items.append(
                GalleryFigureItem(
                    id=f"not_estimable_part5_{arm}",
                    task_id="formal_part5_prepare",
                    title=f"Part 5 Model Fit: {arm} (NOT_ESTIMABLE)",
                    stage_part="Part 5",
                    panel_id="F05_NOT_ESTIMABLE",
                    status="NOT_ESTIMABLE",
                    caption=(
                        "The donor-level association model is not estimable under "
                        "frozen protocol criteria."
                    ),
                    reasons=reasons,
                    source_data=elig_csv,
                )
            )

    rule_blocks = session.scalars(
        select(RuleResultRow).where(
            RuleResultRow.stage_run_id == run_id,
            RuleResultRow.rule_id == "DESIGN_ESTIMABLE",
            RuleResultRow.rule_status == "BLOCK",
        )
    ).all()
    for r in rule_blocks:
        try:
            detail = json.loads(r.detail_json)
            arm = str(detail.get("arm", "default"))
            reason = str(detail.get("reason", "DESIGN_NOT_ESTIMABLE"))
        except (json.JSONDecodeError, OSError):
            arm, reason = "default", "DESIGN_NOT_ESTIMABLE"
        target_id = f"not_estimable_part5_{arm}"
        if not any(f.id == target_id for f in items):
            items.append(
                GalleryFigureItem(
                    id=target_id,
                    task_id="formal_part5_prepare",
                    title=f"Part 5 Model Fit: {arm} (NOT_ESTIMABLE)",
                    stage_part="Part 5",
                    panel_id="F05_NOT_ESTIMABLE",
                    status="NOT_ESTIMABLE",
                    caption="Model design not estimable. Slot preserved.",
                    reasons=[reason],
                )
            )
    return items


def get_authorized_raw_artifact(session: Session, run: StageRun, rel: str) -> Path:
    normalized = rel.replace("\\", "/").strip().lstrip("/")
    parts = [p for p in normalized.split("/") if p]
    if any(p == ".studio" or p.startswith(".studio") for p in parts) or ".studio" in normalized:
        raise ArtifactAccessDenied("ACCESS_DENIED_STUDIO_INTERNAL", 403)

    stage_dir = resolve_stage_dir(session, run)
    try:
        path = resolve_inside(stage_dir, normalized)
    except PathRejected as exc:
        raise ArtifactAccessDenied(exc.detail, exc.status) from exc

    try:
        rel_clean = path.relative_to(stage_dir.resolve()).as_posix()
    except ValueError:
        try:
            rel_clean = path.relative_to(stage_dir).as_posix()
        except ValueError:
            raise ArtifactAccessDenied("PATH_OUTSIDE_STAGE_DIR", 403) from None

    art = session.scalars(
        select(Artifact)
        .join(Job, Artifact.job_id == Job.id)
        .where(
            Job.stage_run_id == run.id,
            Artifact.relative_path == rel_clean,
            Artifact.artifact_status == "VALID",
        )
    ).first()
    if art is None:
        raise ArtifactAccessDenied("ARTIFACT_NOT_VALID", 403)

    if is_blinding_active(session, run):
        target_gene = get_target_gene(session, run)
        if is_target_gene_artifact(rel_clean, target_gene):
            raise ArtifactAccessDenied("TARGET_GENE_BLINDED", 403)

    if not path.is_file():
        raise ArtifactAccessDenied("FILE_NOT_FOUND", 404)

    return path
