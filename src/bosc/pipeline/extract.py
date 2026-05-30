"""Stage 2 — extract.

Turn a scanned cost-estimate page into a reviewed, structured extraction.

The flow is **hybrid** (see the read-mode decision):

1. Pull the page's embedded OCR text via :class:`PdfDocument` — a cheap
   *structural* hint (section names, item ordering). Its digits are unreliable.
2. Render the page to a 300 DPI image — the *authoritative* source.
3. Force a Claude model to read the image and populate an
   :class:`EstimateExtraction` (tool use + Pydantic validation), using the OCR
   text only as a hint.
4. Wrap the result with provenance into a :class:`PageExtraction` and (option-
   ally) write it to ``data/extracted`` for human review.

The reference sheets live at 0-based PDF pages 317 (summary) and 318-327 (the
six detail estimates) of ``PRR-01-bundle.ocr.pdf``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bosc.config import Settings, get_settings
from bosc.documents import DEFAULT_DPI, PdfDocument
from bosc.logging import get_logger
from bosc.models import (
    DetailExtraction,
    DetailPageExtraction,
    EstimateExtraction,
    OPCSummary,
    PageExtraction,
)
from bosc.pipeline.ingest import SourceDocument

if TYPE_CHECKING:
    # Imported lazily at call time to avoid a bosc.agent <-> bosc.pipeline cycle.
    from bosc.agent.extractor import StructuredExtractor

log = get_logger(__name__)

# Sections an estimate sheet may contain (corridors omit several).
_SECTIONS = (
    "ROADWAY, EROSION_CONTROL, DRAINAGE, PAVEMENT, WATER_WORK, LIGHTING, "
    "TRAFFIC_CONTROL, LANDSCAPING, RIGHT_OF_WAY, INCIDENTALS, DESIGN_SURVEY_INSPECTION"
)

ESTIMATE_INSTRUCTIONS = f"""\
You are reading ONE page of a Tetra Tech "Opinion of Probable Project Cost"
sheet for the Project BOSC roadwork program. Read the cost table from the IMAGE,
which is authoritative. An embedded OCR text layer may be provided as a hint, but
its digits are frequently wrong — never trust a number from it; read every figure
off the image.

Record into the tool:
  * name: the estimate / intersection title printed on the sheet.
  * construction_subtotal, contingency_inflation_25pct (the 25% line), and total.
  * section_subtotals for each section present: {_SECTIONS}.
    Omit sections that do not appear on this sheet (corridors lack several).

Rules:
  * Dollar totals and section subtotals must be read carefully — high confidence.
  * If a digit is genuinely illegible, give your best read AND add a warning
    naming the field; do not silently guess.
  * Never invent sections or line items. Prefer omission over fabrication.
  * Set `confidence` (high/medium/low) for the page overall.
"""

DETAIL_INSTRUCTIONS = f"""\
You are reading ONE page of a Tetra Tech "Opinion of Probable Project Cost"
sheet for the Project BOSC roadwork program. Read the cost table from the IMAGE,
which is authoritative. An embedded OCR text layer may be provided as a hint, but
its digits are frequently wrong — never trust a number from it; read every figure
off the image.

Extract EVERY line item, grouped into `line_items` by section
({_SECTIONS}). For each line item record:
  * item_no: the ODOT item number (e.g. 203E10000), or a short `custom_*` tag
    for non-standard / lump-sum lines that have no ODOT code.
  * description, quantity, unit (LS, CY, SY, FT, EACH, GAL, SF, AC),
    unit_amount (per-unit dollars), total_amount (extended dollars).

Also record the roll-up figures: section_subtotals (the SUBTOTAL line under each
section), construction_subtotal, contingency_inflation_25pct (the 25% line), total.

