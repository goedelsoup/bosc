"""Baseline vs data-center-buildout scenarios over the municipal water loop.

The dominant uncertainty in the loop is the campus's *consumptive* cooling demand —
evaporated water that never returns to the Ottawa/Auglaize basin. This module makes
that the knob: a :class:`Scenario` carries a cooling intake and a consumptive
fraction (both assumptions), and :func:`evaluate` computes the net basin loss and
sets it on the campus node's ``consumptive_use`` seam. :func:`diff` reports the new
draw against the **cited Ottawa 7Q10** (0.2 cfs) — the scale that makes the point:
at design low flow the river already nearly dries, so any material cooling draw is a
large multiple of what the Ottawa carries.

Results persist to ``data/scenarios/*.scenario.yaml`` — committed, reviewed, and
self-auditing (every number keeps its provenance tag).
"""

from __future__ import annotations

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.assimilative import check_assimilative
from watermark.hydrology.balance import (
    CAMPUS_COOLING_DERIVED_WARNING_PREFIX,
    build_water_balance,
)
from watermark.hydrology.connectors.nwis import DISCHARGE_CFS, fetch_streamflow
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.lowflow import low_flow_context, low_flow_for
from watermark.hydrology.model import (
    CoolingBasis,
    MonthlyWithdrawal,
    ProvenancedValue,
    Scenario,
    ScenarioDiff,
    ScenarioResult,
    SeasonalWithdrawal,
)
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger
from watermark.sites import CoolingModelType, active_profile

log = get_logger(__name__)


def baseline_scenario() -> Scenario:
    """The current system: no incremental cooling draw."""
    return Scenario(
        name="baseline",
        description="Current municipal loop, no data-center cooling draw.",
        cooling_model=CoolingModelType.OFF,
        cooling_demand=ProvenancedValue.assume(0.0, "MGD", why="baseline: no campus cooling load"),
        consumptive_fraction=ProvenancedValue.assume(0.0, "fraction", why="baseline"),
    )


def buildout_scenario(
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    cooling_model: CoolingModelType | str | None = None,
    basis: CoolingBasis | None = None,
    settings: Settings | None = None,
) -> Scenario:
    """Data-center buildout with the site facility's cooling-archetype consumptive draw.

    Defaults to the sourced :class:`CoolingBasis` derived for the facility's
    ``cooling_model`` (#1056); ``cooling_model`` overrides the archetype for
    sensitivity runs, and explicit ``cooling_demand_mgd`` / ``consumptive_fraction``
    override the knobs (and are then tagged as assumptions).
    """
    basis = basis or derive_cooling_basis(settings, cooling_model=cooling_model)
    if cooling_demand_mgd is None:
        # Honesty guard (CLAUDE.md): a bracketed (undisclosed-method) basis carries the
        # evaporative envelope in `makeup_demand` for plumbing completeness, but it is not
        # an estimate — don't default the scenario knob to it. Require an explicit demand.
        makeup_pv = basis.headline_makeup()
        if makeup_pv is None:
            raise ValueError(
                f"cooling basis for {basis.cooling_model.value} is bracketed (undisclosed "
                "method) — pass an explicit cooling_demand_mgd for the sensitivity instead of "
                "defaulting to the bracket envelope"
            )
        cooling_demand = makeup_pv
    else:
        cooling_demand = ProvenancedValue.assume(
            cooling_demand_mgd, "MGD", why="campus cooling intake — scenario override"
        )
    if consumptive_fraction is None:
        frac = basis.consumptive_fraction
    else:
        frac = ProvenancedValue.assume(
            consumptive_fraction, "fraction", why="consumptive fraction — scenario override"
        )
    return Scenario(
        name="buildout",
        description=(
            f"Data-center campus cooling draw ({basis.cooling_model.value}) on the "
            "municipal supply."
        ),
        cooling_model=basis.cooling_model,
        cooling_demand=cooling_demand,
        consumptive_fraction=frac,
        basis=basis,
    )


