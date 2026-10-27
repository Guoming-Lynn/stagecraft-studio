"""Server-side review gates. Callers cannot supply a pass bit."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from stagecraft_studio.db.models import ProtocolVersion, ReviewDecision, StageRun
from stagecraft_studio.engine.registry import TARGET_EXPOSING_TASKS

BLINDING_VALUES = frozenset({"BLIND", "UNBLINDED_WITH_REASON", "NOT_APPLICABLE"})
LEIDEN_RESOLUTIONS: tuple[str, ...] = (
    "0.2",
    "0.3",
    "0.4",
    "0.5",
    "0.6",
    "0.8",
    "1.0",
    "1.2",
    "1.5",
)
RESOLUTIONS = frozenset(LEIDEN_RESOLUTIONS)
DECISIONS = frozenset({"KEEP", "DELETE"})
PRE_RESOLUTION = frozenset(
    {
        "formal_part1_load",
        "formal_part1_qc",
        "formal_part1_merge",
        "formal_part1_grid",
        "formal_part1_review_tables",
    }
)
POST_LOCK_TASKS = frozenset(
    {
        "formal_part2_survey",
        "formal_part2_figures",
        "formal_part3_recluster",
        "formal_part4_survey",
        "formal_part4_figures",
        "formal_part5_prepare",
    }
)
_HEX = frozenset("0123456789abcdef")


class GateRejected(Exception):
    """A review rule refused the request."""

    def __init__(self, rule_id: str, status_code: int) -> None:
        self.rule_id = rule_id
        self.status_code = status_code
        super().__init__(rule_id)


def canonical_resolution(value: object) -> str:
    """Normalize resolution strings (e.g. '0.20' -> '0.2') to match LEIDEN_RESOLUTIONS."""
    text = str(value).strip()
    if text in RESOLUTIONS:
        return text
    try:
        val_f = float(text)
        for canon in LEIDEN_RESOLUTIONS:
            if abs(val_f - float(canon)) < 1e-6:
                return canon
    except (ValueError, TypeError):
        pass
    return text


def require_text(value: str, rule_id: str) -> str:
    text = value.strip()
    if not text:
        raise GateRejected(rule_id, 400)
    return text


def require_date(value: str, rule_id: str) -> str:
    parts = value.split("-")
    if len(parts) != 3 or len(parts[0]) != 4 or not all(part.isdigit() for part in parts):
        raise GateRejected(rule_id, 400)
    return value


def require_hash(value: str, rule_id: str) -> str:
    folded = value.casefold()
    if len(folded) != 64 or any(character not in _HEX for character in folded):
        raise GateRejected(rule_id, 400)
    return folded


def require_blinding(value: str) -> str:
    if value not in BLINDING_VALUES:
        raise GateRejected("REVIEW_BLINDING_RECORDED", 400)
    return value


def exposure_blinding(requested: str, quicklook_seen: bool) -> tuple[str, str]:
    """A project that already saw quicklook target-gene output cannot stay blind."""
    chosen = require_blinding(requested)
    if quicklook_seen:
        return "UNBLINDED_WITH_REASON", "看过速览的目标基因结果"
    return chosen, ""


def require_resolution(value: str) -> str:
    canon = canonical_resolution(value)
    if canon not in RESOLUTIONS:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    return canon


_EXCLUDED_EVIDENCE = frozenset(
    {
        "part2",
        "part3",
        "part3_overview",
        "part3_clusters_by_resolution",
        "part4",
        "verdict",
        "lock",
        "active_resolution",
        "active_leiden_ids",
        "clusters",
        "active_grid_rel",
        "active_part1_round",
        "review_tables_run",
    }
)


def evidence_digest(evidence_json: str) -> str:
    try:
        data = json.loads(evidence_json)
        if isinstance(data, dict):
            clean = {k: v for k, v in data.items() if k not in _EXCLUDED_EVIDENCE}
            payload = json.dumps(clean, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except (json.JSONDecodeError, OSError):
        pass
    return hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()


def part3_evidence_digest(evidence_json: str) -> str:
    try:
        data = json.loads(evidence_json)
        if isinstance(data, dict):
            part3_data = {
                "overview": data.get("part3_overview"),
                "clusters": data.get("part3_clusters_by_resolution"),
            }
            payload = json.dumps(part3_data, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except (json.JSONDecodeError, OSError):
        pass
    return hashlib.sha256(b"").hexdigest()


def cluster_set_hash(leiden_ids: list[str]) -> str:
    payload = json.dumps(sorted(leiden_ids), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_cluster_rows(rows: list[dict[str, str]], leiden_ids: list[str]) -> list[dict[str, str]]:
    """Every current Leiden id needs one KEEP or DELETE. No blanks, no extras."""
    if not leiden_ids:
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
    seen: list[str] = []
    cleaned: list[dict[str, str]] = []
    for row in rows:
        cluster = require_text(row.get("cluster", ""), "REVIEW_CLUSTER_COMPLETE")
        decision = row.get("decision", "")
        if decision not in DECISIONS:
            raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
        rationale = require_text(row.get("rationale", ""), "REVIEW_CLUSTER_COMPLETE")
        reviewer = require_text(row.get("reviewer", ""), "REVIEW_CLUSTER_COMPLETE")
        decided_on = require_date(row.get("decided_on", ""), "REVIEW_CLUSTER_COMPLETE")
        name = row.get("name", "").strip()
        cleaned.append(
            {
                "cluster": cluster,
                "decision": decision,
                "rationale": rationale,
                "reviewer": reviewer,
                "decided_on": decided_on,
                "name": name,
            }
        )
        seen.append(cluster)
    if set(seen) != set(leiden_ids) or len(seen) != len(leiden_ids):
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
    named = any(row["name"] for row in cleaned)
    deleted = any(row["decision"] == "DELETE" for row in cleaned)
    if named and deleted:
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
    if named and any(not row["name"] for row in cleaned):
        raise GateRejected("REVIEW_CLUSTER_COMPLETE", 400)
    return cleaned


def filter_annotation_evidence(payload: dict[str, object], target_gene: str) -> dict[str, object]:
    """Drop the target gene and grouping labels before the response is built."""
    genes = payload.get("genes")
    kept: list[dict[str, object]] = []
    if isinstance(genes, list):
        for item in genes:
            if not isinstance(item, dict):
                continue
            name = item.get("gene")
            if not isinstance(name, str) or name.casefold() == target_gene.casefold():
                continue
            expression = item.get("expression")
            if not isinstance(expression, list):
                expression = []
            kept.append({"gene": name, "expression": expression})
    clusters = payload.get("clusters")
    cluster_ids: list[str] = []
    if isinstance(clusters, list):
        cluster_ids = [item for item in clusters if isinstance(item, str)]
    elif "clusters_by_resolution" in payload and isinstance(
        payload["clusters_by_resolution"], dict
    ):
        res_map = payload["clusters_by_resolution"]
        chosen = "0.2" if "0.2" in res_map else (next(iter(res_map)) if res_map else None)
        if chosen and isinstance(res_map.get(chosen), list):
            cluster_ids = [str(x) for x in res_map[chosen]]
    return {"genes": kept, "clusters": cluster_ids}


def get_latest_review(session: Session, run_id: int, kind: str) -> ReviewDecision | None:
    rows = session.scalars(
        select(ReviewDecision)
        .where(ReviewDecision.stage_run_id == run_id)
        .order_by(ReviewDecision.id.desc())
    )
    for row in rows:
        try:
            body = json.loads(row.body_json)
            if isinstance(body, dict) and body.get("kind") == kind:
                return row
        except (json.JSONDecodeError, OSError):
            continue
    return None


def is_blinding_active(session: Session, run: StageRun) -> bool:
    """True until a cluster review matching the current cluster set is recorded.

    ``BLIND`` records how the reviewer worked; it does not keep results hidden afterwards.
    """
    decision = get_latest_review(session, run.id, "clusters")
    if decision is None:
        return True
    leiden_ids: list[str] = []
    if run.leiden_ids_json:
        try:
            parsed = json.loads(run.leiden_ids_json)
            if isinstance(parsed, list):
                leiden_ids = [str(x) for x in parsed]
        except (json.JSONDecodeError, OSError):
            pass
    if leiden_ids and decision.evidence_hash != cluster_set_hash(leiden_ids):
        return True
    try:
        body = json.loads(decision.body_json)
    except (json.JSONDecodeError, OSError):
        return True
    return not (isinstance(body, dict) and body.get("blinding") in BLINDING_VALUES)


def get_target_gene(session: Session, run: StageRun) -> str:
    protocol = session.get(ProtocolVersion, run.protocol_id)
    if protocol and protocol.document_json:
        try:
            doc = json.loads(protocol.document_json)
            if isinstance(doc, dict) and doc.get("target_gene"):
                return str(doc["target_gene"])
        except (json.JSONDecodeError, OSError):
            pass
    return ""


def is_target_gene_artifact(rel_path: str, target_gene: str = "") -> bool:
    norm = rel_path.replace("\\", "/")
    parts = [p for p in norm.split("/") if p]
    filename = parts[-1].lower() if parts else norm.lower()
    if parts and parts[0] in TARGET_EXPOSING_TASKS:
        return True
    if target_gene and target_gene.strip():
        tg = target_gene.strip().lower()
        if tg in filename or any(tg == part.lower() for part in parts):
            return True
    return False
