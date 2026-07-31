"""Typed models for the Tier-0 hydrology subsystem.

Unlike the extraction models in :mod:`watermark.models` (``extra="allow"`` because the
LLM emits unanticipated keys), these are **computed by our own code**, so they use
``extra="forbid"`` to catch bugs early.

The cornerstone is :class:`ProvenancedValue`: every number that enters the water
balance carries where it came from, so a result is self-auditing. The ``source``
tag maps onto the dossier's evidence discipline:

    document, connector  ->  [verified]   (read from a record or a live gauge)
    assumption, derived  ->  [inference]  (asserted, or computed from the above)

The models are grouped into cluster modules (``_core``, ``_routed``, ``_supply``,
``_lowflow``, ``_stormwater``, ``_cooling``, ``_sanitary``, ``_findings``) and
re-exported here. :mod:`watermark.hydrology.model` (singular) re-exports this package for
back-compat; new code may import from either.
"""

from __future__ import annotations

from watermark.hydrology.models._cooling import (
    CoolingBasis as CoolingBasis,
)
from watermark.hydrology.models._cooling import (
    MonthlyWithdrawal as MonthlyWithdrawal,
)
from watermark.hydrology.models._cooling import (
    Scenario as Scenario,
)
from watermark.hydrology.models._cooling import (
    ScenarioDiff as ScenarioDiff,
)
from watermark.hydrology.models._cooling import (
    ScenarioResult as ScenarioResult,
)
from watermark.hydrology.models._cooling import (
    SeasonalWithdrawal as SeasonalWithdrawal,
)
from watermark.hydrology.models._core import (
    Node as Node,
)
from watermark.hydrology.models._core import (
    NodeRole as NodeRole,
)
from watermark.hydrology.models._core import (
    ProvenancedValue as ProvenancedValue,
)
from watermark.hydrology.models._core import (
    SourceKind as SourceKind,
)
from watermark.hydrology.models._core import (
    WaterBalance as WaterBalance,
)
from watermark.hydrology.models._core import (
    WaterBalanceNode as WaterBalanceNode,
)
from watermark.hydrology.models._findings import (
    HydroFinding as HydroFinding,
)
from watermark.hydrology.models._lowflow import (
    DILUTION_TIGHT as DILUTION_TIGHT,
)
from watermark.hydrology.models._lowflow import (
    DILUTION_VIOLATION as DILUTION_VIOLATION,
)
from watermark.hydrology.models._lowflow import (
    AnnualMinimum as AnnualMinimum,
)
from watermark.hydrology.models._lowflow import (
    AssimilativeCheck as AssimilativeCheck,
)
from watermark.hydrology.models._lowflow import (
    Flag as Flag,
)
from watermark.hydrology.models._lowflow import (
    HarmonicMeanFlow as HarmonicMeanFlow,
)
from watermark.hydrology.models._lowflow import (
    LowFlowFrequency as LowFlowFrequency,
)
from watermark.hydrology.models._lowflow import (
    LowFlowStatistic as LowFlowStatistic,
)
from watermark.hydrology.models._monitor import (
    ContinuousMonitorRead as ContinuousMonitorRead,
)
from watermark.hydrology.models._monitor import (
    MonitorSpike as MonitorSpike,
)
from watermark.hydrology.models._routed import (
    Catchment as Catchment,
)
from watermark.hydrology.models._routed import (
    NetworkNode as NetworkNode,
)
from watermark.hydrology.models._routed import (
    NetworkNodeKind as NetworkNodeKind,
)
from watermark.hydrology.models._routed import (
    NetworkTheory as NetworkTheory,
)
from watermark.hydrology.models._routed import (
    Reach as Reach,
)
from watermark.hydrology.models._routed import (
    ReachFlow as ReachFlow,
)
from watermark.hydrology.models._routed import (
    ReachRouting as ReachRouting,
)
from watermark.hydrology.models._routed import (
    ReachTable as ReachTable,
)
from watermark.hydrology.models._routed import (
    RoutedHydrographNetwork as RoutedHydrographNetwork,
)
from watermark.hydrology.models._routed import (
    RoutedNetwork as RoutedNetwork,
)
from watermark.hydrology.models._routed import (
    RoutedNetworkDiff as RoutedNetworkDiff,
)
from watermark.hydrology.models._sanitary import (
    DetentionDesign as DetentionDesign,
)
from watermark.hydrology.models._sanitary import (
    MaumeeTmdl as MaumeeTmdl,
)
from watermark.hydrology.models._sanitary import (
    SanitaryBasis as SanitaryBasis,
)
from watermark.hydrology.models._sanitary import (
    SanitaryPlant as SanitaryPlant,
)
from watermark.hydrology.models._sanitary import (
    SanitarySurcharge as SanitarySurcharge,
)
from watermark.hydrology.models._sanitary import (
    StormPlanInventory as StormPlanInventory,
)
from watermark.hydrology.models._sanitary import (
    SwmmDeck as SwmmDeck,
)
from watermark.hydrology.models._sanitary import (
    Tier1Result as Tier1Result,
)
from watermark.hydrology.models._sanitary import (
    TmdlWla as TmdlWla,
)
from watermark.hydrology.models._stormwater import (
    CampusDischargeScreen as CampusDischargeScreen,
)
from watermark.hydrology.models._stormwater import (
    DesignStorm as DesignStorm,
)
from watermark.hydrology.models._stormwater import (
    DischargePeak as DischargePeak,
)
from watermark.hydrology.models._stormwater import (
    HsgDrainageBasis as HsgDrainageBasis,
)
from watermark.hydrology.models._stormwater import (
    Hydrograph as Hydrograph,
)
from watermark.hydrology.models._stormwater import (
    OutfallCapacity as OutfallCapacity,
)
from watermark.hydrology.models._stormwater import (
    RoundaboutFlow as RoundaboutFlow,
)
from watermark.hydrology.models._stormwater import (
    RoundaboutStormPeak as RoundaboutStormPeak,
)
from watermark.hydrology.models._stormwater import (
    RoutedDischarge as RoutedDischarge,
)
from watermark.hydrology.models._stormwater import (
    SiteFootprint as SiteFootprint,
)
from watermark.hydrology.models._stormwater import (
    StormRunoff as StormRunoff,
)
from watermark.hydrology.models._supply import (
    DroughtDrawdown as DroughtDrawdown,
)
from watermark.hydrology.models._supply import (
    PumpStation as PumpStation,
)
from watermark.hydrology.models._supply import (
    RefillAdequacy as RefillAdequacy,
)
from watermark.hydrology.models._supply import (
    Reservoir as Reservoir,
)
from watermark.hydrology.models._supply import (
    ReservoirEvaporation as ReservoirEvaporation,
)
from watermark.hydrology.models._supply import (
    RiverFlowStat as RiverFlowStat,
)
from watermark.hydrology.models._supply import (
    WaterBudget as WaterBudget,
)
from watermark.hydrology.models._supply import (
    WaterSupplySystem as WaterSupplySystem,
)

