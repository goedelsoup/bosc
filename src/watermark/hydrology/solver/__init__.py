"""Tier-0 SCS hydrology solver — rainfall, runoff, routing.

Pure-Python (numpy) implementations of the screening-grade methods Periplus used
as Tier-0: SCS Type-II design rainfall, the Curve Number runoff method (USDA
TR-55), the SCS dimensionless unit hydrograph, and Muskingum-Cunge channel routing.
These are *approximations* — fast, auditable, and always labelled ``tier0``; they
are not a substitute for EPA SWMM or HEC-RAS.
"""

from __future__ import annotations

from watermark.hydrology.solver.curve_number import (
    adjust_amc,
    composite_cn,
    excess_rainfall,
    storage_s,
    weighted_excess_rainfall,
)
from watermark.hydrology.solver.rainfall import build_distribution, scs_type_ii_hyetograph
from watermark.hydrology.solver.routing import muskingum_coeffs, route
from watermark.hydrology.solver.runoff import gamma_shape_for, simulate_runoff, unit_duration_hr

__all__ = [
    "adjust_amc",
    "build_distribution",
    "composite_cn",
    "excess_rainfall",
    "gamma_shape_for",
    "muskingum_coeffs",
    "route",
    "scs_type_ii_hyetograph",
    "simulate_runoff",
    "storage_s",
    "unit_duration_hr",
    "weighted_excess_rainfall",
]
