"""Stage 1 — ingest.

Discover source documents under ``data/documents`` and produce a manifest of
:class:`SourceDocument` records. This stage deliberately does *no* parsing; it
just inventories what raw material exists so later stages have a stable handle.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import opentelemetry.trace

from watermark.config import Settings, get_settings
from watermark.documents import IMAGE_SUFFIXES
from watermark.logging import get_logger

log = get_logger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)

# Extensions the extract stage can actually read: PDF (pdfium render + pypdf text),
# OpenDocument Drawing (read_odg), and raster scans (read_image_png → straight to the
# vision model, no text layer; #703). `discover` is the *extraction* inventory, so it
# admits only what has an extractor path. Discovery only inventories — extraction is
# kind-dispatched (`extract_document(doc, kind=…)`), so an admitted image isn't
# auto-extracted; it just becomes a handle. A `.txt` source has no vision path and stays
# out. (Reference/evidence files under data/documents/ remain immutable corpus and are
# surfaced by the site documents feed, which walks the tree independently.)
SOURCE_SUFFIXES = {".pdf", ".odg", *IMAGE_SUFFIXES}


@dataclass(frozen=True)
class SourceDocument:
    """A raw source document discovered during ingest."""

    path: Path
    doc_id: str
    suffix: str
    size_bytes: int
    collection: str = field(default="")
    #: Are the bytes readable HERE? False for a document the committed `vault.yaml` names whose
    #: bytes are in the vault and not on this disk (#2147). Listing it is right — the corpus holds
    #: it — but nothing that opens the file may proceed; `watermark documents hydrate` fetches it.
    available: bool = field(default=True)

    @property
    def is_pdf(self) -> bool:
        return self.suffix == ".pdf"

    @property
    def is_image(self) -> bool:
        """A raster source (.png/.jpg/.tif) read straight into the vision model (#703)."""
        return self.suffix in IMAGE_SUFFIXES


def _doc_id(path: Path) -> str:
    """Stable short id from the path (not the contents — files may be huge)."""
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"{path.stem}-{digest[:8]}"


def _recorded_only(root: Path, seen: set[str], site: str | None) -> list[SourceDocument]:
    """Documents the committed manifests name that this disk does not hold.

    Scoped by the same site rule as the walk, and `size_bytes` comes from the record — the one
    number about an absent file that is knowable without it.
    """
    from watermark.documents.vault import recorded_sizes

    out: list[SourceDocument] = []
    for full_rel, size in recorded_sizes(root.parent).items():
        prefix, _, rel = full_rel.partition("/")
        if prefix != root.name or not rel or rel in seen:
            continue
        path = root / rel
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        parts = PurePosixPath(rel).parts
        if site and site not in parts:
            continue
        out.append(
            SourceDocument(
                path=path,
                doc_id=_doc_id(path),
                suffix=path.suffix.lower(),
                size_bytes=size,
                collection=parts[0] if len(parts) > 1 else "",
                available=False,
            )
        )
    return out


def discover(settings: Settings | None = None, site: str | None = None) -> list[SourceDocument]:
    """Walk ``documents_dir`` and return a manifest of source documents.

    ``collection`` is the first sub-directory under ``documents`` (e.g.
    ``aedg``), letting you group documents by their origin/request batch.
    When ``site`` is provided, only documents whose path includes that slug as
    a component are returned (e.g. ``data/documents/idem/fort-wayne/`` for
    ``site="fort-wayne"``).
    """
    settings = settings or get_settings()
    with tracer.start_as_current_span("pipeline.ingest") as span:
        span.set_attribute("pipeline.site", settings.site)
        root = settings.documents_dir
        if not root.exists():
            log.warning("documents_dir missing", path=str(root))
            span.set_attribute("pipeline.doc_count", 0)
            return []

        docs: list[SourceDocument] = []
        seen: set[str] = set()
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            rel = path.relative_to(root)
            if site and site not in rel.parts:
                continue
            seen.add(rel.as_posix())
            collection = rel.parts[0] if len(rel.parts) > 1 else ""
            docs.append(
                SourceDocument(
                    path=path,
                    doc_id=_doc_id(path),
                    suffix=path.suffix.lower(),
                    size_bytes=path.stat().st_size,
                    collection=collection,
                )
            )
        span.set_attribute("pipeline.doc_count", len(docs))
        # The committed record is the second witness (#2147). After the Git-LFS untrack a fresh
        # checkout holds NO source bytes, so this walk alone answers "no documents" for a corpus of
        # 3,662 — which is what it did, until the agent's `list_documents` said so out loud in CI.
        # A recorded document is listed and marked `available=False`: the corpus has it, this disk
        # does not, and anything that opens the file must say so rather than crash on the `open`.
        docs.extend(_recorded_only(root, seen, site))
        docs.sort(key=lambda d: d.path)
        log.info(
            "ingest.discovered",
            count=len(docs),
            unavailable=sum(1 for d in docs if not d.available),
            root=str(root),
        )
        return docs
