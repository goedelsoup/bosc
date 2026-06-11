"""Localized economic baselines for the corridor — beyond utility consumption.

The hydrology axis answers what the campus *consumes*; this answers what the *place*
is, quantitatively: employment by industry, the export-orientation of each sector
(BLS QCEW location quotients), and an employment trend over time — so the economic
argument is grounded in Allen County's real economy, not only qualitative entity
research. Mirrors the hydrology connector pattern (pure-sync ``fn(..., settings) ->
pydantic`` through the shared ``cached_get`` cache/offline/fixture machinery).
"""

from __future__ import annotations

from bosc.economics.baseline import build_baseline, load_baseline
from bosc.economics.energy import (
    build_consumer_energy,
    derive_demand_pressure,
    load_consumer_energy,
    write_consumer_energy,
)
from bosc.economics.model import (
    ConsumerEnergyCosts,
    ConsumerEnergyPrice,
    EconomicBaseline,
    FacilityDemandPressure,
    IndustryEmployment,
    SectorEmployment,
    YearTotal,
)

__all__ = [
    "ConsumerEnergyCosts",
    "ConsumerEnergyPrice",
    "EconomicBaseline",
    "FacilityDemandPressure",
    "IndustryEmployment",
    "SectorEmployment",
    "YearTotal",
    "build_baseline",
    "build_consumer_energy",
    "derive_demand_pressure",
    "load_baseline",
    "load_consumer_energy",
    "write_consumer_energy",
]
