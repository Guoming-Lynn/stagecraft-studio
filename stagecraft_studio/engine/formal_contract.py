"""Output contracts for formal engine tasks.

Every task has a fixed list of output files.
If a task finishes with exit code 0 but any of these files are missing,
the job is marked FAILED with reason OUTPUT_CONTRACT_MISSING and output
is not renamed to the final destination.
"""

from __future__ import annotations

FORMAL_OUTPUT_CONTRACTS: dict[str, tuple[str, ...]] = {
    "formal_part1_load": ("loaded.h5ad", "symbol_audit.csv"),
    "formal_part1_qc": ("qc_record.json",),
    "formal_part1_merge": (
        "all_context_union.h5ad",
        "primary_union.h5ad",
        "primary_common.h5ad",
        "gene_presence_by_dataset.csv",
    ),
    "formal_part1_grid": (
        "Leiden_resolution_overview.csv",
        "cluster_by_dataset.csv",
        "pca_audit.csv",
        "grid_record.json",
        "leiden_resolution_overview.png",
    ),
    "formal_part3_recluster": ("grid_record.json",),
    "formal_part2_survey": (
        "group_summary.csv",
        "unit_by_group.csv",
        "lodo_detection.csv",
        "survey_record.json",
    ),
    "formal_part2_figures": ("part2_figure_record.json",),
    "formal_part4_survey": ("part4_survey_record.json",),
    "formal_part4_figures": ("part4_figure_record.json",),
    "formal_part5_prepare": (
        "metadata.csv",
        "genes.csv",
        "outcome_counts.mtx",
        "source_block_suggestions.csv",
        "eligibility.csv",
        "verdict.json",
    ),
    "formal_stage_report": ("REPORT.md",),
}
