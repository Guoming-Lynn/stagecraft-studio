"""Local quicklook form. It binds to 127.0.0.1 and stops before Enrichr."""

from __future__ import annotations

import json
import os
import secrets
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from stagecraft_studio.api.templates import ERROR_PAGE, FORM_PAGE, INSPECT_PAGE, RESULT_PAGE
from stagecraft_studio.engine.input_format import UnsupportedInput
from stagecraft_studio.engine.inspect import (
    InspectColumn,
    InspectFailed,
    InspectRequest,
    InspectResult,
    run_inspect,
)
from stagecraft_studio.engine.launch import EngineLaunch, resolve_engine_launch
from stagecraft_studio.engine.quicklook import (
    OutputRejected,
    QuicklookRequest,
    require_empty_output,
    run_quicklook,
)


def create_app(token: str, *, port: int, launch: EngineLaunch) -> FastAPI:
    app = FastAPI()
    allowed_origin = f"http://127.0.0.1:{port}"

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        gmt_path = escape(os.environ.get("STAGECRAFT_QUICKLOOK_GMT", ""), quote=True)
        return (
            FORM_PAGE.replace("__TITLE__", "Stagecraft 速览")
            .replace("__TOKEN__", token)
            .replace("__PYTHON__", escape(str(launch.python)))
            .replace("__SCRIPT__", escape(str(launch.script)))
            .replace("__GMT__", gmt_path)
        )

    @app.exception_handler(HTTPException)
    def http_error(_request: Request, exc: HTTPException) -> HTMLResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "请求被拒绝"
        page = ERROR_PAGE.replace("__TITLE__", "Stagecraft 速览").replace(
            "__MESSAGE__", escape(detail)
        )
        return HTMLResponse(page, status_code=exc.status_code)

    @app.post("/quicklook/inspect", response_class=HTMLResponse)
    def inspect(
        request: Request,
        input_path: str = Form(),
        gene: str = Form(),
        out: str = Form(),
        token_field: str = Form(alias="token"),
        local_gmt: str = Form(default=""),
        python_path: str | None = Form(default=None),
        script: str | None = Form(default=None),
    ) -> HTMLResponse:
        _guard(request, token, allowed_origin, token_field, python_path, script)
        parsed = _parse_request(input_path, gene, out, local_gmt)
        if isinstance(parsed, HTMLResponse):
            return parsed
        try:
            require_empty_output(parsed.output_root)
            found = run_inspect(
                InspectRequest(input_path=parsed.input_path),
                python=launch.python,
                script=launch.inspect_script(),
            )
        except (FileNotFoundError, OutputRejected, InspectFailed) as exc:
            return _error(str(exc), 400)
        return HTMLResponse(_inspect_page(token, parsed, local_gmt, found))

    @app.post("/quicklook", response_class=HTMLResponse)
    def quicklook(
        request: Request,
        input_path: str = Form(),
        gene: str = Form(),
        out: str = Form(),
        token_field: str = Form(alias="token"),
        group: str = Form(default=""),
        case_label: str = Form(default=""),
        control_label: str = Form(default=""),
        batch_column: str = Form(default=""),
        local_gmt: str = Form(default=""),
        python_path: str | None = Form(default=None),
        script: str | None = Form(default=None),
    ) -> HTMLResponse:
        _guard(request, token, allowed_origin, token_field, python_path, script)
        parsed = _parse_request(
            input_path,
            gene,
            out,
            local_gmt,
            group=group,
            case_label=case_label,
            control_label=control_label,
            batch_column=batch_column,
        )
        if isinstance(parsed, HTMLResponse):
            return parsed
        try:
            result = run_quicklook(parsed, python=launch.python, script=launch.script)
        except (FileNotFoundError, UnsupportedInput, OutputRejected) as exc:
            return _error(str(exc), 400)
        page = _result_page(result.returncode, parsed.output_root)
        return HTMLResponse(page)

    return app


