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

Zone selection (Lima's Ottawa River → ``lake_erie_basin_general``) and the live effluent-temperature
validation (ECHO DMR) are **Phase-3** (#1718) concerns: this module reads the table's
``default_zone_hint`` and degrades to a stated design ambient when the gage carries no 00010.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology import cooling_models, units
from watermark.hydrology.connectors import nwis
from watermark.hydrology.connectors._cache import HydroOfflineError
from watermark.hydrology.cooling_models import CoolingParams
from watermark.hydrology.lowflow import low_flow_context, low_flow_for
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


class ThermalDischargeScreen(BaseModel):
    """One facility's cooling heat load read against its receiving reach's temperature WQS + RIS."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    facility_key: str
    cooling_model: str  # the resolved archetype
    method_disclosed: bool  # False for the `unknown` archetype — the flag is qualified

    # The screened heat load (condenser rejection; ranged with the disclosed IT-load span).
    reject_heat_mw: ProvenancedValue | None

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
    settings: Settings,
) -> ProvenancedValue | None:
    """Background receiving-water temperature (degC) at the design period, on a provenance ladder.

    1. The site's abstraction gage's live NWIS ``00010`` peak (``connector``) — the issue's
       directive. Degrades quietly (offline replay, or a gage with no temperature block).
    2. The zone's seasonal-**average** temperature criterion at the design period, as a stated
       ``reference`` design ambient (the temperature the reach is expected to sit at in the design
       season per Ohio's own standard) — always available, fully cited.
    Returns ``None`` only when the zone prints no average either (nothing to stand on).
    """
    if gage:
        try:
            observed = nwis.observed_water_temperature(gage, settings=settings)
        except HydroOfflineError:
            observed = None
        if observed is not None:
            return observed
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
) -> ThermalFlowScreen:
    """Screen the heat load against the daily-max criterion at one design low flow."""
    capacity = thermal_capacity_mw(flow.value, headroom)
    factor = round(reject.value / capacity, 2) if capacity > 0 else None
    frac = round(capacity / reject.value, 6) if reject.value > 0 else None
    rise = instream_delta_t_c(reject.value, flow.value + discharge_cfs)

    delta_pv: ProvenancedValue | None = None
    mixed_pv: ProvenancedValue | None = None
    note: str | None = None
    if capacity <= 0.0:
        note = (
            f"{label} = {flow.value:g} cfs: no thermal assimilative capacity"
            + (" (0 cfs design flow)" if flow.value <= 0 else " (ambient at/over the criterion)")
            + " — any heat load exceeds the criterion by construction"
        )
    elif rise is not None and ambient.value + rise <= _LIQUID_CEILING_C:
        cite = (
            f"{reject.value:g} MW rejected / (rho*cp*({flow.value:g} + {discharge_cfs:.2g} cfs)) "
            "fully mixed — conservative once-through-equivalent screen (no plume/mixing-zone credit)"
        )
        delta_pv = ProvenancedValue.derived(round(rise, 1), "degC", citation=cite, confidence="low")
        mixed_pv = ProvenancedValue.derived(
            round(ambient.value + rise, 1),
            "degC",
            citation=f"design ambient {ambient.value:g} + {round(rise, 1):g} degC in-stream rise",
            confidence="low",
        )
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
        flag=("no_capacity" if capacity <= 0 else _flag(factor)),
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


# --- Build -----------------------------------------------------------------
def build_screen(settings: Settings | None = None) -> ThermalDischargeInventory:
    """Screen the active site's cooling facilities against their receiving reach's thermal WQS.

    Each disclosed facility's condenser heat rejection (``cooling_models.reject_heat_load``) is
    carried into the site's receiving water at its cited design low flows (1Q10 / 7Q10 / summer
    30Q10) and read against the Ohio daily-maximum temperature criterion for the reach's zone and
    the Great Lakes RIS biological tolerances. The facility flag rolls the per-flow capacity
    exceedances up (``critical`` = a computed daily-max exceedance = a §316(a)/mixing-zone trigger).
    """
    settings = settings or get_settings()
    prof = active_profile(settings)
    table = load_temperature_criteria(settings=settings)
    tolerances = load_thermal_tolerances(settings=settings)

    receiving = prof.receiving_water_name or None
    # Zone selection is a Phase-3 (#1718) SiteProfile knob; until then read the table's hint
    # (Lima's Ottawa River -> lake_erie_basin_general). Forward-compatible: prefer a profile field.
    zone_id = getattr(prof, "temperature_zone_id", None) or table.default_zone_hint
    zone = table.zone(zone_id)
    period_index = _peak_summer_period(zone, table) if zone else None
    daily_max = zone.daily_max_c(period_index) if (zone and period_index is not None) else None
    design_period = (
        table.periods[period_index].label if (period_index is not None and table.periods) else None
    )

    daily_max_pv: ProvenancedValue | None = None
    ambient: ProvenancedValue | None = None
    headroom: float | None = None
    if zone and period_index is not None and daily_max is not None:
        daily_max_pv = ProvenancedValue.from_reference(
            daily_max,
            "degC",
            citation=f"{zone.rule} daily-maximum temperature criterion, {design_period}",
            confidence="high",
        )
        ambient = _resolve_ambient(zone, period_index, prof.abstraction_gage, settings=settings)
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

        flag = _facility_flag(
            reject, receiving, model, discharge_cfs, flow_screens, blowdown_exempt
        )
        detail = _facility_detail(fac, reject, receiving, flow_screens, flag)

        screens.append(
            ThermalDischargeScreen(
                facility=fac.name,
                facility_key=fac.key or fac.name,
                cooling_model=model.value,
                method_disclosed=(model != CoolingModelType.UNKNOWN),
                reject_heat_mw=reject,
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
                blowdown_exempt=blowdown_exempt,
                blowdown_exempt_note=blowdown_note,
                flag=flag,
                detail=detail,
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
    screens.sort(
        key=lambda s: (order.get(s.flag, 9), -(s.reject_heat_mw.value if s.reject_heat_mw else 0.0))
    )

    meta: dict[str, Any] = {
        "subject": "Data-center cooling heat load vs receiving-water temperature WQS / CWA §316(a)",
        "source": (
            "watermark.hydrology.cooling_models (condenser heat rejection) x Ohio EPA cited design "
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
        "facility_count": len(screens),
        "critical_count": sum(1 for s in screens if s.flag == "critical"),
        "caveats": [
            "The heat load is the CONDENSER heat rejection (IT x cooling overhead) — a "
            "conservative, once-through-equivalent bound that treats the full rejection as "
            "reaching the receiving water. An evaporative tower rejects most of it to the "
            "atmosphere; the finding leans on the capacity ratio, which is robust to this "
            "partition (even a small in-stream fraction exceeds the tiny capacity).",
            "Fully-mixed, design-low-flow, order-of-magnitude: no CORMIX plume model, no "
            "mixing-zone credit, no decay. T_mixed above the daily-max criterion flags the need "
            "for a permit-level thermal / CWA §316(a) analysis, NOT an automatic violation.",
            "The thermal assimilative capacity is rho*cp*Q*(daily_max - ambient). At a 0 cfs "
            "design flow (the Ottawa 1Q10) or an ambient already at the criterion the capacity is "
            "0 — any heat load exceeds by construction (no Inf ΔT, mirroring the toxics screen).",
            "The design ambient is a live NWIS 00010 reading where the gage carries one, else the "
            "zone's seasonal-average temperature criterion (a stated design ambient). RIS "
            "tolerances are the Great Lakes biological limits for a §316(a) balanced-indigenous-"
            "community read, [reference] (federal guidance, not law).",
            "The OAC 3745-1-06 (O)(5) closed-cycle-blowdown exemption (blowdown < 5% of the 7Q10) "
            "is evaluated and surfaced. Zone selection and live effluent-temperature (DMR) "
            "validation are Phase-3 (#1718) concerns.",
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
