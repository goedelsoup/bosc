"""Analyze-layer entrypoint for the Tier-0 hydrology model.

Mirrors :func:`bosc.pipeline.analyze.reconcile`'s shape: a single deterministic
call that assembles the municipal water balance and screens each WWTP discharge
against its receiving water's cited low flow.
"""

from __future__ import annotations

from collections.abc import Sequence

from bosc.config import Settings, get_settings
from bosc.hydrology import network as network_stage
from bosc.hydrology import refill as refill_stage
from bosc.hydrology import scenario as scenario_stage
from bosc.hydrology import supply as supply_stage
from bosc.hydrology.assimilative import assimilative_findings, check_assimilative
from bosc.hydrology.balance import build_water_balance
from bosc.hydrology.model import (
    AssimilativeCheck,
    HydroFinding,
    RefillAdequacy,
    RoutedNetwork,
    RoutedNetworkDiff,
    ScenarioDiff,
    ScenarioResult,
    StormRunoff,
    WaterBalance,
    WaterBudget,
    WaterSupplySystem,
)
from bosc.hydrology.stormwater import run_storm_scenario
from bosc.hydrology.units import mgd_to_cfs
from bosc.logging import get_logger

log = get_logger(__name__)


def run_water_budget(
    *,
    settings: Settings | None = None,
) -> tuple[WaterSupplySystem | None, WaterBudget | None, list[HydroFinding]]:
    """Screen the campus draw against Lima's reservoir storage (the supply water-budget).

    The intake-side counterpart to :func:`run_network`: instead of routing discharges
    into the Ottawa, it loads the off-stream-storage supply system
    (``data/reference/hydrology/water-supply.yaml``) and screens the campus's treated-water
    draw against the ~15 BG reservoir storage — drought-reserve drawdown, share of plant
    production, net basin loss. Returns ``(None, None, [])`` if the supply file is absent.
    """
    settings = settings or get_settings()
    supply = supply_stage.load_supply(settings=settings)
    if supply is None:
        return None, None, []
    budget = supply_stage.campus_budget_from_cooling(supply)
    findings = supply_stage.water_budget_findings(budget, supply)
    log.info(
        "hydro.water_budget.run",
        storage_bg=round(supply.total_storage_mg / 1000, 2),
        gross_mgd=budget.gross_production_mgd,
        reserve_lost_days=budget.drought_reserve_lost_days,
    )
    return supply, budget, findings


def run_refill(
    *,
    settings: Settings | None = None,
) -> tuple[RefillAdequacy | None, list[HydroFinding]]:
    """Load the committed refill-adequacy analysis + findings (offline; reads the artifact).

    The flow-side counterpart to :func:`run_water_budget`: where the storage budget screens
    the campus draw against the reservoir *stock*, this reads the committed sequent-peak
    drought storage-requirement (regenerate it from the live USGS record with
    ``bosc refill --write``). Returns ``(None, [])`` if the artifact is absent.
    """
    settings = settings or get_settings()
    ra = refill_stage.load_refill_adequacy(settings=settings)
    if ra is None:
        return None, []
    findings = refill_stage.refill_findings(ra)
    log.info(
        "hydro.refill.run",
        supply_multiple=ra.annual_supply_multiple,
        scenarios=len(ra.scenarios),
    )
    return ra, findings


def run_baseline(
    *,
    settings: Settings | None = None,
    live: bool = True,
) -> tuple[WaterBalance, list[AssimilativeCheck], list[HydroFinding]]:
    """Build the baseline water balance + low-flow assimilative findings.

    ``live`` grounds the abstraction reach with USGS streamflow (offline-aware);
    set it False for a pure document/assumption balance.
    """
    settings = settings or get_settings()
    balance = build_water_balance(settings=settings, live=live)
    checks = check_assimilative(balance)
    findings = assimilative_findings(checks)
    log.info(
        "hydro.baseline",
        nodes=len(balance.nodes),
        checks=len(checks),
        violations=sum(1 for f in findings if not f.ok),
    )
    return balance, checks, findings


def run_storm(
    *,
    return_period_yr: int = 25,
    settings: Settings | None = None,
    live: bool = True,
) -> tuple[StormRunoff, list[HydroFinding]]:
    """Pre- vs post-development design-storm runoff over the campus footprint.

    The stormwater counterpart to :func:`run_baseline`: how paving the corridor
    changes peak flow and runoff volume for a NOAA Atlas-14 design storm.
    """
    settings = settings or get_settings()
    return run_storm_scenario(return_period_yr=return_period_yr, settings=settings, live=live)


