"""USGS 3DEP/NED terrain connector — the AERMAP DEM input.

Pulls a GeoTIFF digital elevation model (DEM) over the AERMAP terrain domain from the USGS
3DEPElevation ImageServer (3DEP is the successor to the National Elevation Dataset) and
samples receptor / source elevations from it with ``rasterio``. AERMAP's own binary
(#1178) consumes the DEM to compute elevations **and** hill-height scales; #1179 fetches
the DEM and computes the point *elevations* directly by bilinear interpolation — a
deterministic read of authoritative pixels (tagged ``[derived]``), never a fabricated
value. The hill-height-scale computation stays with the AERMAP binary.

A DEM is a raster, so — like :mod:`watermark.gis.raster` — this connector does **not** use
the JSON connector cache: the live path writes a GeoTIFF under ``air_cache_dir/ned/`` and
the offline path replays a committed fixture GeoTIFF under ``air_fixtures_dir/ned/`` (a
small windowed/decimated stand-in, so tests stay hermetic). A fixture miss raises
:class:`AirOfflineError` naming the key to record.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import numpy as np
import rasterio
from pydantic import BaseModel, ConfigDict
from rasterio.transform import rowcol

from watermark.air.connectors._cache import AirOfflineError, cache_key
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

if TYPE_CHECKING:
    from rasterio.io import DatasetReader

log = get_logger(__name__)

_CONNECTOR = "ned"
# 3DEP native posting is 1/3 arc-second (~10 m); request that so the DEM is faithful.
_CELLSIZE_DEG = 1.0 / 10800.0
_MAX_PIXELS = 4000  # ImageServer exportImage size guard


class PointElevation(BaseModel):
    """A receptor/source point and its DEM-sampled ground elevation (metres)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    latitude: float
    longitude: float
    elevation_m: float | None  # None = point outside the DEM domain or nodata


class TerrainDomain(BaseModel):
    """The fetched AERMAP DEM domain: where the GeoTIFF lives + its grid provenance."""

    model_config = ConfigDict(extra="forbid")

    center_lat: float
    center_lon: float
    bbox: tuple[float, float, float, float]  # WGS84 (minlon, minlat, maxlon, maxlat)
    epsg: int | None
    width: int
    height: int
    cell_size_deg: float  # actual DEM pixel size (degrees), read from the raster — QA sees the
    # true export resolution even when the request was clamped by _MAX_PIXELS.
    dem_path: str
    source: str  # "fixture DEM (offline)" / "USGS 3DEP ImageServer" / "... (cached)"


def _bbox(center_lat: float, center_lon: float, half: float) -> tuple[float, float, float, float]:
    return (center_lon - half, center_lat - half, center_lon + half, center_lat + half)


def _resolve_dem(
    key: str, bbox: tuple[float, float, float, float], settings: Settings
) -> tuple[Path, str]:
    """Return ``(dem_path, source_label)`` — a committed fixture or a freshly exported DEM."""
    if settings.air_offline:
        if settings.air_fixtures_dir is None:
            raise AirOfflineError(f"offline: no air_fixtures_dir set to resolve NED DEM key={key}")
        path = settings.air_fixtures_dir / _CONNECTOR / f"{key}.tif"
        if not path.is_file():
            raise AirOfflineError(
                f"offline: no fixture DEM for NED key={key} (bbox={bbox}); record one at {path}"
            )
        return path, "fixture DEM (offline)"

    dest = settings.air_cache_dir / _CONNECTOR / f"{key}.tif"
    if dest.is_file():  # deterministic key already exported — reuse, skip the network
        return dest, "USGS 3DEP ImageServer (cached)"

    minlon, minlat, maxlon, maxlat = bbox
    span = max(maxlon - minlon, maxlat - minlat)
    requested_px = max(1, round(span / _CELLSIZE_DEG))
    size = min(_MAX_PIXELS, requested_px)
    if requested_px > _MAX_PIXELS:  # clamped — the export is coarser than 3DEP native; say so
        log.warning(
            "ned.resolution_clamped",
            key=key,
            requested_px=requested_px,
            capped_px=_MAX_PIXELS,
            requested_cell_deg=_CELLSIZE_DEG,
            achieved_cell_deg=round(span / size, 8),
        )
    query = {
        "bbox": f"{minlon},{minlat},{maxlon},{maxlat}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{size},{size}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    url = f"{settings.ned_base_url}/exportImage"
    resp = httpx.get(
        url, params=query, timeout=settings.air_request_timeout_s, follow_redirects=True
    )
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tif.part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)  # atomic: only a fully-fetched file lands at the cache key
    log.info("connector.fetch", connector=_CONNECTOR, key=key)
    return dest, "USGS 3DEP ImageServer"


