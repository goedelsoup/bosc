"""Stage 2 — extract.

Turn a scanned cost-estimate page into a reviewed, structured extraction.

The flow is **hybrid** (see the read-mode decision):

1. Pull the page's embedded OCR text via :class:`PdfDocument` — a cheap
   *structural* hint (section names, item ordering). Its digits are unreliable.
2. Render the page to a 300 DPI image — the *authoritative* source.
3. Resolve a format :class:`~watermark.profiles.Profile` (explicit or auto-detected
   from the OCR text), build its prompt, and force a Claude model to populate a
   contractor-agnostic :class:`~watermark.models.Estimate` (tool use + validation).
4. Wrap the result with provenance into a :class:`PageExtraction`.

Extraction is dispatched by *document kind* (``opc`` today) via
:data:`EXTRACTORS`, leaving room for other public-records genres later.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import opentelemetry.trace
from opentelemetry.trace import StatusCode
from pydantic import BaseModel

from watermark import profiles
from watermark.config import Settings, get_settings
from watermark.documents import DEFAULT_DPI, PdfDocument, read_image_png, read_odg
from watermark.logging import get_logger
from watermark.models import (
    BusinessFiling,
    Deed,
    DeedExtraction,
    DocExtraction,
    EngineeringExtraction,
    EngineeringRecord,
    EpaExtraction,
    EpaPermitAction,
    Estimate,
    NpdesExtraction,
    NpdesPermit,
    OPCMeta,
    OPCSummary,
    PageExtraction,
    PlanExtraction,
    SectionSubtotals,
    SitePlan,
    SosExtraction,
    SubEstimate,
    WetlandDetermination,
    WetlandExtraction,
)
from watermark.pipeline.ingest import SourceDocument

if TYPE_CHECKING:
    # Imported lazily at call time to avoid a watermark.agent <-> watermark.pipeline cycle.
    from watermark.agent.extractor import StructuredExtractor

log = get_logger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)

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
    from watermark.agent.extractor import StructuredExtractor

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
    with tracer.start_as_current_span("pipeline.extract.page") as span:
        span.set_attribute("pipeline.doc_id", doc.doc_id)
        span.set_attribute("pipeline.page_index", page_index)
        span.set_attribute("pipeline.kind", kind)
        try:
            result = EXTRACTORS[kind](doc, page_index, **kwargs)
            span.set_attribute("pipeline.profile", result.estimate.profile or "")
            return result
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            raise


def _collection_dir(source_path: str, settings: Settings) -> Path:
    """Sub-directory of ``extracted`` mirroring the source's collection.

    The extracted tree parallels ``data/documents``: an artifact lands under the
    same first-level collection as its source (e.g. ``recorder``, ``oepa``),
    mirroring :func:`ingest.discover` (``collection = rel.parts[0]``). Sources that
    sit directly under ``documents`` — or outside it entirely (tests) — map to the
    root of ``extracted``. The directory is created.
    """
    target = settings.extracted_dir
    try:
        rel = Path(source_path).resolve().relative_to(settings.documents_dir.resolve())
    except ValueError:
        rel = None
    if rel is not None and len(rel.parts) > 1:
        target = target / rel.parts[0]
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_extraction(extraction: PageExtraction, *, settings: Settings | None = None) -> Path:
    """Write a page extraction to ``data/extracted`` as YAML; return the path.

    The file lands under a collection sub-directory mirroring its source (see
    :func:`_collection_dir`). Files with line items get a ``.detail.opc.yaml``
    suffix; subtotal-only ones get ``.opc.yaml``.
    """
    settings = settings or get_settings()
    target = _collection_dir(extraction.source_path, settings)
    kind = "detail.opc" if extraction.estimate.has_line_items() else "opc"
    slug = extraction.estimate.name.lower().replace("/", "-").replace(" ", "_")
    path = target / f"{slug}.p{extraction.pdf_page}.{kind}.yaml"
    path.write_text(extraction.to_yaml(), encoding="utf-8")
    log.info("extract.saved", path=str(path))
    return path


# ---------------------------------------------------------------------------
# OPC page-sweep + summary assembly (issue #39).
#
# The hand-assembled ``roundabouts.summary.opc.yaml`` (six sub-estimates, 25%
# contingency) becomes *regenerable*: sweep the bundle's OPC pages, then assemble the
# per-page :class:`Estimate`s into the legacy :class:`OPCSummary` shape that
# ``analyze.reconcile`` checks. ``sweep_opc_pages`` is the live vision path (a reusable
# PDF + extractor across pages); ``assemble_opc_summary`` is pure (testable offline).
# ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    """The outcome of an OPC page sweep: what extracted, and — crucially — what didn't.

    A page that raises is logged and skipped so one bad sheet never aborts a live sweep, but the
    failure is **surfaced** here rather than swallowed (#1364): ``failed`` lists every requested
    index that raised and ``requested`` is the full input range, so a caller can tell a *complete*
    sweep from a *truncated* one instead of mistaking the survivors for the whole set. ``complete``
    is the headline gate the CLI / assembly cross-check.
    """

    extractions: list[PageExtraction]
    failed: list[int]
    requested: list[int]

    @property
    def complete(self) -> bool:
        return not self.failed


def sweep_opc_pages(
    doc: SourceDocument,
    page_indices: Iterable[int],
    *,
    profile: str | None = "auto",
    detail: bool = False,
    extractor: StructuredExtractor | None = None,
    dpi: int = DEFAULT_DPI,
    settings: Settings | None = None,
) -> SweepResult:
    """Extract a range of OPC pages, reusing one open PDF + extractor across them.

    The live page-sweep behind the regenerable summary (PDF pages 317-327 of the PRR
    bundle). One bad page is logged and skipped (not fatal) but its index is carried on the
    returned :class:`SweepResult`, so a truncated sweep can't pass for a complete one (#1364).
    ``extractor`` is injectable so the sweep can be driven without the Claude API in tests.
    """
    settings = settings or get_settings()
    indices = list(page_indices)
    pdf = PdfDocument(doc.path, dpi=dpi)
    out: list[PageExtraction] = []
    failed: list[int] = []
    try:
        for i in indices:
            try:
                out.append(
                    extract_opc_page(
                        doc,
                        i,
                        profile=profile,
                        detail=detail,
                        extractor=extractor,
                        pdf=pdf,
                        dpi=dpi,
                        settings=settings,
                    )
                )
            except Exception as exc:  # one bad page must not abort the whole sweep
                failed.append(i)
                log.warning("extract.sweep.page_failed", page=i, error=str(exc).splitlines()[0])
    finally:
        pdf.close()
    log.info("extract.sweep", pages=len(indices), extracted=len(out), failed=len(failed))
    return SweepResult(extractions=out, failed=failed, requested=indices)


def assemble_opc_summary(
    estimates: list[Estimate],
    *,
    pdf_pages: list[int] | None = None,
    section_schema: list[str] | None = None,
    expected_count: int | None = None,
) -> OPCSummary:
    """Assemble per-page generic :class:`Estimate`s into the legacy OPCSummary shape.

    Each Estimate becomes a :class:`SubEstimate` (name, construction subtotal,
    post-markup total, per-section subtotals); ``meta.summary_construction_total`` is set
    to the sum of the sub-estimate totals (the program headline ``analyze.reconcile``
    cross-checks against ``grand_total()``). Estimates missing a construction subtotal or
    total are skipped with a warning rather than fabricated. Pure — no I/O, no API.

    ``expected_count`` (the number of pages the sweep was asked to cover) is recorded on
    ``meta.expected_sub_estimates`` so ``analyze.reconcile`` fails loudly when a page dropped out
    — the headline total is derived from the survivors, so without this cross-check a truncated
    summary reconciles green (#1364).
    """
    subs: list[SubEstimate] = []
    for idx, est in enumerate(estimates):
        if est.construction_subtotal is None or est.total is None:
            log.warning("extract.assemble.skipped", name=est.name, reason="no subtotal/total")
            continue
        section_subtotals = SectionSubtotals.model_validate(
            {s.key: s.subtotal for s in est.sections if s.subtotal is not None}
        )
        markup = est.markups_total()
        subs.append(
            SubEstimate(
                name=est.name,
                pdf_page=(pdf_pages[idx] if pdf_pages and idx < len(pdf_pages) else None),
                construction_subtotal=est.construction_subtotal,
                contingency_inflation_25pct=(round(markup) if markup else None),
                total=est.total,
                section_subtotals=section_subtotals,
            )
        )
    grand_total = sum(int(se.total) for se in subs)
    return OPCSummary(
        meta=OPCMeta(
            summary_construction_total=grand_total,
            expected_sub_estimates=expected_count,
        ),
        section_schema=section_schema or [],
        sub_estimates=subs,
    )


# ---------------------------------------------------------------------------
# Document-level extraction (deeds, NPDES permits).
#
# Unlike OPC sheets (one estimate per page), these read across the first several
# pages of a document and produce one record. Deeds are usually scanned (vision-
# primary); NPDES fact sheets have clean text layers (text-primary).
# ---------------------------------------------------------------------------

_DEED_DPI = 200
_NPDES_DPI = 150
_SOS_DPI = 200
_EPA_DPI = 150
_WETLAND_DPI = 200
_ENGINEERING_DPI = 200

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


SOS_INSTRUCTIONS = """\
You are reading a Secretary of State business filing (e.g. an Ohio Articles of
Organization for a domestic LLC, or a Registration of a Foreign LLC). The page
images are authoritative; the text layer is usually just a stamped document id.
Record into the tool:
  * entity_name: the LLC / business name exactly as printed.
  * filing_id: the SoS document / filing number (often stamped "DOC ID" or at the
    top of the form).
  * filing_type: e.g. "Articles of Organization", "Registration of a Foreign
    Limited Liability Company".
  * entity_type: "domestic LLC", "foreign LLC", etc.
  * jurisdiction: the formation state. For a foreign registration this is the
    home state (e.g. Delaware); for a domestic Ohio filing this is Ohio.
  * filing_date and effective_date: ISO yyyy-mm-dd if legible.
  * registered_agent: the statutory / registered agent NAME; agent_address: their
    address. (A commercial agent such as "CT Corporation System" is common.)
  * organizer: the organizer / authorized representative / signer NAME;
    organizer_address if shown.
  * principal_address: the principal office address, if stated.
  * officers: any members / managers / officers disclosed (Ohio often discloses
    none — leave empty rather than guessing).
Rules: copy names and the filing id exactly; dates as ISO; leave a field null if
not present; NEVER invent an agent, organizer, or officer; set confidence and add
a warning for any field you had to strain to read.
"""


EPA_INSTRUCTIONS = """\
You are reading an Ohio EPA (Division of Surface Water) or U.S. Army Corps of
Engineers permit action or correspondence letter for a development project. The
text layer is reliable; verify against the page image. These letters carry a
header "Re:" block (applicant, permit type, program, county, permit number) and a
"Subject:" line. Record into the tool:
  * agency (e.g. "Ohio EPA", "U.S. Army Corps of Engineers");
    program: the permit program — e.g. "Surface Water Permit-to-Install",
    "401 Water Quality Certification", "Isolated Wetland Permit", "Section 404".
  * permit_no exactly as printed (e.g. DSWPTI-260294, DSW401252260W, or an
    "Ohio EPA ID No." like 252260W).
  * action: what the letter does — one of issued | approved | denied | incomplete
    | comments | application | correspondence.
  * action_date: the letter date (ISO); plans_received_date; expiration_date if any.
  * applicant and applicant_address (copy the mailing address as printed).
  * contact_name: the addressee or submitter; contact_email; contact_firm (the
    law firm or engineering firm, e.g. Vorys, EMH&T) if discernible.
  * project_name (e.g. "Project Bosc", "BOSC-1A"); site_address;
    affected_resource (e.g. "private sanitary sewer", "isolated wetland").
  * parcel_ids if listed.
Rules: copy permit numbers, names, and the address exactly; dates as ISO; leave a
field null if absent; never invent; set confidence and add warnings for strained
reads.
"""


WETLAND_INSTRUCTIONS = """\
You are reading a U.S. Army Corps of Engineers "Wetland Determination Data Form"
— a routine on-site delineation worksheet (e.g. the Midwest or Eastern Mountains
and Piedmont regional supplement). It records ONE sampling point and the three
regulatory criteria that decide whether that point is a wetland. The page images
are authoritative: the text layer carries the printed field LABELS, but the
ENTERED values (checkboxes, species, percentages, coordinates) must be read from
the image. Record into the tool:
  * project_site ("Project/Site"); applicant ("Applicant/Owner", e.g. Bistrozzi
    LLC); investigators (the field investigator names).
  * city_county exactly as printed (e.g. "Sugar Creek Township/Allen"); state;
    region (the ACE regional supplement named in the title, e.g. "Midwest").
  * sampling_date as ISO yyyy-mm-dd; sampling_point (the label, e.g. WD-1, WE-1).
  * landform; slope_pct; latitude and longitude in decimal degrees — mind the
    sign: western-Ohio longitudes are NEGATIVE (~ -84), and a "° North/West" label
    on the form does not change that; datum if shown.
  * soil_map_unit; nwi_classification.
  * The SUMMARY OF FINDINGS three determinations, each true/false from the CHECKED
    box: hydrophytic_vegetation_present, hydric_soil_present,
    wetland_hydrology_present. is_wetland: the overall "Is the Sampled Area within
    a Wetland?" box (true = Yes, false = No).
  * dominant_species: the dominant plant species listed, if legible.
Rules: read the CHECKED box from the image, not the label; copy names/IDs and
coordinates exactly; dates as ISO; leave a field null — and a boolean null — if
you cannot clearly resolve it. NEVER guess a determination. Set confidence and add
a warning for any strained read or any criterion box you could not resolve.
"""


def _read_doc(
    doc: SourceDocument,
    *,
    text_pages: int,
    image_pages: int,
    dpi: int,
    pdf: PdfDocument | None,
) -> tuple[str, list[bytes], list[int], list[int]]:
    """Read the first pages of a document.

    Returns ``(text, page_images, pages_consulted, image_pages)``: ``pages_consulted``
    is the text-and-image page union; ``image_pages`` is the honest subset actually
    rendered and sent to the vision model — recorded separately so a text-primary read
    (e.g. 6 text pages, 1 image) doesn't over-report the pages the model *saw* (#613).
    """
    if doc.is_image:
        # A raster source (#703): no text layer, no pages — the single image is read
        # straight into the vision model with no OCR hint. `text_pages`/`image_pages`/
        # `dpi`/`pdf` don't apply (it's already a rendered scan).
        return "", [read_image_png(doc.path)], [0], [0]
    owns_pdf = pdf is None
    pdf = pdf or PdfDocument(doc.path, dpi=dpi)
    try:
        n_text = min(text_pages, pdf.page_count)
        n_img = min(image_pages, pdf.page_count)
        text = "\n\n".join(pdf.page_text(i) for i in range(n_text))
        images = [pdf.render_page_png(i, dpi=dpi) for i in range(n_img)]
        return text, images, list(range(max(n_text, n_img))), list(range(n_img))
    finally:
        if owns_pdf:
            pdf.close()


@dataclass(frozen=True)
class DocSpec:
    """A document-level extraction recipe — the per-kind knobs the generic read varies.

    The six document extractors (deed, npdes, sos, epa, wetland, engineering) share one
    body: default settings/extractor → :func:`_read_doc` → force the model to populate a
    record → wrap it with provenance → log start/done. Only these fields differ, so
    :func:`_extract_doc` drives the whole read from one spec.

    ``summary`` maps the extracted record to the *type-specific* ``extract.doc.done`` log
    fields; the universal ``confidence``/``warnings`` are added by :func:`_extract_doc`.
    """

    kind: str
    model: type[BaseModel]
    extraction_cls: type[DocExtraction]
    field: str  # the attribute on ``extraction_cls`` that receives the extracted record
    instructions: str
    dpi: int
    text_pages: int
    image_pages: int
    summary: Callable[[Any], dict[str, object]]
    max_tokens: int = 4096


def _extract_doc(
    spec: DocSpec,
    doc: SourceDocument,
    *,
    kind: str | None = None,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int | None = None,
    settings: Settings | None = None,
    text_pages: int | None = None,
    image_pages: int | None = None,
) -> DocExtraction:
    """Run the document-level extraction described by ``spec``.

    The shared body of the document extractors: ``spec`` supplies the model,
    instructions, page budget, and per-kind summary fields, while the keyword overrides
    (``kind``/``dpi``/``text_pages``/``image_pages``) let a wrapper or caller adjust
    without copying the body. ``kind`` defaults to ``spec.kind`` but is overridable so a
    discipline alias (e.g. ``sanitary``) stamps its own provenance / output filename.
    """
    from watermark.agent.extractor import StructuredExtractor

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=spec.max_tokens)
    dpi = spec.dpi if dpi is None else dpi
    kind = kind or spec.kind
    text, images, pages, image_pages_read = _read_doc(
        doc,
        text_pages=spec.text_pages if text_pages is None else text_pages,
        image_pages=spec.image_pages if image_pages is None else image_pages,
        dpi=dpi,
        pdf=pdf,
    )

    log.info("extract.doc.start", doc_id=doc.doc_id, kind=kind, pages=len(pages), dpi=dpi)
    record: Any = extractor.extract(
        spec.model, instructions=spec.instructions, images=images, context_text=text
    )
    extraction = spec.extraction_cls(
        **{
            "doc_id": doc.doc_id,
            "source_path": str(doc.path),
            "kind": kind,
            "pages_read": pages,
            "image_pages_read": image_pages_read,
            # A raster source isn't rendered at a DPI — it's already an image (#703).
            "dpi": 0 if doc.is_image else dpi,
            "source_text_excerpt": text[:600],
            spec.field: record,
        }
    )
    log.info(
        "extract.doc.done",
        doc_id=doc.doc_id,
        kind=kind,
        **spec.summary(record),
        confidence=record.confidence,
        warnings=len(record.warnings),
    )
    return extraction


_DEED_SPEC = DocSpec(
    kind="deed",
    model=Deed,
    extraction_cls=DeedExtraction,
    field="deed",
    instructions=DEED_INSTRUCTIONS,
    dpi=_DEED_DPI,
    text_pages=8,
    image_pages=8,
    summary=lambda d: {"grantees": len(d.grantees), "parcels": len(d.parcel_ids)},
)


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
    return cast(
        "DeedExtraction",
        _extract_doc(
            _DEED_SPEC,
            doc,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=max_pages,
            image_pages=max_pages,
        ),
    )


_NPDES_SPEC = DocSpec(
    kind="npdes",
    model=NpdesPermit,
    extraction_cls=NpdesExtraction,
    field="permit",
    instructions=NPDES_INSTRUCTIONS,
    dpi=_NPDES_DPI,
    text_pages=6,
    image_pages=1,
    summary=lambda p: {"permit_no": p.permit_no, "facility": p.facility_name},
)


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
    return cast(
        "NpdesExtraction",
        _extract_doc(
            _NPDES_SPEC,
            doc,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=text_pages,
        ),
    )


_SOS_SPEC = DocSpec(
    kind="sos",
    model=BusinessFiling,
    extraction_cls=SosExtraction,
    field="filing",
    instructions=SOS_INSTRUCTIONS,
    dpi=_SOS_DPI,
    text_pages=6,
    image_pages=6,
    summary=lambda f: {
        "entity": f.entity_name,
        "agent": f.registered_agent,
        "jurisdiction": f.jurisdiction,
    },
)


def extract_sos(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _SOS_DPI,
    settings: Settings | None = None,
    max_pages: int = 6,
) -> SosExtraction:
    """Extract a Secretary-of-State business filing (vision-primary)."""
    return cast(
        "SosExtraction",
        _extract_doc(
            _SOS_SPEC,
            doc,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=max_pages,
            image_pages=max_pages,
        ),
    )


PLAN_INSTRUCTIONS = """\
You are reading one sheet of a civil/site engineering plan set (an OpenDocument
Drawing). You are given (1) a low-resolution preview image for spatial context and
(2) the sheet's actual text labels — the titleblock, legend, and on-drawing call-
outs — which are AUTHORITATIVE (the preview is too small to read). Use the labels
as the source of truth. Record into the tool:
  * project_name; site_address; project_no.
  * sheet_id (e.g. a sheet number or drawing id); discipline (what the sheet
    depicts, e.g. "Grading & Storm Plan"); phase (e.g. "95% SPS Design");
    scale; status (e.g. "Not For Construction"); date if shown.
  * prepared_by: each design firm on the titleblock with its discipline
    (Civil / Architecture / MEP/Structure / Survey) and location if shown.
  * key_features: notable site/utility features from the LEGEND or callouts that
    say what the site contains — e.g. substation, transformer, electric easement,
    security fence, fiber duct bank, storm/sanitary/water mains, detention,
    building pads. Prefer distinctive features over generic ones.
  * summary: 1-3 sentences describing what this sheet shows and what the site is.
Rules: copy names exactly from the labels; do not invent firms or features not in
the labels; set confidence and add warnings where the labels are ambiguous.
"""


def extract_plan(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    odg: object | None = None,
    settings: Settings | None = None,
    max_labels: int = 140,
) -> PlanExtraction:
    """Extract a site-plan sheet from an ``.odg`` (text labels lead, thumbnail hints)."""
    from watermark.agent.extractor import StructuredExtractor
    from watermark.documents import OdgContent

    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=4096)
    content = odg if isinstance(odg, OdgContent) else read_odg(doc.path, max_labels=max_labels)

    log.info("extract.doc.start", doc_id=doc.doc_id, kind="plan", labels=len(content.labels))
    images = [content.thumbnail_png] if content.thumbnail_png else []
    plan = extractor.extract(
        SitePlan, instructions=PLAN_INSTRUCTIONS, images=images, context_text=content.label_text()
    )
    extraction = PlanExtraction(
        doc_id=doc.doc_id,
        source_path=str(doc.path),
        kind="plan",
        pages_read=[0],
        dpi=0,
        plan=plan,
        source_text_excerpt=content.label_text()[:600],
    )
    log.info(
        "extract.doc.done",
        doc_id=doc.doc_id,
        kind="plan",
        project=plan.project_name,
        discipline=plan.discipline,
        firms=len(plan.prepared_by),
        confidence=plan.confidence,
        warnings=len(plan.warnings),
    )
    return extraction


_EPA_SPEC = DocSpec(
    kind="epa",
    model=EpaPermitAction,
    extraction_cls=EpaExtraction,
    field="action",
    instructions=EPA_INSTRUCTIONS,
    dpi=_EPA_DPI,
    text_pages=3,
    image_pages=1,
    summary=lambda a: {"program": a.program, "permit_no": a.permit_no, "applicant": a.applicant},
)


def extract_epa(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _EPA_DPI,
    settings: Settings | None = None,
    text_pages: int = 3,
) -> EpaExtraction:
    """Extract an Ohio EPA / USACE permit action letter (text-first, page-1 image)."""
    return cast(
        "EpaExtraction",
        _extract_doc(
            _EPA_SPEC,
            doc,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=text_pages,
        ),
    )


_WETLAND_SPEC = DocSpec(
    kind="wetland",
    model=WetlandDetermination,
    extraction_cls=WetlandExtraction,
    field="determination",
    instructions=WETLAND_INSTRUCTIONS,
    dpi=_WETLAND_DPI,
    text_pages=2,
    image_pages=2,
    summary=lambda d: {"sampling_point": d.sampling_point, "is_wetland": d.is_wetland},
)


def extract_wetland(
    doc: SourceDocument,
    *,
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _WETLAND_DPI,
    settings: Settings | None = None,
    text_pages: int = 2,
) -> WetlandExtraction:
    """Extract a USACE Wetland Determination Data Form (image-first, both pages)."""
    return cast(
        "WetlandExtraction",
        _extract_doc(
            _WETLAND_SPEC,
            doc,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=text_pages,
        ),
    )


ENGINEERING_INSTRUCTIONS = """\
You are reading a civil / utility ENGINEERING record — an as-built (record)
drawing set, a construction plan set, or a component specification. It may be any
discipline: sanitary sewer / pump station, water main, stormwater, electrical,
structural. The pages are SCANNED drawings: the image is authoritative; any text
layer is unreliable or absent. Read the titleblock, the drawing index, the legend,
the schedules/tables (pump schedule, pipe schedule, equipment list), and the
on-drawing callouts. Record into the tool, GENERICALLY (do not force the data into
one discipline):
  * project_name; facility_name (the asset itself, e.g. "Indian Brook Pump
    Station"); record_type (as-built | record drawing | construction plans |
    specification); discipline (read it off the drawing: sanitary | water |
    stormwater | electrical | structural | ...); record_date (ISO if legible);
    project_no; site_address.
  * prepared_by: each design / engineering firm on the titleblock, with its
    discipline and location if shown.
  * sheets: the drawing index — each sheet's id (e.g. "C-1", "M-3", "1 of 4") and
    title. This is the IMPLEMENTATION-LAYOUT axis: how the set is organized.
  * components: the COMPONENT-SPECIFICATION axis. One entry per physical component
    the drawings install or specify — a pipe run (e.g. "forcemain"), a structure
    (wet well, manhole, vault), a pump, a valve, a tank, an electrical unit. For
    each: name; category (pipe | pump | structure | valve | tank | equipment |
    electrical | ...); quantity if stated; and specs: a list of {parameter, value,
    unit} read off the schedules / callouts — e.g. {parameter: "diameter",
    value: "8", unit: "in"}, {parameter: "material", value: "ductile iron"},
    {parameter: "capacity", value: "150", unit: "gpm"}, {parameter: "TDH",
    value: "45", unit: "ft"}, {parameter: "manufacturer", value: "Flygt"}.
  * design_parameters: system-level design figures NOT tied to one component —
    e.g. {parameter: "peak design flow", value: "1.2", unit: "MGD"},
    {parameter: "firm capacity", value: "~450", unit: "gpm"}. Same {parameter,
    value, unit} shape.
  * key_features: notable callouts worth surfacing; summary: 1-3 sentences on what
    the record documents and what the asset is.
Rules: figures come from the IMAGE, never a garbled text layer. Copy numbers,
sizes, and names exactly as printed; keep the value as printed (a figure, a
material, a model). Mark an APPROXIMATE numeric read with a leading "~" in value
(e.g. "~150") AND add a warning — never silently round. Leave a field null / a
list empty rather than inventing a component, spec, or firm. Set confidence and add
a warning for any schedule or callout you had to strain to read.
"""


_ENGINEERING_SPEC = DocSpec(
    kind="engineering",
    model=EngineeringRecord,
    extraction_cls=EngineeringExtraction,
    field="record",
    instructions=ENGINEERING_INSTRUCTIONS,
    dpi=_ENGINEERING_DPI,
    text_pages=12,
    image_pages=12,
    summary=lambda r: {
        "facility": r.facility_name,
        "discipline": r.discipline,
        "components": len(r.components),
        "sheets": len(r.sheets),
    },
    max_tokens=_DETAIL_MAX_TOKENS,
)


def extract_engineering(
    doc: SourceDocument,
    *,
    kind: str = "engineering",
    extractor: StructuredExtractor | None = None,
    pdf: PdfDocument | None = None,
    dpi: int = _ENGINEERING_DPI,
    settings: Settings | None = None,
    max_pages: int = 12,
) -> EngineeringExtraction:
    """Extract a civil/utility engineering record (as-built, plan set, or spec).

    Image-first across the drawing set's pages into a discipline-agnostic
    :class:`~watermark.models.EngineeringRecord` (issue #41). ``kind`` stamps the
    provenance / output filename — ``"engineering"`` generically, or a discipline
    alias such as ``"sanitary"`` — without changing what is read. ``pdf``/
    ``extractor`` are injectable for page reuse and for offline tests.
    """
    return cast(
        "EngineeringExtraction",
        _extract_doc(
            _ENGINEERING_SPEC,
            doc,
            kind=kind,
            extractor=extractor,
            pdf=pdf,
            dpi=dpi,
            settings=settings,
            text_pages=max_pages,
            image_pages=max_pages,
        ),
    )


def extract_sanitary(doc: SourceDocument, **kwargs: object) -> EngineeringExtraction:
    """Sanitary as-built / record drawing — :func:`extract_engineering`, kind=sanitary.

    A discipline alias so the artifact lands as ``<stem>.sanitary.yaml`` (issue #41);
    the read itself is the same generic engineering extraction.
    """
    return extract_engineering(doc, kind="sanitary", **kwargs)  # type: ignore[arg-type]


# Document-level kind dispatch (parallel to the page-level EXTRACTORS above).
DocumentExtractor = Callable[..., DocExtraction]
DOC_EXTRACTORS: dict[str, DocumentExtractor] = {
    "deed": extract_deed,
    "npdes": extract_npdes,
    "sos": extract_sos,
    "epa": extract_epa,
    "wetland": extract_wetland,
    "plan": extract_plan,
    "engineering": extract_engineering,
    "sanitary": extract_sanitary,
}


def extract_document(doc: SourceDocument, *, kind: str, **kwargs: object) -> DocExtraction:
    """Dispatch a document-level extraction to the handler for ``kind``."""
    if kind not in DOC_EXTRACTORS:
        raise ValueError(f"unknown document kind {kind!r}; known: {sorted(DOC_EXTRACTORS)}")
    return DOC_EXTRACTORS[kind](doc, **kwargs)


def save_doc_extraction(extraction: DocExtraction, *, settings: Settings | None = None) -> Path:
    """Write a document-level extraction under its collection sub-directory.

    The artifact mirrors its source's collection (see :func:`_collection_dir`),
    named ``<stem>.<kind>.yaml``.
    """
    settings = settings or get_settings()
    target = _collection_dir(extraction.source_path, settings)
    stem = Path(extraction.source_path).stem
    path = target / f"{stem}.{extraction.kind}.yaml"
    path.write_text(extraction.to_yaml(), encoding="utf-8")
    log.info("extract.saved", path=str(path))
    return path
