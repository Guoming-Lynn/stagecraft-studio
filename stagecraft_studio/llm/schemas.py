"""Strict contracts for user settings, proposals, and the four model tools."""

from __future__ import annotations

from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from stagecraft_studio.domain.protocol_form import FormError, document_from_form


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


CallStatus = Literal["COMPLETED", "FAILED", "REJECTED", "CANCELLED"]
ProviderStorage = Literal["none", "session", "credential_store"]
AssistantMode = Literal["local", "explanation", "tools"]


class ProviderConfig(StrictModel):
    provider: Literal["openai", "anthropic"]
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:/-]+$")
    timeout_seconds: int = Field(default=30, ge=1, le=60)
    max_output_tokens: int = Field(default=1024, ge=64, le=2048)
    context_chars: int = Field(default=16000, ge=4000, le=24000)
    call_limit: int = Field(default=20, ge=1, le=100)

    @field_validator("base_url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        parts = urlsplit(value.strip())
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("模型地址不能包含凭据、查询或片段")
        if not parts.hostname or parts.scheme not in {"http", "https"}:
            raise ValueError("模型地址需要是 http(s) URL")
        if parts.scheme == "http" and parts.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("远程模型地址必须使用 HTTPS")
        try:
            _ = parts.port
        except ValueError as exc:
            raise ValueError("模型地址端口无效") from exc
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class ProviderSettings(StrictModel):
    config: ProviderConfig
    api_key: SecretStr = SecretStr("")
    remember_key: bool = False


class Capabilities(StrictModel):
    text: bool = False
    streaming: bool = False
    structured_output: bool = False
    tool_calling: bool = False
    probed: bool = False


class ProviderView(StrictModel):
    config: ProviderConfig | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)
    key_storage: ProviderStorage = "none"
    calls_used: int = 0


class ProtocolDraft(StrictModel):
    target_gene: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    species: Literal["human", "mouse"]
    harmony_keys: list[str] = Field(min_length=1, max_length=4)
    loose_min_genes: int = Field(ge=1, le=10000, strict=True)

    @model_validator(mode="after")
    def ordinary_validation(self) -> ProtocolDraft:
        try:
            document_from_form(
                **self.model_dump(),
                libraries=[{"library_id": "validation", "dataset": "validation"}],
            )
        except FormError as exc:
            raise ValueError(exc.rule_id) from exc
        return self


class ClusterAnnotationDraft(StrictModel):
    cluster_id: str = Field(min_length=1, max_length=64)
    candidate_name: str = Field(
        min_length=1, max_length=100, pattern=r"^[A-Za-z][A-Za-z0-9 _./-]*$"
    )
    marker_genes: list[str] = Field(min_length=1, max_length=20)
    rationale: str = Field(min_length=1, max_length=1000)


class ProposalInput(StrictModel):
    kind: Literal["protocol_config", "cluster_annotation"]
    values: ProtocolDraft | ClusterAnnotationDraft
    rationale: str = Field(min_length=1, max_length=1000)


class StageTool(StrictModel):
    name: Literal["get_stage_summary"]
    arguments: StrictModel


class RuleArguments(StrictModel):
    rule_id: str = Field(min_length=1, max_length=64)


class RuleTool(StrictModel):
    name: Literal["get_rule_explanation"]
    arguments: RuleArguments


class ArtifactArguments(StrictModel):
    artifact_id: int = Field(gt=0, strict=True)


class ArtifactTool(StrictModel):
    name: Literal["get_allowed_artifact_summary"]
    arguments: ArtifactArguments


class ProposalTool(StrictModel):
    name: Literal["create_proposal"]
    arguments: ProposalInput


ToolRequest = Annotated[
    StageTool | RuleTool | ArtifactTool | ProposalTool, Field(discriminator="name")
]


class PreviewRequest(StrictModel):
    stage_run_id: int | None = Field(default=None, gt=0)
    topic: Literal["stage", "rule", "field", "proposal", "annotation"] = "stage"
    rule_id: str = Field(default="DESIGN_ESTIMABLE", max_length=64)
    field_name: str = Field(default="harmony_keys", max_length=64)
    question: str = Field(default="", max_length=1000)


class PreviewView(StrictModel):
    preview_id: str
    input_hash: str
    payload: dict[str, object]
    sources: list[dict[str, object]]
    mode: AssistantMode
    local_text: str


class CallRequest(StrictModel):
    preview_id: str
    call_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorized: bool = False


class ProposalView(StrictModel):
    id: int
    kind: str
    values: ProtocolDraft | ClusterAnnotationDraft
    rationale: str
    status: Literal["DRAFT"] = "DRAFT"
    note: str = "仅为草案；转入研究设计表单后由用户检查，仍需通过常规校验才能冻结。"


class CallView(StrictModel):
    call_id: str
    status: CallStatus
    text: str
    model: str
    prompt_version: str
    input_hash: str
    sources: list[dict[str, object]]
    created_at: str
    usage: dict[str, int] | None = None
    proposal: ProposalView | None = None
    auxiliary: bool = True
