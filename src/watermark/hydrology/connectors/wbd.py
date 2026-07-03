"""USGS Watershed Boundary Dataset (WBD) — HUC boundary connector.

Pulls Hydrologic Unit (HU) polygon boundaries from the USGS National Map **WBD**
ArcGIS REST service (the authoritative seamless WBD). Given a WGS84 point, returns
the containing HU polygon at a requested level — HU8 *Subbasin*, HU10 *Watershed*, or
HU12 *Subwatershed* — by querying the matching MapServer sublayer with the point
geometry and ``f=geojson`` (so geometry comes back as GeoJSON in WGS84, no Esri-rings
conversion). Geometry is kept **verbatim** (display-only, ``outSR=4326``, no
reprojection); attributes are read **by name**, never by index.

This drives ``watermark wbd``, which writes the campus's nested watershed boundaries to
``data/reference/hydrology/wbd/`` (a committed, regenerable reference dataset) — the
source geometry the ``watershed`` GeoJSON feed (#61) is assembled from. Reuses the
shared hydrology connector cache/offline/fixture machinery; synchronous (``httpx``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

# HU digit-count → WBD MapServer sublayer id (8 = Subbasin, 10 = Watershed,
# 12 = Subwatershed). Other levels exist on the service but these frame a campus AOI.
_LEVEL_LAYER: dict[int, int] = {8: 4, 10: 5, 12: 6}
_HU_LABEL: dict[int, str] = {8: "Subbasin", 10: "Watershed", 12: "Subwatershed"}


class WbdError(RuntimeError):
    """The WBD ArcGIS service returned an error object (bad field, bad geometry, ...)."""


class HucBoundary(BaseModel):
    """One Hydrologic Unit boundary polygon, as returned by the USGS WBD service."""

    model_config = ConfigDict(extra="forbid")

    huc: str  # the HUC code (8 / 10 / 12 digits), verbatim
    level: int  # 8 | 10 | 12 — the HU digit count
    hu_label: str  # Subbasin | Watershed | Subwatershed
    name: str  # the HU name, verbatim (e.g. "Pike Run")
    states: str | None  # comma-joined state codes, verbatim
    area_sqkm: float | None  # the published HU area
    to_huc: str | None  # the downstream HUC the unit drains to (tohuc), where present
    geometry: dict[str, Any]  # GeoJSON geometry (Polygon/MultiPolygon), WGS84 verbatim


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_huc_at_point(
    lon: float, lat: float, *, level: int, settings: Settings | None = None
) -> HucBoundary | None:
    """The HU polygon (at ``level``) containing the WGS84 point ``(lon, lat)``.

    ``level`` is the HU digit count: 8 (Subbasin), 10 (Watershed), or 12
    (Subwatershed). Returns ``None`` when the point falls in no unit (e.g. offshore).
    Replayed from cache/fixture when offline; an offline miss raises ``HydroOfflineError``.
    """
    settings = settings or get_settings()
    if level not in _LEVEL_LAYER:
        raise ValueError(f"unsupported HU level {level}; expected one of {sorted(_LEVEL_LAYER)}")
    layer = _LEVEL_LAYER[level]
    field = f"huc{level}"

    # f=geojson → the service returns a GeoJSON FeatureCollection (geometry in outSR).
    query: dict[str, Any] = {
        "f": "geojson",
        "geometry": f"{round(lon, 6)},{round(lat, 6)}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
    }
    # `layer` namespaces the cache key so the three levels at one point never collide
    # (it routes the URL path, not a query param the server reads).
    key_params = {**query, "layer": layer}

    def fetch() -> Any:
        log.info("wbd.fetch", level=level, lon=lon, lat=lat)
        resp = httpx.get(
            f"{settings.wbd_url}/{layer}/query",
            params=query,
            timeout=settings.hydro_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cast("dict[str, Any]", cached_get("wbd", key_params, fetch, settings=settings))
    if isinstance(payload, dict) and "error" in payload:
        raise WbdError(f"WBD ArcGIS error: {payload['error']}")

    features = payload.get("features") or []
    if not features:
        return None
    feat = features[0]
    props = feat.get("properties") or {}
    geometry = feat.get("geometry")
    if not geometry:
        return None
    return HucBoundary(
        huc=str(props.get(field) or "").strip(),
        level=level,
        hu_label=_HU_LABEL[level],
        name=str(props.get("name") or "").strip(),
        states=_s(props.get("states")),
        area_sqkm=_f(props.get("areasqkm")),
        to_huc=_s(props.get("tohuc")),
        geometry=geometry,
    )


def watershed_chain(
    lon: float, lat: float, *, levels: tuple[int, ...] = (12, 10), settings: Settings | None = None
) -> list[HucBoundary]:
    """The nested HU boundaries containing a point, finest level first.

    The default ``(12, 10)`` is the campus framing: its Subwatershed and the Watershed it
    drains through. (The coarser Subbasin/Maumee basin nests further out — pass
    ``levels=(12, 10, 8)`` to include HU8 — but a basin polygon is heavy and adds little
    to a campus-scale map.) Levels with no unit at the point are skipped, never fabricated.
    """
    settings = settings or get_settings()
    out: list[HucBoundary] = []
    for level in levels:
        hu = fetch_huc_at_point(lon, lat, level=level, settings=settings)
        if hu is None:
            log.warning("wbd.no_unit_at_point", level=level, lon=lon, lat=lat)
            continue
        out.append(hu)
    return out


def _slug(name: str) -> str:
    """A filename slug from an HU name: "Middle Ottawa River" → "middle-ottawa-river"."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def boundary_geojson(
    hu: HucBoundary, *, queried_point: tuple[float, float] | None = None
) -> dict[str, Any]:
    """One HU boundary as a committed-reference FeatureCollection (provenance in ``meta``).

    Geometry is carried verbatim; ``properties`` keep the HU attributes (by name) so the
    ``watershed`` feed exporter has everything it needs without re-querying the service.
    """
    layer = _LEVEL_LAYER[hu.level]
    meta: dict[str, Any] = {
        "subject": f"USGS WBD Hydrologic Unit — HU{hu.level} {hu.name} ({hu.huc})",
        "source": (
            "USGS National Map Watershed Boundary Dataset (WBD), ArcGIS REST, "
            f"layer {layer} ({hu.level}-digit HU / {hu.hu_label})"
        ),
        "source_url": f"https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/{layer}",
        "huc": hu.huc,
        "level": hu.level,
        "hu_label": hu.hu_label,
        "name": hu.name,
        "states": hu.states,
        "area_sqkm": hu.area_sqkm,
        "to_huc": hu.to_huc,
        "crs": "WGS84 (EPSG:4326)",
        "caveats": [
            "Geometry is verbatim from the USGS WBD (WGS84 / EPSG:4326), display-only — "
            "no reprojection or simplification.",
            "Selected as the HU containing the queried point (the tracked-AOI centroid).",
        ],
    }
    if queried_point is not None:
        meta["queried_point"] = [round(queried_point[0], 6), round(queried_point[1], 6)]
    properties: dict[str, Any] = {
        "huc": hu.huc,
        "level": hu.level,
        "hu_label": hu.hu_label,
        "name": hu.name,
        "states": hu.states,
        "area_sqkm": hu.area_sqkm,
        "to_huc": hu.to_huc,
    }
    return {
        "type": "FeatureCollection",
        "meta": meta,
        "features": [{"type": "Feature", "properties": properties, "geometry": hu.geometry}],
    }


def write_watershed_boundaries(
    boundaries: list[HucBoundary],
    out_dir: Path,
    *,
    queried_point: tuple[float, float] | None = None,
) -> list[Path]:
    """Write each HU boundary to ``out_dir/<huc>-<slug>.geojson``; return the paths.

    One file per unit (provenance per HU), the geometry the ``watershed`` feed reads.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for hu in boundaries:
        path = out_dir / f"{hu.huc}-{_slug(hu.name)}.geojson"
        doc = boundary_geojson(hu, queried_point=queried_point)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
