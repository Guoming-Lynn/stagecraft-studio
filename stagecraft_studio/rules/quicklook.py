"""Reject quicklook artifacts as formal inputs and enforce quicklook claim scope."""

from __future__ import annotations

import json
import re
from pathlib import Path

QUICKLOOK_TIER = "quicklook"
TIER_FILENAME = "analysis_tier.json"
QUICKLOOK_CLAIM_TEXT = "细胞水平探索性分析，不做 donor 水平推断，p 值不代表样本间的可重复性"

_CLAUSE_SPLIT = re.compile(r"[.。!！?？;；\n,，]")
_CLAIM_NEGATION = re.compile(
    r"\b(?:not|no|never|cannot|can't|without)\b|不|未|没有|不能|不得|非",
    re.IGNORECASE,
)
_FORBIDDEN_QUICKLOOK_CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "independent_replication",
        re.compile(
            r"\bindependent(?:ly)?\s+(?:replicat|validat|confirm)\w*|(?:独立|外部)(?:复制|验证)",
            re.IGNORECASE,
        ),
    ),
    (
        "donor_level_inference",
        re.compile(
            r"\bdonor[- ]level\s+(?:inference|association|test|p[- ]?value)\b"
            r"|(?:供体|donor)\s*水平(?:正式)?推断"
            r"|代表样本间(?:的)?可重复性",
            re.IGNORECASE,
        ),
    ),
    (
        "calibrated_verdict",
        re.compile(
            r"\bcalibrated\s+(?:model|p[- ]?value|verdict|effect)\b|(?:已完成|已建立)校准",
            re.IGNORECASE,
        ),
    ),
    (
        "causal_mechanism",
        re.compile(
            r"\bcausal(?:ly)?\s+(?:drives?|effects?|regulat\w*)\b|因果(?:效应|推断|驱动)",
            re.IGNORECASE,
        ),
    ),
)


class QuicklookClaimRejected(ValueError):
    """Quicklook text omitted the required scope notice or exceeded cell-level claims."""

    def __init__(self, reason: str) -> None:
        self.rule_id = "QUICKLOOK_CLAIM_SCOPE"
        self.reason = reason
        super().__init__(f"{self.rule_id}: {reason}")


def require_quicklook_claim_scope(text: str) -> str:
    """Ensure quicklook copy states cell-level scope verbatim and makes no overclaims."""
    if not text.strip() or QUICKLOOK_CLAIM_TEXT not in text:
        raise QuicklookClaimRejected("MISSING_CLAIM_SCOPE")
    for line in text.splitlines():
        for code, pattern in _FORBIDDEN_QUICKLOOK_CLAIMS:
            for match in pattern.finditer(line):
                clause_prefix = _CLAUSE_SPLIT.split(line[: match.start()])[-1][-24:]
                if _CLAIM_NEGATION.search(clause_prefix):
                    continue
                raise QuicklookClaimRejected(f"OVERCLAIM:{code}")
    return text


class FormalInputRejected(Exception):
    """A formal task tried to read a quicklook product."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def quicklook_not_formal(path: Path) -> None:
    """Raise when `path` is inside a directory marked analysis_tier quicklook."""
    start = path.resolve()
    cursor = start if start.is_dir() else start.parent
    while True:
        tier_path = cursor / TIER_FILENAME
        if tier_path.is_file():
            payload = _read_tier(tier_path)
            if payload.get("analysis_tier") == QUICKLOOK_TIER:
                raise FormalInputRejected(path, "QUICKLOOK_NOT_FORMAL")
        parent = cursor.parent
        if parent == cursor:
            return
        cursor = parent


def _read_tier(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FormalInputRejected(path, "QUICKLOOK_TIER_UNREADABLE") from exc
    if not isinstance(payload, dict):
        raise FormalInputRejected(path, "QUICKLOOK_TIER_UNREADABLE")
    return payload


def saw_quicklook(path: Path) -> bool:
    cursor = path.resolve()
    if cursor.is_file():
        cursor = cursor.parent
    while True:
        tier = cursor / TIER_FILENAME
        if tier.is_file():
            try:
                payload = json.loads(tier.read_text(encoding="utf-8"))
                return isinstance(payload, dict) and payload.get("analysis_tier") == QUICKLOOK_TIER
            except Exception:
                return False
        if cursor.parent == cursor:
            return False
        cursor = cursor.parent
