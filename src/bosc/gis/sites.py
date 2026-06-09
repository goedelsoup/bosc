"""Tracking sites — named AOIs drawn from the committed GIS findings.

A *tracking site* is an area of interest we want to watch over time with satellite
imagery. Rather than author new geometry (which would be fabricated evidence), a site
is assembled from features already committed to ``data/site/gis-findings.geojson`` by
grouping them on the GeoJSON ``layer`` property — e.g. the ten ``campus`` parcels
become one "Data-center campus" AOI. Which layers count as trackable is configurable
(``settings.gis_tracking_layers``; default ``["campus"]``).

Geometry is the union footprint of the grouped features; the WGS84 ``bbox`` is what the
imagery search ([`bosc.gis.imagery`](imagery.py)) hands a STAC catalog as its query
envelope. Pure stdlib + Pydantic — no shapely needed for the bbox/assembly here.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings

# Friendly display names for the trackable layers; falls back to a title-cased key.
_LAYER_NAMES = {
    "campus": "Data-center campus",
    "jsmc": "JSMC / Lima Army Tank Plant",
    "wwtp": "WWTP receivers",
}

_SOURCE = "data/site/gis-findings.geojson (grouped by layer)"


class TrackingSite(BaseModel):
    """A named AOI to track over time, assembled from committed GIS features."""

    model_config = ConfigDict(extra="forbid")

    id: str  # the GeoJSON layer key, e.g. "campus"
    name: str
    layer: str
    n_features: int
    acreage: float | None  # summed feature acreage, when the source carries it
    bbox: tuple[float, float, float, float]  # WGS84 (minx, miny, maxx, maxy)
    geometry: dict[str, Any]  # GeoJSON union footprint (MultiPolygon or GeometryCollection)
    source: str = _SOURCE

    def padded_bbox(self, pad_deg: float = 0.0) -> tuple[float, float, float, float]:
        """The site bbox grown by ``pad_deg`` degrees — a search envelope."""
        minx, miny, maxx, maxy = self.bbox
        return (minx - pad_deg, miny - pad_deg, maxx + pad_deg, maxy + pad_deg)


def _load_features(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features", []) if isinstance(data, dict) else data
    return cast("list[dict[str, Any]]", features or [])


def _iter_coords(node: Any) -> Iterator[tuple[float, float]]:
    """Yield every (lon, lat) pair in a GeoJSON coordinate array, any nesting depth."""
    if (
        isinstance(node, (list, tuple))
        and len(node) >= 2
        and all(isinstance(c, (int, float)) for c in node[:2])
    ):
        yield (float(node[0]), float(node[1]))
        return
    if isinstance(node, (list, tuple)):
        for child in node:
            yield from _iter_coords(child)


def _bounds(geoms: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    pts = [pt for g in geoms for pt in _iter_coords(g.get("coordinates"))]
    if not pts:
        raise ValueError("no coordinates to bound")
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _assemble_geometry(geoms: list[dict[str, Any]]) -> dict[str, Any]:
    """Union the member geometries into one GeoJSON object (no reprojection).

    All-polygonal members collapse into a single ``MultiPolygon``; a mixed set falls
    back to a ``GeometryCollection`` (always valid, used as-is downstream).
    """
    polys: list[Any] = []
    all_poly = True
    for g in geoms:
        gtype = g.get("type")
        if gtype == "Polygon":
            polys.append(g.get("coordinates"))
        elif gtype == "MultiPolygon":
            polys.extend(g.get("coordinates") or [])
        else:
            all_poly = False
            break
    if all_poly and polys:
        return {"type": "MultiPolygon", "coordinates": polys}
    return {"type": "GeometryCollection", "geometries": geoms}


def _site_from_features(layer: str, feats: list[dict[str, Any]]) -> TrackingSite:
    geoms = [f["geometry"] for f in feats if f.get("geometry")]
    acres = [
        float(f["properties"]["acreage"])
        for f in feats
        if isinstance(f.get("properties"), dict) and f["properties"].get("acreage") is not None
    ]
    return TrackingSite(
        id=layer,
        name=_LAYER_NAMES.get(layer, layer.replace("_", " ").title()),
        layer=layer,
        n_features=len(feats),
        acreage=round(sum(acres), 2) if acres else None,
        bbox=_bounds(geoms),
        geometry=_assemble_geometry(geoms),
    )


def load_tracking_sites(
    *, layers: list[str] | None = None, settings: Settings | None = None
) -> list[TrackingSite]:
    """Tracking sites assembled from the committed GIS findings, one per trackable layer.

    ``layers`` overrides ``settings.gis_tracking_layers``. Layers with no usable
    geometry are skipped. Sites are returned in the configured layer order.
    """
    settings = settings or get_settings()
    wanted = layers if layers is not None else list(settings.gis_tracking_layers)
    features = _load_features(settings.gis_findings_path)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for feat in features:
        props = feat.get("properties") or {}
        layer = props.get("layer")
        if layer in wanted and feat.get("geometry"):
            grouped.setdefault(str(layer), []).append(feat)

    sites: list[TrackingSite] = []
    for layer in wanted:
        feats = grouped.get(layer)
        if not feats:
            continue
        try:
            sites.append(_site_from_features(layer, feats))
        except ValueError:
            continue  # no boundable coordinates in this layer
    return sites


def get_site(site_id: str, *, settings: Settings | None = None) -> TrackingSite | None:
    """One tracking site by id (its layer key), or ``None`` if not trackable."""
    # Resolve against all known trackable names so an explicit id works even if it
    # isn't in the default `gis_tracking_layers` set.
    settings = settings or get_settings()
    layers = sorted({*settings.gis_tracking_layers, *_LAYER_NAMES, site_id})
    for site in load_tracking_sites(layers=layers, settings=settings):
        if site.id == site_id:
            return site
    return None
