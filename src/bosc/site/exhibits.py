"""Publish a curated set of source PDFs as downloadable exhibits.

Reads ``data/site/exhibits.yaml`` (a hand-curated allowlist), copies each
standalone PDF into ``<web>/exhibits/``, and for a ``pages`` range slices just
those pages out of a large bundle with :mod:`pypdf` so the full (often >100 MB)
document is never republished. Source PDFs live under ``data/documents`` and are
Git-LFS-tracked — a missing/locally-unpulled file is reported as *unavailable*
rather than aborting the build.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bosc.logging import get_logger

log = get_logger(__name__)


@dataclass
class Exhibit:
    slug: str
    title: str
    caption: str
    source: str  # relative to data/documents
    pages: str | None  # "317-327", 0-based inclusive, or None for the whole file
    available: bool
    out_name: str | None  # filename under exhibits/, when available


def _parse_range(spec: str) -> tuple[int, int]:
    """Parse a ``"a-b"`` (or ``"a"``) 0-based inclusive page range."""
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return int(lo), int(hi)
    n = int(spec)
    return n, n


def _slice_pdf(src: Path, dst: Path, pages: str) -> None:
    """Write ``dst`` containing only ``pages`` (0-based inclusive) of ``src``."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(src))
    writer = PdfWriter()
    lo, hi = _parse_range(pages)
    last = len(reader.pages) - 1
    for i in range(max(lo, 0), min(hi, last) + 1):
        writer.add_page(reader.pages[i])
    with dst.open("wb") as fh:
        writer.write(fh)


def build_exhibits(manifest_path: Path, documents_dir: Path, exhibits_dir: Path) -> list[Exhibit]:
    """Copy/slice every manifest exhibit into ``exhibits_dir``; return their status."""
    if not manifest_path.exists():
        log.info("site.exhibits.no_manifest", path=str(manifest_path))
        return []
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    entries: list[dict[str, Any]] = raw.get("exhibits") or []

    exhibits_dir.mkdir(parents=True, exist_ok=True)
    results: list[Exhibit] = []
    for entry in entries:
        slug = str(entry["slug"])
        source = str(entry["source"])
        pages = entry.get("pages")
        pages = str(pages) if pages is not None else None
        src = documents_dir / source
        available = src.is_file()
        out_name: str | None = None
        if available:
            out_name = f"{slug}.pdf"
            dst = exhibits_dir / out_name
            try:
                if pages:
                    _slice_pdf(src, dst, pages)
                else:
                    shutil.copy2(src, dst)
            except Exception as exc:  # a corrupt/locked source must not kill the build
                log.warning("site.exhibits.copy_failed", slug=slug, error=str(exc).splitlines()[0])
                available, out_name = False, None
        else:
            log.warning("site.exhibits.missing", slug=slug, source=source)
        results.append(
            Exhibit(
                slug=slug,
                title=str(entry.get("title", slug)),
                caption=str(entry.get("caption", "")),
                source=source,
                pages=pages,
                available=available,
                out_name=out_name,
            )
        )
    log.info(
        "site.exhibits.built",
        total=len(results),
        available=sum(1 for e in results if e.available),
    )
    return results


def render_exhibits(exhibits: list[Exhibit]) -> str:
    """Render ``exhibits.md`` — a table of downloadable source documents."""
    lines = [
        "# Exhibits",
        "",
        "A curated set of primary-source documents from the corpus, published as "
        "downloadable PDFs. Page-range exhibits are sliced from larger bundles. "
        "Everything else in the record is summarized under "
        "[Records](records/index.md) with its raw extraction.",
        "",
    ]
    if not exhibits:
        lines.append("*No exhibits configured.*")
        return "\n".join(lines) + "\n"
    lines += ["| Exhibit | Source | Download |", "|---|---|---|"]
    for ex in exhibits:
        src = f"`{ex.source}`" + (f" (pp. {ex.pages})" if ex.pages else "")
        if ex.available and ex.out_name:
            link = f"[Download PDF](exhibits/{ex.out_name})"
        else:
            link = "_unavailable — `git lfs pull` the source_"
        title = ex.title + (f"<br><small>{ex.caption}</small>" if ex.caption else "")
        lines.append(f"| {title} | {src} | {link} |")
    lines.append("")
    return "\n".join(lines)
