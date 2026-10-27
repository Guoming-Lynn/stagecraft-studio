"""M6 assistant safety and model-independence tests."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from stagecraft_studio.api.app import create_app
from stagecraft_studio.db.assistant_models import LLMCall, Proposal, ProviderProfile
from stagecraft_studio.db.migrate import upgrade_database
from stagecraft_studio.db.store import session_factory
from stagecraft_studio.engine.launch import EngineLaunch
from stagecraft_studio.llm.context import AssistantRejected
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
from stagecraft_studio.llm.tools import resolve_tool

TOKEN = {"origin": "http://127.0.0.1:8765", "x-stagecraft-token": "secret-token"}
LAUNCH = EngineLaunch(python=Path(sys.executable), script=Path("run_pipeline.py"))


def test_local_preview_requires_authorized_send_and_persists_only_hash(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    app = create_app("secret-token", port=8765, launch=LAUNCH, database=database)
    with TestClient(app) as client:
        assert client.get("/api/assistant/provider").status_code == 401
        preview = client.post(
            "/api/assistant/preview",
            headers=TOKEN,
            json={"topic": "field", "field_name": "harmony_keys", "question": "为什么？"},
        )
        assert preview.status_code == 200
        body = preview.json()
        assert body["mode"] == "local"
        assert "data_path" not in str(body["payload"])
        wrong = client.post(
            "/api/assistant/call",
            headers=TOKEN,
            json={"preview_id": body["preview_id"], "call_id": "a" * 32, "input_hash": "0" * 64},
        )
        assert wrong.status_code == 409
        assert wrong.json()["detail"] == "PREVIEW_CHANGED"

        preview = client.post(
            "/api/assistant/preview",
            headers=TOKEN,
            json={"topic": "field", "field_name": "harmony_keys"},
        ).json()
        completed = client.post(
            "/api/assistant/call",
            headers=TOKEN,
            json={
                "preview_id": preview["preview_id"],
                "call_id": "b" * 32,
                "input_hash": preview["input_hash"],
                "authorized": False,
            },
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "COMPLETED"
    with session_factory(database)() as session:
        row = session.get(LLMCall, "b" * 32)
        assert row is not None
        assert "原始" not in row.result_json
        assert session.query(ProviderProfile).count() == 0


def test_unknown_tool_and_invalid_proposal_are_rejected_without_side_effect() -> None:
    with pytest.raises(ValidationError):
        resolve_tool(
            {"name": "run_code", "arguments": {"code": "print(1)"}},
            {"rules": {}, "artifacts": [], "stage": None},
        )


def test_marker_annotation_proposal_is_allowlisted_and_read_only() -> None:
    context = {
        "topic": "annotation",
        "stage": {"stage_run_id": 1},
        "rules": {},
        "artifacts": [],
        "marker_evidence": [{"cluster_id": "0", "marker_genes": ["LYZ", "FCER1G"]}],
    }
    result, proposal = resolve_tool(
        {
            "name": "create_proposal",
            "arguments": {
                "kind": "cluster_annotation",
                "values": {
                    "cluster_id": "0",
                    "candidate_name": "Myeloid_like",
                    "marker_genes": ["LYZ"],
                    "rationale": "The supplied marker evidence supports a candidate only.",
                },
                "rationale": "Candidate for human review; not a label.",
            },
        },
        context,
    )
    assert proposal is not None
    assert proposal.kind == "cluster_annotation"
    assert result["status"] == "DRAFT_PENDING_VALIDATION"
    with pytest.raises(AssistantRejected, match="MARKER_NOT_AUTHORIZED"):
        resolve_tool(
            {
                "name": "create_proposal",
                "arguments": {
                    "kind": "cluster_annotation",
                    "values": {
                        "cluster_id": "0",
                        "candidate_name": "Bad",
                        "marker_genes": ["STAT1"],
                        "rationale": "not authorized",
                    },
                    "rationale": "bad",
                },
            },
            context,
        )


def test_provider_probe_and_error_responses_use_stable_mock_transport() -> None:
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


def test_valid_proposal_stays_a_draft_and_does_not_freeze(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite"
    upgrade_database(database)
    service = AssistantService(database, client=ProposalProvider())  # type: ignore[arg-type]
    asyncio.run(
        service.configure(
            ProviderSettings(
                config={
                    "provider": "openai",
                    "base_url": "http://127.0.0.1:9999/v1",
                    "model": "fake",
                },
                api_key="test-secret",
            )
        )
    )
    preview = service.preview(PreviewRequest(topic="proposal"))
    result = asyncio.run(
        service.call(
            CallRequest(
                preview_id=preview.preview_id,
                call_id="d" * 32,
                input_hash=preview.input_hash,
                authorized=True,
            )
        )
    )
    assert result.status == "COMPLETED"
    assert result.proposal is not None
    assert result.proposal.status == "DRAFT"
    with session_factory(database)() as session:
        assert session.query(Proposal).count() == 1
        assert session.query(ProviderProfile).count() == 1
        from stagecraft_studio.db.models import StageRun

        assert session.query(StageRun).count() == 0
    asyncio.run(service.close())