def _guard(
    request: Request,
    token: str,
    allowed_origin: str,
    token_field: str,
    python_path: str | None,
    script: str | None,
) -> None:
    if token_field != token:
        raise HTTPException(status_code=401, detail="缺少会话令牌")
    if request.headers.get("origin") != allowed_origin:
        raise HTTPException(status_code=403, detail="来源不被接受")
    if python_path is not None or script is not None:
        raise HTTPException(status_code=422, detail="解释器和脚本由服务端决定，不能在请求里指定")


def _parse_request(
    input_path: str,
    gene: str,
    out: str,
    local_gmt: str,
    *,
    group: str = "",
    case_label: str = "",
    control_label: str = "",
    batch_column: str = "",
) -> QuicklookRequest | HTMLResponse:
    try:
        return QuicklookRequest(
            input_path=Path(input_path),
            target_gene=gene,
            output_root=Path(out),
            group_column=group or None,
            case_label=case_label or None,
            control_label=control_label or None,
            batch_column=batch_column or None,
            local_gmt=Path(local_gmt) if local_gmt else None,
        )
    except ValidationError:
        return _error("目标基因需要是一个符号，路径也要完整。", 400)


def _inspect_page(
    token: str,
    parsed: QuicklookRequest,
    local_gmt: str,
    found: InspectResult,
) -> str:
    columns = [column.name for column in found.columns]
    return (
        INSPECT_PAGE.replace("__TITLE__", "Stagecraft 速览")
        .replace("__TOKEN__", escape(token, quote=True))
        .replace("__INPUT_TEXT__", escape(str(parsed.input_path)))
        .replace("__INPUT__", escape(str(parsed.input_path), quote=True))
        .replace("__GENE_TEXT__", escape(parsed.target_gene))
        .replace("__GENE__", escape(parsed.target_gene, quote=True))
        .replace("__OUT_TEXT__", escape(str(parsed.output_root)))
        .replace("__OUT__", escape(str(parsed.output_root), quote=True))
        .replace("__GMT_TEXT__", escape(local_gmt or "未提供"))
        .replace("__GMT__", escape(local_gmt, quote=True))
        .replace("__GROUP_OPTIONS__", _options(columns, "不分组"))
        .replace("__BATCH_OPTIONS__", _options(columns, "不指定批次"))
        .replace("__CASE_OPTIONS__", _value_options(found.columns, "不指定"))
        .replace("__CONTROL_OPTIONS__", _value_options(found.columns, "不指定"))
        .replace("__NOTE__", escape(found.note))
    )


def _options(values: list[str], blank: str) -> str:
    rows = [f'<option value="">{escape(blank)}</option>']
    for value in values:
        rows.append(f'<option value="{escape(value, quote=True)}">{escape(value)}</option>')
    return "".join(rows)


def _value_options(columns: list[InspectColumn], blank: str) -> str:
    rows = [f'<option value="">{escape(blank)}</option>']
    seen: set[tuple[str, str]] = set()
    for column in columns:
        for value in column.values:
            key = (column.name, value)
            if key in seen:
                continue
            seen.add(key)
            label = escape(f"{column.name} · {value}")
            rows.append(f'<option value="{escape(value, quote=True)}">{label}</option>')
    return "".join(rows)


def _error(message: str, status_code: int) -> HTMLResponse:
    page = ERROR_PAGE.replace("__TITLE__", "Stagecraft 速览").replace(
        "__MESSAGE__", escape(message)
    )
    return HTMLResponse(page, status_code=status_code)


