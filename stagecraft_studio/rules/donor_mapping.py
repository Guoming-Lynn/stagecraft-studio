"""Enforce explicit donor identity mapping before donor-level inference."""

from __future__ import annotations

from collections.abc import Mapping

from stagecraft_studio.rules.gates import GateRejected

ALLOWED_DONOR_SOURCES = frozenset({"obs_donor_id", "obs_donor", "donor_map"})
DONOR_INFERENCE_TASKS = frozenset({"formal_part5_prepare"})
INDEPENDENCE_NOTE = "程序仅核验供体标识对应关系存在，不能凭字符串证明身份独立"
_NULL_DONOR_TOKENS = frozenset({"", "nan", "none", "na", "null"})


def _is_missing_donor(value: object) -> bool:
    if value is None:
        return True
    return str(value).strip().casefold() in _NULL_DONOR_TOKENS


def evaluate_donor_audit(
    audit: object,
    *,
    library_id: str = "",
    failure_reason: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Evaluate a Part 1 load donor_audit.json payload or load failure reason."""
    if failure_reason:
        return "BLOCK", {"library_id": library_id, "reason": failure_reason}
    if not isinstance(audit, dict):
        return "BLOCK", {"library_id": library_id, "reason": "DONOR_AUDIT_UNREADABLE"}
    source = str(audit.get("donor_source", "")).strip()
    raw_count = audit.get("donor_count")
    if source not in ALLOWED_DONOR_SOURCES:
        return (
            "BLOCK",
            {
                "library_id": library_id,
                "donor_source": source,
                "reason": "DONOR_SOURCE_NOT_ALLOWED",
            },
        )
    if not isinstance(raw_count, int) or isinstance(raw_count, bool) or raw_count < 1:
        return (
            "BLOCK",
            {
                "library_id": library_id,
                "donor_source": source,
                "reason": "DONOR_COUNT_EMPTY",
            },
        )
    if source == "obs_donor":
        return (
            "WARN",
            {
                "library_id": library_id,
                "donor_source": source,
                "donor_count": raw_count,
                "note": f"donor 列提升为 donor_id；{INDEPENDENCE_NOTE}",
            },
        )
    return (
        "PASS",
        {
            "library_id": library_id,
            "donor_source": source,
            "donor_count": raw_count,
            "note": INDEPENDENCE_NOTE,
        },
    )


def evaluate_donor_metadata_rows(
    rows: list[dict[str, str]],
) -> tuple[str, dict[str, object]]:
    """Validate pseudobulk metadata rows for Part 5 donor-level inference."""
    if not rows:
        return "BLOCK", {"reason": "DONOR_METADATA_EMPTY"}
    units: set[str] = set()
    for row in rows:
        donor_id = row.get("donor_id", "")
        unit_id = row.get("dataset_donor_id", "")
        if _is_missing_donor(donor_id) or _is_missing_donor(unit_id):
            return "BLOCK", {"reason": "DONOR_METADATA_INCOMPLETE"}
        units.add(unit_id.strip())
    return (
        "PASS",
        {
            "n_units": len(rows),
            "n_donors": len(units),
            "note": INDEPENDENCE_NOTE,
        },
    )


def require_donor_mapping_for_inference(
    task_id: str,
    *,
    protocol_document: Mapping[str, object],
    recorded_statuses: Mapping[str, str],
    has_any_block: bool = False,
) -> None:
    """Refuse donor-level inference when donor mapping is missing or blocked."""
    if task_id not in DONOR_INFERENCE_TASKS:
        return
    if has_any_block or any(status == "BLOCK" for status in recorded_statuses.values()):
        raise GateRejected("DONOR_MAPPING_REQUIRED", 409)

    raw_rows = protocol_document.get("manifest") or protocol_document.get("libraries")
    lib_rows = (
        [item for item in raw_rows if isinstance(item, dict)] if isinstance(raw_rows, list) else []
    )
    if not lib_rows and not any(
        status in {"PASS", "WARN"} for status in recorded_statuses.values()
    ):
        raise GateRejected("DONOR_MAPPING_REQUIRED", 409)

    for item in lib_rows:
        lib_id = str(item.get("library_id", "")).strip()
        explicit_donor = item.get("donor_id")
        has_explicit = not _is_missing_donor(explicit_donor)
        recorded = recorded_statuses.get(lib_id)
        if not has_explicit and recorded not in {"PASS", "WARN"}:
            raise GateRejected("DONOR_MAPPING_REQUIRED", 409)
