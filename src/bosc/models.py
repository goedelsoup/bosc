"""Typed models for BOSC structured extractions.

These mirror the ``*.opc.yaml`` extraction files under ``data/extracted``.
The source scans are degraded, so many numbers are transcribed as *approximate*
(written ``~12345`` in YAML, which parses as a string). :data:`ApproxInt`
transparently coerces those to integers while preserving the approximate flag
in a sidecar set on the model where it matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _coerce_number(value: Any) -> Any:
    """Coerce ``"~12345"`` / ``"12,345"`` style scalars to ``int``.

    Plain ints/floats pass through. ``None`` passes through. Anything that
    cannot be parsed is returned unchanged so Pydantic raises a clear error.
    """
    if value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lstrip("~").replace(",", "").replace("$", "")
        if cleaned == "":
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            return value
    return value


# An int that tolerates the approximate ``~`` marker and thousands separators.
ApproxInt = Annotated[int, BeforeValidator(_coerce_number)]
OptApproxInt = Annotated[int | None, BeforeValidator(_coerce_number)]


def _coerce_number_keep(value: Any) -> Any:
    """Like :func:`_coerce_number` but preserves int-vs-float for line items.

    ``"~17.0"`` -> ``17.0`` (a unit rate), ``"~2,490"`` -> ``2490`` (a quantity).
    Numbers pass through unchanged so a printed ``17.0`` stays a float.
    """
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
Number = Annotated[int | float | None, BeforeValidator(_coerce_number_keep)]


class OPCMeta(BaseModel):
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


class SectionSubtotals(BaseModel):
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


class SubEstimate(BaseModel):
    """A single roundabout or corridor sub-estimate."""

    model_config = ConfigDict(extra="allow")

    name: str
    pdf_page: int | None = None
    work: str | None = None
    note: str | None = None
    type: str | None = None
    construction_subtotal: ApproxInt
    contingency_inflation_25pct: OptApproxInt = None
    total: ApproxInt
    section_subtotals: SectionSubtotals = Field(default_factory=SectionSubtotals)
    notes: str | None = None

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
# knowledge lives in a format Profile (see bosc.profiles).
# ---------------------------------------------------------------------------


def _num(value: Any) -> float:
    """A Number coerced to float, treating None / non-numeric as 0.0."""
    return float(value) if isinstance(value, (int, float)) else 0.0


class LineItem(BaseModel):
    """A single estimate line item read from a cost sheet."""

    model_config = ConfigDict(extra="allow")

    item_no: str | None = None  # contractor/agency item code, or a custom_ tag
    description: str
    quantity: Number = None
    unit: str | None = None  # e.g. LS, CY, SY, FT, EACH, GAL, SF, AC
    unit_amount: Number = None  # per-unit dollars
    total_amount: Number = None  # extended dollars
    note: str | None = None  # e.g. "qty inferred from total"


class EstimateSection(BaseModel):
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


class MarkupLine(BaseModel):
    """A markup/adjustment applied to the construction subtotal.

    Covers contingency, inflation, mobilization, escalation, etc. ``rate`` is the
    fraction of the construction subtotal when the line is a percentage.
    """

    model_config = ConfigDict(extra="allow")

    label: str
    rate: float | None = None  # e.g. 0.25 for a 25% line
    amount: Number = None


class Estimate(BaseModel):
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


class _Extracted(BaseModel):
    """Mixin: self-reported confidence + warnings for any extracted document."""

    model_config = ConfigDict(extra="allow")

    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: list[str] = Field(default_factory=list)


class Deed(_Extracted):
    """A recorded land instrument (deed, easement, etc.)."""

    instrument_type: str | None = None  # e.g. "General Warranty Deed", "Quitclaim"
    instrument_no: str | None = None  # recorder instrument / document number
    recording_date: str | None = None  # ISO date if legible
    grantors: list[str] = Field(default_factory=list)  # party conveying
    grantees: list[str] = Field(default_factory=list)  # party receiving
    consideration: Number = None  # stated dollar consideration
    parcel_ids: list[str] = Field(default_factory=list)  # auditor/parcel numbers
    county: str | None = None
    legal_description: str | None = None  # short excerpt / summary, not the full metes-and-bounds
    note: str | None = None


class NpdesPermit(_Extracted):
    """An Ohio EPA NPDES discharge permit / fact sheet."""

    facility_name: str | None = None
    permit_no: str | None = None  # Ohio EPA permit no, e.g. 2PH00006*LD
    permit_action: str | None = None  # renewal | modification | new | draft
    applicant: str | None = None
    application_no: str | None = None  # e.g. OH0037338
    public_notice_no: str | None = None
    public_notice_date: str | None = None
    comment_period_end: str | None = None
    facility_address: str | None = None
    discharge_address: str | None = None
    receiving_water: str | None = None
    stream_network: str | None = None  # downstream chain to a major water body
    outfalls: list[str] = Field(default_factory=list)
    note: str | None = None


class DocExtraction(BaseModel):
    """Provenance shared by document-level extractions."""

    model_config = ConfigDict(extra="allow")

    doc_id: str
    source_path: str
    kind: str
    pages_read: list[int] = Field(default_factory=list)  # 0-based pages the model saw
    dpi: int
    source_text_excerpt: str = ""

    def to_yaml(self) -> str:
        """Serialize to YAML for writing under data/extracted (review artifact)."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False, allow_unicode=True)


class DeedExtraction(DocExtraction):
    deed: Deed


class NpdesExtraction(DocExtraction):
    permit: NpdesPermit
