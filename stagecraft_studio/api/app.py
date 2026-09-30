"""Local quicklook form. It binds to 127.0.0.1 and stops before Enrichr."""

from __future__ import annotations

import os
import secrets
import tempfile
from html import escape
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError

from stagecraft_studio.api.run_page import render_run_page
from stagecraft_studio.api.templates import ERROR_PAGE, FORM_PAGE, INSPECT_PAGE
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
)
from stagecraft_studio.worker.runs import RunBusy, RunStore


def create_app(
    token: str,
    *,
    port: int,
    launch: EngineLaunch,
    state_path: Path | None = None,
) -> FastAPI:
    app = FastAPI()
    allowed_origin = f"http://127.0.0.1:{port}"
    if state_path is None:
        state_path = Path(tempfile.mkdtemp(prefix="stagecraft-runs-")) / "runs.json"
    store = RunStore(state_path)
    store.recover()

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
    ) -> Response:
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
            run_id = store.start(parsed, launch)
        except RunBusy as exc:
            return _error(str(exc), 409)
        except (FileNotFoundError, UnsupportedInput, OutputRejected, OSError) as exc:
            return _error(str(exc), 400)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_page(run_id: str) -> HTMLResponse:
        if not _run_id_ok(run_id):
            return _error("没有这次运行。", 404)
        record = store.get(run_id)
        if record is None:
            return _error("没有这次运行。", 404)
        page = render_run_page(token, record)
        return HTMLResponse(page)

    @app.post("/runs/{run_id}/cancel", response_class=HTMLResponse)
    def cancel(
        request: Request,
        run_id: str,
        token_field: str = Form(alias="token"),
        python_path: str | None = Form(default=None),
        script: str | None = Form(default=None),
    ) -> Response:
        _guard(request, token, allowed_origin, token_field, python_path, script)
        if _run_id_ok(run_id):
            store.cancel(run_id)
        return RedirectResponse(f"/runs/{run_id}", status_code=303)

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


def _run_id_ok(value: str) -> bool:
    return len(value) == 16 and all(character in "0123456789abcdef" for character in value)


def serve(
    port: int = 8765,
    *,
    python: Path | None = None,
    script: Path | None = None,
) -> None:
    """Serve the form on the loopback interface only."""
    import uvicorn

    launch = resolve_engine_launch(python, script)
    state = Path(tempfile.gettempdir()) / "stagecraft-studio" / "quicklook_runs.json"
    uvicorn.run(
        create_app(secrets.token_hex(16), port=port, launch=launch, state_path=state),
        host="127.0.0.1",
        port=port,
    )
