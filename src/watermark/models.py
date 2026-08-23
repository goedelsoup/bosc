"""Typed models for BOSC structured extractions.

These mirror the ``*.opc.yaml`` extraction files under ``data/extracted``.
The source scans are degraded, so many numbers are transcribed as *approximate*
(written ``~12345`` in YAML, which parses as a string). :data:`ApproxInt` /
:data:`Number` coerce those to numbers, and :class:`ApproxModel` records which
fields arrived approximate in a runtime ``.approximate`` sidecar so the marker is
not silently dropped at validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

import yaml
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

from watermark.provenance import Confidence, SourceKind


class _ApproxMarker:
    """Sentinel placed in an approximate-number type's ``Annotated`` metadata.

    Lets :class:`ApproxModel` tell *which* fields carry the ``~`` convention (so it
    can record which ones actually arrived approximate) without re-listing them by
    name. Pydantic preserves unrecognized metadata objects on ``FieldInfo.metadata``.
    """

    __slots__ = ()


_APPROX = _ApproxMarker()


def _coerce_number(value: Any) -> Any:
    """Coerce ``"~12345"`` / ``"12,345"`` style scalars to ``int``.

    Plain ints/floats pass through. ``None`` passes through. A ``bool`` is rejected
    (it is *not* a stray ``0``/``1`` — ``isinstance(True, int)`` is True, so without
    this it would silently become ``1``). A fractional string is **rounded**, not
    truncated (``"17.9"`` -> ``18``, ``"$108,307.89"`` -> ``108308``) — truncation
    would silently drop value. Anything unparseable is returned unchanged so Pydantic
    raises a clear error.
    """
    if isinstance(value, bool):
        raise ValueError("a boolean is not a valid number")
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lstrip("~").replace(",", "").replace("$", "")
        if cleaned == "":
            return None
        try:
            return round(float(cleaned))
        except ValueError:
            return value
    return value


# An int that tolerates the approximate ``~`` marker and thousands separators.
ApproxInt = Annotated[int, BeforeValidator(_coerce_number), _APPROX]
OptApproxInt = Annotated[int | None, BeforeValidator(_coerce_number), _APPROX]


def _coerce_number_keep(value: Any) -> Any:
    """Like :func:`_coerce_number` but preserves int-vs-float for line items.

    ``"~17.0"`` -> ``17.0`` (a unit rate), ``"~2,490"`` -> ``2490`` (a quantity).
    Numbers pass through unchanged so a printed ``17.0`` stays a float; a ``bool`` is
    rejected (see :func:`_coerce_number`).
    """
    if isinstance(value, bool):
        raise ValueError("a boolean is not a valid number")
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lstrip("~").replace(",", "").replace("$", "")
        if cleaned == "":
            return None
        try:
            return float(cleaned) if "." in cleaned else int(cleaned)
        except ValueError:
            return value
    return value


# A quantity / unit-rate / dollar amount that may be approximate; keeps int or float.
Number = Annotated[int | float | None, BeforeValidator(_coerce_number_keep), _APPROX]


def _approximate_fields(cls: type[BaseModel], data: Any) -> set[str]:
    """Names of this model's ``~``-typed fields whose raw input arrived approximate."""
    if not isinstance(data, dict):
        return set()
    found: set[str] = set()
    for name, field in cls.model_fields.items():
        if not any(isinstance(m, _ApproxMarker) for m in field.metadata):
            continue
        raw = data.get(name)
        if isinstance(raw, str) and raw.strip().startswith("~"):
            found.add(name)
    return found


class ApproxModel(BaseModel):
    """Base for models with approximate (``~``) numeric fields.

    Coercion strips the ``~`` to a plain number; this records *which* fields arrived
    approximate in a runtime sidecar (``.approximate``), so the marker is no longer
    silently dropped at validation (the data-discipline rule in CLAUDE.md). The sidecar
    is a :class:`~pydantic.PrivateAttr` — it never enters the JSON/tool schema or
    ``model_dump`` output, so it changes neither the LLM extraction contract nor the
    committed YAML shape. The source YAML keeps its literal ``~12345`` regardless.
    """

    _approximate: set[str] = PrivateAttr(default_factory=set)

    @model_validator(mode="wrap")
    @classmethod
    def _capture_approximate(cls, data: Any, handler: Any) -> Any:
        # mode="wrap" sees the raw input (still carrying the ``~``) before coercion,
        # then stamps the result of normal validation.
        approx = _approximate_fields(cls, data)
        obj = handler(data)
        if approx:
            obj._approximate |= approx
        return obj

    @property
    def approximate(self) -> set[str]:
        """Set of field names whose value was transcribed approximate (``~``)."""
        return self._approximate