def run_scenarios(
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    settings: Settings | None = None,
    live: bool = True,
) -> tuple[ScenarioResult, ScenarioResult, ScenarioDiff]:
    """Evaluate baseline vs data-center buildout; return both results and their diff.

    The buildout's cooling consumptive draw is compared against the cited Ottawa
    7Q10 — the scale that shows how a data center stresses an already low-flow river.
    """
    settings = settings or get_settings()
    base = scenario_stage.evaluate(scenario_stage.baseline_scenario(), settings=settings, live=live)
    build = scenario_stage.evaluate(
        scenario_stage.buildout_scenario(
            cooling_demand_mgd=cooling_demand_mgd, consumptive_fraction=consumptive_fraction
        ),
        settings=settings,
        live=live,
    )
    delta = scenario_stage.diff(base, build)
    log.info(
        "hydro.scenarios",
        consumptive_increase_cfs=delta.consumptive_increase_cfs,
        multiple_of_7q10=delta.multiple_of_7q10,
    )
    return base, build, delta


def _buildout_consumptive_cfs(
    cooling_demand_mgd: float | None, consumptive_fraction: float | None
) -> float:
    """The buildout cooling consumptive draw (cfs) from the cooling basis or overrides."""
    build_scenario = scenario_stage.buildout_scenario(
        cooling_demand_mgd=cooling_demand_mgd, consumptive_fraction=consumptive_fraction
    )
    return mgd_to_cfs(
        build_scenario.cooling_demand.value * build_scenario.consumptive_fraction.value
    )


def run_network(
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    theories: Sequence[str] | None = None,
    settings: Settings | None = None,
    live: bool = False,
) -> tuple[RoutedNetwork, RoutedNetwork, RoutedNetworkDiff]:
    """Route the loop at design low flow under baseline vs buildout consumptive draw.

    Generalizes :func:`run_baseline`'s per-stream screen: the cited headwater 7Q10s,
    the document-cited WWTP/campus discharges, and the buildout cooling draw are
    accumulated through the cited confluence graph. Returns the baseline network, the
    buildout network, and their diff (the new draw vs the loop's natural low flow).

    ``theories`` overlays unproven structural interventions (``theories.yaml``) on the
    **buildout** side only; the baseline always stays the cited graph. ``None`` uses the
    catalog defaults (all off); a list of ids enables exactly those.
    """
    settings = settings or get_settings()
    balance = build_water_balance(settings=settings, live=live)
    baseline = network_stage.route_network(
        balance, consumptive_cfs=0.0, scenario_name="baseline", theories=[], settings=settings
    )
    consumptive_cfs = _buildout_consumptive_cfs(cooling_demand_mgd, consumptive_fraction)
    buildout = network_stage.route_network(
        balance,
        consumptive_cfs=consumptive_cfs,
        scenario_name="buildout",
        theories=theories,
        settings=settings,
    )
    delta = network_stage.diff_networks(baseline, buildout)
    log.info(
        "hydro.network.diff",
        theories=buildout.theories,
        natural_total_cfs=delta.natural_total_cfs,
        multiple_of_natural=delta.multiple_of_natural,
        mainstem_runs_dry=delta.mainstem_runs_dry,
    )
    return baseline, buildout, delta


def compare_theory(
    theories: Sequence[str],
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    settings: Settings | None = None,
    live: bool = False,
) -> tuple[RoutedNetwork, RoutedNetwork, list[HydroFinding]]:
    """Isolate a theory overlay's effect: same buildout draw, overlay OFF vs ON.

    Solves the buildout network twice at the same cooling draw — once with no theory
    (the cited graph) and once with ``theories`` enabled — and returns both plus the
    quantified :func:`~bosc.hydrology.network.theory_findings` (the directed inflow it
    injects and the net change in outlet flow / effluent share). This separates the
    overlay's effect from the cooling draw's, which :func:`run_network`'s diff conflates.
    """
    settings = settings or get_settings()
    balance = build_water_balance(settings=settings, live=live)
    consumptive_cfs = _buildout_consumptive_cfs(cooling_demand_mgd, consumptive_fraction)
    without = network_stage.route_network(
        balance,
        consumptive_cfs=consumptive_cfs,
        scenario_name="buildout",
        theories=[],
        settings=settings,
    )
    with_theory = network_stage.route_network(
        balance,
        consumptive_cfs=consumptive_cfs,
        scenario_name="buildout",
        theories=theories,
        settings=settings,
    )
    findings = network_stage.theory_findings(without, with_theory)
    log.info(
        "hydro.network.theory",
        theories=with_theory.theories,
        outlet_without=without.outlet_cfs,
        outlet_with=with_theory.outlet_cfs,
    )
    return without, with_theory, findings
