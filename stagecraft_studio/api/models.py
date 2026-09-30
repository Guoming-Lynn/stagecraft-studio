"""JSON shapes for /api. OpenAPI generates the TypeScript from these models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Started(BaseModel):
    run_id: str


class RevealResult(BaseModel):
    status: str


class QuicklookForm(BaseModel):
    """Fields the page may submit. The engine program is not one of them."""

    model_config = ConfigDict(extra="forbid")

    input_path: str
    gene: str
    out: str
    group: str = ""
    case_label: str = ""
    control_label: str = ""
    batch_column: str = ""
    local_gmt: str = ""

    @model_validator(mode="before")
    @classmethod
    def reject_program(cls, value: object) -> object:
        if isinstance(value, dict) and ("python_path" in value or "script" in value):
            raise ValueError("解释器和脚本由服务端决定，不能在请求里指定")
        return value


class ColumnView(BaseModel):
    name: str
    values: list[str]


class InspectView(BaseModel):
    columns: list[ColumnView]
    note: str
    group_note: str
    input_path: str
    gene: str
    out: str
    local_gmt: str


class Bootstrap(BaseModel):
    token: str
    python: str
    script: str
    gmt: str
    group_note: str
    engine_name: str
    engine_version: str
    engine_git: str
    environment_ok: bool


class ParameterRow(BaseModel):
    name: str
    value: str
    source: str
    source_label: str


class LogView(BaseModel):
    name: str
    text: str


class ReasonView(BaseModel):
    code: str
    text: str
    suggestion: str


class ImageView(BaseModel):
    rel: str
    step_id: str
    step_name: str
    passed: bool
    label: str
    reasons: list[ReasonView]


class RunView(BaseModel):
    run_id: str
    task_id: str
    status: str
    status_label: str
    heading: str
    lede: str
    can_cancel: bool
    returncode: int | None
    enrichment: str
    enrichment_label: str
    stopped_after: str
    output_root: str
    engine_name: str
    engine_version: str
    engine_git: str
    command: list[str]
    command_line: str
    config_text: str
    parameters: list[ParameterRow]
    logs: list[LogView]
    pipeline_outcome: str
    pipeline_label: str
    figure_status: str
    figure_label: str
    images: list[ImageView]


class RunListItem(BaseModel):
    run_id: str
    task_id: str
    status: str
    status_label: str
    heading: str
    returncode: int | None
    enrichment: str
    stopped_after: str


class ArtifactView(BaseModel):
    rel: str
    size: int
    quality_label: str


class StepView(BaseModel):
    step_id: str
    name: str
    status: str
    status_label: str
    script_name: str
    artifacts: list[ArtifactView]


class SourceView(BaseModel):
    step_id: str
    name: str
    script_name: str
    sha256: str
    engine_version: str
    engine_git: str
    source: str


class TreeEntry(BaseModel):
    rel: str
    kind: str
    size: int


class FilePreview(BaseModel):
    rel: str
    text: str
    truncated: bool
    note: str
    size: int


class TablePage(BaseModel):
    rel: str
    columns: list[str]
    rows: list[list[str]]
    offset: int
    limit: int = Field(ge=1, le=500)
