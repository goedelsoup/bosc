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
from bosc.economics.model import (
    EconomicBaseline,
    IndustryEmployment,
    SectorEmployment,
    YearTotal,
)

__all__ = [
    "EconomicBaseline",
    "IndustryEmployment",
    "SectorEmployment",
    "YearTotal",
    "build_baseline",
    "load_baseline",
]
