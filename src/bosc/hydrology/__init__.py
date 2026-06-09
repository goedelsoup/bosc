"""Tier-0 hydrological simulation of the Lima municipal water loop.

BOSC's first three stages *deconstruct* records; this subpackage *forecasts* —
it models water, stormwater, and sewage as one closed flow loop on the Auglaize
and Ottawa rivers:

    Auglaize/Ottawa -> Lima reservoirs + WTP (abstraction) -> municipal +
    data-center demand (consumptive use) -> county/Lima WWTPs (return) ->
    Ottawa River (receiving).

The binding constraint is the Ottawa's (and its small tributaries') *low flow*:
abstraction upstream removes dilution water, WWTP discharge downstream adds load,
and stormwater surges perturb both — all squeezing the same assimilative capacity.

Design discipline (mirrors the rest of BOSC): every numeric input is a
:class:`~bosc.hydrology.model.ProvenancedValue` tagged ``document`` / ``connector``
/ ``assumption`` / ``derived`` so a result is self-auditing. Computed hydrology is
never written under ``data/extracted`` (reviewed transcription only). This is a
*Tier-0* model — simplified, screening-grade, and always labelled as such.

Increment 1 ships the water-balance spine + low-flow assimilative check, grounded
by live USGS streamflow. The SCS-CN stormwater solver and scenario diffing follow.
"""

from __future__ import annotations

from bosc.hydrology.assimilative import assimilative_findings, check_assimilative
from bosc.hydrology.balance import build_water_balance
from bosc.hydrology.lowflow_frequency import (
    compute_low_flow_frequency,
    load_low_flow_frequency,
    low_flow_quantiles,
)
from bosc.hydrology.model import (
    AnnualMinimum,
    AssimilativeCheck,
    DroughtDrawdown,
    HydroFinding,
    LowFlowFrequency,
    LowFlowStatistic,
    NetworkNode,
    NetworkTheory,
    Node,
    ProvenancedValue,
    PumpStation,
    ReachFlow,
    RefillAdequacy,
    Reservoir,
    RiverFlowStat,
    RoutedNetwork,
    RoutedNetworkDiff,
    WaterBalance,
    WaterBalanceNode,
    WaterBudget,
    WaterSupplySystem,
)
from bosc.hydrology.network import (
    apply_theories,
    diff_networks,
    load_theories,
    load_topology,
    network_findings,
    resolve_theories,
    route_network,
    theory_findings,
)
from bosc.hydrology.refill import (
    compute_refill_adequacy,
    load_refill_adequacy,
    refill_findings,
    write_refill_adequacy,
)
from bosc.hydrology.supply import (
    campus_budget_from_cooling,
    compute_water_budget,
    load_supply,
    water_budget_findings,
)
from bosc.hydrology.tier1 import load_tier1, run_tier1, tier1_findings, write_tier1

__all__ = [
    "AnnualMinimum",
    "AssimilativeCheck",
    "DroughtDrawdown",
    "HydroFinding",
    "LowFlowFrequency",
    "LowFlowStatistic",
    "NetworkNode",
    "NetworkTheory",
    "Node",
    "ProvenancedValue",
    "PumpStation",
    "ReachFlow",
    "RefillAdequacy",
    "Reservoir",
    "RiverFlowStat",
    "RoutedNetwork",
    "RoutedNetworkDiff",
    "WaterBalance",
    "WaterBalanceNode",
    "WaterBudget",
    "WaterSupplySystem",
    "apply_theories",
    "assimilative_findings",
    "build_water_balance",
    "campus_budget_from_cooling",
    "check_assimilative",
    "compute_low_flow_frequency",
    "compute_refill_adequacy",
    "compute_water_budget",
    "diff_networks",
    "load_low_flow_frequency",
    "load_refill_adequacy",
    "load_supply",
    "load_theories",
    "load_tier1",
    "load_topology",
    "low_flow_quantiles",
    "network_findings",
    "refill_findings",
    "resolve_theories",
    "route_network",
    "run_tier1",
    "theory_findings",
    "tier1_findings",
    "water_budget_findings",
    "write_refill_adequacy",
    "write_tier1",
]
