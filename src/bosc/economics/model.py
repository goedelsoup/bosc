"""Typed models for the localized economic baseline.

Reuses :class:`bosc.hydrology.model.ProvenancedValue` (the project-wide provenance
primitive) so every economic figure carries where it came from — a connector pull
(BLS QCEW), a transcribed reference, or a derived ratio — exactly like the hydrology
numbers. ``extra="forbid"``: these are computed by our own code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from bosc.hydrology.model import ProvenancedValue


class SectorEmployment(BaseModel):
    """One NAICS sector's county employment, with its export-orientation location quotient."""

    model_config = ConfigDict(extra="forbid")

    naics: str  # "31-33", "23", "92", ...
    sector_name: str
    annual_avg_employment: ProvenancedValue  # connector (QCEW)
    establishments: ProvenancedValue | None = None
    # Location quotient = county sector share / national sector share. >1 => the sector
    # is over-represented here, i.e. export-oriented (the closest county-level proxy for
    # an import/export ratio — no clean county trade series exists; see the README).
    location_quotient: ProvenancedValue | None = None


class IndustryEmployment(BaseModel):
    """A county's employment by NAICS sector for one year (BLS QCEW)."""

    model_config = ConfigDict(extra="forbid")

    fips: str
    area_name: str
    year: int
    total_employment: ProvenancedValue
    establishments: ProvenancedValue | None = None
    sectors: list[SectorEmployment]
    source: str = "BLS QCEW (annual averages, private ownership by NAICS sector)"


class YearTotal(BaseModel):
    """Total covered employment in one year — a point on the trend."""

    model_config = ConfigDict(extra="forbid")

    year: int
    total_employment: ProvenancedValue


class PopulationPoint(BaseModel):
    """County population in one year (Census)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    population: ProvenancedValue


class PopulationSeries(BaseModel):
    """County population over time — present only when a Census source is available."""

    model_config = ConfigDict(extra="forbid")

    fips: str
    area_name: str
    points: list[PopulationPoint]
    source: str = "US Census ACS 5-year (B01003)"


class EconomicBaseline(BaseModel):
    """The assembled localized baseline: latest industry mix + employment trend (+ population)."""

    model_config = ConfigDict(extra="forbid")

    fips: str
    area_name: str
    latest: IndustryEmployment
    trend: list[YearTotal] = []  # total covered employment over years
    population: PopulationSeries | None = None  # requires a Census key; omitted otherwise
    note: str = ""
