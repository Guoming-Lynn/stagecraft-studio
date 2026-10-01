"""Chinese labels the API sends to the page. Reason codes stay in figure_copy."""

from __future__ import annotations

ENGINE_STATUS = {
    "running": "运行中",
    "starting": "正在启动",
    "succeeded": "已完成",
    "failed": "未完成",
    "cancelled": "已取消",
    "interrupted": "已中断",
}
STEP_STATUS = {
    "not_started": "未开始",
    "running": "运行中",
    "done": "完成",
    "failed": "失败",
    "cancelled": "已取消",
    "interrupted": "中断",
    "needs_review": "需要人工确认",
}
ENRICHMENT = {
    "not_run_until_local_gmt": "未运行，等本地基因集",
    "local_gmt": "本地基因集",
}
PHASES = {
    "phase03": "聚类",
    "phase04_sensitivity": "差异与富集",
}
SOURCE_LABELS = {
    "user": "用户填写",
    "default": "默认",
    "inferred": "自动推断",
}
GROUP_NOTE = "没有分组时不出 case/control 对比图"
CLAIM_SCOPE = "细胞水平探索性分析，不做 donor 水平推断，p 值不代表样本间的可重复性"
LEDE = "产物标记为 quicklook。它不能当作正式分析的输入。" + CLAIM_SCOPE + "。"
FIGURE_PASS = "通过"
FIGURE_FAIL = "不通过"
FIGURE_DATASET_FAIL = "未通过"
MISSING = "未找到"
