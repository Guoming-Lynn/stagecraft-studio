"""Server-side review gates. Callers cannot supply a pass bit."""

from __future__ import annotations

import hashlib
import json

BLINDING_VALUES = frozenset({"BLIND", "UNBLINDED_WITH_REASON", "NOT_APPLICABLE"})
RESOLUTIONS = frozenset({"0.2", "0.3", "0.4", "0.5", "0.6", "0.8", "1.0", "1.2", "1.5"})
DECISIONS = frozenset({"KEEP", "DELETE"})
PRE_RESOLUTION = frozenset(
    {
        "formal_part1_load",
        "formal_part1_qc",
        "formal_part1_merge",
        "formal_part1_grid",
    }
)
_HEX = frozenset("0123456789abcdef")


class GateRejected(Exception):
    """A review rule refused the request."""

    def __init__(self, rule_id: str, status_code: int) -> None:
        self.rule_id = rule_id
        self.status_code = status_code
        super().__init__(rule_id)


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
    if value not in RESOLUTIONS:
        raise GateRejected("RESOLUTION_REVIEW_REQUIRED", 400)
    return value


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
        cleaned.append(
            {
                "cluster": cluster,
                "decision": decision,
                "rationale": rationale,
                "reviewer": reviewer,
                "decided_on": decided_on,
            }
        )
        seen.append(cluster)
    if set(seen) != set(leiden_ids) or len(seen) != len(leiden_ids):
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
    return {"genes": kept, "clusters": cluster_ids}
