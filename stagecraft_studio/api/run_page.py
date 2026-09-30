"""Run page text. Markup stays in templates.py; this module only fills it."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from stagecraft_studio.api.templates import RESULT_PAGE
from stagecraft_studio.rules.figure_copy import figure_reason, outcome_label
from stagecraft_studio.worker.runs import RunRecord

_ENGINE = {
    "running": "运行中",
    "starting": "正在启动",
    "succeeded": "已完成",
    "failed": "未完成",
    "cancelled": "已取消",
    "interrupted": "已中断",
}
_PHASES = {
    "phase03": "聚类",
    "phase04_sensitivity": "差异与富集",
}
_ENRICHMENT = {
    "not_run_until_local_gmt": "未运行，等本地基因集",
    "local_gmt": "本地基因集",
}


def render_run_page(token: str, record: RunRecord) -> str:
    """Fill the existing result page. Running pages refresh and can be cancelled."""
    phase = _PHASES.get(record.stopped_after, record.stopped_after or "这一阶段")
    if record.status == "running":
        heading = f"速览正在跑到{phase}"
    elif record.status == "succeeded":
        heading = f"速览已跑到{phase}"
    elif record.status == "cancelled":
        heading = f"速览已取消，当时计划跑到{phase}"
    else:
        heading = f"速览没有跑完，当时计划跑到{phase}"
    page = (
        RESULT_PAGE.replace("__TITLE__", "Stagecraft 速览")
        .replace("__HEADING__", escape(heading))
        .replace("__LEDE__", "产物标记为 quicklook。它不能当作正式分析的输入。")
        .replace("__STATUS_CLASS__", "")
        .replace("__STATUS__", "探索性结果")
        .replace("__RETURNCODE__", _returncode(record))
        .replace("__BODY__", _body(token, record))
    )
    if record.status == "running":
        page = page.replace("<head>", '<head>\n<meta http-equiv="refresh" content="3">', 1)
    return page


def _body(token: str, record: RunRecord) -> str:
    status = _read(record.output_root / "run_status.json")
    pipeline = _read(record.output_root / "99_logs" / "pipeline_status.json")
    quality = _read(record.output_root / "99_logs" / "figure_quality_dataset_report.json")
    engine = _ENGINE.get(record.status, record.status)
    enrichment = _text(status, "enrichment")
    enrichment_label = _ENRICHMENT.get(enrichment, enrichment or "未找到")
    parts = [
        "<h2>引擎是否跑完</h2>",
        _pairs(
            [
                ("状态", engine),
                ("退出码", _returncode(record) or "未结束"),
                ("富集", enrichment_label),
                ("停止于", _text(status, "stopped_after") or "未找到"),
            ]
        ),
        "<h2>输入是否被拒</h2>",
        _pairs([("结论", _outcome(pipeline))]),
        "<h2>图质量</h2>",
        _quality(quality),
        "<h2>日志</h2>",
        _logs(record.output_root),
    ]
    if record.status == "running":
        parts.append(
            '<form method="post" action="/runs/__RUN__/cancel" class="actions">'
            '<input type="hidden" name="token" value="__TOKEN__">'
            '<button type="submit">取消</button>'
            "<p>取消会停掉整个进程。</p>"
            "</form>"
        )
    html = "".join(parts)
    return html.replace("__RUN__", escape(record.run_id, quote=True)).replace(
        "__TOKEN__", escape(token, quote=True)
    )


def _outcome(pipeline: dict[str, object] | None) -> str:
    if pipeline is None:
        return "未找到"
    outcome = pipeline.get("outcome")
    if not isinstance(outcome, str) or not outcome:
        return "未找到"
    return outcome_label(outcome)


def _quality(report: dict[str, object] | None) -> str:
    if report is None:
        return _pairs([("图质量", "未找到")])
    status = report.get("status")
    if status == "pass":
        return _pairs([("图质量", "通过")])
    if status != "reject":
        shown = status if isinstance(status, str) and status else "未找到"
        return _pairs([("图质量", str(shown))])
    rows = ["<p>未通过</p>"]
    bad = report.get("bad_figures")
    if isinstance(bad, list):
        for item in bad:
            if not isinstance(item, dict):
                continue
            figure = item.get("figure")
            name = figure if isinstance(figure, str) and figure else "未命名的图"
            reasons = item.get("reasons")
            codes = [str(code) for code in reasons] if isinstance(reasons, list) else []
            sentences = [_sentence(code) for code in codes]
            detail = " ".join(sentences) if sentences else "没有具体原因码。"
            rows.append(f"<p>{escape(name)}：{escape(detail)}</p>")
    return "".join(rows)


def _sentence(code: str) -> str:
    copy = figure_reason(code)
    return f"{copy.text}。建议：{copy.suggestion}"


def _pairs(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<div class="pair"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in rows
    )
    return f"<dl>{body}</dl>"


def _logs(output: Path) -> str:
    folder = output / "99_logs"
    if not folder.is_dir():
        return '<p class="hint">这次还没有日志。</p>'
    base = output.resolve()
    chunks: list[str] = []
    for path in sorted(folder.glob("*.log"))[:8]:
        resolved = path.resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            continue
        tail = "\n".join(
            path.read_bytes()[-65536:].decode("utf-8", errors="replace").splitlines()[-30:]
        )
        chunks.append(f'<p class="log-name">{escape(path.name)}</p><pre>{escape(tail)}</pre>')
    if not chunks:
        return '<p class="hint">这次还没有日志。</p>'
    return "".join(chunks)


def _returncode(record: RunRecord) -> str:
    payload = _read(record.output_root / "run_status.json")
    if payload is None:
        return ""
    value = payload.get("returncode")
    if isinstance(value, int):
        return str(value)
    return ""


def _read(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key): value for key, value in payload.items()}


def _text(payload: dict[str, object] | None, key: str) -> str:
    if payload is None:
        return ""
    value = payload.get(key)
    if isinstance(value, str):
        return value
    return ""