def _as_str_list(value: Any) -> Any:
    """Coerce a scalar into a single-element list of strings.

    Models populated by the LLM occasionally return a free-text field (e.g.
    ``warnings`` or ``grantors``) as a bare string instead of a list. Wrap it
    rather than fail validation; an empty/whitespace string becomes ``[]``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v) for v in value]
    return value


# A list[str] that tolerates a bare scalar (wraps it) — for LLM-populated fields.
StrList = Annotated[list[str], BeforeValidator(_as_str_list)]


class OPCMeta(ApproxModel):
    """Top-level metadata block of an OPC extraction."""

    model_config = ConfigDict(extra="allow")

    program: str | None = None
    estimator: str | None = None
    basis: str | None = None
    date: str | None = None
    source_file: str | None = None
    pdf_pages: str | None = None
    contingency_and_inflation_pct: int | None = None
    summary_construction_total: OptApproxInt = None
    # How many sub-estimates the assembly was ASKED to cover (the swept page count). When set and
    # it exceeds the number actually assembled, a page silently dropped out — `analyze.reconcile`
    # turns that into a failing coverage finding so a truncated summary can't reconcile green off a
    # headline total derived from only the survivors (#1364). Absent on hand-authored summaries.
    expected_sub_estimates: int | None = None


class SectionSubtotals(ApproxModel):
    """Per-section construction subtotals. Corridors omit several sections."""

    model_config = ConfigDict(extra="allow")

    roadway: OptApproxInt = None
    erosion_control: OptApproxInt = None
    drainage: OptApproxInt = None
    pavement: OptApproxInt = None
    water_work: OptApproxInt = None
    lighting: OptApproxInt = None
    traffic_control: OptApproxInt = None
    landscaping: OptApproxInt = None
    right_of_way: OptApproxInt = None
    incidentals: OptApproxInt = None
    design_survey_inspection: OptApproxInt = None

    def total(self) -> int:
        """Sum of all present section subtotals."""
        return sum(v for v in self.model_dump().values() if isinstance(v, int))


class SubEstimate(ApproxModel):
    """A single roundabout or corridor sub-estimate."""

    model_config = ConfigDict(extra="allow")

    name: str
    pdf_page: int | None = None
    work: str | None = None
    # One free-text note. Transcriptions arrived under either ``note`` or ``notes`` (the LLM
    # picked inconsistently, so data silently split between them, #605) — collapsed to ``note``
    # with ``notes`` accepted as an input alias so every committed key still lands in one field.
    note: str | None = Field(default=None, validation_alias=AliasChoices("note", "notes"))
    type: str | None = None
    construction_subtotal: ApproxInt
    contingency_inflation_25pct: OptApproxInt = None
    total: ApproxInt
    section_subtotals: SectionSubtotals = Field(default_factory=SectionSubtotals)

    def reconciles(self, tolerance: int = 2) -> bool:
        """True if section subtotals roughly sum to the construction subtotal.

        Quantities are approximate, so a small absolute tolerance is allowed.
        """
        return abs(self.section_subtotals.total() - self.construction_subtotal) <= max(
            tolerance, round(self.construction_subtotal * 0.02)
        )


class OPCSummary(BaseModel):
    """A full ``*.summary.opc.yaml`` document."""

    model_config = ConfigDict(extra="allow")

    meta: OPCMeta = Field(default_factory=OPCMeta)
    section_schema: list[str] = Field(default_factory=list)
    item_reference: dict[str, str] = Field(default_factory=dict)
    sub_estimates: list[SubEstimate] = Field(default_factory=list)
    reconciliation: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> OPCSummary:
        """Load and validate a summary extraction from a YAML file."""
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def construction_total(self) -> int:
        """Sum of construction subtotals across all sub-estimates."""
        return sum(se.construction_subtotal for se in self.sub_estimates)

    def grand_total(self) -> int:
        """Sum of the (post-contingency) totals across all sub-estimates."""
        return sum(se.total for se in self.sub_estimates)


# ---------------------------------------------------------------------------
# Generic extraction target — a contractor-agnostic "Opinion of Probable Cost".
#
# An OPC is modeled as a title, a *dynamic* list of sections (each with line
# items and a subtotal), a list of markup lines (contingency / inflation /
# mobilization / ...), a construction subtotal, and a total. Nothing here is
# specific to one contractor's section taxonomy or markup convention — that
# knowledge lives in a format Profile (see watermark.profiles).
# ---------------------------------------------------------------------------


def _num(value: Any) -> float:
    """A Number coerced to float, treating None / non-numeric as 0.0."""
    return float(value) if isinstance(value, (int, float)) else 0.0


class LineItem(ApproxModel):
    """A single estimate line item read from a cost sheet."""

    model_config = ConfigDict(extra="allow")

    item_no: str | None = None  # contractor/agency item code, or a custom_ tag
    description: str
    quantity: Number = None
    unit: str | None = None  # e.g. LS, CY, SY, FT, EACH, GAL, SF, AC
    unit_amount: Number = None  # per-unit dollars
    total_amount: Number = None  # extended dollars
    note: str | None = None  # e.g. "qty inferred from total"


class EstimateSection(ApproxModel):
    """One section of an estimate, named as printed on the sheet."""

    model_config = ConfigDict(extra="allow")

    name: str  # the section name AS PRINTED (e.g. "ROADWAY", "Sitework")
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Number = None
    note: str | None = None

    def items_total(self) -> float:
        """Sum of line-item ``total_amount`` (0 if none / illegible)."""
        return sum(_num(i.total_amount) for i in self.line_items)

    @property
    def key(self) -> str:
        """A normalized key for cross-document comparison (lowercased, underscored)."""
        return "_".join(self.name.lower().split())


class MarkupLine(ApproxModel):
    """A markup/adjustment applied to the construction subtotal.

    Covers contingency, inflation, mobilization, escalation, etc. ``rate`` is the
    fraction of the construction subtotal when the line is a percentage.
    """

    model_config = ConfigDict(extra="allow")

    label: str
    rate: float | None = None  # e.g. 0.25 for a 25% line
    amount: Number = None


class Estimate(ApproxModel):
    """A contractor-agnostic Opinion of Probable Cost read from one sheet."""

    model_config = ConfigDict(extra="allow")

    # ``profile`` is set by the pipeline, not the model — hide it from the schema.
    EXTRACTION_EXCLUDE: ClassVar[tuple[str, ...]] = ("profile",)

    name: str
    profile: str | None = None  # id of the format profile that produced this
    sections: list[EstimateSection] = Field(default_factory=list)
    construction_subtotal: Number = None
    markups: list[MarkupLine] = Field(default_factory=list)
    total: Number = None
    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: list[str] = Field(default_factory=list)

    def section(self, name: str) -> EstimateSection | None:
        """Find a section by printed name or normalized key (case-insensitive)."""
        want = "_".join(name.lower().split())
        return next((s for s in self.sections if s.key == want), None)

    def sections_total(self) -> float:
        """Sum of section subtotals."""
        return sum(_num(s.subtotal) for s in self.sections)

    def markups_total(self) -> float:
        """Sum of markup amounts."""
        return sum(_num(m.amount) for m in self.markups)

    def has_line_items(self) -> bool:
        return any(s.line_items for s in self.sections)

    def reconciles(self, tolerance: int = 2) -> bool:
        """True if section subtotals roughly sum to the construction subtotal."""
        target = _num(self.construction_subtotal)
        return abs(self.sections_total() - target) <= max(tolerance, round(target * 0.02))


class PageExtraction(BaseModel):
    """One extracted estimate page, with provenance for review and audit."""

    model_config = ConfigDict(extra="allow")

    doc_id: str
    source_path: str
    page_index: int  # 0-based PDF page
    pdf_page: int  # 1-based, matches the printed sheet
    dpi: int
    estimate: Estimate
    source_text_excerpt: str = ""

    def to_yaml(self) -> str:
        """Serialize to YAML for writing under data/extracted (review artifact)."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Other document kinds — deeds and NPDES permits.
