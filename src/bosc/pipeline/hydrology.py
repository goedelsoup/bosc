"""Analyze-layer entrypoint for the Tier-0 hydrology model.

Mirrors :func:`bosc.pipeline.analyze.reconcile`'s shape: a single deterministic
call that assembles the municipal water balance and screens each WWTP discharge
against its receiving water's cited low flow.
"""

from __future__ import annotations

from bosc.config import Settings, get_settings
from bosc.hydrology.assimilative import assimilative_findings, check_assimilative
from bosc.hydrology.balance import build_water_balance
from bosc.hydrology.model import AssimilativeCheck, HydroFinding, StormRunoff, WaterBalance
from bosc.hydrology.stormwater import run_storm_scenario
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
