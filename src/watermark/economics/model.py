"""Typed models for the localized economic baseline.

Reuses :class:`watermark.hydrology.model.ProvenancedValue` (the project-wide provenance
primitive) so every economic figure carries where it came from — a connector pull
(BLS QCEW), a transcribed reference, or a derived ratio — exactly like the hydrology
numbers. ``extra="forbid"``: these are computed by our own code.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from watermark.hydrology.model import ProvenancedValue
from watermark.provenance import Confidence, EvidenceRegister

# The QCEW coverage boundary (#1661) — a standing methodological caveat, not site-specific.
# QCEW counts UI-covered private/state/local employment + federal-civilian (UCFE) jobs; it does
# NOT count uniformed active-duty military, which is in neither ``total_employment`` (own 0) nor
# any ownership row. At a federal enclave (WPAFB) the base's uniformed workforce is a large slice
# of real local economic activity that this instrument structurally cannot see — so the total
# itself understates the enclave, above and beyond the federal-civilian jobs now surfaced in
# ``IndustryEmployment.government``. Stated so a reader never mistakes covered employment for the
# base's full footprint.
QCEW_COVERAGE_NOTE = (
    "BLS QCEW counts UI-covered (private, state, local) plus federal-civilian (UCFE) employment. "
    "Uniformed active-duty military is excluded — it appears in neither the county total nor any "
    "ownership row — so at a federal enclave the covered total understates the base's real "
    "employment footprint beyond even the federal-civilian jobs shown here."
)


class SectorEmployment(BaseModel):
    """One NAICS sector's county employment, with its export-orientation location quotient."""

    model_config = ConfigDict(extra="forbid")

    naics: str  # "31-33", "23", "92", ...
    sector_name: str
    annual_avg_employment: ProvenancedValue  # connector (QCEW)
    establishments: ProvenancedValue | None = None
    # QCEW annual pay (connector): the sector's average annual pay per covered job
    # (USD/year) and average weekly wage (USD/week). The pay counterpoint to a
    # data-center job-count claim — how the promised jobs compare to prevailing county
    # pay. Omitted (not zeroed) for a sector QCEW reports with no covered wages.
    avg_annual_pay: ProvenancedValue | None = None
    avg_weekly_wage: ProvenancedValue | None = None
    # Location quotient = county sector share / national sector share. >1 => the sector
    # is over-represented here, i.e. export-oriented (the closest county-level proxy for
    # an import/export ratio — no clean county trade series exists; see the README).
    location_quotient: ProvenancedValue | None = None


class OwnershipEmployment(BaseModel):
    """One government-ownership slice of county employment (QCEW own 1/2/3, agglvl 71).

    The federal / state / local government jobs the private-ownership ``sectors`` mix (own 5)
    structurally cannot show (#1661). ``total_employment`` (all ownerships) reconciles as the
    private sectors plus these government slices, so surfacing them closes the total-vs-sectors
    gap. The federal row matters most: at a federal enclave it is the county's single largest
    employer yet carries no NAICS sector of its own. Same connector-provenanced shape as
    :class:`SectorEmployment`; a slice QCEW reports with no covered wages omits pay (never $0).
    """

    model_config = ConfigDict(extra="forbid")

    ownership: str  # QCEW own_code: "1" (federal), "2" (state), "3" (local)
    ownership_name: str  # "Federal Government" | "State Government" | "Local Government"
    annual_avg_employment: ProvenancedValue  # connector (QCEW)
    establishments: ProvenancedValue | None = None
    avg_annual_pay: ProvenancedValue | None = None
    avg_weekly_wage: ProvenancedValue | None = None
    # Government ownership carries a location quotient too (concentration vs. the national
    # government-employment share) — a high federal LQ marks a procurement/enclave economy.
    location_quotient: ProvenancedValue | None = None


