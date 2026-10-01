"""HTTP routes for the local studio. Rules stay in the engine and worker modules."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import ValidationError

from stagecraft_studio.api.bundle import build_bundle
from stagecraft_studio.api.compare import compare_runs
from stagecraft_studio.api.copy import GROUP_NOTE
from stagecraft_studio.api.demo import DEMO_SOURCE, DemoFailed, start_demo
from stagecraft_studio.api.environment import collect_environment
from stagecraft_studio.api.files import (
    PathRejected,
    list_tree,
    media_file,
    preview_table,
    preview_text,
    reveal,
)
from stagecraft_studio.api.models import (
    Bootstrap,
    ColumnView,
    CompareView,
    DemoStarted,
    EnvironmentReport,
    FilePreview,
    InspectView,
    QuicklookForm,
    RevealResult,
    RunListItem,
    RunView,
    SourceView,
    Started,
    StepView,
    TablePage,
    TreeEntry,
)
from stagecraft_studio.api.steps import EngineIdentity, read_source
from stagecraft_studio.api.view import run_item, run_view, step_views
from stagecraft_studio.engine.input_format import UnsupportedInput
from stagecraft_studio.engine.inspect import InspectFailed, InspectRequest, run_inspect
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.engine.quicklook import (
    OutputRejected,
    QuicklookRequest,
    require_empty_output,
)
from stagecraft_studio.worker.runs import RunBusy, RunRecord, RunStore

T = TypeVar("T")


def build_router(
    *,
    token: str,
    origin: str,
    launch: EngineLaunch,
    store: RunStore,
    identity: EngineIdentity,
) -> APIRouter:
    """Mount /api on the studio process. Mutations require the session token and Origin."""
    router = APIRouter()

    @router.get("/api/bootstrap")
    def bootstrap() -> Bootstrap:
        return Bootstrap(
            token=token,
            python=str(launch.python),
            script=str(launch.script),
            gmt=_gmt(),
            group_note=GROUP_NOTE,
            engine_name=identity.name,
            engine_version=identity.version,
            engine_git=identity.git,
            environment_ok=launch.python.is_file() and launch.script.is_file(),
            demo_source=DEMO_SOURCE,
        )

    @router.get("/api/environment")
    def environment() -> EnvironmentReport:
        return collect_environment(launch, identity)

    @router.get("/api/compare")
    def compare(left: str = Query(), right: str = Query()) -> CompareView:
        return compare_runs(_record(store, left), _record(store, right), identity)

    @router.get("/api/runs")
    def runs() -> list[RunListItem]:
        return [run_item(record) for record in store.records()]

    @router.get("/api/runs/{run_id}")
    def run(run_id: str) -> RunView:
        return run_view(_record(store, run_id), identity)

    @router.get("/api/runs/{run_id}/bundle")
    def bundle(run_id: str) -> Response:
        record = _record(store, run_id)
        payload = build_bundle(
            record.output_root,
            run_view(record, identity).command_line,
            identity,
        )
        filename = f"{run_id}-reproduce.zip"
        return Response(
            content=payload,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get("/api/runs/{run_id}/steps")
    def steps(run_id: str) -> list[StepView]:
        return step_views(_record(store, run_id))

    @router.get("/api/runs/{run_id}/events")
    def events(run_id: str) -> StreamingResponse:
        payload = run_view(_record(store, run_id), identity).model_dump_json()

        def stream() -> Iterator[str]:
            yield f"data: {payload}\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @router.get("/api/runs/{run_id}/tree")
    def tree(run_id: str) -> list[TreeEntry]:
        return list_tree(_record(store, run_id).output_root)

    @router.get("/api/runs/{run_id}/file")
    def file(run_id: str, rel: str = Query()) -> FilePreview:
        return _files(lambda: preview_text(_record(store, run_id).output_root, rel))

    @router.get("/api/runs/{run_id}/media")
    def media(run_id: str, rel: str = Query()) -> FileResponse:
        path = _files(lambda: media_file(_record(store, run_id).output_root, rel))
        media_type = "image/svg+xml" if path.suffix.casefold() == ".svg" else "image/png"
        return FileResponse(path, media_type=media_type)

    @router.get("/api/runs/{run_id}/table")
    def table(
        run_id: str,
        rel: str = Query(),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
        q: str = Query(default=""),
        sort: str = Query(default=""),
        desc: bool = Query(default=False),
    ) -> TablePage:
        root = _record(store, run_id).output_root
        return _files(
            lambda: preview_table(
                root,
                rel,
                offset,
                limit,
                query=q,
                sort=sort,
                descending=desc,
            )
        )

    @router.get("/api/steps/{step_id}/source")
    def source(step_id: str) -> SourceView:
        return _files(lambda: read_source(identity, step_id))

    @router.post("/api/demo", status_code=201)
    def demo(request: Request) -> DemoStarted:
        _mutation(request, token, origin)
        try:
            run_id, source = start_demo(store, launch)
        except RunBusy as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except DemoFailed as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except (FileNotFoundError, UnsupportedInput, OutputRejected, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return DemoStarted(run_id=run_id, source=source)

    @router.post("/api/runs", status_code=201)
    def start(request: Request, form: QuicklookForm) -> Started:
        _mutation(request, token, origin)
        try:
            run_id = store.start(_request(form), launch)
        except RunBusy as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (FileNotFoundError, UnsupportedInput, OutputRejected, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Started(run_id=run_id)

    @router.post("/api/inspect")
    def inspect(request: Request, form: QuicklookForm) -> InspectView:
        _mutation(request, token, origin)
        parsed = _request(form)
        try:
            require_empty_output(parsed.output_root)
            found = run_inspect(
                InspectRequest(input_path=parsed.input_path),
                python=launch.python,
                script=launch.inspect_script(),
            )
        except (FileNotFoundError, OutputRejected, InspectFailed) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return InspectView(
            columns=[
                ColumnView(name=column.name, values=column.values) for column in found.columns
            ],
            note=found.note,
            group_note=GROUP_NOTE,
            input_path=str(parsed.input_path),
            gene=parsed.target_gene,
            out=str(parsed.output_root),
            local_gmt=form.local_gmt,
        )

    @router.post("/api/runs/{run_id}/cancel")
    def cancel(request: Request, run_id: str) -> RunView:
        _mutation(request, token, origin)
        if _run_id_ok(run_id):
            store.cancel(run_id)
        return run_view(_record(store, run_id), identity)

    @router.post("/api/runs/{run_id}/reveal")
    def open_folder(request: Request, run_id: str) -> RevealResult:
        _mutation(request, token, origin)
        root = _record(store, run_id).output_root
        if not root.is_dir():
            raise HTTPException(status_code=404, detail="没有这次运行的目录")
        reveal(root)
        return RevealResult(status="ok")

    return router


def _mutation(request: Request, token: str, origin: str) -> None:
    if request.headers.get("x-stagecraft-token") != token:
        raise HTTPException(status_code=401, detail="缺少会话令牌")
    if request.headers.get("origin") != origin:
        raise HTTPException(status_code=403, detail="来源不被接受")


def _request(form: QuicklookForm) -> QuicklookRequest:
    try:
        return QuicklookRequest(
            input_path=Path(form.input_path),
            target_gene=form.gene,
            output_root=Path(form.out),
            group_column=form.group or None,
            case_label=form.case_label or None,
            control_label=form.control_label or None,
            batch_column=form.batch_column or None,
            local_gmt=Path(form.local_gmt) if form.local_gmt else None,
            organism=form.organism,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail="目标基因需要是一个符号，路径也要完整。"
        ) from exc


def _record(store: RunStore, run_id: str) -> RunRecord:
    if not _run_id_ok(run_id):
        raise HTTPException(status_code=404, detail="没有这次运行。")
    record = store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="没有这次运行。")
    return record


def _files(load: Callable[[], T]) -> T:
    try:
        return load()
    except PathRejected as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail) from exc


def _run_id_ok(value: str) -> bool:
    return len(value) == 16 and all(character in "0123456789abcdef" for character in value)


def _gmt() -> str:
    return os.environ.get("STAGECRAFT_QUICKLOOK_GMT", "")
