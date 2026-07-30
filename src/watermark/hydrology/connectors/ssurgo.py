"""USDA SSURGO (Soil Data Access) — hydrologic soil group connector.

Resolves the dominant **hydrologic soil group (HSG)** over an area of interest by
grid-sampling its footprint: an ``n x n`` lattice of interior points (``geo.
grid_points_within``), each resolved to its map unit's dominant-component HSG via the
SDA Tabular REST service (``SDA_Get_Mukey_from_intersection_with_WktWgs84``), then
tallied by grid count — an area proxy. One cached POST (a ``UNION ALL`` of per-point
sub-queries) keeps it hermetic; the cache key is the deterministic point grid, so a
committed fixture replays offline.

**One grid point casts exactly one vote.** Map units routinely carry *co-dominant*
components — an exact ``comppct_r`` tie, e.g. two 40% components — so "the dominant
component" has to be picked by a total order, not by ``= MAX(comppct_r)``, which
returns every tied row and lets one sample location vote twice (inflating ``n_points``
and skewing the tally that sets the site curve number). The order is fixed in
:func:`_build_query`, and the tally re-enforces the invariant on the response so a
cache/fixture recorded before this rule still collapses to one vote per point.
Response columns are resolved through the ``JSON+COLUMNNAME`` header by **name**;
a header that doesn't carry them is schema drift and fails loudly rather than being
read positionally.

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

from watermark.config import Settings, get_settings
from watermark.hydrology import geo
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

_CONNECTOR = "ssurgo"
_DEFAULT_GRID_N = 6  # n x n lattice over the footprint bbox; interior points sampled
_PT_COLUMN = "pt"  # SDA response columns, read by name off the JSON+COLUMNNAME header
_HSG_COLUMN = "hsg"


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
    """A single SDA SQL: the dominant-component HSG at each grid point, one row each.

    ``TOP 1`` over a **total order** — not ``= MAX(comppct_r)`` — so co-dominant
    components resolve to one deterministic winner per point instead of one row each:

    1. ``comppct_r DESC`` — the dominant component (T-SQL sorts ``NULL`` last on
       ``DESC``, so an unrated percent never outranks a rated one);
    2. rated ahead of unrated — a ``NULL`` ``hydgrp`` carries no soil-group information
       and T-SQL sorts ``NULL`` *first* ascending, so without this an exact tie between
       a rated and an unrated co-dominant component would drop the point entirely;
    3. ``hydgrp`` then ``cokey`` — arbitrary but stable, so the same grid replays to the
       same answer across pulls.

    ``ORDER BY`` is legal inside the derived table because ``TOP`` is present (it is not
    legal in a bare ``UNION ALL`` branch).
    """
    subs = [
        f"SELECT pt, hsg FROM ("
        f"SELECT TOP 1 {k} AS pt, co.hydgrp AS hsg "
        f"FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('POINT({lon} {lat})') p "
        f"JOIN component co ON co.mukey = p.mukey "
        f"ORDER BY co.comppct_r DESC, CASE WHEN co.hydgrp IS NULL THEN 1 ELSE 0 END, "
        f"co.hydgrp, co.cokey"
        f") AS d{k}"
        for k, (lon, lat) in enumerate(points)
    ]
    return "\nUNION ALL\n".join(subs)


def _resolve_columns(table: list[Any], source: str) -> tuple[int, int, list[Any]]:
    """Map the ``JSON+COLUMNNAME`` header to ``(pt_index, hsg_index, data_rows)``.

    Columns are selected **by name, never by position** (the repo-wide connector rule):
    a response whose header doesn't carry both columns is schema drift and raises rather
    than being read positionally into a plausible-but-wrong tally.
    """
    header = table[0]
    if not isinstance(header, list):
        raise SsurgoError(f"SDA response for {source} has no column header (got {header!r})")
    index = {str(name).strip().lower(): i for i, name in enumerate(header)}
    missing = [c for c in (_PT_COLUMN, _HSG_COLUMN) if c not in index]
    if missing:
        raise SsurgoError(
            f"SDA response for {source} is missing column(s) {', '.join(missing)} "
            f"(header={header!r}); columns are read by name, never by position"
        )
    return index[_PT_COLUMN], index[_HSG_COLUMN], table[1:]


def _hsg_by_point(rows: list[Any], pt_i: int, hsg_i: int, source: str) -> dict[str, str]:
    """One HSG per sampled point (``""`` = sampled but unrated), duplicates collapsed.

    The query already forces a single winner per point; this re-enforces it on the
    response so a cache/fixture recorded before that rule — or any future server-side
    change — can't restore the double-vote. A duplicate is broken by the only field the
    payload carries, mirroring the query's order: a rated group beats an unrated one,
    then lowest ``hydgrp``.
    """
    by_point: dict[str, str] = {}
    duplicates = 0
    for row in rows:
        if not isinstance(row, list) or len(row) <= max(pt_i, hsg_i):
            raise SsurgoError(f"SDA response for {source} has a short/malformed row: {row!r}")
        pt = str(row[pt_i]).strip()
        value = row[hsg_i]
        hsg = str(value).strip().upper() if value else ""
        prior = by_point.get(pt)
        if prior is None:
            by_point[pt] = hsg
            continue
        duplicates += 1
        if hsg and (not prior or hsg < prior):
            by_point[pt] = hsg
    if duplicates:
        # Not fatal — the point still votes once — but it means the payload predates the
        # single-winner query, so say so instead of collapsing it silently.
        log.warning("ssurgo.duplicate_point_rows", duplicates=duplicates, n_rows=len(rows))
    return by_point


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
    pt_i, hsg_i, rows = _resolve_columns(table, footprint_path.name)
    by_point = _hsg_by_point(rows, pt_i, hsg_i, footprint_path.name)

    counts: dict[str, int] = {}
    for hsg in by_point.values():
        if hsg:  # skip points with no rated dominant component (null) — never backfill
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
        n_points=n,  # rated points; <= n_sampled, which is <= the requested grid
        n_sampled=len(by_point),
        n_requested=len(points),
        distribution={d.hsg: d.points for d in distribution},
    )
    return survey
