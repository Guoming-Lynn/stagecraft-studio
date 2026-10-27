"""Authenticated M6 settings and explicit send-preview assistant routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from stagecraft_studio.llm.context import AssistantRejected
from stagecraft_studio.llm.schemas import (
    CallRequest,
    CallView,
    PreviewRequest,
    PreviewView,
    ProviderSettings,
    ProviderView,
)
from stagecraft_studio.llm.service import AssistantService, CallRejected


def build_assistant_router(*, token: str, origin: str, service: AssistantService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/assistant/provider")
    def status(request: Request) -> ProviderView:
        _mutation(request, token, origin)
        return service.status()

    @router.put("/api/assistant/provider")
    async def configure(request: Request, body: ProviderSettings) -> ProviderView:
        _mutation(request, token, origin)
        try:
            return await service.configure(body)
        except CallRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/api/assistant/provider")
    def remove_provider(request: Request) -> dict[str, bool]:
        _mutation(request, token, origin)
        try:
            service.remove()
        except CallRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"removed": True}

    @router.post("/api/assistant/preview")
    def send_preview(request: Request, body: PreviewRequest) -> PreviewView:
        _mutation(request, token, origin)
        try:
            return service.preview(body)
        except AssistantRejected as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (CallRejected, ValidationError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/api/assistant/call")
    async def send_call(request: Request, body: CallRequest) -> CallView:
        _mutation(request, token, origin)
        try:
            return await service.call(body)
        except CallRejected as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/assistant/calls/{call_id}/cancel")
    def cancel(request: Request, call_id: str) -> dict[str, bool]:
        _mutation(request, token, origin)
        return {"cancelled": service.cancel(call_id)}

    return router


def _mutation(request: Request, token: str, origin: str) -> None:
    if request.headers.get("x-stagecraft-token") != token:
        raise HTTPException(status_code=401, detail="缺少会话令牌")
    if request.headers.get("origin") != origin:
        raise HTTPException(status_code=403, detail="来源不被接受")