class IndustryEmployment(BaseModel):
    """A county's employment for one year (BLS QCEW): private NAICS sectors + government ownership.

    ``sectors`` is the **private-ownership** (own 5) NAICS mix; ``total_employment`` is **all
    ownerships** (own 0). The unexplained total-minus-sectors gap is the federal / state / local
    government employment, now surfaced in ``government`` (own 1/2/3) so the two reconcile (#1661).
    QCEW excludes uniformed active-duty military entirely — see :data:`QCEW_COVERAGE_NOTE`.
    """

    model_config = ConfigDict(extra="forbid")

    fips: str
    area_name: str
    year: int
    total_employment: ProvenancedValue
    establishments: ProvenancedValue | None = None
    # County-wide average pay across all ownerships (QCEW total row): the overall
    # "what the place pays" figure, alongside the per-sector pay in ``sectors``.
    avg_annual_pay: ProvenancedValue | None = None
    avg_weekly_wage: ProvenancedValue | None = None
    sectors: list[SectorEmployment]
    # Federal / state / local government employment (QCEW own 1/2/3, agglvl 71) — the ownership
    # slices the private ``sectors`` cannot show, closing the total-vs-sectors reconciliation
    # (#1661). Empty for a pre-#1661 baseline or a county QCEW discloses no government rows for.
    government: list[OwnershipEmployment] = []
    source: str = (
        "BLS QCEW (annual averages): private-ownership NAICS sectors + federal/state/local "
        "government ownership; excludes uniformed active-duty military"
    )


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

    @property
    def vintage(self) -> str:
        """The series' data vintage — its own ``asof``, else the latest period it reported.

        Anything that re-wraps this series into a new :class:`ProvenancedValue` (the
        demand-pressure sensitivity, the energy burden, the grid state denominator, the
        federal backdrop) must carry this through as that value's ``asof``, or the #1107
        staleness marker dies at the re-wrap and a figure derived from a years-old cached
        series reads exactly like one derived this morning (G1/#1644). The ``period``
        fallback covers a committed dataset written before the connector set ``asof``.
        """
        return self.value.asof or self.period

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
    short-run transmission coefficient (a screening illustration, heavily caveated). Retail
    price formation is far more complex than one coefficient — the share and households
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
    transmission_coefficient: ProvenancedValue  # assumption (banded): short-run %price/%demand
    price_pressure_pct_low: ProvenancedValue  # derived: stylized lower price-pressure bound
    price_pressure_pct_high: ProvenancedValue  # derived: stylized upper price-pressure bound
    method: str = (
        "facility draw (PUE-adjusted, #87) -> annual GWh -> share of EIA state retail "
        "sales + households-equivalent; price pressure = demand share x transmission coefficient "
        "(STYLIZED screening sensitivity, not a forecast)"
    )
    caveats: list[str] = []

    @property
    def has_material_load(self) -> bool:
        """True when the sensitivity rests on a real (nonzero) facility draw.

        ``derive_demand_pressure`` never produces a zero-draw record — it raises when the
        facility has no derivable power basis. But a stale or hand-authored demand-pressure
        YAML round-tripped through :func:`load_demand_pressure` can carry a degenerate zero
        draw (e.g. a rezoning-only campus whose IT load is entirely ``[open]``). Such a shell
        has no demand pressure to speak of: the ``economics-demand-pressure`` object feed must
        drop it rather than ship a ``count == 1`` shell that floats facility readiness to
        ``live`` (the #1364 present-but-empty rule, applied on the facility axis — #1631).
        """
        return self.facility_draw_mw.value > 0


