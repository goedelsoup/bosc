"""USDA SSURGO (Soil Data Access) — hydrologic soil group connector.

Resolves the dominant **hydrologic soil group (HSG)** over an area of interest by
grid-sampling its footprint: an ``n x n`` lattice of interior points (``geo.
grid_points_within``), each resolved to its map unit's dominant-component HSG via the
SDA Tabular REST service (``SDA_Get_Mukey_from_intersection_with_WktWgs84``), then
tallied by grid count — an area proxy. One cached POST (a ``UNION ALL`` of per-point
sub-queries) keeps it hermetic; the cache key is the deterministic point grid, so a
committed fixture replays offline.

HSG drives the TR-55 curve number (``solver.curve_number.cn_for``), which reads the
**first letter** of the group — so a dual group like ``B/D`` resolves to its drained
class ``B``, appropriate for the tile-drained lake-plain cropland here and the campus's
engineered storm drainage. Field values are verbatim from SDA; an ``hydgrp`` of ``None``
(no rated dominant component) is skipped, never backfilled. Synchronous (``httpx``),
reusing the shared connector cache/offline/fixture machinery.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology import geo
from bosc.hydrology.connectors._cache import cached_get
from bosc.logging import get_logger

log = get_logger(__name__)

_CONNECTOR = "ssurgo"
_DEFAULT_GRID_N = 6  # n x n lattice over the footprint bbox; interior points sampled


class SsurgoError(RuntimeError):
    """The SDA service returned an error object or an unusable/empty response."""


class HsgShare(BaseModel):
    """One hydrologic soil group's share of the sampled footprint (area proxy)."""

    model_config = ConfigDict(extra="forbid")

    hsg: str  # verbatim component hydgrp: A | B | C | D | A/D | B/D | C/D
    points: int  # grid-sample points whose dominant component falls in this group
    fraction: float  # share of sampled points


class SoilHsgSurvey(BaseModel):
    """Grid-sampled hydrologic soil group distribution over an AOI (SSURGO/SDA)."""

    model_config = ConfigDict(extra="forbid")

    dominant_hsg: str  # the largest-share verbatim hydgrp
    distribution: list[HsgShare]
    n_points: int
    source: str = "USDA NRCS SSURGO via Soil Data Access (SDA) Tabular REST"

    @property
    def hsg_letter(self) -> str:
        """The dominant group's drained (first) HSG letter — the ``cn_for`` input."""
        return self.dominant_hsg.strip().upper()[:1]


def _build_query(points: list[tuple[float, float]]) -> str:
    """A single SDA SQL: the dominant-component HSG at each grid point, one row each."""
    subs = [
        f"SELECT {k} AS pt, co.hydgrp AS hsg "
        f"FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('POINT({lon} {lat})') p "
        f"JOIN component co ON co.mukey = p.mukey "
        f"WHERE co.comppct_r = (SELECT MAX(c2.comppct_r) FROM component c2 WHERE c2.mukey = p.mukey)"
        for k, (lon, lat) in enumerate(points)
    ]
    return "\nUNION ALL\n".join(subs)


def dominant_hsg(
    footprint_path: Path,
    *,
    grid_n: int = _DEFAULT_GRID_N,
    settings: Settings | None = None,
) -> SoilHsgSurvey:
    """Dominant HSG over a polygon footprint, grid-sampled from SSURGO via SDA.

    ``footprint_path`` is a GeoJSON of polygon features (e.g. the recorded Bistrozzi
    parcels). Raises :class:`SsurgoError` on an SDA error / empty result; an offline
    cache/fixture miss raises ``HydroOfflineError`` naming the key to record.
    """
    settings = settings or get_settings()
    points = geo.grid_points_within(footprint_path, grid_n)
    if not points:
        raise SsurgoError(f"no interior grid points in {footprint_path.name} (grid_n={grid_n})")
    sql = _build_query(points)

    def fetch() -> Any:
        log.info("ssurgo.fetch", points=len(points))
        resp = httpx.post(
            settings.ssurgo_sda_url,
            json={"query": sql, "format": "JSON+COLUMNNAME"},
            timeout=settings.hydro_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    # Cache/fixture key is the deterministic point grid (the SQL is derived from it).
    params = {"points": [list(p) for p in points]}
    payload = cast("dict[str, Any]", cached_get(_CONNECTOR, params, fetch, settings=settings))

    table = payload.get("Table") if isinstance(payload, dict) else None
    if not isinstance(table, list) or not table:
        raise SsurgoError(f"SDA returned no soil rows for {footprint_path.name}")
    # JSON+COLUMNNAME: row 0 is the column header (["pt","hsg"]); the rest are samples.
    rows = table[1:] if str(table[0][0]).lower() == "pt" else table

    counts: dict[str, int] = {}
    for row in rows:
        value = row[1] if len(row) > 1 else None
        hsg = str(value).strip().upper() if value else ""
        if hsg:  # skip components with no rated HSG (null) — never backfill
            counts[hsg] = counts.get(hsg, 0) + 1
    n = sum(counts.values())
    if n == 0:
        raise SsurgoError(f"SDA returned no rated HSG values for {footprint_path.name}")

    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    distribution = [HsgShare(hsg=h, points=c, fraction=round(c / n, 3)) for h, c in ordered]
    survey = SoilHsgSurvey(dominant_hsg=distribution[0].hsg, distribution=distribution, n_points=n)
    log.info(
        "ssurgo.survey",
        dominant=survey.dominant_hsg,
        n_points=n,
        distribution={d.hsg: d.points for d in distribution},
    )
    return survey