def evaluate(
    scenario: Scenario,
    *,
    settings: Settings | None = None,
    live: bool = True,
) -> ScenarioResult:
    """Evaluate a scenario: net consumptive loss, modified balance, low-flow context."""
    settings = settings or get_settings()
    loss_cfs = mgd_to_cfs(scenario.cooling_demand.value * scenario.consumptive_fraction.value)
    consumptive = ProvenancedValue.derived(
        loss_cfs,
        "cfs",
        citation=(
            f"{scenario.cooling_demand.value:g} MGD x {scenario.consumptive_fraction.value:g} "
            f"consumptive (scenario {scenario.name})"
        ),
    )

    balance = build_water_balance(settings=settings, live=live)
    campus = balance.node("bosc-campus")
    if campus is not None:
        campus.consumptive_use = consumptive
        # A no-cooling scenario (baseline) zeroes the campus draw, so the balance's derived
        # cooling caveat — a buildout-only figure — doesn't apply here; drop it.
        if scenario.cooling_model is CoolingModelType.OFF:
            balance.warnings[:] = [
                w
                for w in balance.warnings
                if not w.startswith(CAMPUS_COOLING_DERIVED_WARNING_PREFIX)
            ]

    receiving_water = active_profile(settings).receiving_water_name
    receiving_7q10 = low_flow_for(receiving_water, settings=settings)
    receiving_live = _receiving_live(settings=settings, live=live)

    return ScenarioResult(
        scenario=scenario,
        cooling_model=scenario.cooling_model,
        consumptive_loss=consumptive,
        receiving_7q10=receiving_7q10,
        receiving_live=receiving_live,
        receiving_water_name=receiving_water,
        balance=balance,
        assimilative=check_assimilative(balance),
    )


def _receiving_live(*, settings: Settings, live: bool) -> ProvenancedValue | None:
    if not live:
        return None
    try:
        readings = fetch_streamflow(
            sites=[active_profile(settings).abstraction_gage], settings=settings
        )
    except Exception as exc:
        log.info("hydro.scenario.no_live", error=type(exc).__name__)
        return None
    flow = next(
        (r for r in readings if r.parameter_cd == DISCHARGE_CFS and r.value is not None), None
    )
    if flow is None or flow.value is None:
        return None
    # A provisional ("P") real-time reading is unreviewed and subject to revision; tag it
    # low-confidence so it never enters the scenario as an authoritative flow (#1602).
    return ProvenancedValue.from_connector(
        flow.value,
        "cfs",
        citation=f"NWIS {flow.site_no} ({flow.name})",
        asof=flow.datetime,
        confidence="low" if flow.provisional else "high",
    )


def diff(baseline: ScenarioResult, scenario: ScenarioResult) -> ScenarioDiff:
    """Net new consumptive draw and its scale against the per-site receiving-water 7Q10."""
    increase = scenario.consumptive_loss.value - baseline.consumptive_loss.value
    q7 = scenario.receiving_7q10.value if scenario.receiving_7q10 else None
    multiple = (increase / q7) if (q7 and q7 > 0) else None
    return ScenarioDiff(
        baseline=baseline.scenario.name,
        scenario=scenario.scenario.name,
        consumptive_increase_cfs=round(increase, 3),
        receiving_water_name=scenario.receiving_water_name,
        receiving_7q10_cfs=q7,
        multiple_of_7q10=round(multiple, 1) if multiple is not None else None,
    )


