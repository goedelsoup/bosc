"""Stage 2 — extract.

Turn a scanned cost-estimate page into a reviewed, structured extraction.

The flow is **hybrid** (see the read-mode decision):

1. Pull the page's embedded OCR text via :class:`PdfDocument` — a cheap
   *structural* hint (section names, item ordering). Its digits are unreliable.
2. Render the page to a 300 DPI image — the *authoritative* source.
3. Resolve a format :class:`~bosc.profiles.Profile` (explicit or auto-detected
   from the OCR text), build its prompt, and force a Claude model to populate a
   contractor-agnostic :class:`~bosc.models.Estimate` (tool use + validation).
4. Wrap the result with provenance into a :class:`PageExtraction`.

Extraction is dispatched by *document kind* (``opc`` today) via
:data:`EXTRACTORS`, leaving room for other public-records genres later.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from bosc import profiles
from bosc.config import Settings, get_settings
from bosc.documents import DEFAULT_DPI, PdfDocument
from bosc.logging import get_logger
from bosc.models import Estimate, OPCSummary, PageExtraction
from bosc.pipeline.ingest import SourceDocument

if TYPE_CHECKING:
    # Imported lazily at call time to avoid a bosc.agent <-> bosc.pipeline cycle.
    from bosc.agent.extractor import StructuredExtractor

log = get_logger(__name__)

# Token budgets: detail extractions can carry dozens of line items.
_SUMMARY_MAX_TOKENS = 4096
_DETAIL_MAX_TOKENS = 8192


def _read_page(
    doc: SourceDocument, page_index: int, dpi: int, pdf: PdfDocument | None
) -> tuple[str, bytes]:
    """Return ``(ocr_text, png_bytes)`` for a page, closing only a pdf we opened."""
    owns_pdf = pdf is None
    pdf = pdf or PdfDocument(doc.path, dpi=dpi)
    try:
        return pdf.page_text(page_index), pdf.render_page_png(page_index, dpi=dpi)
    finally:
        if owns_pdf:
            pdf.close()


def extract_opc_page(
    doc: SourceDocument,
    page_index: int,
    *,
    profile: str | None = None,
    detail: bool = False,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = DEFAULT_DPI,
    settings: Settings | None = None,
) -> PageExtraction:
    """Extract one Opinion-of-Probable-Cost page into a validated :class:`PageExtraction`.

    ``profile`` is a profile id, ``"auto"``/``None`` to auto-detect from the page,
    and ``detail`` toggles full line-item extraction. ``pdf``/``extractor`` are
    injectable for reuse across pages and for tests.
    """
    from bosc.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    max_tokens = _DETAIL_MAX_TOKENS if detail else _SUMMARY_MAX_TOKENS
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=max_tokens)

    text, image = _read_page(doc, page_index, dpi, pdf)
    prof = profiles.resolve(profile, text)

    log.info(
        "extract.page.start",
        doc_id=doc.doc_id,
        page_index=page_index,
        dpi=dpi,
        profile=prof.id,
        detail=detail,
    )
    estimate = extractor.extract(
        Estimate,
        instructions=prof.prompt(detail=detail),
        image_png=image,
        context_text=text,
    )
    estimate.profile = prof.id

    extraction = PageExtraction(
        doc_id=doc.doc_id,
        source_path=str(doc.path),
        page_index=page_index,
        pdf_page=page_index + 1,
        dpi=dpi,
        estimate=estimate,
        source_text_excerpt=text[:600],
    )
    log.info(
        "extract.page.done",
        doc_id=doc.doc_id,
        page_index=page_index,
        profile=prof.id,
        name=estimate.name,
        sections=len(estimate.sections),
        confidence=estimate.confidence,
        reconciles=estimate.reconciles(),
        warnings=len(estimate.warnings),
    )
    return extraction


# Document-kind dispatch. Add other public-records genres here later.
PageExtractor = Callable[..., PageExtraction]
EXTRACTORS: dict[str, PageExtractor] = {"opc": extract_opc_page}


def extract_page(
    doc: SourceDocument, page_index: int, *, kind: str = "opc", **kwargs: object
) -> PageExtraction:
    """Dispatch a page extraction to the handler for ``kind`` (default ``opc``)."""
    if kind not in EXTRACTORS:
        raise ValueError(f"unknown document kind {kind!r}; known: {sorted(EXTRACTORS)}")
    return EXTRACTORS[kind](doc, page_index, **kwargs)


def save_extraction(extraction: PageExtraction, *, settings: Settings | None = None) -> Path:
    """Write a page extraction to ``data/extracted`` as YAML; return the path.

    Files with line items get a ``.detail.opc.yaml`` suffix; subtotal-only ones
    get ``.opc.yaml``.
    """
    settings = settings or get_settings()
    settings.extracted_dir.mkdir(parents=True, exist_ok=True)
    kind = "detail.opc" if extraction.estimate.has_line_items() else "opc"
    slug = extraction.estimate.name.lower().replace("/", "-").replace(" ", "_")
    path = settings.extracted_dir / f"{slug}.p{extraction.pdf_page}.{kind}.yaml"
    path.write_text(extraction.to_yaml(), encoding="utf-8")
    log.info("extract.saved", path=str(path))
    return path


def validate_summary(path: str | Path) -> OPCSummary:
    """Load and validate an assembled summary extraction (legacy Tetra Tech shape)."""
    summary = OPCSummary.from_yaml(path)
    log.info("extract.validated", path=str(path), sub_estimates=len(summary.sub_estimates))
    return summary
