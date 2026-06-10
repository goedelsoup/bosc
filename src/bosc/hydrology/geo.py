"""Geospatial helpers for the hydrology subsystem.

Increment 1 stays light: **shapely + pyproj + the stdlib ``json`` module only**
(no geopandas/rasterio). GeoJSON reference data is WGS84 (EPSG:4326); areas are
computed by reprojecting to UTM zone 17N (Allen County, OH) so shapely's planar
``.area`` is in metres. All ``Any``-typed shapely access is contained to this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shapely_transform
from shapely.ops import unary_union

from bosc.config import Settings, get_settings
from bosc.hydrology.model import Node

_SQM_PER_ACRE = 4046.8564224
_SQM_PER_SQMI = 2_589_988.110336


def _load_features(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", []) if isinstance(data, dict) else []
    return cast("list[dict[str, Any]]", features)


def _to_utm_area_sqm(geometry: dict[str, Any], utm_epsg: int) -> float:
    """Planar area (m^2) of a GeoJSON geometry, reprojected WGS84 -> UTM."""
    geom = shape(geometry)
    transformer = Transformer.from_crs(4326, utm_epsg, always_xy=True)
    projected = shapely_transform(transformer.transform, geom)
    return float(projected.area)


def feature_area_acres(geometry: dict[str, Any], *, settings: Settings | None = None) -> float:
    """Area of a single GeoJSON polygon geometry, in acres (0 for non-areal)."""
    settings = settings or get_settings()
    return _to_utm_area_sqm(geometry, settings.hydro_utm_epsg) / _SQM_PER_ACRE


def parcels_total_acres(path: Path, *, settings: Settings | None = None) -> float:
    """Sum the polygon areas in a parcels GeoJSON, in acres.

    Point features (geocoded approximations without a footprint) contribute 0;
    callers that need them should fall back to the ``acreage`` property.
    """
    settings = settings or get_settings()
    total = 0.0
    for feat in _load_features(path):
        geom = feat.get("geometry") or {}
        if geom.get("type") in ("Polygon", "MultiPolygon"):
            total += _to_utm_area_sqm(geom, settings.hydro_utm_epsg) / _SQM_PER_ACRE
    return total


def bbox_of(path: Path, *, pad_deg: float = 0.0) -> tuple[float, float, float, float]:
    """WGS84 bounding box ``(minx, miny, maxx, maxy)`` over every feature.

    Padded by ``pad_deg`` degrees, suitable as a connector ``bBox`` parameter.
    """
    geoms = [shape(f["geometry"]) for f in _load_features(path) if f.get("geometry")]
    if not geoms:
        raise ValueError(f"no geometries in {path}")
    minx = min(g.bounds[0] for g in geoms) - pad_deg
    miny = min(g.bounds[1] for g in geoms) - pad_deg
    maxx = max(g.bounds[2] for g in geoms) + pad_deg
    maxy = max(g.bounds[3] for g in geoms) + pad_deg
    return (minx, miny, maxx, maxy)


def grid_points_within(path: Path, n_side: int) -> list[tuple[float, float]]:
    """Deterministic ``(lon, lat)`` grid-cell centers that fall inside the footprint.

    An ``n_side x n_side`` lattice over the bounding box of the GeoJSON's polygon
    features, keeping the centers inside their union — a uniform area sample of the
    footprint (e.g. for a soil-survey point grid). Deterministic, so the sample (and
    any cache key derived from it) is stable for a given committed geometry.
    """
    geoms = [
        shape(f["geometry"])
        for f in _load_features(path)
        if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
    ]
    if not geoms:
        raise ValueError(f"no polygon geometries in {path}")
    footprint = unary_union(geoms)
    minx, miny, maxx, maxy = footprint.bounds
    points: list[tuple[float, float]] = []
    for i in range(n_side):
        for j in range(n_side):
            lon = minx + (maxx - minx) * (i + 0.5) / n_side
            lat = miny + (maxy - miny) * (j + 0.5) / n_side
            if footprint.contains(Point(lon, lat)):
                points.append((round(lon, 6), round(lat, 6)))
    return points


def wwtp_nodes_from_watch_items(path: Path) -> list[Node]:
    """Parse the WWTP receiver Points from ``watch-items.geojson`` into nodes.

    The watch list tags each county plant with ``status=bosc_fm1_receiver`` (or, for
    Shawnee II, an ``infrastructure`` point whose title ends "WWTP"). We read the
    plant's coordinates and name here; the cited design flows live in the feature
    summaries and are attached in :mod:`bosc.hydrology.balance`.
    """
    nodes: list[Node] = []
    for feat in _load_features(path):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        title = str(props.get("title", ""))
        is_wwtp = props.get("status") == "bosc_fm1_receiver" or title.endswith("WWTP")
        if not is_wwtp or geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][0], geom["coordinates"][1]
        nodes.append(
            Node(
                id=str(props.get("id", title)),
                name=title,
                role="wwtp",
                lat=float(lat),
                lon=float(lon),
            )
        )
    return nodes