#
# Unlike OPC sheets (one estimate per page), these are *document-level*
# extractions read across several pages. Each kind is a self-contained model
# plus a thin provenance wrapper sharing :class:`DocExtraction`.
# ---------------------------------------------------------------------------


class _Extracted(ApproxModel):
    """Mixin: self-reported confidence + warnings for any extracted document."""

    model_config = ConfigDict(extra="allow")

    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: StrList = Field(default_factory=list)


class Deed(_Extracted):
    """A recorded land instrument (deed, easement, etc.)."""

    instrument_type: str | None = None  # e.g. "General Warranty Deed", "Quitclaim"
    instrument_no: str | None = None  # recorder instrument / document number
    recording_date: str | None = None  # ISO date if legible
    grantors: StrList = Field(default_factory=list)  # party conveying
    grantees: StrList = Field(default_factory=list)  # party receiving
    consideration: Number = None  # stated dollar consideration
    parcel_ids: StrList = Field(default_factory=list)  # auditor/parcel numbers
    county: str | None = None
    legal_description: str | None = None  # short excerpt / summary, not the full metes-and-bounds
    note: str | None = None


class NpdesPermit(_Extracted):
    """An Ohio EPA NPDES discharge permit / fact sheet."""

    facility_name: str | None = None
    permit_no: str | None = None  # Ohio EPA permit no, e.g. 2PH00006*LD
    permit_action: str | None = None  # renewal | modification | new | draft
    # Ohio EPA writes the party as "Applicant" on a fact sheet and "Permittee" in the permit
    # body; they are the same party, and #1994's Sidney read kept the permit's own word
    # (`permittee: City of Sidney`). Re-keying the DATA to `applicant:` would erase the source's
    # vocabulary to suit a model — so the MODEL learns the synonym instead, and the entity
    # graph's `operates` edge stops depending on which face page a transcriber was reading.
    # `applicant` wins when both are present. NOT aliased: `applicant_of_record`, which on that
    # same file is a DIFFERENT party ("Mayor and Council, City of Sidney") — folding it in would
    # misattribute the operator.
    applicant: str | None = Field(
        default=None, validation_alias=AliasChoices("applicant", "permittee")
    )
    application_no: str | None = None  # e.g. OH0037338
    public_notice_no: str | None = None
    public_notice_date: str | None = None
    comment_period_end: str | None = None
    facility_address: str | None = None
    discharge_address: str | None = None
    receiving_water: str | None = None
    stream_network: str | None = None  # downstream chain to a major water body
    outfalls: StrList = Field(default_factory=list)
    note: str | None = None


class BusinessFiling(_Extracted):
    """A Secretary-of-State business filing (LLC formation / registration).

    The entity-control genre: who organized the LLC, its statutory (registered)
    agent and address, and its formation jurisdiction. A shared agent address
    across entities is the strongest shell-pattern signal available from public
    SoS records (it does not reveal beneficial ownership).
    """

    entity_name: str | None = None
    filing_id: str | None = None  # SoS document / filing number (the "DOC ID")
    filing_type: str | None = None  # e.g. "Articles of Organization", "Registration of Foreign LLC"
    entity_type: str | None = None  # domestic LLC | foreign LLC | corporation | ...
    jurisdiction: str | None = None  # formation state (e.g. Delaware, Ohio)
    filing_date: str | None = None
    effective_date: str | None = None
    registered_agent: str | None = None  # statutory agent name
    agent_address: str | None = None
    organizer: str | None = None  # organizer / authorized representative / signatory
    organizer_address: str | None = None
    principal_address: str | None = None  # principal office, if stated
    officers: StrList = Field(default_factory=list)  # members/managers, if disclosed
    note: str | None = None


class EpaPermitAction(_Extracted):
    """An Ohio EPA / USACE surface-water permit action or correspondence letter.

    The ``permits/`` collection is largely a stream of Division of Surface Water
    actions on one project — Permits-to-Install (sanitary sewer / waterline),
    401 Water Quality Certifications, Isolated Wetland Permits, Section 404 — plus
    dated agency correspondence (incomplete notices, comment letters). This model
    captures the common letter header (the "Re:" block) and the action taken.
    """

    agency: str | None = None  # e.g. "Ohio EPA", "U.S. Army Corps of Engineers"
    program: str | None = None  # PTI | 401 WQC | Isolated Wetland Permit | Section 404 | ...
    permit_no: str | None = None  # e.g. DSWPTI-260294, DSW401252260W, Ohio EPA ID 252260W
    action: str | None = None  # issued | approved | denied | incomplete | comments | application
    action_date: str | None = None  # the letter date (ISO)
    plans_received_date: str | None = None
    expiration_date: str | None = None
    applicant: str | None = None
    applicant_address: str | None = None
    contact_name: str | None = None  # the addressee / submitter (often counsel or engineer)
    contact_email: str | None = None
    contact_firm: str | None = None  # e.g. Vorys, EMH&T
    project_name: str | None = None  # e.g. "Project Bosc", "BOSC-1A"
    site_address: str | None = None
    affected_resource: str | None = (
        None  # sanitary sewer | isolated wetland | receiving water | ...
    )
    parcel_ids: StrList = Field(default_factory=list)
    note: str | None = None


class OrderObligation(ApproxModel):
    """One requirement inside an enforcement instrument, with its deadline."""

    model_config = ConfigDict(extra="allow")

    requirement: str | None = None  # what the order requires, briefly
    deadline: str | None = None  # ISO date if stated (e.g. an SSO-elimination date)
    status: str | None = None  # met | missed | extended | pending, if the record says


