"""Analyze-layer entrypoint for the Tier-0 hydrology model.

Mirrors :func:`bosc.pipeline.analyze.reconcile`'s shape: a single deterministic
call that assembles the municipal water balance and screens each WWTP discharge
against its receiving water's cited low flow.
"""

from __future__ import annotations

from bosc.config import Settings, get_settings
from bosc.hydrology import network as network_stage
from bosc.hydrology import scenario as scenario_stage
from bosc.hydrology.assimilative import assimilative_findings, check_assimilative
from bosc.hydrology.balance import build_water_balance
from bosc.hydrology.model import (
    AssimilativeCheck,
    HydroFinding,
    RoutedNetwork,
    RoutedNetworkDiff,
    ScenarioDiff,
    ScenarioResult,
    StormRunoff,
    WaterBalance,
)
from bosc.hydrology.stormwater import run_storm_scenario
from bosc.hydrology.units import mgd_to_cfs
from bosc.logging import get_logger

log = get_logger(__name__)


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


def run_network(
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    settings: Settings | None = None,
    live: bool = False,
) -> tuple[RoutedNetwork, RoutedNetwork, RoutedNetworkDiff]:
    """Route the loop at design low flow under baseline vs buildout consumptive draw.

    Generalizes :func:`run_baseline`'s per-stream screen: the cited headwater 7Q10s,
    the document-cited WWTP/campus discharges, and the buildout cooling draw are
    accumulated through the cited confluence graph. Returns the baseline network, the
    buildout network, and their diff (the new draw vs the loop's natural low flow).
    """
    settings = settings or get_settings()
    balance = build_water_balance(settings=settings, live=live)
    baseline = network_stage.route_network(
        balance, consumptive_cfs=0.0, scenario_name="baseline", settings=settings
    )
    build_scenario = scenario_stage.buildout_scenario(
        cooling_demand_mgd=cooling_demand_mgd, consumptive_fraction=consumptive_fraction
    )
    consumptive_cfs = mgd_to_cfs(
        build_scenario.cooling_demand.value * build_scenario.consumptive_fraction.value
    )
    buildout = network_stage.route_network(
        balance, consumptive_cfs=consumptive_cfs, scenario_name="buildout", settings=settings
    )
    delta = network_stage.diff_networks(baseline, buildout)
    log.info(
        "hydro.network.diff",
        natural_total_cfs=delta.natural_total_cfs,
        multiple_of_natural=delta.multiple_of_natural,
        mainstem_runs_dry=delta.mainstem_runs_dry,
    )
    return baseline, buildout, delta
