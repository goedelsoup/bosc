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
    HydroFinding,
    LowFlowFrequency,
    LowFlowStatistic,
    NetworkNode,
    Node,
    ProvenancedValue,
    ReachFlow,
    RoutedNetwork,
    RoutedNetworkDiff,
    WaterBalance,
    WaterBalanceNode,
)
from bosc.hydrology.network import (
    diff_networks,
    load_topology,
    network_findings,
    route_network,
)

__all__ = [
    "AnnualMinimum",
    "AssimilativeCheck",
    "HydroFinding",
    "LowFlowFrequency",
    "LowFlowStatistic",
    "NetworkNode",
    "Node",
    "ProvenancedValue",
    "ReachFlow",
    "RoutedNetwork",
    "RoutedNetworkDiff",
    "WaterBalance",
    "WaterBalanceNode",
    "assimilative_findings",
    "build_water_balance",
    "check_assimilative",
    "compute_low_flow_frequency",
    "diff_networks",
    "load_low_flow_frequency",
    "load_topology",
    "low_flow_quantiles",
    "network_findings",
    "route_network",
]
