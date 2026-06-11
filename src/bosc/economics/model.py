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


class ConsumerEnergyPrice(BaseModel):
    """One EIA consumer energy-price (or sales) series point.

    A consumer-level energy figure for the state/region — residential electricity
    price, residential natural-gas price, or total electricity retail sales — read
    from the EIA API v2. ``value`` carries its native units (cents/kWh, $/Mcf, or
    million kWh for the sales series); ``source: connector``.
    """

    model_config = ConfigDict(extra="forbid")

    series_id: str  # EIA legacy series id (e.g. ELEC.PRICE.OH-RES.A)
    label: str  # "Ohio residential electricity price"
    fuel: str  # "electricity" | "natural_gas"
    metric: str = "price"  # "price" | "sales"
    period: str  # "2023" (annual) or "2023-12"
    area: str  # "OH"
    value: ProvenancedValue  # connector; native units in .unit


class ConsumerEnergyCosts(BaseModel):
    """Committed EIA consumer energy-cost reference for the state/region (issue #91).

    The consumer-price half of the demand thread: what households pay for electricity
    and heating fuel, against which the data-center load's pressure is screened. A
    vendored, regenerable reference (``bosc eia``) like the QCEW baseline — the site
    reads the committed YAML, never a live pull. Every figure is connector-sourced.
    """

    model_config = ConfigDict(extra="forbid")

    area: str  # "OH"
    area_name: str  # "Ohio"
    prices: list[ConsumerEnergyPrice]
    source: str = "US EIA API v2 (seriesid route): residential prices + retail sales"
    note: str = ""

    def series(self, series_id: str) -> ConsumerEnergyPrice | None:
        return next((p for p in self.prices if p.series_id == series_id), None)

    def by_metric(self, fuel: str, metric: str) -> ConsumerEnergyPrice | None:
        return next((p for p in self.prices if p.fuel == fuel and p.metric == metric), None)


class FacilityDemandPressure(BaseModel):
    """A SENSITIVITY linking the data-center's total draw to consumer energy prices.

    The 2026-06-10 call's "bring in fuel costs at the consumer level due to macro
    pressures and data-center demand." Not a forecast: it sizes the campus's annual
    electricity demand from the first-class ``facility_draw`` (issue #87), expresses it
    as a share of state retail sales and as a households-equivalent (both robust,
    EIA-cited), and adds a deliberately STYLIZED price-pressure band from a stated
    short-run supply elasticity (a screening illustration, heavily caveated). Retail
    price formation is far more complex than one elasticity — the share and households
    figures are the defensible headline; the price-pressure band is illustrative only.
    """

    model_config = ConfigDict(extra="forbid")

    area: str  # "OH"
    facility_draw_mw: ProvenancedValue  # total facility draw, central (from PowerBasis, #87)
    load_factor: ProvenancedValue  # assumption: capacity utilization (data centers run flat)
    annual_consumption_gwh: ProvenancedValue  # derived: draw x 8760 x load factor
    state_retail_sales_gwh: ProvenancedValue  # EIA: total state electricity retail sales
    demand_share_pct: ProvenancedValue  # derived: campus consumption / state sales
    avg_household_kwh_yr: ProvenancedValue  # assumption: avg residential annual use
    households_equivalent: ProvenancedValue  # derived: campus consumption / household use
    residential_price: ProvenancedValue  # EIA: residential electricity price (cents/kWh)
    supply_elasticity: ProvenancedValue  # assumption (banded): short-run inverse-supply slope
    price_pressure_pct_low: ProvenancedValue  # derived: stylized lower price-pressure bound
    price_pressure_pct_high: ProvenancedValue  # derived: stylized upper price-pressure bound
    method: str = (
        "facility draw (PUE-adjusted, #87) -> annual GWh -> share of EIA state retail "
        "sales + households-equivalent; price pressure = demand share / supply elasticity "
        "(STYLIZED screening sensitivity, not a forecast)"
    )
    caveats: list[str] = []


class EconomicBaseline(BaseModel):
    """The assembled localized baseline: latest industry mix + employment trend (+ population)."""

    model_config = ConfigDict(extra="forbid")

    fips: str
    area_name: str
    latest: IndustryEmployment
    trend: list[YearTotal] = []  # total covered employment over years
    population: PopulationSeries | None = None  # requires a Census key; omitted otherwise
    note: str = ""
