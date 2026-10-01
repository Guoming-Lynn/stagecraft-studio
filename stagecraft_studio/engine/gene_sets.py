"""Download the default gene-set libraries. User gene lists are not sent anywhere.

MSigDB 2026.1 has human and mouse Hallmark and GO Biological Process.
KEGG is not included. Import a GMT file when that collection is needed.
# ponytail: pinned 2026.1 URLs; change these constants when a new release is published.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

_RELEASE = "2026.1"
_MSIGDB = "https://data.broadinstitute.org/gsea-msigdb/msigdb/release"
_HUMAN_HALLMARK = f"{_MSIGDB}/{_RELEASE}.Hs/h.all.v{_RELEASE}.Hs.symbols.gmt"
_HUMAN_GOBP = f"{_MSIGDB}/{_RELEASE}.Hs/c5.go.bp.v{_RELEASE}.Hs.symbols.gmt"
_MOUSE_HALLMARK = f"{_MSIGDB}/{_RELEASE}.Mm/mh.all.v{_RELEASE}.Mm.symbols.gmt"
_MOUSE_GOBP = f"{_MSIGDB}/{_RELEASE}.Mm/m5.go.bp.v{_RELEASE}.Mm.symbols.gmt"
_HUMAN = (_HUMAN_HALLMARK, _HUMAN_GOBP)
_MOUSE = (_MOUSE_HALLMARK, _MOUSE_GOBP)
LIBRARIES = {"human": _HUMAN, "mouse": _MOUSE}
_DIGESTS = {
    _HUMAN_HALLMARK: "eecaf6dad908334ae885406ec72bdc0646d8917588ed7c219fac92fc5363f596",
    _HUMAN_GOBP: "9be09dd06d6652566eb52eed530d62e6dfecc4365c1e81afd6f0b7f2e86dd4f9",
    _MOUSE_HALLMARK: "3a21be724a87dc0375955e725ca9688b87a26e7b74b62fba0c62da0967b789f7",
    _MOUSE_GOBP: "fd720ba92a3131a1596409f4b642a1a5950392fa51b45055b810215082e6f0c1",
}


class GeneSetError(OSError):
    """The default libraries were not available."""


def library_for_request(user_gmt: Path | None, species: str) -> Path | None:
    """Use an imported GMT when one was given. Otherwise download the default set."""
    if user_gmt is not None:
        return user_gmt
    if os.environ.get("STAGECRAFT_GENE_SETS") == "off":
        return None
    return ensure_default_gmt(species)


def ensure_default_gmt(
    species: str,
    *,
    fetch: Callable[[str], bytes] | None = None,
    cache: Path | None = None,
    digests: Mapping[str, str] | None = None,
) -> Path:
    """Return one GMT for this species, downloading it once into the cache."""
    urls = LIBRARIES.get(species)
    if urls is None:
        raise GeneSetError("物种只能是人或鼠。")
    folder = cache if cache is not None else _cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{species}-{_RELEASE}.gmt"
    if target.is_file() and target.stat().st_size > 0:
        return target
    reader = _fetch if fetch is None else fetch
    expected = _DIGESTS if digests is None else digests
    try:
        chunks = [reader(url) for url in urls]
    except OSError as exc:
        raise GeneSetError("默认基因集没有下载成功。可以改填一个本地 GMT 文件。") from exc
    for url, raw in zip(urls, chunks, strict=True):
        _require_digest(url, raw, expected)
    text = _combine(chunks)
    if not text.strip():
        raise GeneSetError("默认基因集没有下载成功。可以改填一个本地 GMT 文件。")
    temporary = folder / f".{species}-{_RELEASE}.gmt.partial"
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(target)
    return target


def _cache_dir() -> Path:
    override = os.environ.get("STAGECRAFT_GENE_SET_CACHE")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "stagecraft-studio" / "gene-sets"
    return Path.home() / ".local" / "share" / "stagecraft-studio" / "gene-sets"


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return bytes(response.read())


def _require_digest(url: str, raw: bytes, expected: Mapping[str, str]) -> None:
    digest = hashlib.sha256(raw).hexdigest()
    if expected.get(url) != digest:
        raise GeneSetError("默认基因集和固定的校验值不一致。")


def _combine(chunks: list[bytes]) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw in chunks:
        for line in raw.decode("utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) < 3 or not parts[0].strip():
                continue
            name = parts[0].strip()
            if name in seen:
                name = f"{name}__{len(seen)}"
            seen.add(parts[0].strip())
            seen.add(name)
            genes = [item.split(",", 1)[0].strip() for item in parts[2:]]
            genes = [gene for gene in genes if gene]
            if genes:
                lines.append("\t".join([name, parts[1], *genes]))
    return "\n".join(lines) + ("\n" if lines else "")
