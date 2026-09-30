"""Local studio process. It binds to 127.0.0.1 and does not run analysis inline."""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from stagecraft_studio.api.routes import build_router
from stagecraft_studio.api.steps import engine_identity
from stagecraft_studio.engine.launch import EngineLaunch, resolve_engine_launch
from stagecraft_studio.worker.runs import RunStore


def create_app(
    token: str,
    *,
    port: int,
    launch: EngineLaunch,
    state_path: Path | None = None,
    include_ui: bool = True,
) -> FastAPI:
    app = FastAPI(title="Stagecraft Studio", version="0.0.0")
    allowed_origin = f"http://127.0.0.1:{port}"
    if state_path is None:
        state_path = Path(tempfile.mkdtemp(prefix="stagecraft-runs-")) / "runs.json"
    store = RunStore(state_path)
    store.recover()
    identity = engine_identity(launch.script)
    app.include_router(
        build_router(
            token=token,
            origin=allowed_origin,
            launch=launch,
            store=store,
            identity=identity,
        )
    )
    if include_ui:
        _mount_ui(app)
    return app


def _mount_ui(app: FastAPI) -> None:
    dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    assets = dist / "assets"
    index = dist / "index.html"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", response_model=None)
    def home() -> FileResponse | HTMLResponse:
        if index.is_file():
            return FileResponse(index)
        page = "前端还没有构建。在 web 目录执行 pnpm build。"
        return HTMLResponse(page, status_code=503)


def serve(
    port: int = 8765,
    *,
    python: Path | None = None,
    script: Path | None = None,
) -> None:
    """Serve the studio on the loopback interface only."""
    import uvicorn

    launch = resolve_engine_launch(python, script)
    state = Path(tempfile.gettempdir()) / "stagecraft-studio" / "quicklook_runs.json"
    uvicorn.run(
        create_app(secrets.token_hex(16), port=port, launch=launch, state_path=state),
        host="127.0.0.1",
        port=port,
    )
