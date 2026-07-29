"""Receiving-water temperature-rise screen for a data-center cooling discharge (epic #1715, P2).

The **heat-side** peer of :mod:`watermark.hydrology.toxics`. Where the toxics screen carries a
facility's chemical load at a receiving reach's design low flow and reads the derived
concentration against Ohio's per-chemical WQS, this screen carries a facility's *heat* load —
the condenser rejection ``cooling_models.reject_heat_load`` already computes but discards — into
the same reach at the same cited design low flows and reads the fully-mixed in-stream temperature
against **Ohio's numeric temperature criteria** (OAC 3745-1-35/31/06, :mod:`.thermal_criteria`)
**and** the **Great Lakes RIS** biological tolerances (EPA-833-F-23-007 Table 3-5). The output is
a CWA **§316(a) / thermal-mixing-zone** flag: where the heat load overwhelms the reach's thermal
assimilative capacity, a permit-level thermal analysis (CORMIX/§316(a) demonstration) is warranted.

**The finding it carries** (symmetric to WS-07's toxics result). The Ottawa River at Lima has a
cited **7Q10 of 0.2 cfs (1Q10 = 0)** — near-zero thermal assimilative capacity. The reach can
absorb only a fraction of a megawatt before its summer daily-maximum criterion is reached, against
a modeled ~300 MW condenser rejection: **thousands of times** the capacity. The finding is
**robust to the heat-partition assumption** — even if only a sliver of the condenser rejection
reaches the stream (an evaporative tower rejects most of it to the atmosphere), that sliver still
exceeds the capacity by orders of magnitude — so the screen reports both the capacity ratio and
the fraction of the rejection that would exhaust the whole capacity.

**Discipline (this is a SCREEN, not a permit determination).**

* The heat load is ``reject_heat_load`` = IT x cooling overhead — a deliberately **conservative,
  once-through-equivalent** bound: it treats the *full* condenser rejection as reaching the
  receiving water. A real evaporative tower rejects most of that to the air (latent heat of
  evaporation); the in-stream load is a fraction. The screen says so, and leans on the
  *capacity ratio* (which is insensitive to the partition) rather than a literal ΔT.
* **Fully-mixed, design-low-flow, order-of-magnitude.** No plume model, no mixing-zone credit,
  no decay. ``T_mixed = ambient + reject / (rho*cp*(Q_s + Q_d))``; the thermal assimilative
  capacity is ``rho*cp*Q_s*(daily_max - ambient)``.
* The **zero-flow** case mirrors the Ottawa 1Q10 = 0 handling in ``toxics`` — no ``Inf`` ΔT, the
  capacity is 0 and the flag is ``no_capacity`` (any heat exceeds by construction).
* The OAC 3745-1-06 (O)(5) **closed-cycle-blowdown exemption** (a closed-cycle cooling blowdown
  whose flow is < 5% of the receiving 7Q10 is exempt from the thermal-mixing-zone rule) is wired
  directly as a regulatory off-ramp — surfaced whether or not it applies.

Zone selection (Lima's Ottawa River → ``lake_erie_basin_general``) reads the table's
``default_zone_hint`` unless a profile pins one.

**Phase 3 (#1718) — facility wiring + ECHO-DMR validation.** The screen no longer models only the
site's own cooling facilities against a stated design ambient. Three additions, all grounded in the
permittees' own reported record (EPA ECHO DMR, :mod:`watermark.hydrology.connectors.echo_dmr`):

1. **The corridor's permitted dischargers are screened too**, on the same reach, at the same design
   low flows, against the same criterion — but their heat load is **observed, not modeled**:
   ``rho*cp*Q_reported*(T_effluent_reported - T_ambient)`` from the outfall's own DMR temperature
   and flow. On the Ottawa at Lima that is the Lima Refinery (OH0002623), PCS Nitrogen (OH0002615)
   and the Lima WWTP (OH0026069). The refinery reports a **32.2 °C** peak daily-maximum effluent
   at ~3.7 MGD into a reach whose 7Q10 is 0.2 cfs: at the design condition the Ottawa below the
   outfall *is* the effluent, ~2.8 °C above Ohio's own daily-maximum criterion, and outfall 001
   carries **no numeric thermal limit**.
2. **The cooling archetypes are screened as explicit scenarios** rather than one conservative bound:
   ``once_through`` (the whole rejection reaches the water — the definition), ``evaporative_blowdown``
   (only the blowdown carries sensible heat; the rest leaves as latent heat to the air, and the
   blowdown temperature is calibrated to the corridor's own observed industrial effluent), and the
   Phase-2 ``conservative_bound``. All three exceed the reach's thermal capacity by 1-3 orders of
   magnitude, which is what makes the finding robust to the heat-partition assumption *quantitatively*
   instead of rhetorically.
3. **The design ambient gains an observed rung.** A permit that requires upstream/downstream river
   monitoring reports the receiving water's own temperature (Lima's WWTP outfall 901,
   "Downstream Monitoring", 24.0 °C peak) — a permittee-reported measurement of this very reach,
   better evidence than the zone's seasonal-average criterion standing in as a design ambient. It
   ranks below a live NWIS 00010 reading and above the reference fallback, and it *lowers* the
   screened severity (more headroom, ~3x more thermal capacity) — the screen is calibrated by the
   record, not defended against it. ``build_screen(dmr=False)`` restores the Phase-2 behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology import cooling_models, units
from watermark.hydrology.connectors import echo, echo_dmr, nwis
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.connectors.echo_dmr import EchoDmrError, OutfallThermal, ThermalDmrRecord
from watermark.hydrology.cooling_models import CoolingParams
from watermark.hydrology.lowflow import _normalize, low_flow_context, low_flow_for
from watermark.hydrology.model import ProvenancedValue, SourceKind
from watermark.hydrology.thermal_criteria import (
    RisSpecies,
    TemperatureCriteriaTable,
    TemperatureZone,
    ThermalToleranceTable,
    load_temperature_criteria,
    load_thermal_tolerances,
)
from watermark.logging import get_logger
from watermark.sites import CoolingModelType, SiteFacility, active_profile

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

# Water's volumetric heat capacity: rho ~= 1000 kg/m^3 x c_p ~= 4.186 kJ/(kg*degC) = 4.186
# MJ/(m^3*degC). Since 1 MW = 1 MJ/s, a heat load H (MW) fully mixed into a flow Q (m^3/s) raises
# it by H / (rho*cp*Q) degC. The same 4.186 c_p the once-through withdrawal derivation uses
# (`cooling_models._OT_LPD_PER_MW`), so the heat/flow unit chain can never drift between them.
_RHO_CP_MJ_PER_M3_C = 4.186
_CFS_TO_M3S = 0.028316846592  # 1 cubic foot = 0.028316846592 m^3

# Above this fully-mixed temperature the reach cannot physically carry the modeled heat load as
# sensible heat in liquid water — reporting a literal ΔT of hundreds of degrees reads as broken.
# The screen sets the ΔT/mixed fields to None with a note instead; the *capacity ratio* (always
# physical) carries the magnitude. 100 degC is the 1-atm boiling point.
_LIQUID_CEILING_C = 100.0

# Exceedance bands on the capacity ratio (reject heat / thermal assimilative capacity), the direct
# heat analog of the toxics concentration/criterion ratio. >= 1 exceeds; >= 0.1 approaches.
_EXCEEDANCE = 1.0
_APPROACH = 0.1

# Closed-cycle cooling archetypes the OAC 3745-1-06 (O)(5) blowdown exemption can bear on — the
# discharge to the stream is tower/loop blowdown, not a once-through pass-through.
_CLOSED_CYCLE = {
    CoolingModelType.EVAPORATIVE_TOWER,
    CoolingModelType.CLOSED_LOOP_DRY,
    CoolingModelType.HYBRID_ADIABATIC,
}
# Dry/no-discharge archetypes: heat is rejected to the air, so there is ~no in-stream thermal load.
_DRY = {CoolingModelType.CLOSED_LOOP_DRY, CoolingModelType.OFF}

# How many Great Lakes RIS thermal anchors to carry as biological context (most sensitive first).
_RIS_ANCHORS = 8

# --- Phase-3 (#1718) DMR validation ----------------------------------------
# The reported-record window the screen validates against. **Fixed**, not "now"-relative: the
# committed screen artifact has to regenerate byte-stable, and a rolling window would silently
# re-rank the corridor between runs. May-Oct is the Ohio EPA regulatory summer window
# (``lowflow.OEPA_SUMMER_MONTHS``, NPDES permit 2PH00006 Part II) — the season the peak-summer
# daily-maximum criterion binds in, and the only season a thermal observation is design-relevant.
# Advance both when a newer complete warm season is on the reported record (and re-record the
# connector fixtures); the CLI's --dmr-start/--dmr-end override them for an ad-hoc read.
DMR_WINDOW_START = "2024-05-01"
DMR_WINDOW_END = "2024-10-31"

# Rows on the screen, split by where the heat load COMES FROM (not by sector). A ``data_center``
# row's load is MODELLED from the disclosed IT load (``cooling_models.reject_heat_load``); a
# ``permitted_discharger`` row's is OBSERVED from the permittee's own reported effluent temperature
# x reported flow. They are screened identically from there on — same reach, same design low flows,
# same criterion — but must never be conflated: one is an inference about a facility that is not
# yet discharging, the other is a measurement. The observed cohort is the corridor's industrial
# dischargers *and* the POTW that shares the reach (``facility_type`` keeps them distinguishable).
KIND_DATA_CENTER = "data_center"
KIND_PERMITTED = "permitted_discharger"

# Cooling scenarios (#1718). The Phase-2 screen carried ONE heat load — the whole condenser
# rejection — as a deliberately conservative bound. Phase 3 keeps that as the upper bound and adds
# the two physically-distinct archetypes, so the §316(a) number is reported per partition instead
# of resting on the bound alone.
SCENARIO_BOUND = "conservative_bound"
SCENARIO_ONCE_THROUGH = "once_through"
SCENARIO_EVAPORATIVE = "evaporative_blowdown"

# Verdicts for the derived-vs-observed cross-check.
_VERDICT_CONSERVATIVE = "conservative"  # the model runs hotter than the corridor's observed record
_VERDICT_CONSISTENT = "consistent"  # within the tolerance below
_VERDICT_UNDERSTATED = "understated"  # the model runs COOLER than what is actually reported
_VERDICT_UNVALIDATED = "unvalidated"  # no observed analog on the reach
# How close a derived effluent temperature has to sit to the observed analog to read "consistent".
# 2 degC — the spread between the corridor's own reported outfalls (27.8-32.2 degC daily max), so
# the tolerance is set by the observed data rather than picked to make the model look good.
_CALIBRATION_TOLERANCE_C = 2.0


# --- Models ----------------------------------------------------------------
class ThermalFlowScreen(BaseModel):
    """The heat load read against the Ohio daily-maximum criterion at one design low flow.

    The direct heat analog of :class:`watermark.hydrology.toxics.CriterionScreen`.
    ``thermal_capacity_mw`` = ``rho*cp*Q*(daily_max - ambient)`` is the loading capacity;
    ``exceedance_factor`` = ``reject_heat / thermal_capacity`` (>= 1 exceeds). When the design
    flow is 0 (the Ottawa 1Q10) or the ambient already meets the criterion, the capacity is 0 and
    both the factor and the mixed temperature are ``None`` (not ``Inf``) — ``flag`` is
    ``no_capacity``. ``capacity_fraction`` = ``thermal_capacity / reject_heat`` is the
    partition-robustness metric: the fraction of the condenser rejection that would exhaust the
    reach's entire thermal capacity.
    """

    model_config = ConfigDict(extra="forbid")

    flow_label: str  # "1Q10" | "7Q10" | "summer 30Q10"
    design_flow: ProvenancedValue  # cfs
    thermal_capacity_mw: float | None  # rho*cp*Q*(daily_max - ambient); 0 when no capacity
    delta_t_c: ProvenancedValue | None  # fully-mixed in-stream rise (None when unbounded)
    mixed_c: ProvenancedValue | None  # ambient + delta_t (None when unbounded)
    exceedance_factor: float | None  # reject_heat / thermal_capacity (None when capacity 0)
    capacity_fraction: float | None  # thermal_capacity / reject_heat (None when reject 0)
    # The share of the reach's temperature headroom the fully-mixed rise consumes — the
    # **dilution-corrected** peer of ``exceedance_factor`` and, where it is computable, what
    # ``flag`` is set from. ``exceedance_factor`` divides by the reach's design flow alone, so it
    # overstates a discharge whose own flow dominates the reach (a 12.8 MGD POTW into a 0.2 cfs
    # 7Q10 reads ~26x "over capacity" while its fully-mixed temperature sits 4 degC *under* the
    # criterion). Ohio's criterion is a TEMPERATURE, so the temperature is the test.
    headroom_fraction: float | None = None  # delta_t / (daily_max - ambient)
    mixed_over_criterion: bool | None = None  # None when the mixed temperature is unbounded
    flag: str  # "exceedance" | "approach" | "ok" | "no_capacity"
    note: str | None = None


class RisThresholdCheck(BaseModel):
    """One Great Lakes RIS thermal limit vs the screened mixed temperature (biological context)."""

    model_config = ConfigDict(extra="forbid")

    common_name: str
    scientific_name: str
    life_stage: str
    metric: str  # "acute_upper" | "optimal_upper"
    limit_c: float
    exceeded: bool | None  # None when the mixed temperature is unbounded (exceeded by construction)


class DmrThermalObservation(BaseModel):
    """A permittee's own reported effluent-temperature record on the screened reach (#1718).

    Every figure is verbatim from EPA ECHO's effluent-chart service, reduced to °C by its
    **reported** unit — ICIS carries temperature under 00010 (°C) *and* 00011 (°F) and this
    corridor uses both. ``effluent_c`` is the peak **daily maximum**, matching the form of Ohio's
    numeric criterion. ``monitor_only`` records the permit that requires temperature monitoring
    but sets no numeric thermal limit — a cited absence, and on the Ottawa the common case.
    ``instream_c`` is the permit's own upstream/downstream river station where it has one: an
    observed *receiving-water* temperature, categorically different from an effluent reading.
    """

    model_config = ConfigDict(extra="forbid")

    npdes_id: str
    permit_name: str | None = None
    window: str
    outfall: str | None = None
    monitoring_location: str | None = None
    parameter_code: str | None = None  # 00010 (degC) | 00011 (degF)
    reported_unit: str | None = None
    n_obs: int = 0
    effluent_c: ProvenancedValue | None = None  # peak reported daily maximum
    mean_monthly_avg_c: float | None = None
    flow: ProvenancedValue | None = None  # the same outfall's reported monthly-average flow, MGD
    permitted_limit_c: ProvenancedValue | None = None  # warm-season numeric daily-max ceiling
    permitted_limit_outfall: str | None = None
    limit_seasonal: bool = False
    monitor_only: bool = True
    reported_exceedances: int = 0  # rows ECHO itself flagged (never computed here)
    over_criterion: bool | None = None  # peak daily max at/over the Ohio daily-max criterion
    over_permitted_limit: bool | None = None
    instream_c: ProvenancedValue | None = None
    instream_station: str | None = None  # "<outfall> (<monitoring location>)"
    note: str | None = None


class ThermalCalibration(BaseModel):
    """The derived-vs-observed cross-check the phase exists to produce (#1718).

    Reads a modelled facility's derived effluent temperature against the corridor's own observed
    industrial effluent (the nearest available analog — the campus holds no discharge permit, so
    there is nothing of its own to read against) and records the design ambient against the
    reach's observed in-stream temperature. ``verdict`` is about the MODEL, not the facility:
    ``conservative`` means the screen runs hotter than the record, which is the defensible
    direction; ``understated`` would mean the record is hotter than the screen and the screen
    needs revisiting.
    """

    model_config = ConfigDict(extra="forbid")

    basis: str
    modeled_effluent_c: float | None = None
    observed_effluent_c: float | None = None
    observed_source: str | None = None  # "NPDES OH0002623 outfall 001 (Lima Refinery)"
    delta_c: float | None = None  # modelled - observed
    verdict: str = _VERDICT_UNVALIDATED
    design_ambient_c: float | None = None
    observed_instream_c: float | None = None
    ambient_delta_c: float | None = None  # design ambient - observed in-stream
    note: str | None = None


class ThermalScenario(BaseModel):
    """One cooling archetype's in-stream heat load, screened at the reach's design low flows.

    The Phase-2 screen carried a single conservative bound (the whole condenser rejection reaching
    the water). A scenario makes the **heat partition** explicit instead: ``instream_heat_mw`` is
    what actually enters the stream under this archetype, and ``instream_fraction`` is its share of
    the condenser rejection. The point of running all three is that they span two orders of
    magnitude of partition and *all* exceed the reach's capacity — the robustness claim, quantified.
    """

    model_config = ConfigDict(extra="forbid")

    scenario: str  # conservative_bound | once_through | evaporative_blowdown
    basis: str
    reject_heat_mw: ProvenancedValue | None = None  # the condenser rejection (same in every case)
    instream_heat_mw: ProvenancedValue | None = None  # the share that reaches the receiving water
    instream_fraction: float | None = None
    discharge_flow: ProvenancedValue | None = None  # the discharge carrying it, MGD
    effluent_c: ProvenancedValue | None = None  # the modelled discharge temperature
    flow_screens: list[ThermalFlowScreen] = []
    flag: str = "context"
    note: str | None = None


class ThermalDischargeScreen(BaseModel):
    """One facility's cooling heat load read against its receiving reach's temperature WQS + RIS."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    facility_key: str
    # `data_center` (heat load MODELLED from the disclosed IT load) or `industrial` (heat load
    # OBSERVED from the permittee's own reported effluent temperature x flow) — #1718.
    kind: str = KIND_DATA_CENTER
    npdes_id: str | None = None
    facility_type: str | None = None  # ECHO's POTW / NON-POTW, for an observed discharger
    cooling_model: str | None = None  # the resolved archetype (None for an industrial discharger)
    method_disclosed: bool  # False for the `unknown` archetype — the flag is qualified

    # The screened heat load (condenser rejection; ranged with the disclosed IT-load span).
    reject_heat_mw: ProvenancedValue | None
    # The heat actually screened into the reach: the condenser rejection for a modelled facility
    # (the conservative once-through-equivalent bound), the reported-record heat load for an
    # industrial one. Distinct fields so a measurement is never displayed as an inference.
    instream_heat_mw: ProvenancedValue | None = None

    # Receiving reach + the Ohio temperature threshold at the peak-summer design period.
    receiving_water: str | None = None
    receiving_water_source: SourceKind | None = None
    zone_id: str | None = None
    zone_rule: str | None = None
    design_period: str | None = None  # the peak-summer half-month label, e.g. "Jul 16-31"
    daily_max_c: ProvenancedValue | None = None  # the Ohio ceiling (reference)
    ambient_c: ProvenancedValue | None = None  # background T_s (connector or reference design)
    headroom_c: float | None = None  # daily_max - ambient (<= 0 -> reach already at/over)
    discharge_flow: ProvenancedValue | None = None  # the facility's cooling discharge Q_d (context)

    flow_screens: list[ThermalFlowScreen] = []
    ris_checks: list[RisThresholdCheck] = []

    # Per-archetype heat-partition scenarios (#1718) — data-center rows only.
    scenarios: list[ThermalScenario] = []
    # The permittee-reported record behind (industrial) or alongside (data-center) this row.
    dmr: DmrThermalObservation | None = None
    # The derived-vs-observed cross-check — data-center rows only.
    calibration: ThermalCalibration | None = None

    # OAC 3745-1-06 (O)(5): a closed-cycle blowdown < 5% of the receiving 7Q10 is exempt from the
    # thermal-mixing-zone rule. Surfaced whether or not it applies (None = not a closed-cycle case).
    blowdown_exempt: bool | None = None
    blowdown_exempt_note: str | None = None

    flag: str  # "critical" | "elevated" | "exempt" | "dry" | "context" | "uncharacterized"
    detail: str


class ThermalDischargeInventory(BaseModel):
    """The screen artifact: provenance meta + the per-facility thermal screens."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    screens: list[ThermalDischargeScreen]

    @property
    def flagged(self) -> list[ThermalDischargeScreen]:
        """Facilities whose heat load overwhelms the reach (the ``critical`` band)."""
        return [s for s in self.screens if s.flag == "critical"]

    @property
    def modelled(self) -> list[ThermalDischargeScreen]:
        """The site's own cooling facilities (heat load derived from the disclosed IT load)."""
        return [s for s in self.screens if s.kind == KIND_DATA_CENTER]

    @property
    def observed(self) -> list[ThermalDischargeScreen]:
        """The corridor's permitted dischargers (heat load from their own reported DMRs)."""
        return [s for s in self.screens if s.kind == KIND_PERMITTED]


# --- Physics ---------------------------------------------------------------
def instream_delta_t_c(heat_mw: float, flow_cfs: float) -> float | None:
    """Fully-mixed in-stream temperature rise (degC) of a heat load over a flow, or ``None``.

    ``ΔT = H / (rho*cp*Q)``. ``None`` when the flow is <= 0 (no water to carry the heat — the
    rise is unbounded), mirroring the toxics zero-design-flow handling (no ``Inf``).
    """
    if flow_cfs <= 0.0 or heat_mw <= 0.0:
        return None if flow_cfs <= 0.0 else 0.0
    return heat_mw / (_RHO_CP_MJ_PER_M3_C * flow_cfs * _CFS_TO_M3S)


def thermal_capacity_mw(flow_cfs: float, headroom_c: float) -> float:
    """The reach's thermal loading capacity (MW): ``rho*cp*Q*(daily_max - ambient)``.

    0 when the design flow is 0 (no assimilative capacity) or the ambient already meets/exceeds
    the criterion (no headroom) — the loading-capacity analog of ``criterion x Q x 8.34`` in
    :mod:`watermark.hydrology.toxics`.
    """
    if flow_cfs <= 0.0 or headroom_c <= 0.0:
        return 0.0
    return _RHO_CP_MJ_PER_M3_C * flow_cfs * _CFS_TO_M3S * headroom_c


def _flag(ratio: float | None) -> str:
    """Band a (reject heat / thermal capacity) ratio: exceedance / approach / ok."""
    if ratio is None:
        return "ok"
    if ratio >= _EXCEEDANCE:
        return "exceedance"
    if ratio >= _APPROACH:
        return "approach"
    return "ok"


# --- Design-condition resolution -------------------------------------------
def _peak_summer_period(zone: TemperatureZone, table: TemperatureCriteriaTable) -> int | None:
    """The index of the zone's warmest half-month (max daily-maximum) — the binding design period.

    Ties resolve to the earliest such period. ``None`` when the zone prints no daily-max at all.
    """
    best_i, best_c = None, float("-inf")
    for i in range(len(table.periods)):
        c = zone.daily_max_c(i)
        if c is not None and c > best_c:
            best_i, best_c = i, c
    return best_i


def _resolve_ambient(
    zone: TemperatureZone,
    period_index: int,
    gage: str | None,
    *,
    instream: ProvenancedValue | None = None,
    settings: Settings,
) -> ProvenancedValue | None:
    """Background receiving-water temperature (degC) at the design period, on a provenance ladder.

    1. The site's abstraction gage's live NWIS ``00010`` peak (``connector``) — a continuous,
       independent instrument. Degrades quietly (offline replay, or a gage with no temperature
       block — most small gages, including the Ottawa's, report only discharge).
    2. The **reach's own reported in-stream monitoring** (#1718): where an NPDES permit on this
       reach requires upstream/downstream river monitoring, the permittee reports the receiving
       water's temperature month by month (Lima's WWTP outfall 901). A permittee-reported
       measurement of this very reach in the design season beats a criterion standing in for one.
    3. The zone's seasonal-**average** temperature criterion at the design period, as a stated
       ``reference`` design ambient (the temperature the reach is expected to sit at in the design
       season per Ohio's own standard) — always available, fully cited.
    Returns ``None`` only when the zone prints no average either (nothing to stand on).
    """
    if gage:
        # A live-service failure degrades to the next rung exactly as an offline replay does: a
        # USGS outage (the Ottawa gage's 00010 request answers 503) must not take the whole screen
        # down when two cited fallbacks are standing right behind it.
        try:
            observed = nwis.observed_water_temperature(gage, settings=settings)
        except (HydroOfflineError, httpx.HTTPError) as exc:
            log.info("thermal.nwis_ambient_unavailable", gage=gage, error=str(exc))
            observed = None
        if observed is not None:
            return observed
    if instream is not None:
        return instream
    avg = zone.average_c(period_index)
    if avg is None:
        return None
    return ProvenancedValue.from_reference(
        avg,
        "degC",
        citation=(
            f"design ambient = the {zone.rule} seasonal-average temperature criterion at the "
            f"design period (no live NWIS 00010 at the receiving gage) — a stated design ambient"
        ),
        confidence="low",
    )


def _design_flow_pv(raw: float, label: str, base: ProvenancedValue | None) -> ProvenancedValue:
    """One design low flow (cfs) as a document value carrying the 7Q10 table's citation."""
    cite = f"{label} — {base.citation}" if base and base.citation else f"{label} design flow"
    return ProvenancedValue.from_document(
        float(raw), "cfs", cite, confidence=(base.confidence if base else "high")
    )


def _design_flows(
    receiving: str, q7: ProvenancedValue | None, *, settings: Settings
) -> list[tuple[str, ProvenancedValue]]:
    """The (label, cfs) design low flows to screen, worst (lowest) first: 1Q10, 7Q10, summer 30Q10.

    The 7Q10 is the cited top-level value; the 1Q10 and summer 30Q10 come from the reach's cited
    ``context`` block. A flow absent from the committed table is omitted (never guessed).
    """
    ctx = low_flow_context(receiving, settings=settings)
    out: list[tuple[str, ProvenancedValue]] = []
    one = ctx.get("one_q10_cfs")
    if one is not None:
        out.append(("1Q10", _design_flow_pv(one, "driest-day 1Q10", q7)))
    if q7 is not None:
        out.append(("7Q10", q7))
    summer = ctx.get("thirty_q10_summer_cfs")
    if summer is not None:
        out.append(("summer 30Q10", _design_flow_pv(summer, "summer 30Q10", q7)))
    out.sort(key=lambda t: t[1].value)
    return out


# --- Corridor NPDES cohort + reported thermal record (#1718) ----------------
class CorridorPermit(NamedTuple):
    """An NPDES permit on the site's receiving reach, plus how its receiving water was resolved.

    The same two-rung ladder :mod:`watermark.hydrology.toxics` resolves a discharger's receiving
    water on, so the heat-side and chemical-side screens can never disagree about who is on the
    reach: ECHO's own cited receiving water first (``connector``), else membership in the site's
    industrial-corridor coordinate box with **no** cited receiving water at all (``assumption``,
    flagged as the inference it is). A permit ECHO cites to a *different* water body is excluded
    outright — never re-pointed onto this reach to pad the cohort.
    """

    npdes_id: str
    name: str
    facility_type: str | None
    receiving_water: str
    source: SourceKind
    citation: str


def _corridor_permits(settings: Settings) -> list[CorridorPermit]:
    """Every NPDES permit on the active site's receiving reach, from the committed ECHO inventory.

    Per-site by construction: the basin inventory file comes from ``SiteProfile.basin`` (via
    :data:`watermark.hydrology.connectors.echo.BASINS`) and the corridor box from
    ``SiteProfile.toxic_corridor_bbox``, so a peer site reads its own basin and its own corridor —
    or, with neither registered, an empty cohort (degrade, don't break).
    """
    prof = active_profile(settings)
    receiving = prof.receiving_water_name or ""
    basin = echo.BASINS.get(prof.basin)
    if basin is None or not receiving:
        return []
    path = settings.reference_dir / "echo" / f"{basin.file_stem}.all-npdes.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    lat_min, lat_max, lon_min, lon_max = prof.toxic_corridor_bbox
    permits: list[CorridorPermit] = []
    for row in data.get("facilities") or []:
        npdes = str(row.get("npdes_id") or "").strip()
        lat, lon = row.get("latitude"), row.get("longitude")
        if not npdes or lat is None or lon is None:
            continue
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            continue
        cited = row.get("receiving_water")
        if cited and _normalize(str(cited)) != _normalize(receiving):
            continue  # ECHO cites a different water body — not this reach
        source: SourceKind = "connector" if cited else "assumption"
        citation = (
            f"EPA ECHO {npdes} — {cited}"
            if cited
            else (
                f"within the {receiving} industrial corridor at {prof.place} (coordinate cluster "
                f"{lat_min}-{lat_max}N, {abs(lon_max)}-{abs(lon_min)}W); receiving water not "
                "independently cited in ECHO"
            )
        )
        permits.append(
            CorridorPermit(
                npdes_id=npdes,
                name=str(row.get("name") or npdes),
                facility_type=(str(row["facility_type"]) if row.get("facility_type") else None),
                receiving_water=receiving,
                source=source,
                citation=citation,
            )
        )
    permits.sort(key=lambda p: p.npdes_id)
    return permits


def _thermal_records(
    permits: list[CorridorPermit], *, start: str, end: str, settings: Settings
) -> dict[str, ThermalDmrRecord]:
    """Pull each corridor permit's reported temperature record; a permit that can't be read is skipped.

    Offline (no cache/fixture) and an ECHO error both degrade to "no record for this permit" —
    the screen then reports the discharger as uncharacterized rather than crashing the whole run
    on one permit, exactly as the ambient ladder degrades.
    """
    records: dict[str, ThermalDmrRecord] = {}
    for permit in permits:
        try:
            records[permit.npdes_id] = echo_dmr.fetch_thermal_record(
                permit.npdes_id, start_date=start, end_date=end, settings=settings
            )
        except (HydroOfflineError, EchoDmrError, httpx.HTTPError) as exc:
            log.info("thermal.dmr_unavailable", npdes=permit.npdes_id, error=str(exc))
    return records


class InstreamAmbient(NamedTuple):
    """The reach's observed in-stream temperature, and which permit's station reported it."""

    value: ProvenancedValue
    station: str
    npdes_id: str


def _instream_ambient(records: dict[str, ThermalDmrRecord]) -> InstreamAmbient | None:
    """The warmest reported **in-stream** temperature on the reach, as a connector design ambient.

    A permit's upstream/downstream river station measures the receiving water itself. The warmest
    daily maximum across the corridor's stations in the window is the design-relevant (peak-summer)
    figure. Returns ``(value, station label)``, or ``None`` when no permit on the reach carries an
    in-stream station.
    """
    best: tuple[str, ThermalDmrRecord, OutfallThermal] | None = None
    for npdes, record in sorted(records.items()):
        outfall = record.warmest_instream
        if outfall is None or outfall.temperature.peak_daily_max_c is None:
            continue
        peak = outfall.temperature.peak_daily_max_c
        if best is None or peak > (best[2].temperature.peak_daily_max_c or -273.0):
            best = (npdes, record, outfall)
    if best is None:
        return None
    npdes, record, outfall = best
    temp = outfall.temperature
    station = f"{npdes} outfall {outfall.outfall} ({outfall.monitoring_location})"
    value = ProvenancedValue.from_connector(
        temp.peak_daily_max_c or 0.0,
        "degC",
        citation=(
            f"peak reported daily-maximum in-stream temperature, EPA ECHO DMR {station}, "
            f"{record.window} — the receiving water's own monitored temperature. It is a "
            "permit-required station DOWNSTREAM of that plant's own outfall, so it is a measured "
            "in-stream temperature, not an undisturbed upstream background"
        ),
        asof=temp.asof,
        confidence="medium",
    )
    return InstreamAmbient(value=value, station=station, npdes_id=npdes)


def _corridor_analog(
    records: dict[str, ThermalDmrRecord], permits: list[CorridorPermit]
) -> tuple[float, str] | None:
    """The warmest reported **effluent** temperature on the reach — the modelling analog.

    The campus holds no discharge permit, so its blowdown temperature has no observation of its
    own. The corridor's own warmest reported industrial effluent is the nearest thing on the
    record; it calibrates the evaporative scenario and grades the modelled effluent temperature.
    An analog by construction, never the campus's own figure.
    """
    names = {p.npdes_id: p.name for p in permits}
    best: tuple[float, str] | None = None
    for npdes, record in sorted(records.items()):
        outfall = record.primary_effluent
        if outfall is None or outfall.temperature.peak_daily_max_c is None:
            continue
        peak = outfall.temperature.peak_daily_max_c
        if best is None or peak > best[0]:
            best = (
                peak,
                f"NPDES {npdes} outfall {outfall.outfall} ({names.get(npdes, record.name or npdes)})",
            )
    return best


def _join_notes(*parts: str | None) -> str | None:
    """Join note sentences with proper terminal punctuation between them.

    The notes are assembled from independent clauses written at different points in the screen,
    so concatenating them raw runs two sentences together ("…reported, not capped The design
    ambient…"). Each part gets a full stop before the next begins.
    """
    kept = [p.strip() for p in parts if p and p.strip()]
    if not kept:
        return None
    return " ".join(p if p.endswith((".", "!", "?")) else f"{p}." for p in kept)


def _absence_note(permit: CorridorPermit, record: ThermalDmrRecord, *, available: bool) -> str:
    """Why a permit on the reach carries no screenable effluent temperature.

    Three distinguishable absences, and collapsing them would misreport the evidence: the
    record could not be **read** at all (offline with no fixture, or an ECHO error — a gap in
    OUR pull, not in the permit); the permit **reports nothing** under either temperature
    parameter; or it reported values under a statistic this screen does not use (neither a
    daily maximum nor a monthly average), which is data on the record that simply cannot be
    read against a daily-maximum criterion.
    """
    if not available:
        return (
            f"NPDES {permit.npdes_id}: its reported record could not be read for "
            f"{record.window} (no cached/committed ECHO response, or the service refused) — a "
            "gap in this pull, NOT a finding about the permit; re-run online to resolve it."
        )
    unscreened = sum(o.temperature.n_unscreened_obs for o in record.effluent)
    if unscreened:
        return (
            f"NPDES {permit.npdes_id} reported {unscreened} effluent temperature value(s) in "
            f"{record.window}, but none under a daily-maximum or monthly-average statistic — "
            "there is nothing here that can be read against a daily-maximum criterion."
        )
    return (
        f"NPDES {permit.npdes_id} reports no effluent temperature in {record.window} — a "
        "cited absence (the permit is not thermally monitored at an effluent outfall in this "
        "window), never read as 'no thermal discharge'."
    )


def _observation(
    permit: CorridorPermit,
    record: ThermalDmrRecord,
    *,
    criterion_c: float | None,
    available: bool = True,
) -> DmrThermalObservation:
    """Reduce one permit's reported thermal record to the screen's observation block.

    ``available`` is ``False`` when the permit's record could not be pulled at all, so the
    absence is attributed to this pull rather than to the permit.
    """
    outfall = record.primary_effluent
    instream = record.warmest_instream
    obs = DmrThermalObservation(
        npdes_id=record.npdes_id,
        permit_name=record.name or permit.name,
        window=record.window,
    )
    # The permitted numeric ceiling can sit on a *different* outfall than the warmest reported one
    # (the Lima Refinery's outfall 003 carries an 85 degF daily max; outfall 001, the one that
    # actually discharges, carries none), so it is resolved across the permit and labelled.
    limited = [o for o in record.effluent if o.temperature.limit_daily_max_c is not None]
    if limited:
        tightest = min(limited, key=lambda o: o.temperature.limit_daily_max_c or 0.0)
        limit_c = tightest.temperature.limit_daily_max_c
        obs.permitted_limit_outfall = tightest.outfall
        obs.limit_seasonal = tightest.temperature.limit_seasonal
        obs.permitted_limit_c = ProvenancedValue.from_document(
            limit_c or 0.0,
            "degC",
            (
                f"NPDES {record.npdes_id} outfall {tightest.outfall} permitted daily-maximum "
                f"temperature limit, reported via EPA ECHO DMR ({record.window})"
                + (
                    " — seasonal; the warm-season ceiling"
                    if tightest.temperature.limit_seasonal
                    else ""
                )
            ),
            confidence="high",
        )

    if instream is not None and instream.temperature.peak_daily_max_c is not None:
        obs.instream_station = f"outfall {instream.outfall} ({instream.monitoring_location})"
        obs.instream_c = ProvenancedValue.from_connector(
            instream.temperature.peak_daily_max_c,
            "degC",
            citation=(
                f"peak reported daily-maximum in-stream temperature, EPA ECHO DMR "
                f"{record.npdes_id} {obs.instream_station}, {record.window}"
            ),
            asof=instream.temperature.asof,
            confidence="medium",
        )

    if outfall is None:
        obs.monitor_only = obs.permitted_limit_c is None
        obs.note = _absence_note(permit, record, available=available)
        return obs

    temp = outfall.temperature
    obs.outfall = outfall.outfall
    obs.monitoring_location = temp.monitoring_location
    obs.parameter_code = temp.parameter_code
    obs.reported_unit = temp.reported_unit
    obs.n_obs = temp.n_obs
    obs.mean_monthly_avg_c = temp.mean_monthly_avg_c
    # `monitor_only` is a property of the outfall that actually discharges, NOT of the permit:
    # the Lima Refinery carries an 85 degF daily-max limit on outfall 003 (which did not
    # discharge in the window) while outfall 001 — the one screened here — carries none. Reading
    # the permit-wide limit as this outfall's cap would report a ceiling that does not bind it.
    obs.monitor_only = temp.limit_daily_max_c is None and temp.limit_monthly_avg_c is None
    obs.reported_exceedances = temp.reported_exceedances
    if temp.peak_daily_max_c is not None:
        obs.effluent_c = ProvenancedValue.from_connector(
            temp.peak_daily_max_c,
            "degC",
            citation=(
                f"peak reported daily-maximum effluent temperature, EPA ECHO DMR "
                f"{record.npdes_id} outfall {outfall.outfall} (parameter {temp.parameter_code}, "
                f"reported in {temp.reported_unit or 'an unstated unit'}), {record.window}"
            ),
            asof=temp.asof,
            confidence="high",
        )
        if criterion_c is not None:
            obs.over_criterion = temp.peak_daily_max_c >= criterion_c
        # Compare against a permit limit ONLY where the limit governs this same outfall. A limit
        # set on a different outfall is real and worth surfacing (it is kept, with its outfall
        # named) but reading this outfall's temperature against it would assert a permit-limit
        # exceedance that has not occurred — `None` is the honest answer, not `True`.
        if obs.permitted_limit_c is not None and obs.permitted_limit_outfall == outfall.outfall:
            obs.over_permitted_limit = temp.peak_daily_max_c >= obs.permitted_limit_c.value
    if outfall.flow_mean_mgd is not None:
        obs.flow = ProvenancedValue.from_connector(
            outfall.flow_mean_mgd,
            "MGD",
            citation=(
                f"mean reported monthly-average flow, EPA ECHO DMR {record.npdes_id} outfall "
                f"{outfall.outfall} (parameter {echo_dmr.FLOW_PARAM}) over "
                f"{outfall.n_flow_months} month(s), {record.window}"
            ),
            asof=temp.asof,
            confidence="high",
        )
    if obs.monitor_only:
        elsewhere = (
            f", though outfall {obs.permitted_limit_outfall} of the same permit does carry one "
            f"({obs.permitted_limit_c.value:g} degC) — a limit that does not bind this discharge"
            if obs.permitted_limit_c is not None
            else ""
        )
        obs.note = (
            f"NPDES {record.npdes_id} monitors effluent temperature at outfall {outfall.outfall} "
            "but ECHO carries NO numeric thermal limit for it — the discharge temperature is "
            f"reported, not capped{elsewhere}."
        )
    return obs


# --- Facility heat + discharge ---------------------------------------------
def _discharge_flow_mgd(fac: SiteFacility, model: CoolingModelType, settings: Settings) -> float:
    """The facility's cooling **discharge** flow to the stream (MGD), for the mixing denominator.

    Once-through returns its whole withdrawal warmed, so the discharge is the withdrawal
    (``makeup_demand``); a tower/hybrid discharges only blowdown; a dry loop / ``off`` discharges
    ~nothing. Undisclosed (``unknown``) is left at 0 — the conservative (largest-rise) denominator.
    """
    if model == CoolingModelType.ONCE_THROUGH:
        basis = cooling_models.get(model).derive(fac, CoolingParams(), settings)
        return basis.makeup_demand.value
    if model in _CLOSED_CYCLE:
        return fac.blowdown_mgd or 0.0
    return 0.0


def _blowdown_exemption(
    fac: SiteFacility, model: CoolingModelType, q7: ProvenancedValue | None
) -> tuple[bool | None, str | None]:
    """OAC 3745-1-06 (O)(5): is a closed-cycle blowdown < 5% of the receiving 7Q10 (exempt)?

    ``(None, None)`` when it does not bear (not a closed-cycle discharge, no disclosed blowdown,
    or no cited 7Q10). At the Ottawa's 0.2 cfs 7Q10 the 5% threshold is ~0.01 cfs — Lima's 2.5 MGD
    blowdown is ~600x that, so **not** exempt; the off-ramp is surfaced with its arithmetic.
    """
    if model not in _CLOSED_CYCLE or fac.blowdown_mgd is None or q7 is None:
        return None, None
    blowdown_cfs = units.mgd_to_cfs(fac.blowdown_mgd)
    threshold_cfs = 0.05 * q7.value
    exempt = blowdown_cfs < threshold_cfs
    note = (
        f"OAC 3745-1-06 (O)(5): closed-cycle blowdown {fac.blowdown_mgd:g} MGD "
        f"({blowdown_cfs:.3f} cfs) vs 5% of the {q7.value:g} cfs 7Q10 = {threshold_cfs:.3f} cfs — "
        f"{'exempt' if exempt else 'NOT exempt'} from the thermal-mixing-zone rule"
    )
    return exempt, note


# --- RIS biological context ------------------------------------------------
def _species_acute_upper(sp: RisSpecies) -> tuple[str, float] | None:
    """The species' most sensitive acute-upper thermal limit (life stage, lowest degC), or ``None``."""
    best: tuple[str, float] | None = None
    for stage in sp.tolerances:
        span = stage.acute.upper_span() if stage.acute else None
        if span is None:
            continue
        low = span[0]
        if best is None or low < best[1]:
            best = (stage.life_stage, low)
    return best


def _ris_checks(
    tolerances: ThermalToleranceTable, mixed_c: float | None
) -> list[RisThresholdCheck]:
    """The most heat-sensitive Great Lakes RIS acute limits vs the mixed temperature (context).

    ``exceeded`` is ``None`` when the mixed temperature is unbounded (the Ottawa design case) —
    every biological limit is exceeded by construction, reported honestly rather than as ``True``
    off a fabricated temperature.
    """
    rows: list[RisThresholdCheck] = []
    for sp in tolerances.species:
        anchor = _species_acute_upper(sp)
        if anchor is None:
            continue
        stage, limit = anchor
        rows.append(
            RisThresholdCheck(
                common_name=sp.common_name,
                scientific_name=sp.scientific_name,
                life_stage=stage,
                metric="acute_upper",
                limit_c=limit,
                exceeded=(None if mixed_c is None else mixed_c >= limit),
            )
        )
    rows.sort(key=lambda r: r.limit_c)  # most heat-sensitive first
    return rows[:_RIS_ANCHORS]


# --- Screen one facility ---------------------------------------------------
def _screen_flow(
    label: str,
    flow: ProvenancedValue,
    reject: ProvenancedValue,
    ambient: ProvenancedValue,
    headroom: float,
    discharge_cfs: float,
    *,
    basis: str = "conservative once-through-equivalent screen",
) -> ThermalFlowScreen:
    """Screen the heat load against the daily-max criterion at one design low flow.

    ``reject`` is the heat that reaches the receiving water under whatever partition the caller
    has already applied — the whole condenser rejection for the conservative bound, the blowdown's
    sensible heat for the evaporative scenario, or a permittee's reported-record heat load for an
    industrial discharger. ``basis`` names that partition in the derived value's citation so a
    stored ΔT always says which read produced it.

    **The flag is the temperature test, not the heat test** (#1718). Ohio's criterion is a
    daily-maximum *temperature*, so where the fully-mixed temperature is computable the flag comes
    from how much of the reach's headroom the rise consumes (``headroom_fraction``), which accounts
    for the discharge's own flow in the mixing denominator. ``exceedance_factor`` — the loading
    ratio against the reach's design flow alone — stays as the cross-facility magnitude, but on its
    own it declares a large, barely-warm discharge an exceedance when its mixed temperature sits
    comfortably under the criterion. Only where the mixed temperature is unbounded (zero design
    flow, or a rise past the liquid-water range) does the loading ratio drive the flag.
    """
    capacity = thermal_capacity_mw(flow.value, headroom)
    factor = round(reject.value / capacity, 2) if capacity > 0 else None
    frac = round(capacity / reject.value, 6) if reject.value > 0 else None
    rise = instream_delta_t_c(reject.value, flow.value + discharge_cfs)

    delta_pv: ProvenancedValue | None = None
    mixed_pv: ProvenancedValue | None = None
    note: str | None = None
    headroom_fraction: float | None = None
    over: bool | None = None
    flag = "no_capacity" if capacity <= 0 else _flag(factor)
    if capacity <= 0.0:
        note = (
            f"{label} = {flow.value:g} cfs: no thermal assimilative capacity"
            + (" (0 cfs design flow)" if flow.value <= 0 else " (ambient at/over the criterion)")
            + " — any heat load exceeds the criterion by construction"
        )
    elif rise is not None and ambient.value + rise <= _LIQUID_CEILING_C:
        cite = (
            f"{reject.value:g} MW to water / (rho*cp*({flow.value:g} + {discharge_cfs:.2g} cfs)) "
            f"fully mixed — {basis} (no plume/mixing-zone credit)"
        )
        delta_pv = ProvenancedValue.derived(round(rise, 1), "degC", citation=cite, confidence="low")
        mixed_pv = ProvenancedValue.derived(
            round(ambient.value + rise, 1),
            "degC",
            citation=f"design ambient {ambient.value:g} + {round(rise, 1):g} degC in-stream rise",
            confidence="low",
        )
        headroom_fraction = round(rise / headroom, 3)
        over = headroom_fraction >= _EXCEEDANCE
        flag = _flag(headroom_fraction)
    else:
        note = (
            f"in-stream rise exceeds the liquid-water range at {label} = {flow.value:g} cfs — the "
            f"reach cannot carry {reject.value:g} MW; effectively no assimilative capacity "
            "(see the capacity ratio)"
        )
    return ThermalFlowScreen(
        flow_label=label,
        design_flow=flow,
        thermal_capacity_mw=(round(capacity, 4) if capacity > 0 else 0.0),
        delta_t_c=delta_pv,
        mixed_c=mixed_pv,
        exceedance_factor=factor,
        capacity_fraction=frac,
        headroom_fraction=headroom_fraction,
        mixed_over_criterion=over,
        flag=flag,
        note=note,
    )


def _facility_flag(
    reject: ProvenancedValue | None,
    receiving: str | None,
    model: CoolingModelType,
    discharge_cfs: float,
    flow_screens: list[ThermalFlowScreen],
    blowdown_exempt: bool | None,
) -> str:
    """Roll the per-flow screens up to a facility flag (preserving the toxics screen vocabulary).

    ``critical`` requires a **computed** exceedance — a nonzero-flow daily-max exceedance with a
    real ``exceedance_factor`` — **under a disclosed cooling method**. The degenerate zero-capacity
    case (1Q10 = 0, or ambient already over the criterion) alone only lifts to ``elevated``,
    mirroring the toxics 1Q10 = 0 handling (otherwise every trickle-flow reach would read
    ``critical``). An ``unknown`` (undisclosed) cooling method also caps at ``elevated``: whether
    the heat even reaches the water is undisclosed, so a conservative once-through-equivalent
    exceedance is not asserted as a §316(a) trigger (never fake certainty a partial site lacks). A
    closed-cycle blowdown under the 5%-of-7Q10 exemption is ``exempt``; a dry/no-discharge
    archetype is ``dry`` (~no in-stream heat).
    """
    if reject is None or receiving is None:
        return "uncharacterized"
    if model in _DRY or (model in _CLOSED_CYCLE and discharge_cfs <= 0.0):
        return "dry"
    if blowdown_exempt:
        return "exempt"
    computed_exceedance = any(
        fs.flag == "exceedance" and fs.exceedance_factor is not None for fs in flow_screens
    )
    if computed_exceedance and model != CoolingModelType.UNKNOWN:
        return "critical"
    if computed_exceedance or any(fs.flag in ("approach", "no_capacity") for fs in flow_screens):
        return "elevated"
    return "context"


def _format_factor(factor: float) -> str:
    """A human capacity-exceedance factor: integer above 10x, one decimal below."""
    return f"{factor:,.0f}x" if factor >= 10.0 else f"{factor:.1f}x"


def _facility_detail(
    fac: SiteFacility,
    reject: ProvenancedValue | None,
    receiving: str | None,
    flow_screens: list[ThermalFlowScreen],
    flag: str,
) -> str:
    """A one-line summary leading with the binding capacity ratio (the partition-robust metric)."""
    if reject is None:
        return f"{fac.name}: no resolvable IT/heat load — thermal impact uncharacterized."
    if receiving is None:
        return (
            f"{fac.name}: {reject.value:g} MW rejected, no cited receiving water — uncharacterized."
        )
    worst = max(
        (fs for fs in flow_screens if fs.exceedance_factor is not None),
        key=lambda fs: fs.exceedance_factor or 0.0,
        default=None,
    )
    if worst is not None and worst.exceedance_factor is not None:
        frac_pct = (worst.capacity_fraction or 0.0) * 100.0
        return (
            f"{fac.name}: ~{reject.value:g} MW condenser rejection vs {receiving} thermal capacity "
            f"— {_format_factor(worst.exceedance_factor)} over at {worst.flow_label} "
            f"(only {frac_pct:.2g}% of the rejection exhausts the capacity) [{flag}]."
        )
    return (
        f"{fac.name}: ~{reject.value:g} MW rejected to {receiving} — no thermal assimilative "
        f"capacity at design low flow [{flag}]."
    )


# --- Cooling scenarios (#1718) ---------------------------------------------
def _heat_mw(flow_mgd: float, delta_c: float) -> float:
    """Sensible heat (MW) a discharge of ``flow_mgd`` carries at ``delta_c`` above ambient."""
    return _RHO_CP_MJ_PER_M3_C * units.mgd_to_cfs(flow_mgd) * _CFS_TO_M3S * delta_c


def _scenario_screens(
    heat: ProvenancedValue,
    ambient: ProvenancedValue,
    headroom: float,
    flows: list[tuple[str, ProvenancedValue]],
    discharge_cfs: float,
    basis: str,
) -> tuple[list[ThermalFlowScreen], str]:
    """Screen one scenario's in-stream heat at every design low flow; return the screens + flag."""
    screens = [
        _screen_flow(label, flow, heat, ambient, headroom, discharge_cfs, basis=basis)
        for label, flow in flows
    ]
    computed = any(s.flag == "exceedance" and s.exceedance_factor is not None for s in screens)
    if computed:
        flag = "critical"
    elif any(s.flag in ("approach", "no_capacity") for s in screens):
        flag = "elevated"
    else:
        flag = "context"
    return screens, flag


def _scenarios(
    fac: SiteFacility,
    model: CoolingModelType,
    reject: ProvenancedValue,
    ambient: ProvenancedValue,
    headroom: float,
    flows: list[tuple[str, ProvenancedValue]],
    pinned_discharge_mgd: float,
    analog: tuple[float, str] | None,
    settings: Settings,
) -> list[ThermalScenario]:
    """The heat-partition scenarios for one modelled facility (#1718).

    ``conservative_bound`` is the Phase-2 read kept as the upper bound. ``once_through`` is the
    archetype where the partition question does not arise — the condenser water *is* the discharge,
    so the whole rejection reaches the stream, and its effluent rise falls straight out of the
    withdrawal ``cooling_models`` already derives. ``evaporative_blowdown`` is the realistic
    tower case: the latent heat of evaporation leaves to the atmosphere and only the **blowdown**
    carries sensible heat downstream, at a temperature calibrated to the corridor's own reported
    industrial effluent (``analog``). Each scenario is omitted, never guessed, when its inputs are
    not on the record: no disclosed blowdown or no observed analog and the evaporative scenario
    simply does not appear.
    """
    out: list[ThermalScenario] = []
    pinned_cfs = units.mgd_to_cfs(pinned_discharge_mgd)
    bound_screens, bound_flag = _scenario_screens(
        reject,
        ambient,
        headroom,
        flows,
        pinned_cfs,
        "the whole condenser rejection treated as reaching the water",
    )
    bound_rise = instream_delta_t_c(reject.value, pinned_cfs) if pinned_discharge_mgd > 0 else None
    out.append(
        ThermalScenario(
            scenario=SCENARIO_BOUND,
            basis=(
                "Upper bound: the entire condenser heat rejection reaches the receiving water at "
                f"the pinned {model.value} archetype's discharge flow. Physically generous for any "
                "closed-cycle archetype (a tower rejects most of it to the air) — carried so the "
                "other scenarios are read against a stated ceiling, not against nothing."
            ),
            reject_heat_mw=reject,
            instream_heat_mw=reject,
            instream_fraction=1.0,
            discharge_flow=(
                ProvenancedValue.derived(
                    round(pinned_discharge_mgd, 2),
                    "MGD",
                    citation=f"the {model.value} archetype's discharge to the receiving water",
                    confidence="low",
                )
                if pinned_discharge_mgd > 0
                else None
            ),
            effluent_c=(
                ProvenancedValue.derived(
                    round(ambient.value + bound_rise, 1),
                    "degC",
                    citation=(
                        f"design ambient {ambient.value:g} + the whole {reject.value:g} MW "
                        f"rejection carried by {pinned_discharge_mgd:g} MGD of discharge"
                    ),
                    confidence="low",
                )
                if bound_rise is not None and ambient.value + bound_rise <= _LIQUID_CEILING_C
                else None
            ),
            flow_screens=bound_screens,
            flag=bound_flag,
        )
    )

    # --- once-through: the whole rejection, carried by the whole withdrawal -----------------
    ot_basis = cooling_models.get(CoolingModelType.ONCE_THROUGH).derive(
        fac, CoolingParams(), settings
    )
    ot_mgd = ot_basis.makeup_demand.value
    ot_cfs = units.mgd_to_cfs(ot_mgd)
    ot_rise = instream_delta_t_c(reject.value, ot_cfs)
    ot_screens, ot_flag = _scenario_screens(
        reject,
        ambient,
        headroom,
        flows,
        ot_cfs,
        "once-through: the condenser water IS the discharge",
    )
    out.append(
        ThermalScenario(
            scenario=SCENARIO_ONCE_THROUGH,
            basis=(
                "Once-through: the cooling water passes the condenser once and returns to the "
                "stream warmed, so the whole rejection reaches the receiving water by definition "
                "— but it arrives diluted in the whole withdrawal, which itself dwarfs the design "
                "low flow. The reach below the outfall is then effectively the discharge."
            ),
            reject_heat_mw=reject,
            instream_heat_mw=reject,
            instream_fraction=1.0,
            discharge_flow=ot_basis.makeup_demand,
            effluent_c=(
                ProvenancedValue.derived(
                    round(ambient.value + ot_rise, 1),
                    "degC",
                    citation=(
                        f"design ambient {ambient.value:g} + the condenser rise of "
                        f"{reject.value:g} MW over the {ot_mgd:,.0f} MGD once-through withdrawal"
                    ),
                    confidence="low",
                )
                if ot_rise is not None
                else None
            ),
            flow_screens=ot_screens,
            flag=ot_flag,
        )
    )

    # --- evaporative blowdown: only the blowdown's sensible heat ----------------------------
    if fac.blowdown_mgd and analog is not None:
        analog_c, analog_src = analog
        delta = round(analog_c - ambient.value, 2)
        if delta > 0.0:
            instream = _heat_mw(fac.blowdown_mgd, delta)
            heat_pv = ProvenancedValue.derived(
                round(instream, 3),
                "MW",
                citation=(
                    f"rho*cp x {fac.blowdown_mgd:g} MGD blowdown x ({analog_c:g} - "
                    f"{ambient.value:g}) degC — the sensible heat the blowdown carries at the "
                    f"corridor's own observed effluent temperature ({analog_src}). The latent "
                    "heat of evaporation leaves to the atmosphere and is not screened here."
                ),
                confidence="low",
            )
            blow_cfs = units.mgd_to_cfs(fac.blowdown_mgd)
            screens, flag = _scenario_screens(
                heat_pv,
                ambient,
                headroom,
                flows,
                blow_cfs,
                "evaporative tower: only the blowdown's sensible heat reaches the water",
            )
            out.append(
                ThermalScenario(
                    scenario=SCENARIO_EVAPORATIVE,
                    basis=(
                        "Evaporative tower: most of the rejection leaves as latent heat of "
                        "evaporation to the atmosphere; only the blowdown carries sensible heat "
                        f"downstream. Its temperature is CALIBRATED to {analog_src} — an observed "
                        "corridor analog, not a figure for this facility, which holds no discharge "
                        "permit of its own."
                    ),
                    reject_heat_mw=reject,
                    instream_heat_mw=heat_pv,
                    instream_fraction=(
                        round(instream / reject.value, 4) if reject.value > 0 else None
                    ),
                    discharge_flow=ProvenancedValue.from_document(
                        fac.blowdown_mgd,
                        "MGD",
                        fac.blowdown_citation or "disclosed cooling blowdown",
                    ),
                    effluent_c=ProvenancedValue.derived(
                        round(analog_c, 1),
                        "degC",
                        citation=(
                            f"blowdown temperature taken from the corridor's observed effluent "
                            f"analog ({analog_src}) — an [inference] by analogy"
                        ),
                        confidence="low",
                    ),
                    flow_screens=screens,
                    flag=flag,
                )
            )
    return out


def _calibration(
    scenarios: list[ThermalScenario],
    ambient: ProvenancedValue,
    analog: tuple[float, str] | None,
    instream: InstreamAmbient | None,
    reference_ambient: float | None,
) -> ThermalCalibration:
    """Grade the modelled effluent temperature against the corridor's observed record (#1718)."""
    once_through = next(
        (s for s in scenarios if s.scenario == SCENARIO_ONCE_THROUGH and s.effluent_c), None
    )
    modeled = once_through.effluent_c.value if once_through and once_through.effluent_c else None
    observed = analog[0] if analog else None
    delta = round(modeled - observed, 2) if (modeled is not None and observed is not None) else None
    if delta is None:
        verdict = _VERDICT_UNVALIDATED
    elif delta > _CALIBRATION_TOLERANCE_C:
        verdict = _VERDICT_CONSERVATIVE
    elif delta < -_CALIBRATION_TOLERANCE_C:
        verdict = _VERDICT_UNDERSTATED
    else:
        verdict = _VERDICT_CONSISTENT

    ambient_delta: float | None = None
    ambient_note = ""
    if instream is not None and reference_ambient is not None:
        ambient_delta = round(reference_ambient - instream.value.value, 2)
        ambient_note = (
            f" The reach's own reported in-stream temperature ({instream.station}) is "
            f"{abs(ambient_delta):g} degC {'below' if ambient_delta >= 0 else 'above'} the "
            "reference design ambient the criteria table supplies, so the observed rung is the "
            "one used."
        )
    if verdict == _VERDICT_UNVALIDATED:
        note = (
            "No permitted discharger on this reach reports an effluent temperature in the window, "
            "so the derived effluent temperature has no observed analog to be read against — the "
            "screen stands on the criteria alone and the cross-check is an [open] gap."
        ) + ambient_note
    else:
        note = (
            f"The modelled once-through effluent runs {abs(delta or 0.0):g} degC "
            f"{'above' if (delta or 0.0) >= 0 else 'BELOW'} the corridor's warmest observed "
            f"industrial effluent — {verdict}."
        ) + ambient_note
    return ThermalCalibration(
        basis=(
            "Derived once-through effluent temperature vs the warmest reported effluent "
            "temperature among the permitted dischargers on the same reach (EPA ECHO DMR). The "
            "campus holds no discharge permit, so the corridor analog is the closest observation "
            "on the record; a `conservative` verdict means the SCREEN runs hotter than the record."
        ),
        modeled_effluent_c=modeled,
        observed_effluent_c=observed,
        observed_source=analog[1] if analog else None,
        delta_c=delta,
        verdict=verdict,
        design_ambient_c=ambient.value,
        observed_instream_c=instream.value.value if instream else None,
        ambient_delta_c=ambient_delta,
        note=note,
    )


# --- Industrial dischargers (observed heat load, #1718) ---------------------
def _industrial_detail(
    permit: CorridorPermit,
    obs: DmrThermalObservation,
    heat: ProvenancedValue | None,
    flow_screens: list[ThermalFlowScreen],
    flag: str,
    criterion_c: float | None,
) -> str:
    """A one-line summary of a permitted discharger's reported thermal record vs the criterion."""
    if obs.effluent_c is None:
        return (
            f"{permit.name} (NPDES {permit.npdes_id}): no effluent temperature reported in "
            f"{obs.window} — thermal load uncharacterized [{flag}]."
        )
    over = (
        f", {round(obs.effluent_c.value - (criterion_c or 0.0), 1):g} degC OVER the "
        f"{criterion_c:g} degC daily-maximum criterion"
        if obs.over_criterion and criterion_c is not None
        else ""
    )
    limit = (
        f"permitted daily-max limit {obs.permitted_limit_c.value:g} degC"
        f" (outfall {obs.permitted_limit_outfall})"
        if obs.permitted_limit_c is not None
        else "NO numeric thermal limit on record"
    )
    if heat is None:
        return (
            f"{permit.name} (NPDES {permit.npdes_id}): reports {obs.effluent_c.value:g} degC peak "
            f"daily-max effluent{over}; {limit}; "
            + (
                f"no reported flow at outfall {obs.outfall}, so the heat load is not derivable"
                if obs.flow is None
                else "no net heat load above the design ambient"
            )
            + f" [{flag}]."
        )
    # Lead with the in-stream temperature the criterion is actually written against; the capacity
    # ratio follows as magnitude. Preferring the worst *computable* mixed temperature keeps a
    # 12 MGD, barely-warm discharge from reading like a hot one on the loading ratio alone.
    worst = max(
        (fs for fs in flow_screens if fs.mixed_c is not None),
        key=lambda fs: fs.mixed_c.value if fs.mixed_c else 0.0,
        default=None,
    )
    if worst is not None and worst.mixed_c is not None:
        verdict = "OVER" if worst.mixed_over_criterion else "under"
        against = f"{verdict} the {criterion_c:g} degC criterion" if criterion_c else verdict
        outcome = (
            f"fully mixed at {worst.flow_label} the reach reaches {worst.mixed_c.value:g} degC — "
            f"{against} ({(worst.headroom_fraction or 0.0) * 100:.0f}% of the reach's headroom"
            + (
                f", {_format_factor(worst.exceedance_factor)} its loading capacity)"
                if worst.exceedance_factor is not None
                else ")"
            )
        )
    else:
        outcome = "no thermal assimilative capacity at design low flow"
    return (
        f"{permit.name} (NPDES {permit.npdes_id}): reports {obs.effluent_c.value:g} degC peak "
        f"daily-max effluent at {obs.flow.value if obs.flow else 0:g} MGD{over}; {limit}. "
        f"Reported-record heat load ~{heat.value:g} MW — {outcome} [{flag}]."
    )


def _screen_industrial(
    permit: CorridorPermit,
    record: ThermalDmrRecord,
    *,
    receiving: str,
    ambient: ProvenancedValue,
    headroom: float,
    flows: list[tuple[str, ProvenancedValue]],
    criterion_c: float | None,
    tolerances: ThermalToleranceTable,
    ambient_npdes: str | None = None,
    available: bool = True,
) -> ThermalDischargeScreen:
    """Screen one permitted discharger's **reported** heat load against the reach's criterion.

    The heat load is measured, not modelled: ``rho*cp*Q_reported*(T_reported - T_ambient)`` from
    the outfall's own DMR temperature and flow. A reported effluent COOLER than the design ambient
    carries no net heat at the design condition and is reported as such (never a negative load),
    and an outfall with a temperature but no flow is reported without a load rather than paired
    with some other outfall's flow.

    ``ambient_npdes`` names the permit whose in-stream station supplied the design ambient. When
    that is *this* permit the read is partly circular — the station sits downstream of this
    plant's own outfall, so the "background" it measures already carries this discharge's heat —
    and the screen says so on the row rather than presenting an independent comparison.

    ``available`` is ``False`` when the permit's record could not be pulled at all. The permit
    still gets a row — dropping it would make the corridor look smaller than it is, and the
    per-permit counts would stop reconciling — but the row is ``uncharacterized`` and says the
    gap is in this pull, not in the permit.
    """
    obs = _observation(permit, record, criterion_c=criterion_c, available=available)
    heat: ProvenancedValue | None = None
    flow_screens: list[ThermalFlowScreen] = []
    ris_checks: list[RisThresholdCheck] = []
    if obs.effluent_c is not None and obs.flow is not None:
        delta = round(obs.effluent_c.value - ambient.value, 2)
        if delta > 0.0:
            heat = ProvenancedValue.derived(
                round(_heat_mw(obs.flow.value, delta), 3),
                "MW",
                citation=(
                    f"rho*cp x {obs.flow.value:g} MGD reported effluent flow x "
                    f"({obs.effluent_c.value:g} - {ambient.value:g}) degC above the design "
                    f"ambient — the reported-record heat load of NPDES {permit.npdes_id} "
                    f"outfall {obs.outfall} (EPA ECHO DMR, {obs.window})"
                ),
                confidence="medium",
            )
            flow_screens = [
                _screen_flow(
                    label,
                    flow,
                    heat,
                    ambient,
                    headroom,
                    units.mgd_to_cfs(obs.flow.value),
                    basis="reported-record heat load (permittee's own DMR temperature x flow)",
                )
                for label, flow in flows
            ]
            binding = flow_screens[0] if flow_screens else None
            ris_checks = _ris_checks(
                tolerances, binding.mixed_c.value if (binding and binding.mixed_c) else None
            )
        else:
            obs.note = (
                f"NPDES {permit.npdes_id}: reported peak effluent ({obs.effluent_c.value:g} degC) "
                f"is at or below the design ambient ({ambient.value:g} degC) — no net heat load at "
                "the design condition, so no capacity ratio is computed."
            )

    if ambient_npdes == permit.npdes_id and obs.instream_c is not None:
        circular = (
            f"The design ambient for this screen is this permit's OWN in-stream station "
            f"({obs.instream_station}), which sits downstream of its outfall — so the heat load "
            "below is measured against water this discharge has already warmed, and is a floor."
        )
        obs.note = _join_notes(obs.note, circular)

    if obs.effluent_c is None:
        flag = "uncharacterized"
    elif heat is None and obs.flow is None:
        flag = "elevated" if obs.over_criterion else "context"
    elif heat is None:
        flag = "context"
    elif any(fs.flag == "exceedance" and fs.exceedance_factor is not None for fs in flow_screens):
        flag = "critical"
    elif any(fs.flag in ("approach", "no_capacity") for fs in flow_screens):
        flag = "elevated"
    else:
        flag = "context"

    return ThermalDischargeScreen(
        facility=permit.name,
        facility_key=permit.npdes_id,
        kind=KIND_PERMITTED,
        npdes_id=permit.npdes_id,
        facility_type=permit.facility_type,
        cooling_model=None,
        method_disclosed=True,  # the discharge itself is on the record, whatever cools it
        reject_heat_mw=None,  # no condenser model — the load is measured, not derived from IT
        instream_heat_mw=heat,
        receiving_water=receiving,
        receiving_water_source=permit.source,
        ambient_c=ambient,
        headroom_c=headroom,
        discharge_flow=obs.flow,
        flow_screens=flow_screens,
        ris_checks=ris_checks,
        dmr=obs,
        flag=flag,
        detail=_industrial_detail(permit, obs, heat, flow_screens, flag, criterion_c),
    )


# --- Build -----------------------------------------------------------------
def build_screen(
    settings: Settings | None = None,
    *,
    dmr: bool = True,
    dmr_start: str = DMR_WINDOW_START,
    dmr_end: str = DMR_WINDOW_END,
) -> ThermalDischargeInventory:
    """Screen the active site's cooling facilities — and its reach's permitted dischargers.

    Each disclosed facility's condenser heat rejection (``cooling_models.reject_heat_load``) is
    carried into the site's receiving water at its cited design low flows (1Q10 / 7Q10 / summer
    30Q10) and read against the Ohio daily-maximum temperature criterion for the reach's zone and
    the Great Lakes RIS biological tolerances. The facility flag rolls the per-flow capacity
    exceedances up (``critical`` = a computed daily-max exceedance = a §316(a)/mixing-zone trigger).

    With ``dmr`` (the default, #1718) the screen also reads the reach's **reported record** from
    EPA ECHO over ``dmr_start..dmr_end``: every NPDES permit on the reach is screened on its own
    reported effluent temperature x flow, the reach's in-stream monitoring supplies an observed
    design ambient, and each modelled facility gains its heat-partition scenarios plus a
    derived-vs-observed calibration. ``dmr=False`` is the pure-offline Phase-2 read: no connector
    call, the stated reference design ambient, no scenarios, no observations.
    """
    settings = settings or get_settings()
    prof = active_profile(settings)
    table = load_temperature_criteria(settings=settings)
    tolerances = load_thermal_tolerances(settings=settings)

    receiving = prof.receiving_water_name or None
    # Zone selection reads a profile pin when a site sets one, else the table's hint (Lima's
    # Ottawa River -> lake_erie_basin_general).
    zone_id = getattr(prof, "temperature_zone_id", None) or table.default_zone_hint
    zone = table.zone(zone_id)
    period_index = _peak_summer_period(zone, table) if zone else None
    daily_max = zone.daily_max_c(period_index) if (zone and period_index is not None) else None
    design_period = (
        table.periods[period_index].label if (period_index is not None and table.periods) else None
    )

    # The reported record for the reach: the corridor cohort, its DMR temperature series, the
    # observed in-stream ambient, and the warmest observed effluent (the modelling analog).
    permits = _corridor_permits(settings) if dmr else []
    records = (
        _thermal_records(permits, start=dmr_start, end=dmr_end, settings=settings)
        if permits
        else {}
    )
    instream = _instream_ambient(records) if records else None
    analog = _corridor_analog(records, permits) if records else None

    daily_max_pv: ProvenancedValue | None = None
    ambient: ProvenancedValue | None = None
    headroom: float | None = None
    reference_ambient: float | None = None
    if zone and period_index is not None and daily_max is not None:
        daily_max_pv = ProvenancedValue.from_reference(
            daily_max,
            "degC",
            citation=f"{zone.rule} daily-maximum temperature criterion, {design_period}",
            confidence="high",
        )
        reference_ambient = zone.average_c(period_index)
        ambient = _resolve_ambient(
            zone,
            period_index,
            prof.abstraction_gage,
            instream=instream.value if instream else None,
            settings=settings,
        )
        if ambient is not None:
            headroom = round(daily_max - ambient.value, 2)

    q7 = low_flow_for(receiving, settings=settings) if receiving else None
    flows = _design_flows(receiving, q7, settings=settings) if receiving else []

    screens: list[ThermalDischargeScreen] = []
    for fac in prof.facilities:
        model = cooling_models.resolve_cooling_model(fac)
        reject = cooling_models.reject_heat_load(fac)
        discharge_mgd = _discharge_flow_mgd(fac, model, settings) if reject else 0.0
        discharge_cfs = units.mgd_to_cfs(discharge_mgd)
        discharge_pv = (
            ProvenancedValue.derived(
                round(discharge_mgd, 2),
                "MGD",
                citation=f"cooling discharge to {receiving} for the {model.value} archetype",
                confidence="low",
            )
            if reject and discharge_mgd > 0
            else None
        )

        flow_screens: list[ThermalFlowScreen] = []
        ris_checks: list[RisThresholdCheck] = []
        scenarios: list[ThermalScenario] = []
        calibration: ThermalCalibration | None = None
        blowdown_exempt: bool | None = None
        blowdown_note: str | None = None
        if (
            reject is not None
            and receiving is not None
            and ambient is not None
            and headroom is not None
        ):
            for label, flow in flows:
                flow_screens.append(
                    _screen_flow(label, flow, reject, ambient, headroom, discharge_cfs)
                )
            # RIS context at the binding (worst, lowest-flow) design condition's mixed temperature.
            binding = flow_screens[0] if flow_screens else None
            mixed = binding.mixed_c.value if (binding and binding.mixed_c) else None
            ris_checks = _ris_checks(tolerances, mixed)
            blowdown_exempt, blowdown_note = _blowdown_exemption(fac, model, q7)
            # The heat-partition scenarios + the derived-vs-observed cross-check (#1718). A dry /
            # no-discharge archetype rejects its heat to the air, so there is no partition to
            # explore and no effluent temperature to calibrate — scenarios are omitted.
            if dmr and model not in _DRY:
                scenarios = _scenarios(
                    fac,
                    model,
                    reject,
                    ambient,
                    headroom,
                    flows,
                    discharge_mgd,
                    analog,
                    settings,
                )
                calibration = _calibration(scenarios, ambient, analog, instream, reference_ambient)

        flag = _facility_flag(
            reject, receiving, model, discharge_cfs, flow_screens, blowdown_exempt
        )
        detail = _facility_detail(fac, reject, receiving, flow_screens, flag)

        screens.append(
            ThermalDischargeScreen(
                facility=fac.name,
                facility_key=fac.key or fac.name,
                kind=KIND_DATA_CENTER,
                cooling_model=model.value,
                method_disclosed=(model != CoolingModelType.UNKNOWN),
                reject_heat_mw=reject,
                instream_heat_mw=reject,
                receiving_water=receiving,
                receiving_water_source=("document" if q7 else None) if receiving else None,
                zone_id=zone_id if zone else None,
                zone_rule=zone.rule if zone else None,
                design_period=design_period,
                daily_max_c=daily_max_pv,
                ambient_c=ambient,
                headroom_c=headroom,
                discharge_flow=discharge_pv,
                flow_screens=flow_screens,
                ris_checks=ris_checks,
                scenarios=scenarios,
                calibration=calibration,
                blowdown_exempt=blowdown_exempt,
                blowdown_exempt_note=blowdown_note,
                flag=flag,
                detail=detail,
            )
        )

    # The reach's permitted dischargers, screened on their own reported record (#1718).
    if receiving is not None and ambient is not None and headroom is not None:
        for permit in permits:
            # A permit whose record could not be read still gets a row. Dropping it would shrink
            # the corridor silently — the reader would see a cohort of 3 where the reach holds 6,
            # with no sign that the difference is a pull failure rather than an empty record — and
            # `corridor_permits` would stop reconciling with the rows beneath it. The row says
            # which it is (see `_absence_note`).
            record = records.get(permit.npdes_id)
            available = record is not None
            industrial = _screen_industrial(
                permit,
                record
                or ThermalDmrRecord(
                    npdes_id=permit.npdes_id,
                    name=permit.name,
                    window=f"{dmr_start}..{dmr_end}",
                    permit_status=None,
                    snc_status=None,
                ),
                receiving=receiving,
                ambient=ambient,
                headroom=headroom,
                flows=flows,
                criterion_c=daily_max,
                tolerances=tolerances,
                ambient_npdes=instream.npdes_id if instream else None,
                available=available,
            )
            screens.append(
                industrial.model_copy(
                    update={
                        "zone_id": zone_id if zone else None,
                        "zone_rule": zone.rule if zone else None,
                        "design_period": design_period,
                        "daily_max_c": daily_max_pv,
                    }
                )
            )

    order = {
        "critical": 0,
        "elevated": 1,
        "exempt": 2,
        "dry": 3,
        "context": 4,
        "uncharacterized": 5,
    }

    def _rank(s: ThermalDischargeScreen) -> tuple[int, int, float]:
        """Worst flag first; within a flag, modelled facilities before observed dischargers,
        then by the heat that actually reaches the water (largest first)."""
        heat = s.reject_heat_mw or s.instream_heat_mw
        return (
            order.get(s.flag, 9),
            0 if s.kind == KIND_DATA_CENTER else 1,
            -(heat.value if heat is not None else 0.0),
        )

    screens.sort(key=_rank)

    monitor_only = [s for s in screens if s.dmr is not None and s.dmr.monitor_only and s.dmr.n_obs]
    over_criterion = [s for s in screens if s.dmr is not None and s.dmr.over_criterion]
    meta: dict[str, Any] = {
        "subject": (
            "Cooling + industrial heat load vs receiving-water temperature WQS / CWA §316(a), "
            "validated against the reported (ECHO DMR) effluent-temperature record"
        ),
        "source": (
            "watermark.hydrology.cooling_models (condenser heat rejection) x EPA ECHO DMR "
            "effluent temperature (parameters 00010/00011) + flow (50050) x Ohio EPA cited design "
            "low flows (data/reference/hydrology/low-flow-7q10.yaml) x Ohio temperature criteria "
            "(data/reference/wqs/ohio-temperature-criteria.yaml) x Great Lakes RIS tolerances "
            "(data/reference/thermal/great-lakes-ris-thermal-tolerances.yaml, EPA-833-F-23-007)"
        ),
        "site": settings.site,
        "receiving_water": receiving,
        "zone_id": zone_id if zone else None,
        "zone_rule": zone.rule if zone else None,
        "design_period": design_period,
        "daily_max_c": daily_max,
        "ambient_c": ambient.value if ambient else None,
        "ambient_source": ambient.source if ambient else None,
        "reference_ambient_c": reference_ambient,
        "facility_count": len(screens),
        "modelled_count": sum(1 for s in screens if s.kind == KIND_DATA_CENTER),
        "industrial_count": sum(1 for s in screens if s.kind == KIND_PERMITTED),
        "critical_count": sum(1 for s in screens if s.flag == "critical"),
        # The reported-record read (#1718).
        "dmr_window": f"{dmr_start}..{dmr_end}" if dmr else None,
        "corridor_permits": len(permits),
        "corridor_permits_with_thermal_record": sum(
            1 for s in screens if s.dmr is not None and s.dmr.n_obs > 0
        ),
        "observed_instream_station": instream.station if instream else None,
        "observed_instream_c": instream.value.value if instream else None,
        "observed_effluent_analog": analog[1] if analog else None,
        "observed_effluent_analog_c": analog[0] if analog else None,
        "monitor_only_permits": [s.npdes_id for s in monitor_only],
        "permits_over_daily_max_criterion": [s.npdes_id for s in over_criterion],
        "caveats": [
            "A MODELLED (data-center) row's heat load is the CONDENSER heat rejection (IT x "
            "cooling overhead) — an inference about a facility that is not yet discharging. An "
            "INDUSTRIAL row's is the permittee's own reported effluent temperature x reported "
            "flow — a measurement. They are screened identically from there on but never "
            "conflated; read `kind` before quoting a number.",
            "Fully-mixed, design-low-flow, order-of-magnitude: no CORMIX plume model, no "
            "mixing-zone credit, no decay. T_mixed above the daily-max criterion flags the need "
            "for a permit-level thermal / CWA §316(a) analysis, NOT an automatic violation.",
            "The thermal assimilative capacity is rho*cp*Q*(daily_max - ambient). At a 0 cfs "
            "design flow (the Ottawa 1Q10) or an ambient already at the criterion the capacity is "
            "0 — any heat load exceeds by construction (no Inf ΔT, mirroring the toxics screen).",
            "The design ambient is a live NWIS 00010 reading where the gage carries one, else the "
            "reach's own reported in-stream (upstream/downstream) DMR monitoring, else the zone's "
            "seasonal-average temperature criterion as a stated design ambient. An in-stream "
            "station sits downstream of that plant's own outfall, so it is a measured in-stream "
            "temperature, not an undisturbed upstream background.",
            "Cooling scenarios span the heat PARTITION, not uncertainty in the load: "
            "`once_through` sends the whole rejection to the stream by definition, "
            "`evaporative_blowdown` sends only the blowdown's sensible heat (the rest leaves as "
            "latent heat to the air) at a temperature CALIBRATED to an observed corridor analog — "
            "an [inference] by analogy, never this facility's own figure. "
            "`conservative_bound` is the Phase-2 ceiling.",
            "Reported DMR values are verbatim from the permittee's submissions via ECHO and "
            "reduced to degC by their REPORTED unit (00011 is Fahrenheit, 00010 Celsius); an "
            "exceedance count is ECHO's own determination, never computed here by comparing a "
            "value to a limit. A permit with no numeric thermal limit is recorded as "
            "monitor-only — a cited absence, not a clean bill of health.",
            "The OAC 3745-1-06 (O)(5) closed-cycle-blowdown exemption (blowdown < 5% of the 7Q10) "
            "is evaluated and surfaced whether or not it applies. RIS tolerances are the Great "
            "Lakes biological limits for a §316(a) balanced-indigenous-community read, "
            "[reference] (federal guidance, not law).",
        ],
    }
    return ThermalDischargeInventory(meta=meta, screens=screens)


# --- Persistence -----------------------------------------------------------
def write_screen(inv: ThermalDischargeInventory, out_dir: Path) -> Path:
    """Write the screen to ``<out_dir>/thermal-discharge-screen.yaml``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "thermal-discharge-screen.yaml"
    path.write_text(
        yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_screen(reference_dir: Path) -> ThermalDischargeInventory | None:
    """Load a committed thermal screen, or ``None`` if it hasn't been generated."""
    path = reference_dir / "hydrology" / "thermal-discharge-screen.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ThermalDischargeInventory(**data)
