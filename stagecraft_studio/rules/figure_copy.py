"""Chinese copy for figure-quality reason codes. This is the only mapping."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReasonCopy:
    text: str
    suggestion: str


_FIGURES: dict[str, ReasonCopy] = {
    "empty_violin": ReasonCopy(
        "该面板没有细胞数超过 100 的类别",
        "检查这个分组里是否还有细胞，或换一个有细胞的类别。",
    ),
    "single_category_violin": ReasonCopy(
        "小提琴图只有一个类别",
        "确认 case 和 control 都有细胞。",
    ),
    "all_constant_violin": ReasonCopy(
        "各类别的取值都是常数，画不出分布",
        "检查该基因是否几乎不表达。",
    ),
    "empty_feature_panel": ReasonCopy(
        "这张 feature 图没有细胞",
        "检查过滤是否把细胞去掉了。",
    ),
    "no_positive_target_expression": ReasonCopy(
        "目标基因没有阳性细胞",
        "确认基因名，以及分组里是否真有表达。",
    ),
    "empty_volcano": ReasonCopy(
        "火山图没有点",
        "检查差异分析是否写出了基因表。",
    ),
    "no_significant_genes": ReasonCopy(
        "差异分析没有显著基因",
        "检查 case 和 control 是否选对；也可以接受这个对比没有显著差异。",
    ),
    "low_information_figure_present": ReasonCopy(
        "数据集里有信息不足的图",
        "看下面列出的具体图。",
    ),
    "no_figure_directory": ReasonCopy(
        "没有图目录",
        "确认运行已经画完图。",
    ),
    "no_audited_figures": ReasonCopy(
        "没有可审计的图",
        "确认绘图阶段写了审计文件。",
    ),
}

_OUTCOMES: dict[str, str] = {
    "completed_analysis": "分析已完成",
    "completed_with_degradation": "分析完成，但有降级",
    "rejected_input": "输入被拒绝",
    "failed": "运行失败",
}


def figure_reason(code: str) -> ReasonCopy:
    """Return the Chinese sentence and one suggestion for a reason code."""
    found = _FIGURES.get(code)
    if found is None:
        return ReasonCopy(f"未收录的原因码 {code}", "打开日志查看这个原因码。")
    return found


def outcome_label(outcome: str) -> str:
    """Return the Chinese label for a pipeline outcome. Unknown codes stay visible."""
    if outcome in _OUTCOMES:
        return _OUTCOMES[outcome]
    if outcome.startswith("stopped_after_"):
        return f"停在 {outcome.removeprefix('stopped_after_')}"
    return outcome
