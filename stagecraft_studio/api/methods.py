"""Deterministic Methods text. It is a template, not a model."""

from __future__ import annotations

from stagecraft_studio.api.copy import MISSING, PHASES


def methods_paragraph(
    *,
    gene: str,
    seed: str,
    engine_name: str,
    engine_version: str,
    engine_git: str,
    stopped_after: str,
    enrichment_label: str,
) -> str:
    """Return the same paragraph for the same inputs. Quicklook stays cell-level."""
    phase = PHASES.get(stopped_after, stopped_after or MISSING)
    gene_text = gene or MISSING
    seed_text = seed or MISSING
    return (
        "本段按固定模板写成，没有调用模型。"
        "这次速览是细胞水平、探索性、临时标签。"
        f"目标基因是 {gene_text}，随机种子是 {seed_text}。"
        f"引擎是 {engine_name} {engine_version}（{engine_git}）。"
        f"本次跑到{phase}。富集状态是{enrichment_label}。"
    )
