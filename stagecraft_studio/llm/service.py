"""An isolated optional assistant instance. The engine cannot read its conversation."""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import ValidationError
from sqlalchemy import select

from stagecraft_studio.db.assistant_models import LLMCall, ProviderProfile
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.llm.context import (
    SYSTEM,
    AssistantRejected,
    digest,
    local_explanation,
    make_context,
)
from stagecraft_studio.llm.credentials import Credentials
from stagecraft_studio.llm.providers import ProviderClient, ProviderFailure
from stagecraft_studio.llm.records import read_call, record_call
from stagecraft_studio.llm.schemas import (
    AssistantMode,
    CallRequest,
    CallStatus,
    CallView,
    Capabilities,
    PreviewRequest,
    PreviewView,
    ProviderConfig,
    ProviderSettings,
    ProviderStorage,
    ProviderView,
)
from stagecraft_studio.llm.tools import resolve_tool


class CallRejected(ValueError):
    """The request lacks a current preview or exceeds the assistant limits."""


@dataclass
class Preview:
    expires: float
    request: PreviewRequest
    context: dict[str, object]
    context_hash: str
    state_hash: str
    provider_hash: str
    local: bool


class AssistantService:
    def __init__(self, database: Path, client: ProviderClient | None = None) -> None:
        self.factory = session_factory(database)
        self.credentials = Credentials()
        self.client = client or ProviderClient()
        self.previews: dict[str, Preview] = {}
        self.active: dict[str, asyncio.Task[CallView]] = {}
        self.config: ProviderConfig | None = None
        self.capabilities = Capabilities()
        self.credential_id = ""
        self.key_storage = "none"
        self.probing = False
        self._load_profile()

    def _load_profile(self) -> None:
        with self.factory() as session:
            profile = session.scalar(select(ProviderProfile).limit(1))
            if profile:
                self.config = ProviderConfig.model_validate_json(profile.config_json)
                self.capabilities = Capabilities.model_validate_json(profile.capabilities_json)
                self.credential_id = profile.credential_id
                _, self.key_storage = self.credentials.get(self.credential_id)

    def status(self) -> ProviderView:
        with self.factory() as session:
            calls_used = session.query(LLMCall).filter(LLMCall.model != "LOCAL").count()
        storage = cast(
            ProviderStorage,
            self.key_storage
            if self.key_storage in {"none", "session", "credential_store"}
            else "none",
        )
        return ProviderView(
            config=self.config,
            capabilities=self.capabilities,
            key_storage=storage,
            calls_used=calls_used,
        )

    async def configure(self, settings: ProviderSettings) -> ProviderView:
        if self.active or self.probing:
            raise CallRejected("ASSISTANT_BUSY")
        key = settings.api_key.get_secret_value()
        if len(key) > 500:
            raise CallRejected("KEY_TOO_LONG")
        self.probing = True
        try:
            caps = await asyncio.wait_for(
                self.client.probe(settings.config, key), timeout=settings.config.timeout_seconds
            )
        except (TimeoutError, asyncio.TimeoutError, ProviderFailure):
            caps = Capabilities(probed=True)
        finally:
            self.probing = False
        if self.credential_id:
            self.credentials.forget(self.credential_id)
        self.config = settings.config
        self.capabilities = caps
        self.credential_id = secrets.token_hex(16)
        self.key_storage = self.credentials.put(self.credential_id, key, settings.remember_key)
        with self.factory() as session:
            profile = session.scalar(select(ProviderProfile).limit(1))
            if profile is None:
                profile = ProviderProfile()
                session.add(profile)
            profile.config_json = self.config.model_dump_json()
            profile.capabilities_json = caps.model_dump_json()
            profile.credential_id = self.credential_id
            session.commit()
        self.previews.clear()
        return self.status()

    def remove(self) -> None:
        if self.active or self.probing:
            raise CallRejected("ASSISTANT_BUSY")
        self.credentials.forget(self.credential_id)
        with self.factory() as session:
            for profile in session.scalars(select(ProviderProfile)).all():
                session.delete(profile)
            session.commit()
        self.config = None
        self.capabilities = Capabilities()
        self.key_storage = "none"
        self.credential_id = ""
        self.previews.clear()

    def preview(self, request: PreviewRequest) -> PreviewView:
        with self.factory() as session:
            context, state_hash = make_context(session, request)
        wire: dict[str, object] = {"system": SYSTEM, "summary": context}
        content = json.dumps(context, ensure_ascii=False)
        if self.config and len(content) + len(SYSTEM) > self.config.context_chars:
            raise CallRejected("CONTEXT_LIMIT")
        key = self.credentials.get(self.credential_id)[0]
        local = not self.config or not key or not self.capabilities.text
        mode: AssistantMode = (
            "local" if local else "tools" if self.capabilities.tool_calling else "explanation"
        )
        token = secrets.token_hex(16)
        now = time.monotonic()
        self.previews = {k: v for k, v in self.previews.items() if v.expires > now}
        while len(self.previews) >= 100:
            self.previews.pop(next(iter(self.previews)))
        context_hash = digest(wire)
        self.previews[token] = Preview(
            now + 300, request, context, context_hash, state_hash, self._provider_hash(), local
        )
        sources = context["sources"]
        assert isinstance(sources, list)
        return PreviewView(
            preview_id=token,
            input_hash=context_hash,
            payload=wire,
            sources=sources,
            mode=mode,
            local_text=local_explanation(context),
        )

    def _provider_hash(self) -> str:
        return digest(
            {
                "config": self.config.model_dump() if self.config else None,
                "capabilities": self.capabilities.model_dump(),
                "credential_id": self.credential_id,
            }
        )

    async def call(self, request: CallRequest) -> CallView:
        if request.call_id in self.active:
            raise CallRejected("CALL_ALREADY_IN_PROGRESS")
        with self.factory() as session:
            previous = session.get(LLMCall, request.call_id)
            if previous:
                return read_call(session, previous)
        if self.active or self.probing:
            raise CallRejected("ASSISTANT_BUSY")
        preview = self.previews.pop(request.preview_id, None)
        if preview is None or preview.expires <= time.monotonic():
            raise CallRejected("PREVIEW_EXPIRED")
        if (
            request.input_hash != preview.context_hash
            or preview.provider_hash != self._provider_hash()
        ):
            raise CallRejected("PREVIEW_CHANGED")
        with self.factory() as session:
            _, current_hash = make_context(session, preview.request)
        if current_hash != preview.state_hash:
            raise CallRejected("STAGE_CHANGED_REVIEW_PREVIEW")
        if not preview.local and not request.authorized:
            raise CallRejected("SEND_NOT_AUTHORIZED")
        task = asyncio.create_task(self._execute(request.call_id, preview))
        self.active[request.call_id] = task
        try:
            return await task
        finally:
            self.active.pop(request.call_id, None)

    async def _execute(self, call_id: str, preview: Preview) -> CallView:
        context = preview.context
        text = local_explanation(context)
        status: CallStatus = "COMPLETED"
        model = "LOCAL"
        usage = None
        proposal = None
        try:
            if not preview.local and self.config:
                model = self.config.model
                if self.status().calls_used >= self.config.call_limit:
                    raise CallRejected("CALL_LIMIT")
                key = self.credentials.get(self.credential_id)[0]
                reply = await asyncio.wait_for(
                    self.client.generate(
                        self.config,
                        key,
                        SYSTEM,
                        json.dumps(context, ensure_ascii=False),
                        self.capabilities.tool_calling,
                    ),
                    timeout=self.config.timeout_seconds,
                )
                text, usage = reply.text, reply.usage
                if reply.tools:
                    if not self.capabilities.tool_calling:
                        raise CallRejected("TOOL_CAPABILITY_UNAVAILABLE")
                    tool_result, proposal = resolve_tool(reply.tools[0], context)
                    if proposal:
                        if preview.request.topic not in {"proposal", "annotation"}:
                            raise CallRejected("PROPOSAL_NOT_REQUESTED")
                        text = "配置草案已生成。请检查后转入研究设计表单。"
                    else:
                        followup = await asyncio.wait_for(
                            self.client.generate(
                                self.config,
                                key,
                                SYSTEM,
                                json.dumps(
                                    {
                                        "context": context,
                                        "authorized_tool_result": tool_result,
                                    },
                                    ensure_ascii=False,
                                ),
                                False,
                            ),
                            timeout=self.config.timeout_seconds,
                        )
                        if followup.tools:
                            raise CallRejected("TOOL_CALL_LIMIT")
                        text, usage = followup.text, followup.usage or usage
        except asyncio.CancelledError:
            status, text, proposal = "CANCELLED", "助手调用已取消。", None
        except (ProviderFailure, CallRejected, AssistantRejected, ValidationError) as exc:
            status = "REJECTED" if not isinstance(exc, ProviderFailure) else "FAILED"
            text = (
                str(exc)
                if isinstance(exc, (ProviderFailure, CallRejected, AssistantRejected))
                else "INVALID_TOOL_SCHEMA"
            )
            proposal = None
        except (TimeoutError, asyncio.TimeoutError):
            status, text, proposal = "FAILED", "PROVIDER_TIMEOUT", None
        with self.factory() as session:
            # A late response cannot produce a valid proposal for a changed stage.
            _, current = make_context(session, preview.request)
            if current != preview.state_hash:
                status, text, proposal = "REJECTED", "STAGE_CHANGED_REVIEW_PREVIEW", None
            sources = context["sources"]
            assert isinstance(sources, list)
            return record_call(
                session,
                call_id=call_id,
                run_id=preview.request.stage_run_id,
                input_hash=preview.context_hash,
                sources=sources,
                model=model,
                status=status,
                text=text,
                usage=usage,
                proposal=proposal,
            )

    def cancel(self, call_id: str) -> bool:
        task = self.active.get(call_id)
        if task is None:
            return False
        task.cancel()
        return True

    async def close(self) -> None:
        tasks = list(self.active.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.previews.clear()
        self.credentials.clear()
