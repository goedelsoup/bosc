"""City of Lima, Ohio GIS — zoning connector.

Pulls the **"Current Lima Zoning"** polygon layer from the City of Lima's public
**ArcGIS REST** server (folder ``CitywideMaps/Lima_Zoning``, layer 6). Each zoning
polygon carries a ``ZONING`` district label and a ``PARCEL_NO`` — so zoning joins
to a parcel by id, no spatial query needed. The server is anonymous (no token),
serves ``f=json``, and the layer's ``maxRecordCount`` is 10,000.

Scope caveat (important): this layer covers **Lima city limits only**. Parcels in
unincorporated Allen County (e.g. the American Township corridor) are *not* in it —
a lookup there returning ``None`` means "outside the city," not "unzoned."

Two ways in:

* :func:`zoning_for_parcel` — the district for one parcel number (deed ids like
  ``36-0100-03-002.000`` are normalized to the dashless ``PARCEL_NO``);
* :func:`zoning_districts` — the district catalog (each code + its polygon count),
  via a server-side ``groupBy`` statistics query.

Values are passed through **verbatim** from the service; ``None`` means the service
returned no value. Reuses the shared connector cache/offline/fixture machinery;
synchronous (``httpx``). Mirrors :mod:`bosc.hydrology.connectors.allen_gis`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors._cache import cached_get
from bosc.hydrology.connectors.allen_gis import normalize_parcel_id
from bosc.logging import get_logger

log = get_logger(__name__)

_PAGE_SIZE = 10000  # the layer's maxRecordCount


class LimaGisError(RuntimeError):
    """The ArcGIS service returned an error object (bad field, bad where, ...)."""


class ZoningRecord(BaseModel):
    """One zoning polygon's attributes, as returned by the City of Lima GIS."""

    model_config = ConfigDict(extra="forbid")

    object_id: int | None
    parcel_no: str | None  # PARCEL_NO (dashless, joins to the county CAMA layer)
    zoning: str | None  # ZONING district label, verbatim

    @classmethod
    def from_attrs(cls, a: dict[str, Any]) -> ZoningRecord:
        return cls(
            object_id=_i(a.get("OBJECTID")),
            parcel_no=_s(a.get("PARCEL_NO")),
            zoning=_s(a.get("ZONING")),
        )