Rules:
  * Dollar amounts are read off the image; do not trust OCR digits.
  * For a lump-sum (LS) item: quantity = 1 and unit_amount = total_amount.
  * If a quantity or unit rate was NOT printed and you inferred it from the
    total, record your best value and add a `note` saying it was inferred;
    never present an inferred figure as if printed.
  * If a section's line items are illegible but its SUBTOTAL is readable, record
    the section_subtotal, leave that section's items empty, and add a warning.
  * Never invent items. Set overall `confidence` (high/medium/low).
"""


def output_path_for(doc: SourceDocument, kind: str, settings: Settings | None = None) -> Path:
    """Where the extraction for ``doc`` should be written."""
    settings = settings or get_settings()
    return settings.extracted_dir / f"{doc.path.stem}.{kind}.opc.yaml"


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


def extract_estimate_page(
    doc: SourceDocument,
    page_index: int,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = DEFAULT_DPI,
    settings: Settings | None = None,
) -> PageExtraction:
    """Extract one page's summary (section subtotals + totals) into a PageExtraction.

    ``pdf`` and ``extractor`` are injectable for reuse across pages and for tests.
    """
    from bosc.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings)
    text, image = _read_page(doc, page_index, dpi, pdf)

    log.info(
        "extract.page.start", doc_id=doc.doc_id, page_index=page_index, dpi=dpi, kind="summary"
    )
    estimate = extractor.extract(
        EstimateExtraction,
        instructions=ESTIMATE_INSTRUCTIONS,
        image_png=image,
        context_text=text,
    )
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
        name=estimate.name,
        confidence=estimate.confidence,
        reconciles=estimate.reconciles(),
        warnings=len(estimate.warnings),
    )
    return extraction


def extract_detail_page(
    doc: SourceDocument,
    page_index: int,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = DEFAULT_DPI,
    settings: Settings | None = None,
    max_tokens: int = 8192,
) -> DetailPageExtraction:
    """Extract one page's full line items into a :class:`DetailPageExtraction`.

    Uses a larger ``max_tokens`` budget than the summary path, since a sheet can
    carry dozens of line items.
    """
    from bosc.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=max_tokens)
    text, image = _read_page(doc, page_index, dpi, pdf)

    log.info("extract.page.start", doc_id=doc.doc_id, page_index=page_index, dpi=dpi, kind="detail")
    estimate = extractor.extract(
        DetailExtraction,
        instructions=DETAIL_INSTRUCTIONS,
        image_png=image,
        context_text=text,
    )
    extraction = DetailPageExtraction(
        doc_id=doc.doc_id,
        source_path=str(doc.path),
        page_index=page_index,
        pdf_page=page_index + 1,
        dpi=dpi,
        estimate=estimate,
        source_text_excerpt=text[:600],
    )
    item_count = sum(len(items) for items in estimate.line_items.sections().values())
    log.info(
        "extract.page.done",
        doc_id=doc.doc_id,
        page_index=page_index,
        name=estimate.name,
        confidence=estimate.confidence,
        line_items=item_count,
        warnings=len(estimate.warnings),
    )
    return extraction


def save_extraction(
    extraction: PageExtraction | DetailPageExtraction, *, settings: Settings | None = None
) -> Path:
    """Write a page extraction to ``data/extracted`` as YAML; return the path.

    Detail extractions get a ``.detail.opc.yaml`` suffix; summaries ``.opc.yaml``.
    """
    settings = settings or get_settings()
    settings.extracted_dir.mkdir(parents=True, exist_ok=True)
    kind = "detail.opc" if isinstance(extraction, DetailPageExtraction) else "opc"
    slug = extraction.estimate.name.lower().replace("/", "-").replace(" ", "_")
    path = settings.extracted_dir / f"{slug}.p{extraction.pdf_page}.{kind}.yaml"
    path.write_text(extraction.to_yaml(), encoding="utf-8")
    log.info("extract.saved", path=str(path))
    return path


def validate_summary(path: str | Path) -> OPCSummary:
    """Load and validate a summary extraction, raising on schema violations."""
    summary = OPCSummary.from_yaml(path)
    log.info("extract.validated", path=str(path), sub_estimates=len(summary.sub_estimates))
    return summary
