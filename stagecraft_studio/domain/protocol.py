"""Frozen protocol hash. Old runs stop when the document or the input changes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class ProtocolError(ValueError):
    """The protocol document cannot be frozen."""


class ProtocolBlocked(Exception):
    """An old run no longer matches the protocol or the input."""

    def __init__(self) -> None:
        super().__init__("PROTOCOL_HASH_MATCH")


def protocol_document(
    *,
    target_gene: str,
    species: str,
    manifest: list[dict[str, JsonValue]],
    qc: dict[str, JsonValue],
    harmony_keys: list[str],
) -> dict[str, JsonValue]:
    """The fields that define a frozen Part 1 protocol."""
    if not target_gene or not species:
        raise ProtocolError("目标基因和物种不能为空")
    if not harmony_keys or "dataset" not in harmony_keys:
        raise ProtocolError("Harmony 键必须包含 dataset")
    return {
        "target_gene": target_gene,
        "species": species,
        "manifest": [_json_object(row) for row in manifest],
        "qc": _json_object(qc),
        "harmony_keys": list(harmony_keys),
    }


def content_hash(document: dict[str, JsonValue]) -> str:
    payload = json.dumps(_canonicalize(document), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def protocol_hash_match(
    *,
    stored_protocol_hash: str,
    stored_input_hash: str,
    protocol_hash: str,
    input_hash: str,
) -> None:
    if stored_protocol_hash != protocol_hash or stored_input_hash != input_hash:
        raise ProtocolBlocked


def _json_object(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {key: _canonicalize(item) for key, item in value.items()}


def _canonicalize(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, float)):
        return value
    raise ProtocolError("协议里有不能冻结的值")
