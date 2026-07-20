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

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.model import DesignStorm, ProvenancedValue

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
_QUANTILES_RE = re.compile(r"quantiles\s*=\s*(\[.*?\])\s*;", re.DOTALL)


def _duration_to_hours(duration: str) -> float:
    """Hours for an Atlas-14 duration label (``5-min`` / ``3-hr`` / ``2-day``).

    Derived from the label unit rather than a hardcoded lookup so every duration in
    ``_DURATIONS`` maps to its true length — a ``3-hr`` request no longer silently
    inherits ``24.0`` (which would stretch a 3-hr depth across a 24-hr hyetograph).
    """
    magnitude, _, unit = duration.partition("-")
    hours_per = {"min": 1.0 / 60.0, "hr": 1.0, "day": 24.0}.get(unit)
    if hours_per is None:
        raise ValueError(f"cannot derive hours from duration {duration!r}")
    return float(magnitude) * hours_per


def _validate_grid(grid: list[list[float]]) -> list[list[float]]:
    """Assert the parsed quantiles grid matches the expected duration x return-period shape.

    ``design_storm``/``precip_frequency_grid`` index the grid purely by the fixed
    ``_DURATIONS`` x ``_RETURN_PERIODS`` order, so a NOAA HDSC layout change (reordered
    durations, an added/removed return period, a shifted page) would otherwise return the
    wrong cell's depth — or ``IndexError`` — with no signal. Fail loudly instead.
    """
    n_dur, n_rp = len(_DURATIONS), len(_RETURN_PERIODS)
    if len(grid) != n_dur or any(len(row) != n_rp for row in grid):
        shape = f"{len(grid)}x{{{','.join(str(len(row)) for row in grid)}}}"
        raise ValueError(
            f"NOAA Atlas-14 quantiles grid is {shape}, expected {n_dur}x{n_rp} "
            f"({n_dur} durations x {n_rp} return periods) — the response layout changed; "
            "reading depths by fixed grid position is no longer safe"
        )
    return grid


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
    return _validate_grid([[float(v) for v in row] for row in payload])


def precip_frequency_grid(
    *, lat: float, lon: float, settings: Settings | None = None
) -> dict[str, dict[int, float]]:
    """The full Atlas-14 depth (in) table for a point: ``{duration: {return_period: depth}}``."""
    settings = settings or get_settings()
    grid = _fetch_quantiles(settings, lat, lon)
    return {
        dur: {rp: grid[r][c] for c, rp in enumerate(_RETURN_PERIODS)}
        for r, dur in enumerate(_DURATIONS)
    }


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
        duration_hr=_duration_to_hours(duration),
        depth=ProvenancedValue.from_connector(
            depth,
            "in",
            citation=f"NOAA Atlas-14 PDS {duration} {return_period_yr}-yr @ {lat:.3f},{lon:.3f}",
        ),
    )
