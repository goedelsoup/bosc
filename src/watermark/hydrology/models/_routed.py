"""Routed low-flow stream-network models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.models._core import ProvenancedValue

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
    # Theory-only seam: an exogenous flow this node injects, carrying its OWN provenance
    # (an assumption/derived magnitude, not a 7Q10 or a balance discharge). The cited base
    # topology never sets this — it keeps the graph magnitude-free; only a NetworkTheory's
    # overlay nodes use it, so a toggled-off theory leaves the baseline numerically identical.
    inject_cfs: ProvenancedValue | None = None
    inject_component: Literal["natural", "effluent"] = "natural"  # which component it adds to
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
    inject: ProvenancedValue | None = None  # exogenous theory inflow added here (overlay only)
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
    theories: list[str] = []  # ids of enabled theory overlays (empty = cited baseline)
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
    theories: list[str] = []  # theory overlays active in the buildout side of the diff
    natural_total_cfs: float  # unchanged by the scenario (cited low flows)
    consumptive_increase_cfs: float  # the new draw
    multiple_of_natural: float | None = None  # draw / Σ natural low flow
    outlet_decrease_cfs: float  # baseline outlet - buildout outlet
    mainstem_runs_dry: bool  # the abstraction reach hits 0 under the buildout draw


class NetworkTheory(BaseModel):
    """A toggleable, citation-tagged structural overlay on the routed network.

    A theory is an **unproven** intervention (``status: theorized``) held *out* of the
    cited baseline. Enabling it patches the topology before the solve — it appends
    directed-inflow nodes (each carrying its own ``assumption``/``derived`` injected
    flow via :attr:`NetworkNode.inject_cfs`) and may re-point an existing edge. Both the
    waterfall-roundabout augmentation (directed stormwater into Pike Run) and the FM-3
    Shawnee-II diverter (campus wastewater rebalanced to Shawnee II) are expressed this
    way, so a scenario turns one on by ``id`` without ever editing the cited base graph.
    A toggled-off theory leaves the baseline numerically identical. Nothing here is
    presented as fact — every overlay is labelled theorized and its magnitude tagged
    as an assumption.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    status: Literal["theorized"] = "theorized"
    enabled: bool = False  # catalog default; a run/scenario can override
    confidence: Literal["high", "medium", "low"] = "low"
    citation: str | None = None
    add_nodes: list[NetworkNode] = []  # directed-inflow nodes this theory introduces
    repoint: dict[str, str] = {}  # existing node_id -> new downstream id (re-route an edge)


# ------------------------------------------------------------------ storm-hydrograph routing


class Catchment(BaseModel):
    """The contributing subcatchment that generates a node's design-storm inflow hydrograph.

    Fed to :func:`watermark.hydrology.solver.runoff.simulate_runoff`. Every parameter carries
    its own provenance (``area_acres`` derived from a committed WBD HU polygon where available;
    ``curve_number`` / ``tc_hr`` are stated Tier-0 screening assumptions). Lives in the
    committed ``data/reference/hydrology/reaches.yaml`` companion to the magnitude-free
    ``network.yaml`` topology.
    """

    model_config = ConfigDict(extra="forbid")

    area_acres: ProvenancedValue
    curve_number: ProvenancedValue
    tc_hr: ProvenancedValue


class Reach(BaseModel):
    """The trapezoidal channel a node's hydrograph is routed through to its downstream node.

    Fed to :func:`watermark.hydrology.solver.routing.route` (constant-parameter Muskingum-Cunge).
    ``length_ft`` / ``slope`` are required; the channel-geometry fields are optional and fall
    back to the ``route`` defaults (10 ft bottom width, 2:1 side slope, Manning ``n`` 0.04) when
    omitted — a wide mainstem overrides them, a narrow tributary ditch does not.
    """

    model_config = ConfigDict(extra="forbid")

    length_ft: ProvenancedValue
    slope: ProvenancedValue
    bottom_width_ft: ProvenancedValue | None = None
    side_slope_z: ProvenancedValue | None = None
    manning_n: ProvenancedValue | None = None


class ReachTable(BaseModel):
    """The committed reach geometry + contributing subcatchments, keyed by network node id.

    A node absent from ``catchments`` contributes no storm inflow of its own (a WWTP outfall,
    whose flow is continuous effluent, not a storm event); a node absent from ``reaches`` is a
    pass-through (an outfall sitting at a confluence, or the terminal outlet).
    """

    model_config = ConfigDict(extra="forbid")

    catchments: dict[str, Catchment] = {}
    reaches: dict[str, Reach] = {}


class ReachRouting(BaseModel):
    """How one reach's channel attenuated and lagged the hydrograph passing through it.

    ``attenuation_pct`` is the peak reduction (inflow peak -> outflow peak) and ``lag_hr`` the
    delay in time-to-peak — the two signatures of Muskingum-Cunge routing that a naive
    peak-sum ignores. ``subreaches`` / ``courant`` record the sub-reach discretization the
    reach was routed at (WS-09 / #1609): the reach is split into ``subreaches`` Courant≈1 steps
    routed in series, and ``courant`` (``c·Δt/Δx``, ≈ 1 by construction) is the routing
    validity flag — non-negative Muskingum coefficients + a grid-independent peak.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    name: str
    length_ft: float
    slope: float
    inflow_peak_cfs: float
    inflow_time_to_peak_hr: float
    outflow_peak_cfs: float
    outflow_time_to_peak_hr: float
    attenuation_pct: float  # 100 * (inflow_peak - outflow_peak) / inflow_peak, >= 0
    lag_hr: float  # outflow_time_to_peak - inflow_time_to_peak, >= 0
    subreaches: int = 1  # series Courant≈1 sub-reaches the reach was split into (WS-09 / #1609)
    courant: float = 0.0  # sub-reach Courant number c·Δt/Δx (routing validity flag; ≈ 1)


class RoutedHydrographNetwork(BaseModel):
    """A design-storm runoff hydrograph routed down the cited confluence graph.

    The time-varying counterpart to :class:`RoutedNetwork` (which routes steady-state low
    flow): each contributing subcatchment's SCS design-storm hydrograph is routed downstream
    through Muskingum-Cunge and superposed at confluences, so the outlet peak is **attenuated
    and lagged**, not the arithmetic sum of the tributary peaks. The headline is the routed
    outlet hydrograph vs. the naive ``summed`` hydrograph (the local inflows superposed with no
    routing): ``peak_attenuation_pct`` and ``lag_hr`` quantify what routing buys over the sum.
    Tier-0 screening — not a calibrated HEC-HMS/HEC-RAS model.
    """

    model_config = ConfigDict(extra="forbid")

    tier: Literal["tier0"] = "tier0"
    scenario: str = "design-storm"
    site: str = ""  # the loop's site label (SiteProfile.place) for a site-correct headline
    return_period_yr: int
    storm_depth_in: float
    dt_hr: float
    times_hr: list[float]
    outlet_hydrograph_cfs: list[float]  # routed flow leaving the outlet
    summed_hydrograph_cfs: list[float]  # naive superposition of local inflows (unrouted)
    routed_peak_cfs: float
    summed_peak_cfs: float
    peak_attenuation_pct: float  # 100 * (summed_peak - routed_peak) / summed_peak
    routed_time_to_peak_hr: float
    summed_time_to_peak_hr: float
    lag_hr: float  # routed_time_to_peak - summed_time_to_peak
    reaches: list[ReachRouting]
    warnings: list[str] = []

    def reach(self, node_id: str) -> ReachRouting | None:
        return next((r for r in self.reaches if r.node_id == node_id), None)
