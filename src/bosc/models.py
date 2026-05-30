"""Typed models for BOSC structured extractions.

These mirror the ``*.opc.yaml`` extraction files under ``data/extracted``.
The source scans are degraded, so many numbers are transcribed as *approximate*
(written ``~12345`` in YAML, which parses as a string). :data:`ApproxInt`
transparently coerces those to integers while preserving the approximate flag
in a sidecar set on the model where it matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

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
