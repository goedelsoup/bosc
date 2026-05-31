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
from bosc.models import (
    Deed,
    DeedExtraction,
    DocExtraction,
    Estimate,
    NpdesExtraction,
    NpdesPermit,
    OPCSummary,
    PageExtraction,
)
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


# ---------------------------------------------------------------------------
# Document-level extraction (deeds, NPDES permits).
#
# Unlike OPC sheets (one estimate per page), these read across the first several
# pages of a document and produce one record. Deeds are usually scanned (vision-
# primary); NPDES fact sheets have clean text layers (text-primary).
# ---------------------------------------------------------------------------

_DEED_DPI = 200
_NPDES_DPI = 150

DEED_INSTRUCTIONS = """\
You are reading a recorded land instrument (a deed, easement, or similar) from a
county recorder. The page images are authoritative; the OCR text layer may be
absent or garbled. Record into the tool:
  * instrument_type: e.g. "General Warranty Deed", "Quitclaim Deed", "Easement".
  * instrument_no: the recorder's instrument / document number (often stamped at
    the top of page 1).
  * recording_date: ISO yyyy-mm-dd if legible.
  * grantors: the party/parties conveying; grantees: the party/parties receiving.
    List each name exactly as printed.
  * consideration: the stated dollar amount (e.g. "for the sum of $..."); null if
    nominal or not stated.
  * parcel_ids: auditor's / permanent parcel numbers.
  * county; legal_description: a SHORT summary or the opening line only (do NOT
    transcribe the full metes-and-bounds).
Rules: read names and numbers carefully; if a field is illegible, give your best
read AND add a warning naming it; never invent parties or parcels; set confidence.
"""

NPDES_INSTRUCTIONS = """\
You are reading an Ohio EPA NPDES discharge permit or fact sheet. The text layer
is generally reliable for this document, but verify against the page image.
Record into the tool:
  * facility_name; permit_no exactly as printed (e.g. 2PH00006*LD);
    permit_action: one of renewal | modification | new | draft.
  * applicant; application_no (e.g. OH0037338).
  * public_notice_no; public_notice_date; comment_period_end (ISO dates).
  * facility_address (where the discharge occurs); discharge_address if distinct.
  * receiving_water; stream_network: the downstream chain if stated
    (e.g. "Ottawa River to Auglaize River to Maumee River to Lake Erie").
  * outfalls: outfall identifiers if listed.
Rules: copy permit/application numbers exactly; dates as ISO; leave a field null
if not present; never invent; set confidence and warnings.
"""


def _read_doc(
    doc: SourceDocument,
    *,
    text_pages: int,
    image_pages: int,
    dpi: int,
    pdf: PdfDocument | None,
) -> tuple[str, list[bytes], list[int]]:
    """Read the first pages of a document: ``(text, page_images, pages_touched)``."""
    owns_pdf = pdf is None
    pdf = pdf or PdfDocument(doc.path, dpi=dpi)
    try:
        n_text = min(text_pages, pdf.page_count)
        n_img = min(image_pages, pdf.page_count)
        text = "\n\n".join(pdf.page_text(i) for i in range(n_text))
        images = [pdf.render_page_png(i, dpi=dpi) for i in range(n_img)]
        return text, images, list(range(max(n_text, n_img)))
    finally:
        if owns_pdf:
            pdf.close()


def extract_deed(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _DEED_DPI,
    settings: Settings | None = None,
    max_pages: int = 8,
) -> DeedExtraction:
    """Extract a recorded deed (vision-primary across its first pages)."""
    from bosc.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=4096)
    text, images, pages = _read_doc(
        doc, text_pages=max_pages, image_pages=max_pages, dpi=dpi, pdf=pdf
    )

    log.info("extract.doc.start", doc_id=doc.doc_id, kind="deed", pages=len(pages), dpi=dpi)
    deed = extractor.extract(Deed, instructions=DEED_INSTRUCTIONS, images=images, context_text=text)
    extraction = DeedExtraction(
        doc_id=doc.doc_id,
        source_path=str(doc.path),
        kind="deed",
        pages_read=pages,
        dpi=dpi,
        deed=deed,
        source_text_excerpt=text[:600],
    )
    log.info(
        "extract.doc.done",
        doc_id=doc.doc_id,
        kind="deed",
        grantees=len(deed.grantees),
        parcels=len(deed.parcel_ids),
        confidence=deed.confidence,
        warnings=len(deed.warnings),
    )
    return extraction


def extract_npdes(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _NPDES_DPI,
    settings: Settings | None = None,
    text_pages: int = 6,
) -> NpdesExtraction:
    """Extract an NPDES permit / fact sheet (text-primary, page-1 image as backup)."""
    from bosc.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=4096)
    text, images, pages = _read_doc(doc, text_pages=text_pages, image_pages=1, dpi=dpi, pdf=pdf)

    log.info("extract.doc.start", doc_id=doc.doc_id, kind="npdes", pages=len(pages), dpi=dpi)
    permit = extractor.extract(
        NpdesPermit, instructions=NPDES_INSTRUCTIONS, images=images, context_text=text
    )
    extraction = NpdesExtraction(
        doc_id=doc.doc_id,
        source_path=str(doc.path),
        kind="npdes",
        pages_read=pages,
        dpi=dpi,
        permit=permit,
        source_text_excerpt=text[:600],
    )
    log.info(
        "extract.doc.done",
        doc_id=doc.doc_id,
        kind="npdes",
        permit_no=permit.permit_no,
        facility=permit.facility_name,
        confidence=permit.confidence,
        warnings=len(permit.warnings),
    )
    return extraction


# Document-level kind dispatch (parallel to the page-level EXTRACTORS above).
DocumentExtractor = Callable[..., DocExtraction]
DOC_EXTRACTORS: dict[str, DocumentExtractor] = {"deed": extract_deed, "npdes": extract_npdes}


def extract_document(doc: SourceDocument, *, kind: str, **kwargs: object) -> DocExtraction:
    """Dispatch a document-level extraction to the handler for ``kind``."""
    if kind not in DOC_EXTRACTORS:
        raise ValueError(f"unknown document kind {kind!r}; known: {sorted(DOC_EXTRACTORS)}")
    return DOC_EXTRACTORS[kind](doc, **kwargs)


def save_doc_extraction(extraction: DocExtraction, *, settings: Settings | None = None) -> Path:
    """Write a document-level extraction to ``data/extracted`` as ``<stem>.<kind>.yaml``."""
    settings = settings or get_settings()
    settings.extracted_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(extraction.source_path).stem
    path = settings.extracted_dir / f"{stem}.{extraction.kind}.yaml"
    path.write_text(extraction.to_yaml(), encoding="utf-8")
    log.info("extract.saved", path=str(path))
    return path
