"""Typed models for the Tier-0 hydrology subsystem.

Unlike the extraction models in :mod:`bosc.models` (``extra="allow"`` because the
LLM emits unanticipated keys), these are **computed by our own code**, so they use
``extra="forbid"`` to catch bugs early.

The cornerstone is :class:`ProvenancedValue`: every number that enters the water
balance carries where it came from, so a result is self-auditing. The ``source``
tag maps onto the dossier's evidence discipline:

    document, connector  ->  [verified]   (read from a record or a live gauge)
    assumption, derived  ->  [inference]  (asserted, or computed from the above)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

SourceKind = Literal["document", "connector", "assumption", "derived"]
NodeRole = Literal["abstraction", "demand", "wwtp", "receiving"]
Flag = Literal["ok", "tight", "violation"]


class ProvenancedValue(BaseModel):
    """A single numeric quantity tagged with its provenance.

    Construct via the classmethods (:meth:`from_document`, :meth:`from_connector`,
    :meth:`assume`, :meth:`derived`) so the ``source`` tag is never forgotten.
    """

    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str  # "cfs" | "MGD" | "sqmi" | "acre" | "in" | ...
    source: SourceKind
    citation: str | None = None  # rel_path, geojson feature id, NWIS site, or rationale
    confidence: Literal["high", "medium", "low"] = "medium"
    asof: str | None = None  # ISO datetime, for connector (live) values

    @classmethod
    def from_document(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> ProvenancedValue:
        """A value read from a source record (cite the file / feature id)."""
        return cls(
            value=value, unit=unit, source="document", citation=citation, confidence=confidence
        )

    @classmethod
    def from_connector(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        asof: str | None = None,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> ProvenancedValue:
        """A value fetched live from an external service (cite the site/endpoint)."""
        return cls(
            value=value,
            unit=unit,
            source="connector",
            citation=citation,
            confidence=confidence,
            asof=asof,
        )

    @classmethod
    def assume(
        cls,
        value: float,
        unit: str,
        why: str,
        *,
        confidence: Literal["high", "medium", "low"] = "low",
    ) -> ProvenancedValue:
        """An asserted value not derivable from any record (state the rationale)."""
        return cls(value=value, unit=unit, source="assumption", citation=why, confidence=confidence)

    @classmethod
    def derived(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "medium",
    ) -> ProvenancedValue:
        """A value computed from other provenanced inputs (cite the derivation)."""
        return cls(
            value=value, unit=unit, source="derived", citation=citation, confidence=confidence
        )

    @property
    def verified(self) -> bool:
        """True when the value is grounded in a record or a live gauge."""
        return self.source in ("document", "connector")

    def __str__(self) -> str:
        tag = {"document": "doc", "connector": "live", "assumption": "assume", "derived": "calc"}[
            self.source
        ]
        return f"{self.value:,.2f} {self.unit} [{tag}]"


class Node(BaseModel):
    """A point in the municipal water loop (a plant, a demand center, a stream)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: NodeRole
    receiving_water: str | None = None  # for wwtp nodes: where the discharge goes
    lat: float | None = None
    lon: float | None = None


class WaterBalanceNode(BaseModel):
    """One node's flow terms. Conservation: inflow + stormwater = return + consumptive.

    Terms are optional — a node carries only what's known/relevant (an abstraction
    node has ``inflow``; a demand node has ``consumptive_use`` + ``return_flow``).
    All flows are in **cfs**. ``stormwater`` is the Increment-2 seam: a cited zero
    today, filled by the SCS-CN solver later.
    """

    model_config = ConfigDict(extra="forbid")

    node: Node
    inflow: ProvenancedValue | None = None
    consumptive_use: ProvenancedValue | None = None
    return_flow: ProvenancedValue | None = None
    stormwater: ProvenancedValue | None = None

    def all_values(self) -> list[ProvenancedValue]:
        return [
            v for v in (self.inflow, self.consumptive_use, self.return_flow, self.stormwater) if v
        ]