class EnforcementOrder(_Extracted):
    """A regulatory enforcement instrument or its correspondence (#1746).

    The wastewater-enforcement genre: a federal consent decree, an OEPA Director's
    Final Findings and Orders (DFFO) / modified DFFO, an extension or closure
    letter, a notice of violation. Captures the instrument header, the parties,
    the obligations with their deadlines, and the penalty terms — the fields the
    enforcement timeline reads. Distinct from :class:`EpaPermitAction` (a permit
    action on an application), this is the compliance/orders genre.
    """

    agency: str | None = None  # e.g. "Ohio EPA", "U.S. EPA / DOJ"
    instrument: str | None = (
        None  # consent decree | DFFO | modified DFFO | extension letter | closure notice | NOV
    )
    case_no: str | None = None  # docket / civil-action / journal number as printed
    respondent: str | None = None  # the ordered party (e.g. "Allen County Commissioners")
    facility: str | None = None  # the facility/system the order concerns
    permit_no: str | None = None  # associated NPDES / permit id, if referenced
    issued_date: str | None = None  # ISO — signature / journalization / letter date
    effective_date: str | None = None
    supersedes: str | None = None  # the instrument this modifies or extends, if stated
    obligations: list[OrderObligation] = Field(default_factory=list)
    penalty_usd: Number = None  # civil penalty assessed, if any
    stipulated_penalties: str | None = None  # stipulated-penalty terms, briefly
    status: str | None = None  # active | modified | terminated | closed
    summary: str | None = None  # 1-3 sentences on what the instrument does
    note: str | None = None


class InspectionObservation(ApproxModel):
    """One numbered item from an inspection letter — and WHICH list it came from.

    The distinction is the whole reason this genre exists. An Ohio EPA inspection letter
    prints its numbered items under separate headings, and says so in the document's own
    words: *"The recommendation(s) set out below are not Orders. The recommendations are
    offered by Ohio EPA in an effort to provide compliance assistance to your facility."*
    A finding records what the inspector saw; a recommendation is advisory; a violation
    or deficiency is neither. Flattening them into one list — or into
    :class:`OrderObligation`, which models a REQUIREMENT — would publish advice as though
    it were an enforceable term.
    """

    model_config = ConfigDict(extra="allow")

    kind: str | None = None  # finding | recommendation | violation | deficiency | requested action
    text: str | None = None  # the item as printed, or a close paraphrase
    number: str | None = None  # the item's printed number within its list, if numbered
    deadline: str | None = None  # only where the item itself states one


class ComplianceInspection(_Extracted):
    """An agency inspection or compliance-review report (#2077).

    The inspection genre: an Ohio EPA Division of Surface Water inspection letter and the
    EPA-form report it encloses. Distinct from :class:`EnforcementOrder` — an inspection
    IMPOSES NOTHING. It records a visit, what was observed, and what the agency suggests
    or requires next; the enforcement instrument, if one follows, is a separate document.
    Distinct also from :class:`NoticeOfCommencement`, which despite the name is an Ohio
    R.C. 1311.04 mechanic's-lien filing and unrelated.

    The enclosed report form carries two coded fields worth keeping structured across a
    run of inspections: the inspection TYPE (``CEI``, ``PCI``, ``PAI``, …) and the
    ``Sig. Non-Compliance`` box, which is the agency's own SNC determination at the time
    of the visit rather than a reading of the effluent data.
    """

    agency: str | None = None  # e.g. "Ohio EPA, Division of Surface Water"
    district: str | None = None  # e.g. "Northwest District Office"
    program: str | None = None  # NPDES | NPDES-Biosolids | Pretreatment | CSO, as printed
    inspection_type: str | None = (
        None  # compliance evaluation | reconnaissance | pretreatment compliance |
        # performance audit | minimum controls | sewer overflow, as printed
    )
    type_code: str | None = None  # the report form's coded type (e.g. "CEI"), if present
    facility: str | None = None
    facility_address: str | None = None
    permit_no: str | None = None  # Ohio permit id (e.g. 2PE00000)
    npdes_id: str | None = None  # federal NPDES id (e.g. OH0026069), if printed
    county: str | None = None
    inspection_date: str | None = None  # ISO — the date of the VISIT
    report_date: str | None = None  # ISO — the date of the transmitting letter
    entry_time: str | None = None  # as printed on the report form
    exit_time: str | None = None
    inspectors: StrList = Field(default_factory=list)  # agency personnel conducting it
    facility_representatives: StrList = Field(
        default_factory=list
    )  # who was present for the facility
    significant_noncompliance: bool | None = (
        None  # the form's Sig. Non-Compliance box — None when the form is absent or the box unread
    )
    units_in_service: str | None = None  # the plant's operating state as recorded, if stated
    observations: list[InspectionObservation] = Field(default_factory=list)
    summary: str | None = None  # 1-3 sentences on what the inspection found
    note: str | None = None


