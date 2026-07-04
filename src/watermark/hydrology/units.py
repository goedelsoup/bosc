"""Unit conversions for the Tier-0 water balance.

Tier-0 mass-balance bugs are almost always unit bugs (MGD vs cfs vs ac-ft), so
every conversion lives here once, cited, and is unit-tested. Flows in this
subsystem are carried internally in **cfs** (cubic feet per second) to match the
USGS NWIS streamflow the model is grounded against; permitted plant capacities
are quoted in **MGD** (million gallons per day) per the source documents.
"""

from __future__ import annotations

# 1 MGD = 10^6 gal/day. 1 ft^3 = 7.480519 gal; 1 day = 86_400 s.
#   (10^6 / 7.480519) / 86_400 = 1.5472287516513326 ft^3/s.  (USGS conversion factor.)
# Carry the full-precision quotient, not the 1.547 round-off (a -0.015% bias in the one
# module that claims conversion rigor).
MGD_TO_CFS: float = 1.5472287516513326
CFS_TO_MGD: float = 1.0 / MGD_TO_CFS

# 1 square mile = 640 acres.
ACRES_PER_SQMI: float = 640.0


def mgd_to_cfs(mgd: float) -> float:
    """Million gallons/day -> cubic feet/second."""
    return mgd * MGD_TO_CFS


def cfs_to_mgd(cfs: float) -> float:
    """Cubic feet/second -> million gallons/day."""
    return cfs * CFS_TO_MGD


def acres_to_sqmi(acres: float) -> float:
    """Acres -> square miles."""
    return acres / ACRES_PER_SQMI


def sqmi_to_acres(sqmi: float) -> float:
    """Square miles -> acres."""
    return sqmi * ACRES_PER_SQMI