class WaterBalance(BaseModel):
    """The assembled source -> use -> WWTP -> receiving loop."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[WaterBalanceNode]
    tier: Literal["tier0"] = "tier0"
    warnings: list[str] = []

    def node(self, node_id: str) -> WaterBalanceNode | None:
        return next((n for n in self.nodes if n.node.id == node_id), None)

    def by_role(self, role: NodeRole) -> list[WaterBalanceNode]:
        return [n for n in self.nodes if n.node.role == role]

    def all_values(self) -> list[ProvenancedValue]:
        return [v for n in self.nodes for v in n.all_values()]

    def closes(self, *, rel_tol: float = 0.05) -> bool:
        """True if, where all terms are present, each node conserves mass within tol."""
        for n in self.nodes:
            if n.inflow is None or n.return_flow is None:
                continue
            storm = n.stormwater.value if n.stormwater else 0.0
            consume = n.consumptive_use.value if n.consumptive_use else 0.0
            lhs = n.inflow.value + storm
            rhs = n.return_flow.value + consume
            if abs(lhs - rhs) > max(0.01, abs(lhs) * rel_tol):
                return False
        return True


NetworkNodeKind = Literal["headwater", "abstraction", "outfall", "confluence", "gage", "outlet"]


class NetworkNode(BaseModel):
    """One junction in the routed low-flow stream network (cited topology only).

    The node carries *structure* — its kind, the stream it sits on, and the node it
    drains into — plus a pointer telling the solver where to read its flow term from
    an already-grounded source (``low_flow`` -> cited 7Q10; ``balance_return`` -> a
    WWTP/campus discharge in the :class:`WaterBalance`; ``consumptive`` -> the
    scenario's cooling draw). No flow magnitudes live here, so the topology never
    fabricates a number; the only modeling choice is the *order* of confluences,
    flagged ``status`` (``confirmed`` / ``theorized``) like the routing table.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: NetworkNodeKind
    downstream: str | None = None  # id of the node this drains into (None at the outlet)
    receiving_water: str | None = None
    low_flow: str | None = None  # receiving-water key -> inject its cited 7Q10 as base flow
    balance_return: str | None = None  # WaterBalance node id -> add its return_flow as a gain
    consumptive: bool = False  # apply the scenario's consumptive draw here as a loss
    status: Literal["confirmed", "theorized"] = "confirmed"
    citation: str | None = None


class ReachFlow(BaseModel):
    """The solved low-flow state of the reach leaving one network node.

    ``natural_cfs`` is headwater-origin streamflow; ``effluent_cfs`` is WWTP/campus
    discharge routed downstream. Their sum is ``routed_cfs``. ``deficit_cfs`` is
    consumptive demand the reach could not supply (the draw exceeded the water
    present) — the screening signature of a stream drawn dry at design low flow.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    name: str
    kind: NetworkNodeKind
    base: ProvenancedValue | None = None  # cited 7Q10 injected here (headwater)
    gain: ProvenancedValue | None = None  # discharge added here (outfall)
    loss: ProvenancedValue | None = None  # consumptive draw removed here (abstraction)
    inflow_cfs: float  # sum of upstream routed flow
    natural_cfs: float  # headwater-origin component leaving this node
    effluent_cfs: float  # discharge-origin component leaving this node
    routed_cfs: float  # natural + effluent (>= 0)
    deficit_cfs: float = 0.0  # consumptive demand the reach could not meet
    status: Literal["confirmed", "theorized"] = "confirmed"

    @property
    def effluent_fraction(self) -> float | None:
        return self.effluent_cfs / self.routed_cfs if self.routed_cfs > 0 else None


class RoutedNetwork(BaseModel):
    """The Lima loop solved as a directed low-flow stream network.

    Generalizes the per-stream :class:`AssimilativeCheck`: instead of reading each
    WWTP against its own tributary in isolation, it routes the cited headwater low
    flows, the WWTP/campus discharges, and the scenario's consumptive draw through a
    cited confluence graph and accumulates them downstream. The order-invariant
    **system** totals are the robust headline; the per-reach values are screening.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    scenario: str = "baseline"
    reaches: list[ReachFlow]
    assimilative_reach: str | None = None  # the gage node the loop's flow passes
    natural_total_cfs: float  # Σ cited headwater 7Q10 (system natural low flow)
    effluent_total_cfs: float  # Σ WWTP/campus discharge (system effluent)
    consumptive_cfs: float  # the scenario's consumptive draw on the loop
    outlet_cfs: float  # routed flow leaving the outlet
    outlet_effluent_fraction: float | None = None  # effluent share of the outlet flow
    warnings: list[str] = []

    def reach(self, node_id: str) -> ReachFlow | None:
        return next((r for r in self.reaches if r.node_id == node_id), None)

    @property
    def closes(self) -> bool:
        """Mass conservation: Σ base + Σ gain - Σ(loss applied) == outlet routed flow."""
        applied_loss = sum((r.loss.value if r.loss else 0.0) - r.deficit_cfs for r in self.reaches)
        supplied = self.natural_total_cfs + self.effluent_total_cfs - applied_loss
        return abs(supplied - self.outlet_cfs) <= max(0.01, abs(supplied) * 0.01)


class RoutedNetworkDiff(BaseModel):
    """Baseline vs buildout routed network: what the consumptive draw does to the loop."""

    model_config = ConfigDict(extra="forbid")

    baseline: str
    scenario: str
    natural_total_cfs: float  # unchanged by the scenario (cited low flows)
    consumptive_increase_cfs: float  # the new draw
    multiple_of_natural: float | None = None  # draw / Σ natural low flow
    outlet_decrease_cfs: float  # baseline outlet - buildout outlet
    mainstem_runs_dry: bool  # the abstraction reach hits 0 under the buildout draw


class AssimilativeCheck(BaseModel):
    """Low-flow dilution of one discharge into its receiving water.

    The dilution ratio is ``(design_low_flow + upstream_returns) / discharge``.
    A screening heuristic flags the result; it is **not** a permit determination.
    """

    model_config = ConfigDict(extra="forbid")

    receiving_water: str
    discharger: str
    design_low_flow: ProvenancedValue  # the 7Q10 (cited)
    discharge: ProvenancedValue
    upstream_returns: ProvenancedValue | None = None
    dilution_ratio: float
    flag: Flag
    detail: str


# Screening thresholds on the dilution ratio (stream low-flow : effluent).
# Below 1, the effluent dominates the stream at design low flow — effectively
# undiluted. These are coarse screening bands, not regulatory mixing-zone rules.
DILUTION_VIOLATION = 1.0
DILUTION_TIGHT = 10.0


class AnnualMinimum(BaseModel):
    """One climatic year's minimum n-day average discharge at a gage.

    The climatic year (Apr 1 to Mar 31) brackets the late-summer low-flow season
    so a single drought is never split across two years. ``complete`` records
    whether the year carried enough daily values to enter the frequency fit — the
    exclusion is auditable, never silent.
    """

    model_config = ConfigDict(extra="forbid")

    climatic_year: int  # the Apr 1 start year
    nday: int
    min_cfs: float
    valid_days: int
    complete: bool


class LowFlowStatistic(BaseModel):
    """A computed n-day, T-year low-flow frequency statistic (e.g. the 7Q10).

    Two independent estimates bracket the value: a parametric **log-Pearson III**
    fit (the USGS-standard distribution, by method of moments on the log of the
    annual minima, with a conditional-probability adjustment when some years run
    dry) and a non-parametric **Weibull** plotting-position interpolation. Both are
    ``derived`` — a screening corroboration of the cited regulatory figure, never a
    substitute for it (see :mod:`bosc.hydrology.lowflow`).
    """

    model_config = ConfigDict(extra="forbid")

    label: str  # "7Q10"
    nday: int
    return_period_yr: int  # 10
    nonexceedance_prob: float  # 0.10 (= 1 / return_period_yr)
    n_years: int  # complete climatic years in the fit
    lp3_cfs: ProvenancedValue  # derived, log-Pearson III
    weibull_cfs: ProvenancedValue  # derived, empirical plotting position
    log_skew: float  # skew of log10(annual minima), the LP3 shape
    zero_fraction: float  # fraction of minima that are zero (dry years)
    cited_cfs: ProvenancedValue | None = None  # the cited regulatory value, if any
    cited_basis: str | None = None  # what the cited value represents (e.g. "summer 30Q10")
    corroborates: bool | None = None  # LP3 within the screening band of the cited value


class LowFlowFrequency(BaseModel):
    """Independent low-flow frequency analysis of one USGS gage's daily record.

    Reproduces the design low flows (1Q10 / 7Q10 / 30Q10) from the raw USGS daily
    discharge — the statistic Ohio EPA cites from a fact sheet but never shows its
    work for. A second, self-standing line of evidence under the assimilative
    screen: when the computed 7Q10 lands on the cited value, the "effluent is
    undiluted at design low flow" finding no longer rests on a single number.
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    site_name: str
    receiving_water: str | None = None
    period_start: str  # ISO date of the first daily value used
    period_end: str
    record_days: int  # valid daily values in the record
    complete_years: int  # climatic years that entered the fit
    completeness_threshold_days: int
    statistics: list[LowFlowStatistic]
    annual_minima: list[AnnualMinimum]  # the auditable per-year series (1/7/30-day)
    method: str
    note: str = ""

    def stat(self, label: str) -> LowFlowStatistic | None:
        return next((s for s in self.statistics if s.label == label), None)

    def minima_for(self, nday: int) -> list[AnnualMinimum]:
        return [m for m in self.annual_minima if m.nday == nday]


class DesignStorm(BaseModel):
    """A design rainfall event (return period x duration -> depth)."""

    model_config = ConfigDict(extra="forbid")

    return_period_yr: int
    duration_hr: float
    depth: ProvenancedValue  # inches, source typically connector (NOAA Atlas-14)


class Hydrograph(BaseModel):
    """A Tier-0 runoff hydrograph (SCS unit-hydrograph convolution)."""

    model_config = ConfigDict(extra="forbid")

    times_hr: list[float]
    flows_cfs: list[float]
    peak_cfs: float
    time_to_peak_hr: float
    volume_acft: float
    runoff_depth_in: float
    curve_number: float
    tier: Literal["tier0"] = "tier0"


class StormRunoff(BaseModel):
    """Pre- vs post-development runoff for a design storm over one footprint.

    The headline stormwater impact: paving a pervious footprint raises the curve
    number, so the same storm yields a higher peak and more volume. The extra
    volume is the screening-grade detention deficit (the volume a basin must hold
    to keep post-development discharge at the pre-development rate).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    area: ProvenancedValue  # acres
    hsg: ProvenancedValue  # hydrologic soil group as a coded value (A=1..D=4) + citation
    storm: DesignStorm
    pre: Hydrograph
    post: Hydrograph

    @property
    def peak_increase_cfs(self) -> float:
        return self.post.peak_cfs - self.pre.peak_cfs

    @property
    def volume_increase_acft(self) -> float:
        return self.post.volume_acft - self.pre.volume_acft


class CoolingBasis(BaseModel):
    """A sourced cooling-water design basis, derived from disclosed campus data.

    Two independent estimates bracket the demand: a top-down power x WUE balance
    (disclosed backup generation -> IT load -> evaporative makeup) and a bottom-up
    blowdown x cycles-of-concentration check (documented FM-2 discharge). The
    inputs are document/assumption-tagged; the demands are ``derived``.
    """

    model_config = ConfigDict(extra="forbid")

    it_load: ProvenancedValue  # MW (from the air-permit genset count)
    wue: ProvenancedValue  # L/kWh, consumptive water per IT energy
    cycles_of_concentration: ProvenancedValue  # cooling-tower CoC
    consumptive_fraction: ProvenancedValue  # (CoC-1)/CoC, derived
    makeup_demand: ProvenancedValue  # MGD, the cooling intake (power-based central)
    consumptive_low: ProvenancedValue  # MGD, power x WUE
    consumptive_high: ProvenancedValue  # MGD, full-blowdown x cycles upper bound
    method: str = "power x WUE (central); blowdown x cycles (upper bound)"


class Scenario(BaseModel):
    """A what-if over the municipal loop, parameterized by the cooling knob.

    The data-center campus draws cooling water from the same Ottawa/Auglaize supply
    the WWTPs discharge to; the evaporated (consumptive) fraction is a net loss to
    the basin. The knobs default to the sourced :class:`CoolingBasis` but remain
    overridable — this is a sensitivity, not a forecast.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    cooling_demand: ProvenancedValue  # campus cooling intake (MGD)
    consumptive_fraction: ProvenancedValue  # fraction evaporated (0..1)
    basis: CoolingBasis | None = None  # the sourced derivation, when used


class ScenarioResult(BaseModel):
    """A scenario evaluated against the water balance + cited low flows."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    consumptive_loss: ProvenancedValue  # net basin loss (cfs), derived from the knobs
    ottawa_7q10: ProvenancedValue | None = None  # cited Ottawa mainstem low flow
    ottawa_live: ProvenancedValue | None = None  # live Ottawa streamflow, for context
    balance: WaterBalance
    assimilative: list[AssimilativeCheck]


class ScenarioDiff(BaseModel):
    """Baseline vs buildout: the net new consumptive draw and its low-flow scale."""

    model_config = ConfigDict(extra="forbid")

    baseline: str
    scenario: str
    consumptive_increase_cfs: float
    ottawa_7q10_cfs: float | None = None
    multiple_of_7q10: float | None = None


class MonthlyWithdrawal(BaseModel):
    """One month: the cooling draw vs the season-appropriate cited low flow.

    The consumptive draw is constant year-round; what changes by month is the
    receiving stream's *available* low flow and whether rainfall offsets atmospheric
    demand. In the growing season the draw is read against the cited summer design low
    flow (30Q10), not the annual 7Q10 — and arrives when reference ET exceeds precip,
    so there is no rainfall buffer.
    """

    model_config = ConfigDict(extra="forbid")

    month: str  # JAN..DEC
    growing_season: bool  # ET0 > precip this month
    et0_mm_day: float
    precip_mm_day: float
    net_atmospheric_mm_day: float  # ET0 - precip (positive = deficit, no rainfall buffer)
    low_flow_cfs: float  # the cited design low flow applied this month
    low_flow_basis: str  # "30Q10 summer" | "7Q10 annual"
    consumptive_cfs: float  # the scenario's net consumptive draw (constant)
    multiple: float | None  # consumptive / low_flow (None when the floor is 0)


class SeasonalWithdrawal(BaseModel):
    """The cooling draw screened month-by-month against the Ottawa's seasonal low flow.

    Bridges the climate baseline (reference ET vs precip) and the cooling scenario: the
    annual-7Q10 multiple understates the growing-season pinch, when the river sits at its
    summer design low flow *and* ET exceeds precip. All low-flow figures are cited
    (`data/reference/hydrology/low-flow-7q10.yaml`); no monthly statistic is fabricated.
    """

    model_config = ConfigDict(extra="forbid")

    scenario: str
    consumptive_cfs: float
    months: list[MonthlyWithdrawal]
    growing_season_months: list[str]
    annual_7q10_cfs: float
    summer_30q10_cfs: float | None = None
    one_q10_cfs: float | None = None  # absolute design low flow (often 0)
    annual_multiple: float | None = None  # draw / annual 7Q10
    summer_multiple: float | None = None  # draw / summer 30Q10 — the seasonal headline


class StormPlanInventory(BaseModel):
    """Document-grounded drainage facts read off the campus grading & storm plan.

    Transcribed from the civil sheet (not computed hydrology), so it belongs in
    ``data/extracted/``. It captures what the drawing *states* — the storm-structure
    rim-elevation population, the conveyance inventory, and crucially whether any
    on-site **detention/retention storage** is shown. The connectivity and inverts
    that a routable SWMM network needs are drawn as vector geometry with no schedule
    table, so we deliberately do **not** fabricate a pipe network here; we ground the
    facts the sheet actually carries and flag the absence of storage.
    """

    model_config = ConfigDict(extra="forbid")

    sheet_id: str  # e.g. "1A-C-3104"
    discipline: str  # "Grading & Storm Plan"
    phase: str  # "95% SPS Design"
    status: str  # "Not For Construction"
    source_path: str  # rel path to the source drawing
    engineer: str | None = None

    # Graded surface, from the storm-structure rim labels.
    rim_labels: int  # count of RIM=… labels read
    rim_distinct: int
    rim_min: ProvenancedValue  # ft (document)
    rim_max: ProvenancedValue  # ft (document)
    relief: ProvenancedValue  # ft (derived: max - min)

    # Conveyance inventory (what the legend/labels name).
    structure_types: list[str] = []
    pipe_sizes_in: list[float] = []  # nominal callout sizes
    conveyance_features: list[str] = []  # swale, headwall, check dam, flood routing, …

    # The determination that reframes the Tier-1 detention result.
    detention_shown: bool  # any on-site storage labeled?
    storage_terms_searched: list[str] = []  # the negative is auditable
    note: str = ""


class DetentionDesign(BaseModel):
    """Tier-1 (SWMM) detention sizing: the basin that holds post-dev peak to pre-dev."""

    model_config = ConfigDict(extra="forbid")

    pre_peak_cfs: float
    post_peak_cfs: float  # undetained post-development
    controlled_peak_cfs: float  # released through the sized orifice
    orifice_diam_ft: float
    required_storage_acft: float
    basin_area_acres: float
    tier: Literal["tier1-swmm"] = "tier1-swmm"


class SanitaryPlant(BaseModel):
    """A WWTP's document-cited sanitary design flows (the grounded sanitary basis)."""

    model_config = ConfigDict(extra="forbid")

    plant: str
    npdes: str | None = None
    receiving_water: str | None = None
    avg_design_flow: ProvenancedValue  # MGD, document-cited permitted average
    peak_capacity: ProvenancedValue | None = None  # MGD, document-cited peak hydraulic
    peaking_factor: ProvenancedValue | None = None  # derived: peak / avg
    pretreatment: bool = False
    note: str | None = None

    @property
    def headroom_mgd(self) -> float | None:
        """Wet-weather headroom above the permitted average (peak - avg), if both cited."""
        if self.peak_capacity is None:
            return None
        return round(self.peak_capacity.value - self.avg_design_flow.value, 2)


class TmdlWla(BaseModel):
    """One facility's total-phosphorus wasteload allocation under the Maumee TMDL."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    npdes: str | None = None
    spring_tp: ProvenancedValue  # metric tons TP, spring season (Mar-Jul)
    daily_tp: ProvenancedValue  # kg TP/day (spring load / 153 days)
    note: str | None = None


class MaumeeTmdl(BaseModel):
    """The Maumee Watershed Nutrient TMDL phosphorus WLAs for the Lima loop.

    A vendored, document-cited reference (transcribed verbatim from Appendix 4 of
    the final TMDL), like the 7Q10 and sanitary tables — not computed hydrology — so
    it lives under ``data/reference/hydrology``. Ties the local low-flow assimilative
    failure to the basin-scale, Lake-Erie-driven nutrient cap on the same permits.
    """

    model_config = ConfigDict(extra="forbid")

    facilities: list[TmdlWla]
    grouped_spring_tp: ProvenancedValue | None = None  # category total, metric tons
    grouped_daily_tp: ProvenancedValue | None = None  # category total, kg/day

    def facility(self, name: str) -> TmdlWla | None:
        return next((f for f in self.facilities if f.facility == name), None)


class SanitaryBasis(BaseModel):
    """Document-grounded sanitary design basis for the municipal loop's WWTPs.

    Aggregates cited per-plant design flows (OEPA NPDES permits / watch-items) with the
    system's I/I + SSO regulatory context (the 1996 federal consent decree and the 2005
    OEPA agreement to eliminate bypassing by 2015). Like the 7Q10 table, it is a vendored,
    cited reference — not computed hydrology — so it lives under ``data/reference``.
    """

    model_config = ConfigDict(extra="forbid")

    plants: list[SanitaryPlant]
    campus_industrial: ProvenancedValue  # MGD, the BOSC FM-2 industrial discharge
    ii_remediation_musd: ProvenancedValue  # $M of documented I/I remediation
    decree_note: str = ""
    source_note: str = ""

    def plant(self, name: str) -> SanitaryPlant | None:
        return next((p for p in self.plants if p.plant == name), None)


class SanitarySurcharge(BaseModel):
    """Campus wet-weather sanitary contribution vs a plant's documented headroom.

    ``wet_weather_peak`` is the campus's SWMM-derived storm contribution (dry-weather
    base + RDII). ``headroom_mgd`` is the receiving plant's documented wet-weather
    headroom (peak hydraulic capacity - permitted average). ``exceeds`` compares the two:
    a campus contribution larger than the headroom is screening-grade SSO risk.
    """

    model_config = ConfigDict(extra="forbid")

    plant: str
    capacity: ProvenancedValue  # MGD, document-cited peak hydraulic capacity
    avg_design_flow: ProvenancedValue | None = None  # MGD, document-cited permitted average
    peaking_factor: ProvenancedValue | None = None  # derived, peak / avg (context)
    headroom_mgd: float | None = None  # peak - avg, the wet-weather margin
    wet_weather_peak: ProvenancedValue  # MGD, SWMM-derived campus contribution (base + RDII)
    exceeds: bool
    margin_mgd: float


class Tier1Result(BaseModel):
    """The Tier-1 SWMM escalation: detention sizing + sanitary surcharge."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    detention: DetentionDesign | None = None
    surcharge: list[SanitarySurcharge] = []
    inventory: StormPlanInventory | None = None  # grounds the detention finding in the real sheet
    sanitary_basis: SanitaryBasis | None = None  # grounds the surcharge in cited design flows
    note: str = ""


@dataclass(frozen=True)
class HydroFinding:
    """One hydrology observation. Mirrors :class:`bosc.pipeline.analyze.Finding`."""

    subject: str
    check: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        mark = "OK " if self.ok else "XX "
        return f"{mark} [{self.check}] {self.subject}: {self.detail}"