class ProgressProject(ApproxModel):
    """One named project a compliance progress report tracks across reporting periods."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None  # the project as the report names it (e.g. "CMOM Plan")
    status: str | None = None  # what the report says of it this period
    next_period: str | None = None  # the projection of work for the NEXT period, if given


class DischargeEvent(ApproxModel):
    """One CSO / SSO / bypass / unpermitted discharge a progress report inventories.

    Paragraph 33(f) of the Lima decree requires "a summary of all CSO Discharges, SSOs,
    Bypasses, and other unpermitted discharges occurring within the reporting period
    including the actual or estimated frequency, duration and volume of each". That makes
    a run of these reports a SELF-REPORTED discharge series, which no other genre in this
    corpus carries — the DMR feed is permit-limit monitoring, not overflow events.
    """

    model_config = ConfigDict(extra="allow")

    kind: str | None = None  # CSO | SSO | bypass | unpermitted discharge, as the report classes it
    location: str | None = None  # outfall id / street location as printed
    date: str | None = None  # ISO if a single dated event
    frequency: str | None = None  # e.g. "3 events" — as printed, actual or estimated
    duration: str | None = None
    volume: str | None = None  # keep the printed units; do NOT normalize
    estimated: bool | None = (
        None  # True where the report itself says estimated rather than measured
    )
    note: str | None = None


class ComplianceProgressReport(_Extracted):
    """A periodic progress report filed UNDER an enforcement instrument (#2079).

    The Lima consent decree's paragraph 33 requires a report every January 31 and July 31
    "until termination", and the filings follow its lettered structure exactly. This genre
    is deliberately NOT :class:`EnforcementOrder`: a progress report reports *against*
    obligations rather than imposing them, and reading one as an order would publish a
    near-duplicate of the decree it answers — nine near-duplicates, in Lima's case.

    It is also not :class:`ComplianceInspection`: that genre is the AGENCY visiting the
    facility, this is the RESPONDENT reporting on itself. The difference matters to how a
    reader weighs it, so the two never share a bucket.
    """

    agency: str | None = None  # the recipients (e.g. "U.S. EPA Region 5 / Ohio EPA")
    instrument: str | None = None  # the order reported under (e.g. "consent decree")
    case_no: str | None = None  # the docket of that instrument, so this joins it
    paragraph: str | None = None  # the reporting clause (e.g. "33")
    respondent: str | None = None  # the party filing (e.g. "City of Lima")
    facility: str | None = None
    permit_no: str | None = None
    report_date: str | None = None  # ISO — when filed/received
    period_start: str | None = None  # ISO — the reporting period this covers
    period_end: str | None = None
    deadlines_status: str | None = None  # clause (a): terms due this period and whether met
    noncompliance_reasons: str | None = None  # clause (a): the stated reasons, if any
    projects: list[ProgressProject] = Field(default_factory=list)  # clause (b)
    agency_contacts: StrList = Field(
        default_factory=list
    )  # clause (d): dated deliverables/contacts
    permit_exceedances: StrList = Field(
        default_factory=list
    )  # clause (e), one entry per exceedance
    discharge_events: list[DischargeEvent] = Field(default_factory=list)  # clause (f)
    summary: str | None = None
    note: str | None = None


class FinanceAward(_Extracted):
    """A public-finance award — a loan, grant, or cooperative agreement (#1746).

    The project-financing genre: WPCLF / OWDA loans, principal-forgiveness
    awards, federal grants (FEMA FMA, EPA), and their applications. Captures the
    program, the instrument, the money, and the project it funds — the fields a
    ratepayer-burden or capacity-financing read needs.
    """

    program: str | None = None  # e.g. "WPCLF", "OWDA", "FEMA FMA"
    agency: str | None = None  # awarding body (e.g. "Ohio EPA DEFA", "OWDA", "FEMA")
    instrument: str | None = (
        None  # loan | principal-forgiveness loan | grant | cooperative agreement | application
    )
    award_no: str | None = None  # loan / grant / agreement number as printed
    borrower: str | None = None  # borrower / recipient / grantee
    project_name: str | None = None  # the funded project
    facility: str | None = None  # the facility the project serves, if named
    amount_usd: Number = None  # face amount (loan principal / grant total)
    principal_forgiveness_usd: Number = None
    interest_rate_pct: float | None = None
    term_years: Number = None
    application_date: str | None = None  # ISO
    award_date: str | None = None  # ISO — award / agreement execution date
    first_payment_date: str | None = None
    repayment_source: str | None = None  # dedicated repayment (e.g. "sewer revenue funds")
    resolution_refs: StrList = Field(default_factory=list)  # authorizing resolutions as printed
    engineer: str | None = None  # consulting engineer of record, if named
    note: str | None = None


class WetlandDetermination(_Extracted):
    """A USACE Wetland Determination Data Form (routine on-site delineation).

    A field botanist's point-sample worksheet attached to a Section 404 / 401
    delineation: it records ONE sampling point and the three regulatory criteria —
    hydrophytic vegetation, hydric soil, wetland hydrology — that together decide
    whether the sampled area is a wetland. The vegetation/soil strata tables are
    dense supporting detail; the research-relevant facts are the location, the
    applicant, the sampling point, and the four determinations.
    """

    project_site: str | None = None  # "Project/Site"
    applicant: str | None = None  # "Applicant/Owner"
    investigators: StrList = Field(default_factory=list)
    city_county: str | None = None  # "City/County" as printed, e.g. "Sugar Creek Township/Allen"
    state: str | None = None
    region: str | None = None  # the ACE regional supplement (e.g. "Midwest")
    sampling_date: str | None = None  # ISO yyyy-mm-dd
    sampling_point: str | None = None  # the point label, e.g. WD-1, WE-1
    landform: str | None = None
    slope_pct: float | None = None
    latitude: float | None = None  # decimal degrees
    longitude: float | None = None  # decimal degrees (western Ohio ~ -84, negative)
    datum: str | None = None
    soil_map_unit: str | None = None
    nwi_classification: str | None = None
    # SUMMARY OF FINDINGS — each true/false from the checked box; null if illegible.
    hydrophytic_vegetation_present: bool | None = None
    hydric_soil_present: bool | None = None
    wetland_hydrology_present: bool | None = None
    is_wetland: bool | None = None  # "Is the Sampled Area within a Wetland?"
    dominant_species: StrList = Field(default_factory=list)
    note: str | None = None


class NoticeOfCommencement(_Extracted):
    """An Ohio R.C. 1311.04 Notice of Commencement (mechanic's-lien-priority filing).

    Filed by the property owner/lessee (not the contractor) to start the
    notice-of-furnishing clock ahead of construction. Distinct from a
    :class:`Deed`: it names a project/footprint, an original contractor, and a
    contract-execution date rather than a conveyance.
    """

    project_name: str | None = None
    site_address: str | None = None
    legal_description: str | None = (
        None  # item 1's short summary; full metes-and-bounds is a separate Exhibit
    )
    building_footprint_sf: Number = None  # stated building footprint, sq ft
    parcel_ids: StrList = Field(default_factory=list)  # item 1's APN/parcel list
    improvement_description: str | None = None  # item 2
    owner_lessee: str | None = (
        None  # item 3: name/address/capacity of the party contracting for the improvement
    )
    fee_owner: str | None = None  # item 4, only if stated as different from owner_lessee
    designee: str | None = None  # item 5, only if stated as different from owner_lessee
    original_contractors: StrList = Field(
        default_factory=list
    )  # item 6, one entry per contractor as printed
    contract_execution_date: str | None = None  # item 7, ISO yyyy-mm-dd
    lending_institutions: StrList = Field(default_factory=list)  # item 8
    surety: str | None = None  # item 9
    instrument_no: str | None = None
    recording_date: str | None = None  # ISO date if legible
    notarized_date: str | None = None  # date sworn/subscribed before the notary
    preparer: str | None = None
    county: str | None = None
    note: str | None = None


class DesignFirm(BaseModel):
    """A firm on a plan's titleblock, with its discipline."""

    model_config = ConfigDict(extra="allow")

    name: str
    discipline: str | None = None  # Civil | Architecture | MEP/Structure | Survey | ...
    location: str | None = None


class SitePlan(_Extracted):
    """A civil/site engineering drawing sheet (read from an ``.odg``).

    The titleblock and legend carry the structural content: project, sheet,
    discipline, scale, phase, the design team, and the legend's utility/site
    features (which reveal what the site contains — e.g. a substation).
    """

    project_name: str | None = None
    sheet_id: str | None = None  # e.g. LMA1A-95-SPS / sheet number
    discipline: str | None = None  # e.g. "Grading & Storm Plan"
    phase: str | None = None  # e.g. "95% SPS Design"
    scale: str | None = None
    project_no: str | None = None
    site_address: str | None = None
    date: str | None = None
    status: str | None = None  # e.g. "Not For Construction"
    prepared_by: list[DesignFirm] = Field(default_factory=list)
    key_features: StrList = Field(default_factory=list)  # legend/site features of note
    note: str | None = None
    summary: str | None = None  # short prose description of what the sheet shows


class SpecItem(BaseModel):
    """One named specification or design parameter read off an engineering record.

    Deliberately stringly-typed in ``value`` so the same field carries anything a
    drawing states: a figure ("8", "~150"), a material ("ductile iron"), a model
    ("Flygt NP-3153"), a rating ("460V/3ph"). Keep the ``~`` marker for an
    approximate read (the repo's ``~12345`` convention) rather than dropping it.
    """

    model_config = ConfigDict(extra="allow")

    parameter: str  # e.g. "diameter", "firm capacity", "peak design flow", "material"
    value: str | None = None  # as printed; numeric reads keep the ~ approximate marker
    unit: str | None = None  # e.g. "in", "gpm", "ft TDH", "MGD", "hp"


class ComponentSpec(BaseModel):
    """An installed/specified component on an engineering record.

    The *component-specification* axis (issue #41): each physical component — a
    pipe run, a pump, a structure, a valve, an electrical unit — with its own
    :class:`SpecItem` list, so the schema never hardcodes per-discipline fields
    (no fixed ``forcemain_size`` / ``pump_capacity``).
    """

    model_config = ConfigDict(extra="allow")

    name: str  # e.g. "forcemain", "wet well", "Pump No. 1", "transformer"
    category: str | None = (
        None  # pipe | pump | structure | valve | tank | equipment | electrical | ...
    )
    quantity: str | None = None  # as printed, e.g. "2", "~350 LF"
    specs: list[SpecItem] = Field(default_factory=list)
    note: str | None = None


class SheetRef(BaseModel):
    """One sheet in a drawing set's index — the *implementation-layout* axis."""

    model_config = ConfigDict(extra="allow")

    sheet_id: str | None = None  # e.g. "C-1", "M-3", "1 of 4"
    title: str | None = None  # e.g. "Pump Station Plan & Sections"


class EngineeringRecord(_Extracted):
    """A civil/utility engineering record — as-built, record drawing, plan set, or
    component specification — read from a scanned drawing set.

    **Discipline-agnostic by design (issue #41).** The same model carries a sanitary
    pump-station as-built, a water-main plan, a stormwater detail, or an electrical
    one-line; the discipline is *read off the drawing*, not baked into the schema.
    Two flexible axes the schema deliberately does NOT flatten into fixed fields:
    ``components`` (the component-specification axis — each component with its specs)
    and ``sheets`` + ``design_parameters`` (the implementation-layout axis).
    """

    project_name: str | None = None
    facility_name: str | None = None  # the asset, e.g. "Indian Brook Pump Station"
    record_type: str | None = None  # as-built | record drawing | construction plans | specification
    discipline: str | None = None  # sanitary | water | stormwater | electrical | structural | ...
    record_date: str | None = None  # ISO if legible (the as-built / record-drawing date)
    project_no: str | None = None
    site_address: str | None = None
    prepared_by: list[DesignFirm] = Field(default_factory=list)
    sheets: list[SheetRef] = Field(default_factory=list)  # the drawing index / sheet layout
    components: list[ComponentSpec] = Field(default_factory=list)  # the component-spec axis
    design_parameters: list[SpecItem] = Field(default_factory=list)  # design flows / capacities
    key_features: StrList = Field(default_factory=list)  # notable callouts of note
    summary: str | None = None  # short prose description of what the record documents
    note: str | None = None


class DocExtraction(BaseModel):
    """Provenance shared by document-level extractions."""

    model_config = ConfigDict(extra="allow")

    doc_id: str
    source_path: str
    kind: str
    pages_read: list[int] = Field(default_factory=list)  # 0-based pages consulted (text + images)
    # 0-based subset actually rendered as images and sent to the vision model. For a
    # text-primary read this is far smaller than pages_read (e.g. npdes: 1 vs 6) (#613).
    image_pages_read: list[int] = Field(default_factory=list)
    dpi: int
    source_text_excerpt: str = ""

    def to_yaml(self) -> str:
        """Serialize to YAML for writing under data/extracted (review artifact)."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False, allow_unicode=True)


class DeedExtraction(DocExtraction):
    deed: Deed


class NpdesExtraction(DocExtraction):
    permit: NpdesPermit


# The corpus root, as it appears inside a committed extraction's source reference.
_DOC_ANCHOR = "data/documents/"

# The four keys that exist ONLY because a page was rasterized and handed to the vision model
# (``watermark.agent.extractor.StructuredExtractor``) — i.e. ``DocExtraction``'s required set,
# written out literally rather than derived from ``model_fields[...].is_required()`` so that
# adding a required field to ``DocExtraction`` cannot silently re-route committed transcriptions
# into a genre they were never checked against.
RENDER_ENVELOPE_KEYS = frozenset({"doc_id", "source_path", "kind", "dpi"})


class SourceRef(BaseModel):
    """One committed source document a hand transcription was read from.

    Normalized on READ from the conventions already committed under ``data/extracted/**``; the
    artifacts keep their own bytes. Each convention carries something the others do not — a
    sha256 digest, a reading order, a role name — and ``data/extracted/**`` is reviewed
    evidence, not a schema's scratch space, so nothing is rewritten to make a model happy.
    """

    model_config = ConfigDict(extra="allow")

    path: str  # repo-relative, under data/documents/
    role: str | None = None  # the key it was filed under: "permit", "draft_pn_and_fact_sheet"
    sha256: str | None = None  # chain-of-custody digest, where the artifact recorded one
    url: str | None = None  # where the bytes were captured from


def _coerce_source_refs(raw: Any, role: str | None = None) -> list[SourceRef]:
    """Normalize the committed provenance conventions to one list.

    ``{name: {path, sha256, url}}`` (``oepa/sidney/1PD00009.npdes.yaml`` — a permit AND its
    draft-PN fact sheet, each with a digest), ``[path, path]``
    (``regulatory/ohc000006-construction-stormwater-gp.yaml``), and a bare string are all
    accepted. Nothing is invented from any of them: a convention that records no digest yields
    a ``SourceRef`` with no digest.
    """
    out: list[SourceRef] = []
    if isinstance(raw, str):
        out.append(SourceRef(path=raw, role=role))
    elif isinstance(raw, dict):
        for name, body in raw.items():
            if isinstance(body, str):
                out.append(SourceRef(path=body, role=str(name)))
            elif isinstance(body, dict) and isinstance(body.get("path"), str):
                out.append(SourceRef(**{**body, "role": str(name)}))
    elif isinstance(raw, list):
        for item in raw:
            out.extend(_coerce_source_refs(item, role))
    return out


class TranscribedExtraction(BaseModel):
    """Provenance envelope for a HAND TRANSCRIPTION — the peer of :class:`DocExtraction`.

    ``DocExtraction``'s ``doc_id`` / ``kind`` / ``dpi`` describe a page RENDERED at a DPI and
    sent to the vision model. A transcription was never rendered, so those fields have **no true
    value**, and this envelope declares none of them: a synthetic ``doc_id`` or a ``dpi: 300``
    would assert a method that did not happen, which the corpus's chain-of-custody rule forbids
    ("prefer omission over invention", root ``CLAUDE.md``).

    Declaring nothing is not enough on its own, though, or this is ``extra="allow"`` with extra
    steps. So it requires the assertion a transcription CAN honestly make in place of the render
    assertion it cannot: **at least one committed source under ``data/documents/``**. That is
    exactly the join a dropped file loses (#1994), and requiring it stops this envelope from
    becoming a validation bypass for any dict that happens to key ``permit:``.

    It also refuses a render receipt outright. The tree already contains the failure this
    prevents: ``oepa/van-wert/2GC08872.approval.npdes.yaml`` opens "HAND-READ, not a vision
    extraction … nothing was OCR'd" and then carries ``dpi: 150``, because the type it was
    written against demanded one. A transcription carrying a partial receipt is either a real
    render whose extractor died mid-write (route it to ``npdes`` and let it fail loudly) or a
    false receipt — never a thing this class should quietly accept.
    """

    model_config = ConfigDict(extra="allow")

    kind: str | None = None  # the file's own self-description, e.g. `general_permit`
    source_path: str | None = None  # the primary instrument, when the file names one
    sources: list[SourceRef] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _gather_sources(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("sources"):
            return data
        found: list[SourceRef] = []
        # The block is read FIRST so a role and a digest survive when `source_path` names the
        # same file — Sidney names its permit in both places, and only `meta.sources` has the
        # sha256.
        for block in ("meta", "provenance"):
            if isinstance(body := data.get(block), dict):
                found.extend(_coerce_source_refs(body.get("sources")))
        if isinstance(data.get("source_path"), str):
            found.append(SourceRef(path=data["source_path"], role="source_path"))
        # First mention of a path wins, which is why the blocks are read before `source_path`:
        # the richer reference (role + digest) is the one that survives.
        seen: set[str] = set()
        uniq: list[SourceRef] = []
        for ref in found:
            if ref.path in seen:
                continue
            seen.add(ref.path)
            uniq.append(ref)
        return {**data, "sources": [s.model_dump() for s in uniq]}

    @model_validator(mode="after")
    def _requires_a_committed_source(self) -> TranscribedExtraction:
        if not any(s.path.startswith(_DOC_ANCHOR) for s in self.sources):
            raise ValueError(
                "a transcription must name at least one committed source under "
                "data/documents/ (meta.sources, provenance.sources, or a top-level "
                "source_path) — see TranscribedExtraction"
            )
        return self

    @model_validator(mode="after")
    def _carries_no_render_receipt(self) -> TranscribedExtraction:
        extra = self.__pydantic_extra__ or {}
        asserted = sorted(
            k for k in ("doc_id", "dpi", "pages_read", "image_pages_read") if k in extra
        )
        if asserted:
            raise ValueError(
                f"asserts a vision render ({', '.join(asserted)}) but was classified as a hand "
                "transcription. A render receipt is all-or-nothing: if a page really was "
                "rasterized, carry the full DocExtraction envelope; if it was hand-read from a "
                "text layer, omit doc_id/dpi/pages_read entirely. Do NOT invent a dpi to satisfy "
                "a schema."
            )
        return self


class NpdesTranscription(TranscribedExtraction):
    permit: NpdesPermit


class InstrumentProvenance(BaseModel):
    """Provenance block on a framework instrument read from its own text layer.

    A statewide general permit routinely has MORE THAN ONE source (the permit and its Response
    to Comments), which a single ``source_path`` cannot express at all.
    """

    model_config = ConfigDict(extra="allow")

    sources: StrList = Field(default_factory=list)
    content_verified: str | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def _at_least_one_source(self) -> InstrumentProvenance:
        if not self.sources:
            raise ValueError("provenance.sources must name at least one source document")
        return self


class GeneralPermit(_Extracted):
    """A statewide / framework general permit — the instrument a site's coverage is issued
    *under*, not a facility discharge record (Ohio EPA OHC000006, the construction stormwater
    GP). It has no facility, no applicant and no receiving water BY CONSTRUCTION, and that is
    the point of the separate type: routed to :class:`NpdesPermit` it is one transcribed
    ``facility_name`` away from registering ``npdes:OHC000006`` as a discharger, putting a
    rulemaking instrument in the same namespace as the Lima WWTP.
    """

    permit_no: str
    title: str | None = None
    issuing_agency: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    authority: str | None = None
    note: str | None = None


class GeneralPermitExtraction(TranscribedExtraction):
    """A framework general permit transcribed from its own (clean, non-OCR) text layer.

    Inherits :class:`TranscribedExtraction` rather than restating its own envelope, because it
    is one: a text-layer read with no render behind it. That inheritance is the whole point —
    as a bare model it enforced only "``provenance.sources`` is non-empty", so it accepted a
    source that names no committed file *and* a fabricated render receipt
    (``dpi``/``doc_id``/``pages_read``) sitting beside a document whose entire premise is that
    nothing was rasterized. Its sibling ``NpdesTranscription`` refused both, and there is no
    reason the framework-instrument genre should be the loose one.

    ``_gather_sources`` already reads a ``provenance.sources`` list, so the multi-source shape a
    general permit needs (the permit **and** its Response to Comments) is preserved exactly;
    what changes is that each of those sources must now anchor under ``data/documents/``.
    """

    kind: Literal["general_permit"]  # narrows the base's `str | None`
    subject: str
    provenance: InstrumentProvenance
    permit: GeneralPermit


class DmrMeta(BaseModel):
    """Provenance block on an ECHO DMR effluent-record pull (``watermark dmr``)."""

    model_config = ConfigDict(extra="allow")

    subject: str
    source: str
    regenerate: str
    discipline: str


class DmrPermit(BaseModel):
    """The permit identity + reporting window on a DMR pull."""

    model_config = ConfigDict(extra="allow")

    npdes_id: str
    name: str | None = None
    permit_type: str | None = None
    permit_status: str | None = None
    major_minor: str | None = None
    snc_status: str | None = None
    window: str  # "YYYY-MM-DD..YYYY-MM-DD"


class DmrDischargeSummary(BaseModel):
    """The computed receiving-water read: actual flow vs. design, exceedance count."""

    model_config = ConfigDict(extra="allow")

    design_flow_mgd: float | None = None
    design_flow_cfs: float | None = None
    primary_outfall: str | None = None
    n_flow_months: int
    actual_flow_mean_mgd: float | None = None
    actual_flow_mean_cfs: float | None = None
    actual_flow_min_mgd: float | None = None
    actual_flow_max_mgd: float | None = None
    flow_pct_of_design: float | None = None
    # Overflow (CSO + SSO) outfalls — param 74063 covers both; renamed from `cso_outfalls`
    # (WS-25 / #1625). `active_overflow_outfalls` (the subset with >= 1 reported non-null volume)
    # is optional so a committed snapshot predating the field validates.
    overflow_outfalls: int
    active_overflow_outfalls: int | None = None
    reported_exceedances: int


class DmrSeasonality(BaseModel):
    """The seasonality shape of the primary outfall's monthly flow (``dmr_document()``, #1678).

    Optional (defaulted ``None`` on the parent :class:`DmrExtraction`) so a committed DMR artifact
    generated before the seasonality block existed still validates — the same additive discipline
    that made :attr:`DmrDischargeSummary.active_overflow_outfalls` optional. But a block that IS
    present must carry its provenance quad (``source``/``citation``/``confidence``/``asof``), so
    those are required — ``dmr_document()`` always emits them, and no committed artifact predates
    them. ``extra="allow"`` mirrors the connector's own
    :class:`~watermark.hydrology.connectors.echo_dmr.FlowSeasonality`. A metric value can genuinely
    be ``None`` (a single-season or empty window), so those types stay optional.
    """

    model_config = ConfigDict(extra="allow")

    n_months: int
    warm_months: list[int]
    warm_mean_mgd: float | None = None
    cool_mean_mgd: float | None = None
    warm_ratio: float | None = None
    peak_month: int | None = None
    peak_mean_mgd: float | None = None
    cv: float | None = None
    # Provenance quad (required on a present block; the metric is a `derived`, `medium`-confidence
    # [inference] shape over the permittee's [verified] monthly-average flow).
    source: SourceKind
    citation: str | None
    confidence: Confidence
    asof: str | None


class DmrFlowSample(BaseModel):
    """One reported monthly flow value for the primary (continuous-discharge) outfall.

    Every field is a key ``dmr_document()`` always emits, so each is required (an
    empty dict must not silently validate as a row) — but a value can genuinely be
    ``None`` (e.g. an unparseable ECHO period, a no-discharge month), so the *type*
    stays optional. Mirrors the connector's own ``DmrRow`` (#1492 review).
    """

    model_config = ConfigDict(extra="allow")

    period_end: str | None
    value_mgd: float | None
    stat_base: str | None


class DmrExceedance(BaseModel):
    """One ECHO-flagged effluent exceedance row.

    See :class:`DmrFlowSample` — required keys, optional values.
    """

    model_config = ConfigDict(extra="allow")

    period_end: str | None
    value: float | None
    unit: str | None
    limit: float | None
    exceedance_pct: float | None


class DmrExtraction(BaseModel):
    """An ECHO DMR effluent-record pull (``watermark dmr <NPDES_ID> --out ...``).

    A derived API summary, not a document extraction read from a scanned PDF — it
    carries none of :class:`DocExtraction`'s scan provenance (``doc_id``,
    ``source_path``, ``kind``, ``dpi``, ...). Both this and :class:`NpdesExtraction`
    key off a top-level ``permit:`` block, but the shapes are otherwise disjoint;
    ``pipeline.corpus._classify`` tells them apart by the presence of
    ``discharge_summary`` (#1492).
    """

    model_config = ConfigDict(extra="allow")

    meta: DmrMeta
    permit: DmrPermit
    discharge_summary: DmrDischargeSummary
    # Seasonality shape of the primary outfall's monthly flow (#1678). Optional/defaulted so a
    # DMR artifact predating the block still validates; `None` when the window has no usable
    # monthly series (`dmr_document()` writes `seasonality: null` there).
    seasonality: DmrSeasonality | None = None
    # Required, not defaulted: `dmr_document()` always writes both keys (an empty list
    # for a window with no rows/exceedances) — a missing key means a truncated or hand-
    # edited artifact, which should fail validation rather than silently read as empty.
    flow_monthly: list[DmrFlowSample]
    exceedances: list[DmrExceedance]


class SosExtraction(DocExtraction):
    filing: BusinessFiling


class EpaExtraction(DocExtraction):
    action: EpaPermitAction


class OrderExtraction(DocExtraction):
    order: EnforcementOrder


class InspectionExtraction(DocExtraction):
    inspection: ComplianceInspection


class ProgressReportExtraction(DocExtraction):
    progress_report: ComplianceProgressReport


class AwardExtraction(DocExtraction):
    award: FinanceAward


class WetlandExtraction(DocExtraction):
    determination: WetlandDetermination


class NoticeExtraction(DocExtraction):
    notice: NoticeOfCommencement


class PlanExtraction(DocExtraction):
    plan: SitePlan


class EngineeringExtraction(DocExtraction):
    record: EngineeringRecord
