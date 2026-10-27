"""Server-owned scientific status. Callers cannot raise the ceiling."""

from __future__ import annotations

CALIBRATION = "NOT_ESTABLISHED_FOR_THIS_ANALYSIS"
SOURCE_BLOCK_RECORDED = "source_block_recorded"
LIMITS = (
    "校准状态保持为 NOT_ESTABLISHED_FOR_THIS_ANALYSIS。",
    "留一数据集不是独立复制。",
    "Part 4 的旗不是拟合结果。",
    "NOT_ESTIMABLE 不表示效应不存在。",
)


def scientific_status(
    *,
    stage_status: str,
    invalidated: bool,
    evidence: dict[str, object],
) -> dict[str, object]:
    """Read a stored verdict. Ignore any attempt to mark the run calibrated or associated."""
    verdict = evidence.get("verdict")
    recorded = verdict if isinstance(verdict, dict) else {}
    closed = invalidated or stage_status == "INVALIDATED"
    holdout = recorded.get("holdout")
    source_holdout = holdout == SOURCE_BLOCK_RECORDED
    fitted = recorded.get("fitted") is True and not closed
    model = recorded.get("model")
    claims_limma = fitted and model == "limma_voom" and recorded.get("claims_limma") is True
    if closed:
        status = "INVALIDATED"
    else:
        stopped = recorded.get("stopped")
        status = stopped if isinstance(stopped, str) and stopped else "NOT_REPORTED"
    return {
        "scientific_status": status,
        "calibration_status": CALIBRATION,
        "associated": not closed and source_holdout and recorded.get("associated") is True,
        "claims_limma": claims_limma,
        "forecast_is_not_a_verdict": True,
        "lodo_is_replication": False,
        "holdout": SOURCE_BLOCK_RECORDED if source_holdout else "not_run",
        "read_only": closed,
        "limits": list(LIMITS),
    }
