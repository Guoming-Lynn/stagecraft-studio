"""Validate every model tool call before returning data or staging a proposal."""

from __future__ import annotations

from pydantic import TypeAdapter

from stagecraft_studio.llm.context import AssistantRejected
from stagecraft_studio.llm.schemas import (
    ArtifactTool,
    ClusterAnnotationDraft,
    ProposalInput,
    ProposalTool,
    RuleTool,
    StageTool,
    ToolRequest,
)

ADAPTER: TypeAdapter[ToolRequest] = TypeAdapter(ToolRequest)
TOOL_SCHEMAS = [
    {
        "name": name,
        "description": description,
        "parameters": schema,
    }
    for name, description, schema in (
        (
            "get_stage_summary",
            "读取当前已授权的阶段摘要",
            {"type": "object", "properties": {}, "additionalProperties": False},
        ),
        (
            "get_rule_explanation",
            "读取已授权规则说明",
            {
                "type": "object",
                "properties": {"rule_id": {"type": "string"}},
                "required": ["rule_id"],
                "additionalProperties": False,
            },
        ),
        (
            "get_allowed_artifact_summary",
            "按已授权 ID 读取产物元数据",
            {
                "type": "object",
                "properties": {"artifact_id": {"type": "integer", "minimum": 1}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
        ),
        (
            "create_proposal",
            "提出研究设计或 cluster 候选注释草案，不修改配置或审阅",
            ProposalInput.model_json_schema(),
        ),
    )
]


def resolve_tool(
    raw: dict[str, object], context: dict[str, object]
) -> tuple[object, ProposalInput | None]:
    tool = ADAPTER.validate_python(raw)
    if isinstance(tool, StageTool):
        if context["stage"] is None:
            raise AssistantRejected("STAGE_NOT_AUTHORIZED")
        return context["stage"], None
    if isinstance(tool, RuleTool):
        catalog = context["rules"]
        assert isinstance(catalog, dict)
        if tool.arguments.rule_id not in catalog:
            raise AssistantRejected("RULE_NOT_AUTHORIZED")
        return catalog[tool.arguments.rule_id], None
    if isinstance(tool, ArtifactTool):
        artifacts = context["artifacts"]
        assert isinstance(artifacts, list)
        for item in artifacts:
            if item["artifact_id"] == tool.arguments.artifact_id:
                return item, None
        raise AssistantRejected("ARTIFACT_NOT_AUTHORIZED")
    assert isinstance(tool, ProposalTool)
    if tool.arguments.kind == "cluster_annotation":
        if context["topic"] != "annotation":
            raise AssistantRejected("ANNOTATION_NOT_REQUESTED")
        markers = context["marker_evidence"]
        assert isinstance(markers, list)
        values = tool.arguments.values
        assert isinstance(values, ClusterAnnotationDraft)
        authorized = next(
            (item for item in markers if item["cluster_id"] == values.cluster_id), None
        )
        if authorized is None:
            raise AssistantRejected("CLUSTER_NOT_AUTHORIZED")
        allowed_genes = authorized.get("marker_genes")
        if not isinstance(allowed_genes, list) or any(
            gene not in allowed_genes for gene in values.marker_genes
        ):
            raise AssistantRejected("MARKER_NOT_AUTHORIZED")
        return {
            "status": "DRAFT_PENDING_VALIDATION",
            "note": "只供人工参考，不是正式 cluster 标签。",
        }, tool.arguments
    return {
        "status": "DRAFT_PENDING_VALIDATION",
        "note": "仅暂存于内存，没有配置变更。",
    }, tool.arguments
