"""Typed models for the localized economic baseline.

Reuses :class:`watermark.hydrology.model.ProvenancedValue` (the project-wide provenance
primitive) so every economic figure carries where it came from — a connector pull
(BLS QCEW), a transcribed reference, or a derived ratio — exactly like the hydrology
numbers. ``extra="forbid"``: these are computed by our own code.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from watermark.hydrology.model import ProvenancedValue


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
    """Total covered employment (and establishments) in one year — a point on the trend."""

    model_config = ConfigDict(extra="forbid")

    year: int
    total_employment: ProvenancedValue
    establishments: ProvenancedValue | None = None  # QCEW annual-avg establishments, when reported


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


class EnergyPricePoint(BaseModel):
    """One annual point on an EIA energy series: ``period`` + native-unit ``value``.

    Deliberately compact. Provenance is carried once at the series level
    (:class:`ConsumerEnergyPrice`: ``series_id``, ``value.unit``, connector source) rather
    than repeated on every point — each point's citation is deterministically
    ``EIA API v2 seriesid {series_id} ({period})`` — so the full annual history (25-60 pts)
    stays a tiny fixture (issue #1111). The latest point is additionally exposed as the
    fully-cited ``ConsumerEnergyPrice.value`` for callers needing one provenanced figure.
    """

    model_config = ConfigDict(extra="forbid")

    period: str  # "2023" (annual) or "2023-12"
    value: float  # native units (see the series' value.unit: cents/kWh, $/Mcf, million kWh)


class ConsumerEnergyPrice(BaseModel):
    """One EIA consumer energy-price (or sales) series, with its full annual history.

    A consumer-level energy figure for the state/region — residential electricity
    price, residential natural-gas price, or total electricity retail sales — read
    from the EIA API v2. ``value``/``period`` are the latest point (a convenience for
    callers that only need the current figure); ``points`` is the full annual series
    (oldest→newest) so the site can chart the trend (issue #1111). ``value`` carries its
    native units (cents/kWh, $/Mcf, or million kWh for the sales series); ``source: connector``.
    """

    model_config = ConfigDict(extra="forbid")

    series_id: str  # EIA legacy series id (e.g. ELEC.PRICE.OH-RES.A)
    label: str  # "Ohio residential electricity price"
    fuel: str  # "electricity" | "natural_gas"
    metric: str = "price"  # "price" | "sales"
    period: str  # latest period ("2025"); mirrors points[-1].period
    area: str  # "OH"
    value: ProvenancedValue  # latest point; connector; native units in .unit
    points: list[EnergyPricePoint] = []  # full annual series, oldest→newest (issue #1111)

    @model_validator(mode="after")
    def _latest_mirrors_points(self) -> ConsumerEnergyPrice:
        """Enforce the documented invariant: when a series is present, ``period``/``value``
        are its latest point (``points[-1]``) — so no caller/loader can slip in a headline
        that disagrees with the trend. Empty ``points`` (a series-less latest-only record) is
        allowed for backward compatibility with pre-#1111 committed data."""
        if self.points:
            newest = self.points[-1]
            if self.period != newest.period or self.value.value != newest.value:
                raise ValueError(
                    f"{self.series_id}: latest period/value ({self.period}, {self.value.value}) "
                    f"must mirror points[-1] ({newest.period}, {newest.value})"
                )
        return self


class ConsumerEnergyCosts(BaseModel):
    """Committed EIA consumer energy-cost reference for the state/region (issue #91).

    The consumer-price half of the demand thread: what households pay for electricity
    and heating fuel, against which the data-center load's pressure is screened. A
    vendored, regenerable reference (``watermark eia``) like the QCEW baseline — the site
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
    population: PopulationSeries | None = None  # ACS5 (live fetch keyed); omitted if unreachable
    note: str = ""