def fetch_terrain(
    *,
    center_lat: float | None = None,
    center_lon: float | None = None,
    halfwidth_deg: float | None = None,
    settings: Settings | None = None,
) -> TerrainDomain:
    """Fetch (or replay) the AERMAP DEM over a square domain centred on the site.

    The domain centre defaults to the site's ``nasa_power_lat/lon`` loop centroid (per-site,
    profile-filled) and the half-width to ``settings.air_terrain_halfwidth_deg``.
    """
    settings = settings or get_settings()
    center_lat = settings.nasa_power_lat if center_lat is None else center_lat
    center_lon = settings.nasa_power_lon if center_lon is None else center_lon
    half = settings.air_terrain_halfwidth_deg if halfwidth_deg is None else halfwidth_deg
    bbox = _bbox(center_lat, center_lon, half)
    key = cache_key({"bbox": [round(v, 6) for v in bbox], "cell": _CELLSIZE_DEG})

    path, source = _resolve_dem(key, bbox, settings)
    with rasterio.open(path) as dem:
        epsg = dem.crs.to_epsg() if dem.crs else None
        width, height = dem.width, dem.height
        cell = abs(dem.res[0])  # actual pixel size (degrees) — reflects any export clamp
    return TerrainDomain(
        center_lat=center_lat,
        center_lon=center_lon,
        bbox=bbox,
        epsg=epsg,
        width=width,
        height=height,
        cell_size_deg=cell,
        dem_path=str(path),
        source=source,
    )


def sample_points(
    domain: TerrainDomain, points: list[tuple[str, float, float]]
) -> list[PointElevation]:
    """Bilinearly sample ground elevations (m) at ``(id, lat, lon)`` points from the DEM."""
    with rasterio.open(domain.dem_path) as dem:
        band = dem.read(1, masked=True).astype("float64")
        nodata = dem.nodata
        return [
            PointElevation(
                id=pid,
                latitude=lat,
                longitude=lon,
                elevation_m=_bilinear(dem, band, lon, lat, nodata),
            )
            for pid, lat, lon in points
        ]


def _bilinear(
    dem: DatasetReader, band: np.ma.MaskedArray, lon: float, lat: float, nodata: float | None
) -> float | None:
    """Bilinear interpolation of the DEM at a WGS84 point; ``None`` if outside/nodata."""
    row_raw, col_raw = rowcol(dem.transform, lon, lat, op=lambda v: v)
    row_f, col_f = float(row_raw), float(col_raw)
    if not (0 <= row_f <= dem.height - 1 and 0 <= col_f <= dem.width - 1):
        return None
    r0, c0 = int(np.floor(row_f)), int(np.floor(col_f))
    r1, c1 = min(r0 + 1, dem.height - 1), min(c0 + 1, dem.width - 1)
    fr, fc = row_f - r0, col_f - c0
    corners = [band[r0, c0], band[r0, c1], band[r1, c0], band[r1, c1]]
    if any(np.ma.is_masked(v) or (nodata is not None and float(v) == nodata) for v in corners):
        return None
    top = float(corners[0]) * (1 - fc) + float(corners[1]) * fc
    bot = float(corners[2]) * (1 - fc) + float(corners[3]) * fc
    return round(top * (1 - fr) + bot * fr, 2)
