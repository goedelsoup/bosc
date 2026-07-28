"""Shared geodesy helpers for the hydrology package (no site/model dependencies)."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

_EARTH_RADIUS_FT = 20_902_231.0  # mean Earth radius in feet


def haversine_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in feet between two lon/lat points."""
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2.0 * _EARTH_RADIUS_FT * asin(sqrt(a))
