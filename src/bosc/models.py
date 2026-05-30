"""Typed models for BOSC structured extractions.

These mirror the ``*.opc.yaml`` extraction files under ``data/extracted``.
The source scans are degraded, so many numbers are transcribed as *approximate*
(written ``~12345`` in YAML, which parses as a string). :data:`ApproxInt`
transparently coerces those to integers while preserving the approximate flag
in a sidecar set on the model where it matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

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
# Extraction targets — what the vision extractor fills in for a single page.
# ---------------------------------------------------------------------------


class EstimateExtraction(SubEstimate):
    """A :class:`SubEstimate` read from one cost sheet, plus self-reported confidence.

    This is the model the vision extractor is forced to populate (via tool use),
    so the LLM tells us how sure it is and flags anything it could not read.
    """

    confidence: Literal["high", "medium", "low"] = "medium"
    warnings: list[str] = Field(default_factory=list)


class LineItem(BaseModel):
    """A single estimate line item read from a cost sheet."""

    model_config = ConfigDict(extra="allow")

    item_no: str | None = None  # ODOT code (e.g. 203E10000) or a custom_ tag
    description: str
    quantity: Number = None
    unit: str | None = None  # LS, CY, SY, FT, EACH, GAL, SF, AC
    unit_amount: Number = None  # per-unit dollars
    total_amount: Number = None  # extended dollars
    note: str | None = None  # e.g. "qty inferred from total"


# The eleven estimate sections, in sheet order. Single source of truth.
SECTION_NAMES: tuple[str, ...] = (
    "roadway",
    "erosion_control",
    "drainage",
    "pavement",
    "water_work",
    "lighting",
    "traffic_control",
    "landscaping",
    "right_of_way",
    "incidentals",
    "design_survey_inspection",
)


class SectionLineItems(BaseModel):
    """Line items grouped by estimate section (corridors omit several sections)."""

    model_config = ConfigDict(extra="allow")

    roadway: list[LineItem] = Field(default_factory=list)
    erosion_control: list[LineItem] = Field(default_factory=list)
    drainage: list[LineItem] = Field(default_factory=list)
    pavement: list[LineItem] = Field(default_factory=list)
    water_work: list[LineItem] = Field(default_factory=list)
    lighting: list[LineItem] = Field(default_factory=list)
    traffic_control: list[LineItem] = Field(default_factory=list)
    landscaping: list[LineItem] = Field(default_factory=list)
    right_of_way: list[LineItem] = Field(default_factory=list)
    incidentals: list[LineItem] = Field(default_factory=list)
    design_survey_inspection: list[LineItem] = Field(default_factory=list)

    def sections(self) -> dict[str, list[LineItem]]:
        """Map of section name -> its line items (only the known sections)."""
        return {name: getattr(self, name) for name in SECTION_NAMES}


class DetailExtraction(EstimateExtraction):
    """A full line-item extraction of one cost sheet (summary fields + line items)."""

    line_items: SectionLineItems = Field(default_factory=SectionLineItems)

    def section_item_total(self, section: str) -> float:
        """Sum of line-item ``total_amount`` for one section (0 if none/illegible)."""
        items: list[LineItem] = getattr(self.line_items, section, [])
        return float(sum(i.total_amount for i in items if isinstance(i.total_amount, (int, float))))


class BasePageExtraction(BaseModel):
    """Provenance shared by summary and detail page extractions."""

    model_config = ConfigDict(extra="allow")

    doc_id: str
    source_path: str
    page_index: int  # 0-based PDF page
    pdf_page: int  # 1-based, matches the printed sheet
    dpi: int
    source_text_excerpt: str = ""

    def to_yaml(self) -> str:
        """Serialize to YAML for writing under data/extracted (review artifact)."""
        return yaml.safe_dump(self.model_dump(), sort_keys=False, allow_unicode=True)


class PageExtraction(BasePageExtraction):
    """A summary (section-subtotal) extraction of one page."""

    estimate: EstimateExtraction


class DetailPageExtraction(BasePageExtraction):
    """A full line-item extraction of one page."""

    estimate: DetailExtraction
