"""Protocol form fields. The page renders this list and cannot add a code box."""

from __future__ import annotations

from stagecraft_studio.domain.protocol import JsonValue, protocol_document

FORBIDDEN_HARMONY = frozenset({"donor_id", "region", "condition", "disease", "cell_type"})
SPECIES = ("human", "mouse")


class FormError(Exception):
    """The form cannot be frozen."""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        super().__init__(rule_id)


def form_fields() -> list[dict[str, object]]:
    """Field metadata for the research-design form. No free-text code field."""
    return [
        {
            "name": "target_gene",
            "kind": "text",
            "required": True,
            "default": "",
            "reason": "目标基因写进冻结协议。",
            "freeze_impact": "改了以后，旧 stage run 不能继续。",
        },
        {
            "name": "species",
            "kind": "choice",
            "required": True,
            "default": "human",
            "choices": list(SPECIES),
            "reason": "物种只接受人和鼠。",
            "freeze_impact": "改了以后，旧 stage run 不能继续。",
        },
        {
            "name": "harmony_keys",
            "kind": "tokens",
            "required": True,
            "default": ["dataset"],
            "forbidden": sorted(FORBIDDEN_HARMONY),
            "reason": "必须包含 dataset。不能用 donor、condition、disease、cell_type 或目标基因。",
            "freeze_impact": "改了以后，旧 stage run 不能继续。",
        },
        {
            "name": "loose_min_genes",
            "kind": "integer",
            "required": True,
            "default": 200,
            "minimum": 1,
            "maximum": 10000,
            "reason": "宽松基因数下限。",
            "freeze_impact": "改了以后，旧 stage run 不能继续。",
        },
        {
            "name": "data_path",
            "kind": "text",
            "required": True,
            "default": "",
            "reason": "输入文件的路径。冻结时对文件算 hash。",
            "freeze_impact": "文件字节变了，旧 stage run 不能继续。",
        },
        {
            "name": "libraries",
            "kind": "rows",
            "required": True,
            "columns": ["library_id", "dataset"],
            "reason": "每个 library 属于哪个 dataset。",
            "freeze_impact": "改了以后，旧 stage run 不能继续。",
        },
    ]


def document_from_form(
    *,
    target_gene: str,
    species: str,
    harmony_keys: list[str],
    loose_min_genes: int,
    libraries: list[dict[str, str]],
) -> dict[str, JsonValue]:
    """Build the frozen document. Reject keys the formal engine will not use."""
    gene = target_gene.strip()
    if species not in SPECIES:
        raise FormError("PROTOCOL_FORM")
    if loose_min_genes < 1 or loose_min_genes > 10000:
        raise FormError("PROTOCOL_FORM")
    keys = [item.strip() for item in harmony_keys if item.strip()]
    if "dataset" not in keys or any(item in FORBIDDEN_HARMONY or item == gene for item in keys):
        raise FormError("HARMONY_KEYS_ALLOWED")
    rows: list[dict[str, JsonValue]] = []
    for row in libraries:
        library_id = row.get("library_id", "").strip()
        dataset = row.get("dataset", "").strip()
        if not library_id or not dataset:
            raise FormError("PROTOCOL_FORM")
        rows.append({"library_id": library_id, "dataset": dataset})
    if not rows:
        raise FormError("PROTOCOL_FORM")
    return protocol_document(
        target_gene=gene,
        species=species,
        manifest=rows,
        qc={"loose_min_genes": loose_min_genes},
        harmony_keys=keys,
    )