def _result_page(returncode: int, output_root: Path) -> str:
    ok = returncode == 0
    if ok:
        heading = "速览已跑完聚类"
        lede = "产物标记为 quicklook。它不能当作正式分析的输入。"
        status_class = "ok"
        status = "探索性结果"
    else:
        heading = "速览没有完成"
        lede = "目录已标记为 quicklook，不能当作正式分析的输入。"
        status_class = "bad"
        status = "未完成"
    return (
        RESULT_PAGE.replace("__TITLE__", "Stagecraft 速览")
        .replace("__HEADING__", escape(heading))
        .replace("__LEDE__", escape(lede))
        .replace("__STATUS_CLASS__", status_class)
        .replace("__STATUS__", status)
        .replace("__RETURNCODE__", str(returncode))
        .replace("__BODY__", _result_body(output_root))
    )


def _result_body(output_root: Path) -> str:
    status = _read_object(output_root / "run_status.json")
    tier = _read_object(output_root / "analysis_tier.json")
    blocks = [
        "<h2>运行状态</h2>",
        _pairs(
            [
                ("任务", _field(status, "task_id")),
                ("状态", _status_label(status)),
                ("退出码", _field(status, "returncode")),
                ("富集", _enrichment(status)),
                ("停止于", _field(status, "stopped_after")),
            ]
        ),
        "<h2>速览标记</h2>",
        _pairs(
            [
                ("analysis_tier", _field(tier, "analysis_tier")),
                ("标签", _provisional(tier)),
                ("donor 推断", _donor(tier)),
            ]
        ),
        "<h2>日志</h2>",
        _logs(output_root),
    ]
    return "".join(blocks)


def _pairs(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<div class="pair"><dt>{escape(label)}</dt><dd>{escape(value)}</dd></div>'
        for label, value in rows
    )
    return f"<dl>{body}</dl>"


def _logs(output_root: Path) -> str:
    tails = _log_tails(output_root)
    if not tails:
        return '<p class="hint">这次没有日志。</p>'
    chunks: list[str] = []
    for name, text in tails:
        chunks.append(f'<p class="log-name">{escape(name)}</p><pre>{escape(text)}</pre>')
    return "".join(chunks)


def _log_tails(output_root: Path, limit: int = 30) -> list[tuple[str, str]]:
    folder = output_root / "99_logs"
    if not folder.is_dir() or not _inside(output_root, folder):
        return []
    found: list[tuple[str, str]] = []
    for path in sorted(folder.glob("*.log")):
        if len(found) == 8 or not path.is_file() or not _inside(output_root, path):
            continue
        found.append((path.name, _tail_text(path, limit)))
    return found


def _tail_text(path: Path, limit: int) -> str:
    data = path.read_bytes()[-65536:]
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-limit:])


def _inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _read_object(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return {str(key): value for key, value in payload.items()}


def _field(payload: dict[str, object] | None, key: str) -> str:
    if payload is None or key not in payload:
        return "未找到"
    return str(payload[key])


def _status_label(payload: dict[str, object] | None) -> str:
    labels = {"succeeded": "已完成", "failed": "未完成"}
    return labels.get(_field(payload, "status"), _field(payload, "status"))


def _provisional(payload: dict[str, object] | None) -> str:
    if payload is None:
        return "未找到"
    if payload.get("labels_provisional") is True:
        return "临时，不能导入正式审阅"
    return "未找到"


def _donor(payload: dict[str, object] | None) -> str:
    if payload is None:
        return "未找到"
    if payload.get("donor_level_inference") is False:
        return "不做"
    return "未找到"


def _enrichment(payload: dict[str, object] | None) -> str:
    if payload is None:
        return "未找到"
    labels = {
        "not_run_until_local_gmt": "未运行，等本地基因集",
        "local_gmt": "本地基因集",
    }
    value = payload.get("enrichment")
    if isinstance(value, str) and value in labels:
        return labels[value]
    return _field(payload, "enrichment")


def serve(
    port: int = 8765,
    *,
    python: Path | None = None,
    script: Path | None = None,
) -> None:
    """Serve the form on the loopback interface only."""
    import uvicorn

    launch = resolve_engine_launch(python, script)
    uvicorn.run(
        create_app(secrets.token_hex(16), port=port, launch=launch),
        host="127.0.0.1",
        port=port,
    )