__all__ = [
    "DILUTION_TIGHT",
    "DILUTION_VIOLATION",
    "AnnualMinimum",
    "AssimilativeCheck",
    "CampusDischargeScreen",
    "Catchment",
    "ContinuousMonitorRead",
    "CoolingBasis",
    "DesignStorm",
    "DetentionDesign",
    "DischargePeak",
    "DroughtDrawdown",
    "Flag",
    "HarmonicMeanFlow",
    "HsgDrainageBasis",
    "HydroFinding",
    "Hydrograph",
    "LowFlowFrequency",
    "LowFlowStatistic",
    "MaumeeTmdl",
    "MonitorSpike",
    "MonthlyWithdrawal",
    "NetworkNode",
    "NetworkNodeKind",
    "NetworkTheory",
    "Node",
    "NodeRole",
    "OutfallCapacity",
    "ProvenancedValue",
    "PumpStation",
    "Reach",
    "ReachFlow",
    "ReachRouting",
    "ReachTable",
    "RefillAdequacy",
    "Reservoir",
    "ReservoirEvaporation",
    "RiverFlowStat",
    "RoundaboutFlow",
    "RoundaboutStormPeak",
    "RoutedDischarge",
    "RoutedHydrographNetwork",
    "RoutedNetwork",
    "RoutedNetworkDiff",
    "SanitaryBasis",
    "SanitaryPlant",
    "SanitarySurcharge",
    "Scenario",
    "ScenarioDiff",
    "ScenarioResult",
    "SeasonalWithdrawal",
    "SiteFootprint",
    "SourceKind",
    "StormPlanInventory",
    "StormRunoff",
    "SwmmDeck",
    "Tier1Result",
    "TmdlWla",
    "WaterBalance",
    "WaterBalanceNode",
    "WaterBudget",
    "WaterSupplySystem",
]
