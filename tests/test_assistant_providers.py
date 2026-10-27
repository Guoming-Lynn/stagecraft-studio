"""M6 provider transport and cancellation tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from stagecraft_studio.db.assistant_models import LLMCall, Proposal, ProviderProfile
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.llm.providers import ProviderClient, ProviderFailure, Reply, parse_reply
from stagecraft_studio.llm.schemas import (
    CallRequest,
    Capabilities,
    PreviewRequest,
    ProposalInput,
    ProviderConfig,
    ProviderSettings,
)
from stagecraft_studio.llm.service import AssistantService


def test_openai_probe_and_error_responses_use_stable_mock_transport() -> None:
    calls: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream") is True:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"data: [DONE]\n\n",
            )
        if "response_format" in body:
            result = {"choices": [{"message": {"content": '{"value":"ok"}'}}]}
        elif "tools" in body:
            result = {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "probe",
                                        "arguments": '{"value":"ok"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        else:
            result = {"choices": [{"message": {"content": "OK"}}]}
        return httpx.Response(200, json=result)

    config = ProviderConfig(
        provider="openai",
        base_url="http://127.0.0.1:9999/v1",
        model="mock",
    )
    client = ProviderClient(transport=httpx.MockTransport(handler))
    capabilities = asyncio.run(client.probe(config, "mock-key"))
    assert capabilities.text is True
    assert capabilities.tool_calling is True
    assert capabilities.structured_output is True
    assert capabilities.streaming is True
    assert len(calls) == 4

    with pytest.raises(ProviderFailure, match="MALFORMED_RESPONSE"):
        parse_reply(config, {"choices": [{"message": {"content": {"bad": True}}}]})
    with pytest.raises(ProviderFailure, match="TOOL_CALL_LIMIT"):
        parse_reply(
            config,
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {"type": "function", "function": {"name": "a", "arguments": "{}"}},
                                {"type": "function", "function": {"name": "b", "arguments": "{}"}},
                            ],
                        }
                    }
                ]
            },
        )
    with pytest.raises(ValidationError):
        ProposalInput(
            kind="protocol_config",
            values={
                "target_gene": "STAT1",
                "species": "human",
                "harmony_keys": ["donor_id"],
                "loose_min_genes": 200,
            },
            rationale="bad",
        )


def test_anthropic_probe_uses_messages_contract_and_parses_tool_reply() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        if body.get("stream") is True:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"event: message_stop\ndata: {}\n\n",
            )
        if "tools" in body:
            result = {
                "content": [{"type": "tool_use", "name": "probe", "input": {"value": "ok"}}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }
        else:
            result = {
                "content": [{"type": "text", "text": "OK"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            }
        return httpx.Response(200, json=result)

    config = ProviderConfig(
        provider="anthropic",
        base_url="http://127.0.0.1:9999",
        model="mock-anthropic",
    )
    client = ProviderClient(transport=httpx.MockTransport(handler))
    capabilities = asyncio.run(client.probe(config, "anthropic-key"))

    assert capabilities == Capabilities(
        text=True, streaming=True, structured_output=True, tool_calling=True, probed=True
    )
    assert len(requests) == 3
    assert all(request.url.path == "/v1/messages" for request in requests)
    assert all(request.headers["x-api-key"] == "anthropic-key" for request in requests)
    first = json.loads(requests[0].content)
    assert first["system"]
    assert first["messages"][0]["role"] == "user"
    parsed = parse_reply(
        config,
        {
            "content": [
                {"type": "text", "text": "候选说明"},
                {"type": "tool_use", "name": "probe", "input": {"value": "ok"}},
            ]
        },
    )
    assert parsed.text == "候选说明"
    assert parsed.tools == [{"name": "probe", "arguments": {"value": "ok"}}]


class SlowProvider:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def probe(self, config: ProviderConfig, key: str) -> Capabilities:
        return Capabilities(text=True, probed=True)

    async def generate(
        self,
        config: ProviderConfig,
        key: str,
        system: str,
        content: str,
        tools: bool,
    ) -> Reply:
        self.started.set()
        await asyncio.Event().wait()
        return Reply(text="never", tools=[], usage=None)


def test_cancelled_provider_call_is_recorded_without_a_proposal(tmp_path: Path) -> None:
    async def run() -> None:
        database = tmp_path / "studio.sqlite"
        upgrade_database(database)
        provider = SlowProvider()
        service = AssistantService(database, client=provider)  # type: ignore[arg-type]
        await service.configure(
            ProviderSettings(
                config={
                    "provider": "openai",
                    "base_url": "http://127.0.0.1:9999/v1",
                    "model": "slow",
                },
                api_key="test-secret",
            )
        )
        preview = service.preview(PreviewRequest(topic="proposal"))
        call_id = "e" * 32
        pending = asyncio.create_task(
            service.call(
                CallRequest(
                    preview_id=preview.preview_id,
                    call_id=call_id,
                    input_hash=preview.input_hash,
                    authorized=True,
                )
            )
        )
        await asyncio.wait_for(provider.started.wait(), timeout=1)
        assert service.cancel(call_id) is True
        result = await pending
        assert result.status == "CANCELLED"
        assert result.proposal is None
        with session_factory(database)() as session:
            row = session.get(LLMCall, call_id)
            assert row is not None
            assert row.status == "CANCELLED"
            assert session.query(Proposal).count() == 0
        await service.close()

    asyncio.run(run())


class FailingProvider:
    async def probe(self, config: ProviderConfig, key: str) -> Capabilities:
        return Capabilities(text=True, probed=True)

    async def generate(
        self,
        config: ProviderConfig,
        key: str,
        system: str,
        content: str,
        tools: bool,
    ) -> Reply:
        raise ProviderFailure("PROVIDER_TIMEOUT")


class ProposalProvider:
    async def probe(self, config: ProviderConfig, key: str) -> Capabilities:
        return Capabilities(text=True, tool_calling=True, probed=True)

    async def generate(
        self,
        config: ProviderConfig,
        key: str,
        system: str,
        content: str,
        tools: bool,
    ) -> Reply:
        return Reply(
            text="",
            tools=[
                {
                    "name": "create_proposal",
                    "arguments": {
                        "kind": "protocol_config",
                        "values": {
                            "target_gene": "STAT1",
                            "species": "human",
                            "harmony_keys": ["dataset"],
                            "loose_min_genes": 200,
                        },
                        "rationale": "Keep the dataset as the Harmony key.",
                    },
                }
            ],
            usage=None,
        )


def test_provider_failure_is_auxiliary_and_does_not_change_analysis(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    service = AssistantService(database, client=FailingProvider())  # type: ignore[arg-type]
    settings = ProviderSettings(
        config={"provider": "openai", "base_url": "http://127.0.0.1:9999/v1", "model": "fake"},
        api_key="test-secret",
    )
    asyncio.run(service.configure(settings))
    preview = service.preview(PreviewRequest(topic="field"))
    result = asyncio.run(
        service.call(
            CallRequest(
                preview_id=preview.preview_id,
                call_id="c" * 32,
                input_hash=preview.input_hash,
                authorized=True,
            )
        )
    )
    assert result.status == "FAILED"
    assert result.text == "PROVIDER_TIMEOUT"
    with session_factory(database)() as session:
        assert session.query(LLMCall).count() == 1
        assert session.query(ProviderProfile).count() == 1
    asyncio.run(service.close())