class ZoningDistrict(BaseModel):
    """One zoning district and how many polygons carry it (the catalog row)."""

    model_config = ConfigDict(extra="forbid")

    code: str  # the ZONING label, verbatim
    polygon_count: int


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _i(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bfe(value: Any) -> float | None:
    """A base-flood elevation, or None for missing / the -9999 'no BFE' sentinel."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f == _BFE_SENTINEL else f


def _query(
    params: dict[str, Any], *, settings: Settings, url: str, connector: str = "lima_gis"
) -> dict[str, Any]:
    """Run (or replay) one ArcGIS ``/query`` against ``url``; return the parsed JSON.

    ``connector`` namespaces the cache/fixtures so different layers of the same
    service (zoning vs floodzone) never collide on identical params.
    """
    query = {"f": "json", "returnGeometry": "false", **params}

    def fetch() -> Any:
        log.info(f"{connector}.fetch", where=params.get("where"), offset=params.get("resultOffset"))
        # POST (form-encoded) — spatial queries carry a geometry too large for a GET URL.
        resp = httpx.post(f"{url}/query", data=query, timeout=settings.hydro_request_timeout_s)
        resp.raise_for_status()
        return resp.json()

    payload = cast("dict[str, Any]", cached_get(connector, query, fetch, settings=settings))
    if "error" in payload:
        raise LimaGisError(f"ArcGIS error: {payload['error']}")
    return payload


def query_zoning(
    where: str,
    *,
    max_records: int | None = None,
    settings: Settings | None = None,
) -> list[ZoningRecord]:
    """Every zoning polygon matching ``where``, paged to completion."""
    settings = settings or get_settings()
    records: list[ZoningRecord] = []
    offset = 0
    while True:
        page = _query(
            {
                "where": where,
                "outFields": "OBJECTID,PARCEL_NO,ZONING",
                "resultOffset": offset,
                "resultRecordCount": _PAGE_SIZE,
                "orderByFields": "OBJECTID",
            },
            settings=settings,
            url=settings.lima_zoning_url,
        )
        features = page.get("features") or []
        records.extend(ZoningRecord.from_attrs(f.get("attributes", {})) for f in features)
        if max_records is not None and len(records) >= max_records:
            return records[:max_records]
        if not page.get("exceededTransferLimit") or not features:
            return records
        offset += len(features)


def zoning_for_parcel(parcel_no: str, *, settings: Settings | None = None) -> ZoningRecord | None:
    """The zoning district for one parcel; ``None`` if outside Lima city limits."""
    settings = settings or get_settings()
    normalized = normalize_parcel_id(parcel_no)
    matches = query_zoning(f"PARCEL_NO='{normalized}'", settings=settings)
    return matches[0] if matches else None


def zoning_districts(*, settings: Settings | None = None) -> list[ZoningDistrict]:
    """The zoning-district catalog: each ``ZONING`` code and its polygon count.

    Uses a server-side ``groupBy`` statistics query so the whole catalog comes back
    in one request rather than paging every polygon.
    """
    settings = settings or get_settings()
    stats = [
        {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}
    ]
    page = _query(
        {
            "where": "1=1",
            "outFields": "ZONING",
            "groupByFieldsForStatistics": "ZONING",
            "outStatistics": json.dumps(stats),
        },
        settings=settings,
        url=settings.lima_zoning_url,
    )
    districts = [
        ZoningDistrict(code=str(a.get("ZONING") or "").strip(), polygon_count=int(a.get("n") or 0))
        for a in (f.get("attributes", {}) for f in page.get("features") or [])
        if _s(a.get("ZONING"))
    ]
    return sorted(districts, key=lambda d: (-d.polygon_count, d.code))


def write_zoning_districts(districts: list[ZoningDistrict], out_dir: Path) -> Path:
    """Write the zoning-district catalog to one YAML file with provenance ``meta``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "zoning-districts.yaml"
    doc = {
        "meta": {
            "subject": "City of Lima, Ohio zoning districts (catalog)",
            "source": "City of Lima GIS — ArcGIS REST, CitywideMaps/Lima_Zoning, layer 6 'Current Lima Zoning'",
            "source_url": (
                "https://colgis.cityhall.lima.oh.us/server/rest/services/"
                "CitywideMaps/Lima_Zoning/MapServer/6"
            ),
            "district_count": len(districts),
            "polygon_total": sum(d.polygon_count for d in districts),
            "caveats": [
                "Values are verbatim from the City of Lima GIS.",
                "Coverage is Lima CITY LIMITS ONLY; unincorporated Allen County parcels "
                "(e.g. the American Township corridor) are not in this layer.",
                "polygon_count counts zoning polygons, not distinct parcels (a parcel may "
                "carry more than one polygon).",
            ],
        },
        "districts": [d.model_dump() for d in districts],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# --- FEMA Floodzone (DFIRM) layer ------------------------------------------

_FLOOD_CONNECTOR = "lima_gis_flood"
_BFE_SENTINEL = -9999  # the layer's "no static BFE" sentinel — never a real elevation


class FloodZone(BaseModel):
    """One FEMA DFIRM flood-hazard polygon's attributes (City of Lima GIS, layer 4)."""

    model_config = ConfigDict(extra="forbid")

    object_id: int | None
    fld_zone: str | None  # FEMA zone code: A / AE / AO / X / ...
    zone_subtype: str | None  # e.g. FLOODWAY; None when blank
    sfha: bool  # Special Flood Hazard Area (SFHA_TF == 'T')
    static_bfe: float | None  # base flood elevation, or None for the -9999 sentinel
    dfirm_id: str | None
    source_cit: str | None  # the FIRM / FIS citation

    @classmethod
    def from_attrs(cls, a: dict[str, Any]) -> FloodZone:
        return cls(
            object_id=_i(a.get("OBJECTID")),
            fld_zone=_s(a.get("FLD_ZONE")),
            zone_subtype=_s(a.get("ZONE_SUBTY")),
            sfha=str(a.get("SFHA_TF") or "").strip().upper() == "T",
            static_bfe=_bfe(a.get("STATIC_BFE")),
            dfirm_id=_s(a.get("DFIRM_ID")),
            source_cit=_s(a.get("SOURCE_CIT")),
        )


class FloodZoneClass(BaseModel):
    """One distinct flood-zone class and its polygon count (the catalog row)."""

    model_config = ConfigDict(extra="forbid")

    fld_zone: str
    zone_subtype: str | None
    sfha: bool
    polygon_count: int


def _polygon_rings(path: Path) -> list[list[list[float]]]:
    """Extract all polygon rings from a footprint GeoJSON (Polygon/MultiPolygon).

    Non-areal features (a stray Point/LineString) are skipped — only rings that can
    bound an area contribute to the spatial query geometry.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    rings: list[list[list[float]]] = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        gtype, coords = geom.get("type"), geom.get("coordinates")
        polys: Any = [coords] if gtype == "Polygon" else coords if gtype == "MultiPolygon" else None
        if polys is None:
            continue
        for poly in polys:
            for ring in poly:
                rings.append([[float(pt[0]), float(pt[1])] for pt in ring])
    return rings


def _flood_query(params: dict[str, Any], *, settings: Settings) -> dict[str, Any]:
    return _query(
        params, settings=settings, url=settings.lima_floodzone_url, connector=_FLOOD_CONNECTOR
    )


def query_floodzones(
    where: str = "1=1",
    *,
    rings: list[list[list[float]]] | None = None,
    point: tuple[float, float] | None = None,
    distance_m: float | None = None,
    settings: Settings | None = None,
) -> list[FloodZone]:
    """Flood-hazard polygons matching ``where`` and (optionally) a WGS84 geometry.

    Pass ``rings`` (polygon, lon/lat) or ``point`` (``(lon, lat)``); the service
    reprojects from ``inSR=4326``. A truthy ``distance_m`` buffers the geometry so
    "within N metres" can be answered (omit/0 = exact intersect — ArcGIS rejects a
    literal ``distance=0``). Paged to completion.
    """
    settings = settings or get_settings()
    spatial: dict[str, Any] = {}
    if rings is not None:
        spatial = {
            "geometry": json.dumps({"rings": rings, "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryPolygon",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
    elif point is not None:
        spatial = {
            "geometry": json.dumps(
                {"x": point[0], "y": point[1], "spatialReference": {"wkid": 4326}}
            ),
            "geometryType": "esriGeometryPoint",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
    if spatial and distance_m:
        spatial["distance"] = distance_m
        spatial["units"] = "esriSRUnit_Meter"
    out: list[FloodZone] = []
    offset = 0
    while True:
        page = _flood_query(
            {
                "where": where,
                "outFields": "OBJECTID,FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DFIRM_ID,SOURCE_CIT",
                "resultOffset": offset,
                "resultRecordCount": _PAGE_SIZE,
                "orderByFields": "OBJECTID",
                **spatial,
            },
            settings=settings,
        )
        features = page.get("features") or []
        out.extend(FloodZone.from_attrs(f.get("attributes", {})) for f in features)
        if not page.get("exceededTransferLimit") or not features:
            return out
        offset += len(features)


def floodzone_catalog(*, settings: Settings | None = None) -> list[FloodZoneClass]:
    """The DFIRM flood-zone catalog: each (zone, subtype, SFHA) and its polygon count."""
    settings = settings or get_settings()
    stats = [
        {"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}
    ]
    page = _flood_query(
        {
            "where": "1=1",
            "outFields": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
            "groupByFieldsForStatistics": "FLD_ZONE,ZONE_SUBTY,SFHA_TF",
            "outStatistics": json.dumps(stats),
        },
        settings=settings,
    )
    classes = [
        FloodZoneClass(
            fld_zone=str(a.get("FLD_ZONE") or "").strip(),
            zone_subtype=_s(a.get("ZONE_SUBTY")),
            sfha=str(a.get("SFHA_TF") or "").strip().upper() == "T",
            polygon_count=int(a.get("n") or 0),
        )
        for a in (f.get("attributes", {}) for f in page.get("features") or [])
        if _s(a.get("FLD_ZONE"))
    ]
    return sorted(classes, key=lambda c: (-c.polygon_count, c.fld_zone, c.zone_subtype or ""))


def footprint_floodzones(
    footprint_path: Path, *, distance_m: float = 0.0, settings: Settings | None = None
) -> list[FloodZone]:
    """Flood-hazard polygons intersecting a footprint GeoJSON (optionally buffered)."""
    rings = _polygon_rings(footprint_path)
    dist = distance_m if distance_m else None
    return query_floodzones(rings=rings, distance_m=dist, settings=settings)


def point_floodzones(
    lon: float, lat: float, *, distance_m: float = 0.0, settings: Settings | None = None
) -> list[FloodZone]:
    """Flood-hazard polygons at (or within ``distance_m`` of) a WGS84 point."""
    dist = distance_m if distance_m else None
    return query_floodzones(point=(lon, lat), distance_m=dist, settings=settings)


def write_floodzone_catalog(classes: list[FloodZoneClass], out_dir: Path) -> Path:
    """Write the DFIRM flood-zone catalog to one YAML file with provenance ``meta``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "floodzones.yaml"
    doc = {
        "meta": {
            "subject": "FEMA flood-hazard zones over Allen County (DFIRM panel 39003C)",
            "source": "City of Lima GIS — ArcGIS REST, CitywideMaps/Lima_Zoning, layer 4 'Floodzone' (FEMA DFIRM)",
            "source_url": (
                "https://colgis.cityhall.lima.oh.us/server/rest/services/"
                "CitywideMaps/Lima_Zoning/MapServer/4"
            ),
            "class_count": len(classes),
            "polygon_total": sum(c.polygon_count for c in classes),
            "caveats": [
                "Values are verbatim from the FEMA DFIRM served by the City of Lima GIS.",
                "Only Special Flood Hazard Areas (1%-annual-chance: A/AE incl. floodway, AO) "
                "are mapped here; areas outside the SFHA carry no polygon.",
                "A site's flood zone is a SPATIAL question (no PARCEL_NO on this layer) — use "
                "footprint_floodzones() / bosc floodzone --footprint.",
            ],
        },
        "classes": [c.model_dump() for c in classes],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