class EnergyBurden(BaseModel):
    """Household energy burden: annual home-energy spend as a % of median household income.

    A fully **[derived]** consumer-impact metric (issue #1110) — every input carries its
    citation (EIA residential electricity + natural-gas prices, Census B19013 median
    household income), unlike the deliberately-STYLIZED facility price-pressure band
    (:class:`FacilityDemandPressure`). Electricity burden uses the average household's
    annual electricity use; the gas burden applies to a **gas-heated** household (a stated
    assumption — not every home heats with gas), so the combined burden is the burden on a
    gas-heated home at average use, a reference figure rather than a population mean.
    """

    model_config = ConfigDict(extra="forbid")

    area: str  # "OH" — residential energy prices are state-level
    area_name: str  # "Ohio"
    median_household_income: ProvenancedValue  # Census B19013 (connector); county-level
    avg_household_kwh_yr: ProvenancedValue  # assumption: avg residential annual electricity use
    residential_electricity_price: ProvenancedValue  # EIA (connector): cents/kWh
    electricity_annual_cost: ProvenancedValue  # derived: kWh/yr x price
    electricity_burden_pct: ProvenancedValue  # derived: electricity cost / income
    avg_household_mcf_yr: (
        ProvenancedValue  # assumption: avg residential annual gas use (heated home)
    )
    residential_gas_price: ProvenancedValue  # EIA (connector): $/Mcf
    gas_annual_cost: ProvenancedValue  # derived: Mcf/yr x price
    gas_burden_pct: ProvenancedValue  # derived: gas cost / income
    combined_annual_cost: ProvenancedValue  # derived: electricity + gas $/yr
    combined_burden_pct: ProvenancedValue  # derived: (electricity + gas) / income
    method: str = (
        "annual home-energy spend / median household income. Electricity = avg household "
        "kWh/yr x EIA residential cents/kWh; gas = avg household Mcf/yr x EIA residential "
        "$/Mcf (gas-heated home); burden = spend / Census B19013 median household income."
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
    # ACS5 median household income (B19013, #1110) — the energy-burden denominator; keyed live
    # fetch, so omitted (not faked) when unreachable. Optional keeps pre-#1110 baselines valid.
    median_household_income: ProvenancedValue | None = None
    # The active site's economic-unit caveat, promoted from the prose ``note`` to a first-class
    # field (#1661): when the single-county econ unit does not capture the signature the site's
    # thesis rests on (WPAFB's Greene/Montgomery straddle — the defense-supplier concentration
    # lives in the *other* county), this states it plainly. ``None`` = no caveat (sourced from
    # ``SiteProfile.econ_unit_note``).
    unit_caveat: str | None = None
    # The QCEW coverage boundary (#1661) — a standing methodological caveat naming what the
    # employment figures structurally exclude (uniformed active-duty military). A model default,
    # so every baseline carries it; the same text as :data:`QCEW_COVERAGE_NOTE`.
    coverage_note: str = QCEW_COVERAGE_NOTE
    note: str = ""


# --- The scenario-band layer (#1665, epic #1659 ME-F) -------------------------
# The economic argument — the GovCloud authorized-region premium, the DCTE tax-base
# forecasting risk, the abatement-vs-jobs mismatch, the what-if profile band — used to live
# only in prose (`docs/ECONOMICS.md` §3/§4, `docs/the-economic-ledger.md`) and in a hardcoded
# frontend array. A hand-copied console figure drifts from its source; a typed feed does not.
#
# This is the one part of the platform in tension with the anti-modeling method of
# `docs/defense-nexus.md`, so the discipline is enforced in the type system rather than
# asked for in a docstring:
#
#   * every quantity is a BAND, never a point — `ScenarioBand` refuses `low == high`;
#   * every claim carries an evidence `tag` (the four-tag register, #1663 ME-D) + a
#     `confidence`, and `verified` / anything above `low` is REFUSED — a scenario
#     structurally cannot be published as an assertion;
#   * the profile set must have at least two corners, or it is a point estimate in a
#     scenario's clothing.
#
# Mirrors the stylized-band discipline of `FacilityDemandPressure` (#1105), one rung
# stricter: that model *documents* that its band is a screening sensitivity; this one
# cannot serialize a figure that says otherwise.

SCENARIO_DISCLAIMER = (
    "A labeled counterfactual, not a finding. Every figure here is a band across explicitly "
    "stated scenarios whose constants are all on the table — it prices what the public "
    "instrument WOULD cost under each set of assumptions, and asserts nothing about which "
    "one is true. The GovCloud / defense-hardened profile in particular is a what-if on two "
    "knobs (building share and headcount); it is NOT a claim that this facility does defense "
    "work. That question is open and the corpus does not answer it (docs/defense-nexus.md)."
)


class ScenarioBand(BaseModel):
    """A low/central/high band — the deliverable, never a point estimate.

    ``high > low`` is enforced: a "band" that collapses to a single number is precisely the
    false precision this layer exists to prevent, so it cannot be constructed. ``dist``
    records how the interior of the band is shaped for a consumer that samples it —
    ``profiles`` means the band is the envelope of the discrete scenario corners (no
    distribution is asserted between them), which is the honest default here.
    """

    model_config = ConfigDict(extra="forbid")

    low: float
    central: float
    high: float
    unit: str  # "usd" | "usd_per_job" | "fraction" | "jobs" | "MW_per_job" | "x"
    dist: Literal["triangular", "uniform", "profiles"] = "profiles"

    @model_validator(mode="after")
    def _is_a_band(self) -> ScenarioBand:
        if self.high <= self.low:
            raise ValueError(
                f"a scenario band must span a range, got low={self.low} high={self.high} — "
                "publish a point estimate as a ProvenancedValue, not as a band"
            )
        if not (self.low <= self.central <= self.high):
            raise ValueError(
                f"central {self.central} falls outside the band [{self.low}, {self.high}]"
            )
        return self


def _refuse_assertion(tag: EvidenceRegister, confidence: Confidence, what: str) -> None:
    """Refuse any scenario figure that would read as an assertion (the ME-F discipline).

    ``verified`` is the register of a record read; a modeled counterfactual is never one.
    ``confidence`` above ``low`` would let a screening band be quoted with the authority of a
    measurement. Both are structural, not stylistic — hence a raise, not a caveat string.
    """
    if tag == "verified":
        raise ValueError(
            f"{what}: a scenario is a labeled counterfactual and can never carry the tag "
            "'verified' — use 'open' (a question the record withholds), 'inference' (a "
            "computed reading), or 'reference' (a published outside range)"
        )
    if confidence != "low":
        raise ValueError(
            f"{what}: a scenario band must carry confidence 'low', got {confidence!r} — "
            "a screening range quoted at higher confidence reads as a measurement"
        )


class ScenarioSource(BaseModel):
    """One published source pooled into a scenario axis's band (from the industry priors)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    year: int | None = None
    url: str | None = None
    contributes: str = ""


class ScenarioAxis(BaseModel):
    """One cited driver of the economic argument, published as a band with its sources.

    The typed home of the figures `docs/ECONOMICS.md` §4 carried as prose: the
    authorized-region (GovCloud) premium, the DCTE tax-base forecasting risk, the jobs-per-MW
    staffing range, the subsidy-per-job benchmark. ``band`` is ``None`` for a
    **corroboration** axis that asserts no range of its own (the sales-tax-exemption-dominance
    finding is a qualitative corroboration from other jurisdictions, not a Lima magnitude) —
    those still carry their sources, so the claim can be checked.

    ``site_status`` is the prior's ``lima_status``, generalized: whether the band's application
    to *this* site is ``open`` (unresolved), ``comparative`` (a benchmark the site is read
    against), or ``context`` (national backdrop). It is what keeps an industry range from
    being read as a facility fact.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    question: str  # the [open] question the axis bears on, phrased as a question
    band: ScenarioBand | None = None
    tag: EvidenceRegister = "reference"
    confidence: Confidence = "low"
    site_status: str = "open"  # open | comparative | context
    drives: list[str] = []
    basis: str = ""
    sources: list[ScenarioSource] = []
    resolving_record: str | None = None

    @model_validator(mode="after")
    def _cannot_assert(self) -> ScenarioAxis:
        _refuse_assertion(self.tag, self.confidence, f"axis {self.key!r}")
        return self


class ScenarioProfile(BaseModel):
    """One discrete what-if corner: the two knobs turned, and the ledger priced on them.

    The typed peer of the frontend's former hardcoded ``CRA_PROFILES`` array. Every dollar
    figure is computed here from the committed instrument (the CRA extraction) and the
    committed, cited local parameters — so the profile the site renders and the profile the
    essay tabulates are the same object, and neither can drift from the record.
    """

    model_config = ConfigDict(extra="forbid")

    key: str  # "stated" | "equipment" | "hyperscale" | "govcloud"
    label: str
    note: str = ""
    basis: str = ""
    building_share: float  # the abated real-property share of capex [assumption]
    jobs: int  # modeled steady-state headcount [assumption]
    abatement_usd: float  # 15-yr forgone real-property tax
    kept_usd: float  # the un-abated share the public still collects
    exemption_usd: float  # forgone sales tax on equipment, if the DCTE is taken [open]
    net_subsidy_usd: float  # abatement + exemption (before the school-compensation offset)
    abatement_per_job_usd: float
    net_subsidy_per_job_usd: float


class ScenarioLine(BaseModel):
    """One ledger line, as a band across the scenario profiles."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    band: ScenarioBand
    tag: EvidenceRegister = "inference"
    confidence: Confidence = "low"
    note: str = ""
    resolving_record: str | None = None

    @model_validator(mode="after")
    def _cannot_assert(self) -> ScenarioLine:
        _refuse_assertion(self.tag, self.confidence, f"line {self.key!r}")
        return self


class WithheldInput(BaseModel):
    """A load-bearing figure the record does not fix, and the record that would fix it.

    Naming these is half the discipline: the band is wide *because* of a specific,
    identifiable disclosure that has not been made. ``resolving_record`` is what collapses it.
    """

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    band: ScenarioBand
    tag: EvidenceRegister = "open"
    confidence: Confidence = "low"
    why: str = ""  # why the record does not fix it
    resolving_record: str = ""

    @model_validator(mode="after")
    def _cannot_assert(self) -> WithheldInput:
        _refuse_assertion(self.tag, self.confidence, f"withheld input {self.key!r}")
        return self


class ScenarioConstant(BaseModel):
    """One named modeling constant, carrying its citation and register."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: ProvenancedValue


class EconomicScenarios(BaseModel):
    """The economic argument as disciplined scenario bands (#1665, epic #1659 ME-F).

    Assembled by :func:`watermark.economics.scenarios.derive_economic_scenarios` from three
    committed inputs — the site's abatement instrument (the CRA extraction), its cited local
    tax parameters + what-if knobs (``abatement_parameters_relpath``), and the network-global
    industry priors (``reference/datacenter-industry/priors.yaml``) — plus the facility power
    basis where one exists. Nothing is re-keyed: every figure traces to one of those files.

    Instrument-gated: a site with no abatement agreement on the record produces ``None``, so
    no peer is ever priced off another county's mills.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    site_name: str
    instrument: str  # the abatement agreement this prices, named
    instrument_record: str  # the committed extraction it is read from
    # The whole object's evidence tag. Fixed literals, not defaults a caller can raise: the
    # model as a whole is an open question at low confidence, and cannot serialize otherwise.
    tag: Literal["open"] = "open"
    confidence: Literal["low"] = "low"
    constants: list[ScenarioConstant] = []
    withheld: list[WithheldInput] = []
    axes: list[ScenarioAxis] = []
    profiles: list[ScenarioProfile] = []
    lines: list[ScenarioLine] = []
    # Load-not-jobs: the campus's disclosed IT load per modeled job — the §3 "the public
    # subsidizes load and consumption, not employment" figure, as a band. ``None`` where the
    # site has no derivable power basis (the ratio is not fabricated from a missing numerator).
    load_per_job: ScenarioLine | None = None
    method: str = ""
    disclaimer: str = SCENARIO_DISCLAIMER
    caveats: list[str] = []

    @model_validator(mode="after")
    def _needs_corners(self) -> EconomicScenarios:
        """A scenario model with fewer than two corners is a point estimate in disguise."""
        if self.profiles and len(self.profiles) < 2:
            raise ValueError(
                f"{self.site}: a scenario model needs at least two profiles to be a band, "
                f"got {len(self.profiles)}"
            )
        return self

    @property
    def has_material_content(self) -> bool:
        """True when the model actually carries scenarios (the #1364 present-but-empty rule).

        A parameters file that loaded but yielded no profiles and no axes is an empty shell;
        the object feed must drop it rather than ship a ``count == 1`` husk.
        """
        return bool(self.profiles) and bool(self.lines)
