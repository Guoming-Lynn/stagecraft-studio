"""Bounded HTTP adapters. No model output can select a URL or execute code."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from stagecraft_studio.llm.schemas import Capabilities, ProviderConfig
from stagecraft_studio.llm.tools import TOOL_SCHEMAS


class ProviderFailure(RuntimeError):
    """A stable error code, never a provider body or credential."""


@dataclass
class Reply:
    text: str
    tools: list[dict[str, object]]
    usage: dict[str, int] | None


class ProviderClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.transport = transport

    async def request(
        self,
        config: ProviderConfig,
        key: str,
        payload: dict[str, Any],
        *,
        stream: bool = False,
        attempts: int = 1,
    ) -> dict[str, Any]:
        headers = (
            {"x-api-key": key, "anthropic-version": "2023-06-01"}
            if config.provider == "anthropic"
            else {"authorization": f"Bearer {key}"}
        )
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=config.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            for attempt in range(attempts):
                try:
                    async with client.stream(
                        "POST", endpoint(config), headers=headers, json=payload
                    ) as response:
                        if response.status_code in {429, 502, 503, 504} and attempt + 1 < attempts:
                            retry = response.headers.get("retry-after", "1")
                            delay = (
                                min(float(retry), 2.0)
                                if retry.replace(".", "", 1).isdigit()
                                else 1.0
                            )
                            await asyncio.sleep(max(0, delay))
                            continue
                        if response.status_code >= 300:
                            raise ProviderFailure(f"PROVIDER_HTTP_{response.status_code}")
                        buffer = bytearray()
                        async for block in response.aiter_bytes():
                            buffer.extend(block)
                            if len(buffer) > 128_000:
                                raise ProviderFailure("RESPONSE_TOO_LARGE")
                        if stream:
                            text = buffer.decode("utf-8")
                            # A provider ignoring stream=true must not pass this probe.
                            if (
                                "text/event-stream" not in response.headers.get("content-type", "")
                                or "data:" not in text
                            ):
                                raise ProviderFailure("STREAM_UNSUPPORTED")
                            return {"stream": True}
                        body = json.loads(buffer)
                        if not isinstance(body, dict):
                            raise ProviderFailure("MALFORMED_RESPONSE")
                        return body
                except httpx.TimeoutException as exc:
                    raise ProviderFailure("PROVIDER_TIMEOUT") from exc
                except httpx.HTTPError as exc:
                    raise ProviderFailure("PROVIDER_CONNECTION_FAILED") from exc
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise ProviderFailure("MALFORMED_RESPONSE") from exc
        raise ProviderFailure("RETRY_LIMIT")

    async def probe(self, config: ProviderConfig, key: str) -> Capabilities:
        if not key:
            return Capabilities(probed=True)
        caps = Capabilities(probed=True)
        base = self.payload(
            config, "Reply OK.", "Capability probe; contains no project data.", False
        )
        base["max_tokens"] = 64
        try:
            caps.text = bool(parse_reply(config, await self.request(config, key, base)).text)
        except ProviderFailure:
            return caps
        tool = {
            "name": "probe",
            "description": "Return the value ok",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string", "enum": ["ok"]}},
                "required": ["value"],
                "additionalProperties": False,
            },
        }
        payload = dict(base)
        payload["messages"] = [{"role": "user", "content": "Call probe with value ok."}]
        payload["tools"] = _wire_tools(config, [tool])
        payload["tool_choice"] = (
            {"type": "tool", "name": "probe"}
            if config.provider == "anthropic"
            else {"type": "function", "function": {"name": "probe"}}
        )
        try:
            reply = parse_reply(config, await self.request(config, key, payload))
            caps.tool_calling = reply.tools == [{"name": "probe", "arguments": {"value": "ok"}}]
        except ProviderFailure:
            caps.tool_calling = False
        if config.provider == "openai":
            payload = dict(base)
            payload["messages"] = [{"role": "user", "content": 'Return JSON {"value":"ok"}.'}]
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "probe",
                    "strict": True,
                    "schema": tool["parameters"],
                },
            }
            try:
                reply = parse_reply(config, await self.request(config, key, payload))
                caps.structured_output = json.loads(reply.text) == {"value": "ok"}
            except (ProviderFailure, ValueError):
                caps.structured_output = False
        else:
            caps.structured_output = caps.tool_calling
        payload = dict(base)
        payload["stream"] = True
        try:
            await self.request(config, key, payload, stream=True)
            caps.streaming = True
        except ProviderFailure:
            caps.streaming = False
        return caps

    def payload(
        self, config: ProviderConfig, system: str, content: str, tools: bool
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_output_tokens,
            "stream": False,
        }
        if config.provider == "anthropic":
            payload["system"] = system
            payload["messages"] = [{"role": "user", "content": content}]
        else:
            payload["messages"] = [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ]
        if tools:
            payload["tools"] = _wire_tools(config, TOOL_SCHEMAS)
            if config.provider == "openai":
                payload["parallel_tool_calls"] = False
        return payload

    async def generate(
        self, config: ProviderConfig, key: str, system: str, content: str, tools: bool
    ) -> Reply:
        body = await self.request(
            config, key, self.payload(config, system, content, tools), attempts=2
        )
        return parse_reply(config, body)


def endpoint(config: ProviderConfig) -> str:
    path = urlsplit(config.base_url).path.rstrip("/")
    suffix = "/messages" if config.provider == "anthropic" else "/chat/completions"
    if path.endswith(suffix):
        return config.base_url
    return config.base_url + ("" if path.endswith("/v1") else "/v1") + suffix


def _wire_tools(config: ProviderConfig, schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if config.provider == "openai":
        return [{"type": "function", "function": item} for item in schemas]
    return [
        {
            "name": item["name"],
            "description": item["description"],
            "input_schema": item["parameters"],
        }
        for item in schemas
    ]


def parse_reply(config: ProviderConfig, body: dict[str, Any]) -> Reply:
    try:
        calls: list[dict[str, object]] = []
        if config.provider == "anthropic":
            blocks = body["content"]
            if not isinstance(blocks, list):
                raise ValueError
            text = "\n".join(item["text"] for item in blocks if item.get("type") == "text")
            calls = [
                {"name": item["name"], "arguments": item["input"]}
                for item in blocks
                if item.get("type") == "tool_use"
            ]
            usage = body.get("usage")
            usage_keys = ("input_tokens", "output_tokens")
        else:
            message = body["choices"][0]["message"]
            if "function_call" in message:
                raise ValueError
            text = message.get("content") or ""
            if not isinstance(text, str):
                raise ValueError
            for item in message.get("tool_calls", []):
                if item.get("type") != "function":
                    raise ValueError
                function = item["function"]
                calls.append(
                    {"name": function["name"], "arguments": json.loads(function["arguments"])}
                )
            usage = body.get("usage")
            usage_keys = ("prompt_tokens", "completion_tokens")
        if len(calls) > 1:
            raise ProviderFailure("TOOL_CALL_LIMIT")
        counts = None
        if isinstance(usage, dict) and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in usage_keys
        ):
            counts = {"input_tokens": usage[usage_keys[0]], "output_tokens": usage[usage_keys[1]]}
        if len(text) > 8000 or not text and not calls:
            raise ValueError
        return Reply(text=text, tools=calls, usage=counts)
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ProviderFailure("MALFORMED_RESPONSE") from exc
