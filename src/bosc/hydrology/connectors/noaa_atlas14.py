"""NOAA Atlas-14 precipitation-frequency connector (design storms).

Fetches the point precipitation-frequency estimates (partial-duration series,
English units) from the NOAA HDSC point-query CGI and returns one design-storm
depth as a ``connector``-sourced :class:`ProvenancedValue`. Allen County, OH is in
the SCS Type-II rainfall region, so these depths feed the Type-II hyetograph.

The CGI returns a small JavaScript document, not JSON:

    result = 'values';
    quantiles = [[<return periods>], ...one row per duration...];

``quantiles[duration_index][return_period_index]`` is the depth in inches.
"""

from __future__ import annotations

import ast
import re
from typing import Any

import httpx

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors._cache import cached_get
from bosc.hydrology.model import DesignStorm, ProvenancedValue

# Column order (return periods, years) and row order (durations) of the quantiles grid.
_RETURN_PERIODS: tuple[int, ...] = (1, 2, 5, 10, 25, 50, 100, 200, 500, 1000)
_DURATIONS: tuple[str, ...] = (
    "5-min",
    "10-min",
    "15-min",
    "30-min",
    "60-min",
    "2-hr",
    "3-hr",
    "6-hr",
    "12-hr",
    "24-hr",
    "2-day",
    "3-day",
    "4-day",
    "7-day",
    "10-day",
    "20-day",
    "30-day",
    "45-day",
    "60-day",
)
_DURATION_HOURS: dict[str, float] = {"6-hr": 6.0, "12-hr": 12.0, "24-hr": 24.0}

_QUANTILES_RE = re.compile(r"quantiles\s*=\s*(\[.*?\])\s*;", re.DOTALL)


def _fetch_quantiles(settings: Settings, lat: float, lon: float) -> list[list[float]]:
    params: dict[str, str | float] = {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "data": "depth",
        "units": "english",
        "series": "pds",
    }

    def fetch() -> Any:
        resp = httpx.get(
            settings.noaa_atlas14_base_url,
            params=params,
            timeout=settings.hydro_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        match = _QUANTILES_RE.search(resp.text)
        if not match:
            raise ValueError("NOAA Atlas-14 response missing a quantiles table")
        grid = ast.literal_eval(match.group(1))
        return [[float(v) for v in row] for row in grid]

    payload = cached_get("noaa_atlas14", params, fetch, settings=settings)
    return [[float(v) for v in row] for row in payload]


def design_storm(
    *,
    lat: float,
    lon: float,
    return_period_yr: int = 25,
    duration: str = "24-hr",
    settings: Settings | None = None,
) -> DesignStorm:
    """Return one design storm (depth in inches) for a point, from NOAA Atlas-14."""
    settings = settings or get_settings()
    if return_period_yr not in _RETURN_PERIODS:
        raise ValueError(f"return period must be one of {_RETURN_PERIODS}")
    if duration not in _DURATIONS:
        raise ValueError(f"unknown duration {duration!r}")

    grid = _fetch_quantiles(settings, lat, lon)
    row = _DURATIONS.index(duration)
    col = _RETURN_PERIODS.index(return_period_yr)
    depth = grid[row][col]
    return DesignStorm(
        return_period_yr=return_period_yr,
        duration_hr=_DURATION_HOURS.get(duration, 24.0),
        depth=ProvenancedValue.from_connector(
            depth,
            "in",
            citation=f"NOAA Atlas-14 PDS {duration} {return_period_yr}-yr @ {lat:.3f},{lon:.3f}",
        ),
    )