def evaluate_seasonal(
    consumptive_cfs: float,
    *,
    receiving_water: str | None = None,
    scenario_name: str = "buildout",
    settings: Settings | None = None,
    basis: CoolingBasis | None = None,
) -> SeasonalWithdrawal | None:
    """Screen the consumptive draw against the receiving water's *seasonal* low flow.

    The growing season is the months where reference ET0 exceeds precipitation (from
    the committed NASA POWER normals + FAO-56 ET0). In those months the draw is read
    against the cited **summer 30Q10**; otherwise against the annual **7Q10**. All
    low-flow figures are cited; nothing is interpolated to a per-month statistic we do
    not have. Returns ``None`` if the climate/ET inputs are absent.

    For a ``hybrid_adiabatic`` ``basis`` (#1058) the draw itself is **month-varying**:
    the warm-season (assist) rate — ``basis.consumptive_high`` — applies in the ET0 >
    precip months and ~0 elsewhere, instead of smearing an annual average across the
    year. Constant-draw archetypes ignore ``basis`` and use ``consumptive_cfs`` as is.
    """
    settings = settings or get_settings()
    from watermark.hydrology import climate, et
    from watermark.sites import active_profile

    hybrid = basis is not None and basis.cooling_model == CoolingModelType.HYBRID_ADIABATIC
    # The warm-season assist rate; the seasonal headline for a hybrid facility.
    warm_cfs = mgd_to_cfs(basis.consumptive_high.value) if (hybrid and basis) else consumptive_cfs

    rw = receiving_water or active_profile(settings).receiving_water_name
    clim = climate.load_climatology(settings=settings)
    precip = clim.get("PRECTOTCORR") if clim is not None else None
    if clim is None or precip is None:
        return None
    et0 = et.penman_monteith_et0(clim)

    q7 = low_flow_for(rw, settings=settings)
    ctx = low_flow_context(rw, settings=settings)
    annual_7q10 = q7.value if q7 is not None else None
    if annual_7q10 is None:
        return None
    summer_30q10 = ctx.get("thirty_q10_summer_cfs")
    one_q10 = ctx.get("one_q10_cfs")

    months: list[MonthlyWithdrawal] = []
    growing: list[str] = []
    for m in et._MONTHS:
        e = et0.monthly_mm_day[m]
        p = precip.monthly[m]
        net = round(e - p, 3)
        is_growing = net > 0
        if is_growing:
            growing.append(m)
        # Growing-season months use the cited summer design low flow if available.
        if is_growing and summer_30q10 is not None:
            floor, floor_basis = summer_30q10, "30Q10 summer"
        else:
            floor, floor_basis = annual_7q10, "7Q10 annual"
        # Hybrid (#1058): the evaporative assist runs only in ET0 > precip months.
        month_cfs = (warm_cfs if is_growing else 0.0) if hybrid else consumptive_cfs
        multiple = round(month_cfs / floor, 1) if floor and floor > 0 else None
        months.append(
            MonthlyWithdrawal(
                month=m,
                growing_season=is_growing,
                et0_mm_day=round(e, 2),
                precip_mm_day=round(p, 2),
                net_atmospheric_mm_day=net,
                low_flow_cfs=floor,
                low_flow_basis=floor_basis,
                consumptive_cfs=round(month_cfs, 3),
                multiple=multiple,
            )
        )

    # For a hybrid the annual multiple reads the annual-average draw (assist months
    # only); the summer multiple reads the concentrated warm-season rate.
    annual_cfs = warm_cfs * len(growing) / 12.0 if hybrid else consumptive_cfs
    return SeasonalWithdrawal(
        scenario=scenario_name,
        cooling_model=basis.cooling_model if basis is not None else None,
        consumptive_cfs=round(warm_cfs if hybrid else consumptive_cfs, 3),
        months=months,
        growing_season_months=growing,
        annual_7q10_cfs=annual_7q10,
        summer_30q10_cfs=summer_30q10,
        one_q10_cfs=one_q10,
        annual_multiple=round(annual_cfs / annual_7q10, 1) if annual_7q10 > 0 else None,
        summer_multiple=(
            round((warm_cfs if hybrid else consumptive_cfs) / summer_30q10, 1)
            if summer_30q10 and summer_30q10 > 0
            else None
        ),
    )


def write_scenario(result: ScenarioResult, *, settings: Settings | None = None) -> str:
    """Persist a scenario result as a committed, self-auditing YAML artifact."""
    settings = settings or get_settings()
    out_dir = settings.scenarios_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.scenario.name}.scenario.yaml"
    # mode="json" so CoolingModelType serializes as its value (safe_dump rejects enums).
    path.write_text(
        yaml.safe_dump(result.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("hydro.scenario.wrote", path=str(path))
    return str(path)
