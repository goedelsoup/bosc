"""City/jurisdiction zoning + FEMA floodzone connector — schema-driven (#237).

Pulls a jurisdiction's **zoning** polygon layer and its **flood-hazard** (FEMA DFIRM / NFHL)
layer from a public **ArcGIS REST** server. As with :mod:`watermark.hydrology.connectors.allen_gis`,
the field names + encodings are not hardcoded: they come from the active site's
:class:`~watermark.connectors.gis_schema.GisZoningSchema` / :class:`~watermark.connectors.gis_schema.GisFloodSchema`
(``SiteProfile.gis_zoning`` / ``gis_flood``). Lima = the City of Lima "Current Lima Zoning"
layer (folder ``CitywideMaps/Lima_Zoning``, layer 6) joined to a parcel by id, and the FEMA
DFIRM floodzone (layer 4); its schemas (:data:`watermark.sites.LIMA_ZONING_SCHEMA` /
:data:`watermark.sites.LIMA_FLOOD_SCHEMA`) reproduce the pre-#237 behavior exactly.

Scope caveat (Lima): the zoning layer covers **city limits only**. Parcels in unincorporated
county land (e.g. the American Township corridor) are *not* in it — a lookup there returning
``None`` means "outside the city," not "unzoned."

Values are passed through **verbatim** from the service; ``None`` means the service returned
no value. Reuses the shared connector cache/offline/fixture machinery; synchronous (``httpx``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors.gis_schema import GisFloodSchema, GisZoningSchema
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.connectors.allen_gis import normalize_parcel_id
from watermark.logging import get_logger
from watermark.sites import LIMA_FLOOD_SCHEMA, LIMA_ZONING_SCHEMA, active_profile

log = get_logger(__name__)


class LimaGisError(RuntimeError):
    """The ArcGIS service returned an error object, or the active site has no zoning/flood schema."""


def _zoning_schema(settings: Settings) -> GisZoningSchema:
    """The active site's zoning GIS schema, or a clean error if it has none."""
    schema = active_profile(settings).gis_zoning
    if schema is None:
        raise LimaGisError(
            f"site {settings.site!r} has no zoning GIS schema (gis_zoning) — cannot query zoning"
        )
    return schema


def _flood_schema(settings: Settings) -> GisFloodSchema:
    """The active site's floodzone GIS schema, or a clean error if it has none."""
    schema = active_profile(settings).gis_flood
    if schema is None:
        raise LimaGisError(
            f"site {settings.site!r} has no floodzone GIS schema (gis_flood) — cannot query floodzones"
        )
    return schema


class ZoningRecord(BaseModel):
    """One zoning polygon's attributes, as returned by the jurisdiction's GIS."""

    model_config = ConfigDict(extra="forbid")

    object_id: int | None
    parcel_no: str | None  # joins to the county CAMA layer
    zoning: str | None  # the district label, verbatim

    @classmethod
    def from_attrs(cls, a: dict[str, Any], schema: GisZoningSchema | None = None) -> ZoningRecord:
        s = schema or LIMA_ZONING_SCHEMA
        return cls(
            object_id=_i(a.get(s.object_id_field)),
            parcel_no=_s(a.get(s.parcel_field)) if s.parcel_field else None,
            zoning=_s(a.get(s.zoning_field)),
        )


class ZoningDistrict(BaseModel):
    """One zoning district and how many polygons carry it (the catalog row)."""

    model_config = ConfigDict(extra="forbid")

    code: str  # the district label, verbatim
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


def _bfe(value: Any, sentinel: float) -> float | None:
    """A base-flood elevation, or None for missing / the schema's 'no BFE' sentinel."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f == sentinel else f


def _query(
    params: dict[str, Any],
    *,
    settings: Settings,
    url: str,
    connector: str,
    method: str = "POST",
) -> dict[str, Any]:
    """Run (or replay) one ArcGIS ``/query`` against ``url``; return the parsed JSON.

    ``connector`` namespaces the cache/fixtures so different layers of the same service
    (zoning vs floodzone) never collide on identical params. ``method`` is the schema's HTTP
    verb (Lima POSTs — spatial queries carry a geometry too large for a GET URL).
    """
    query = {"f": "json", "returnGeometry": "false", **params}

    def fetch() -> Any:
        log.info(f"{connector}.fetch", where=params.get("where"), offset=params.get("resultOffset"))
        if method == "GET":
            resp = httpx.get(f"{url}/query", params=query, timeout=settings.hydro_request_timeout_s)
        else:
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
    schema = _zoning_schema(settings)
    records: list[ZoningRecord] = []
    offset = 0
    while True:
        page = _query(
            {
                "where": where,
                "outFields": ",".join(schema.out_fields),
                "resultOffset": offset,
                "resultRecordCount": schema.page_size,
                "orderByFields": schema.object_id_field,
            },
            settings=settings,
            url=settings.zoning_url,
            connector=schema.connector,
            method=schema.http_method,
        )
        features = page.get("features") or []
        records.extend(ZoningRecord.from_attrs(f.get("attributes", {}), schema) for f in features)
        if max_records is not None and len(records) >= max_records:
            return records[:max_records]
        if not page.get("exceededTransferLimit") or not features:
            return records
        offset += len(features)


def zoning_for_parcel(parcel_no: str, *, settings: Settings | None = None) -> ZoningRecord | None:
    """The zoning district for one parcel; ``None`` if outside the layer's jurisdiction.

    Refuses when the active site's zoning layer is polygon-only (no parcel-id field) — there
    the district catalog (:func:`zoning_districts`) is the supported read.
    """
    settings = settings or get_settings()
    schema = _zoning_schema(settings)
    if schema.parcel_field is None:
        raise LimaGisError(
            f"site {settings.site!r} zoning layer has no parcel-id field (polygon-only) — "
            "use zoning_districts() / watermark zoning --districts"
        )
    normalized = normalize_parcel_id(parcel_no, rule=schema.id_normalize)
    matches = query_zoning(f"{schema.parcel_field}='{normalized}'", settings=settings)
    return matches[0] if matches else None


def zoning_districts(*, settings: Settings | None = None) -> list[ZoningDistrict]:
    """The zoning-district catalog: each district code and its polygon count.

    Uses a server-side ``groupBy`` statistics query so the whole catalog comes back in one
    request rather than paging every polygon.
    """
    settings = settings or get_settings()
    schema = _zoning_schema(settings)
    stats = [
        {
            "statisticType": "count",
            "onStatisticField": schema.object_id_field,
            "outStatisticFieldName": "n",
        }
    ]
    page = _query(
        {
            "where": "1=1",
            "outFields": schema.zoning_field,
            "groupByFieldsForStatistics": schema.zoning_field,
            "outStatistics": json.dumps(stats),
        },
        settings=settings,
        url=settings.zoning_url,
        connector=schema.connector,
        method=schema.http_method,
    )
    districts = [
        ZoningDistrict(
            code=str(a.get(schema.zoning_field) or "").strip(), polygon_count=int(a.get("n") or 0)
        )
        for a in (f.get("attributes", {}) for f in page.get("features") or [])
        if _s(a.get(schema.zoning_field))
    ]
    return sorted(districts, key=lambda d: (-d.polygon_count, d.code))


def write_zoning_districts(
    districts: list[ZoningDistrict], out_dir: Path, *, settings: Settings | None = None
) -> Path:
    """Write the zoning-district catalog to one YAML file with provenance ``meta``."""
    settings = settings or get_settings()
    meta = _zoning_schema(settings).meta
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "zoning-districts.yaml"
    doc = {
        "meta": {
            "subject": meta.subject,
            "source": meta.source,
            "source_url": meta.source_url,
            "district_count": len(districts),
            "polygon_total": sum(d.polygon_count for d in districts),
            "caveats": list(meta.caveats),
        },
        "districts": [d.model_dump() for d in districts],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


class CitedParcelZoning(BaseModel):
    """One cited corpus parcel and its jurisdiction zoning (or its absence)."""

    model_config = ConfigDict(extra="forbid")

    parcel_no: str  # as cited in the corpus
    normalized: str  # normalized id used for the join
    in_city: bool  # within the jurisdiction's zoning layer
    zoning: str | None = None  # the district label when in-jurisdiction, else None


def scan_cited_zoning(
    parcel_ids: list[str], *, settings: Settings | None = None
) -> list[CitedParcelZoning]:
    """Look up the jurisdiction zoning for each cited corpus parcel.

    The Lima zoning layer is **city limits only**: a parcel in unincorporated Allen County
    (the American Township corridor) resolves to ``in_city=False`` — a real, recorded null,
    not a gap.
    """
    settings = settings or get_settings()
    schema = _zoning_schema(settings)
    out: list[CitedParcelZoning] = []
    for pid in parcel_ids:
        rec = zoning_for_parcel(pid, settings=settings)
        out.append(
            CitedParcelZoning(
                parcel_no=pid,
                normalized=normalize_parcel_id(pid, rule=schema.id_normalize),
                in_city=rec is not None,
                zoning=rec.zoning if rec is not None else None,
            )
        )
    return out


def write_cited_zoning(
    scan: list[CitedParcelZoning], out_dir: Path, *, settings: Settings | None = None
) -> Path:
    """Persist the cited-parcel zoning scan (the corridor-jurisdiction finding)."""
    settings = settings or get_settings()
    cited = _zoning_schema(settings).cited_meta
    if cited is None:
        raise LimaGisError(
            f"site {settings.site!r} zoning layer has no cited-zoning scan configured "
            "(gis_zoning.cited_meta — needs a parcel join)"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "parcels.zoning.yaml"
    in_city = [s for s in scan if s.in_city]
    finding = f"{len(in_city)} of {len(scan)} cited corpus parcels {cited.finding_lead}" + (
        cited.in_city_finding if in_city else cited.out_of_city_finding
    )
    doc = {
        "meta": {
            "subject": cited.subject,
            "source": cited.source,
            "n_cited": len(scan),
            "n_in_city": len(in_city),
            "finding": finding,
            "caveats": list(cited.caveats),
        },
        "parcels": [s.model_dump() for s in scan],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


# --- FEMA Floodzone (DFIRM / NFHL) layer -----------------------------------


class FloodZone(BaseModel):
    """One FEMA flood-hazard polygon's attributes (per the active flood schema)."""

    model_config = ConfigDict(extra="forbid")

    object_id: int | None
    fld_zone: str | None  # FEMA zone code: A / AE / AO / X / ...
    zone_subtype: str | None  # e.g. FLOODWAY; None when blank
    sfha: bool  # Special Flood Hazard Area
    static_bfe: float | None  # base flood elevation, or None for the sentinel
    dfirm_id: str | None
    source_cit: str | None  # the FIRM / FIS citation

    @classmethod
    def from_attrs(cls, a: dict[str, Any], schema: GisFloodSchema | None = None) -> FloodZone:
        s = schema or LIMA_FLOOD_SCHEMA
        flag = str(a.get(s.sfha_field) or "").strip().upper()
        return cls(
            object_id=_i(a.get(s.object_id_field)),
            fld_zone=_s(a.get(s.fld_zone_field)),
            zone_subtype=_s(a.get(s.zone_subtype_field)),
            sfha=flag == s.sfha_true_value.strip().upper(),
            static_bfe=_bfe(a.get(s.static_bfe_field), s.bfe_sentinel),
            dfirm_id=_s(a.get(s.dfirm_id_field)),
            source_cit=_s(a.get(s.source_cit_field)),
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

    Non-areal features (a stray Point/LineString) are skipped — only rings that can bound an
    area contribute to the spatial query geometry.
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


def query_floodzones(
    where: str = "1=1",
    *,
    rings: list[list[list[float]]] | None = None,
    point: tuple[float, float] | None = None,
    distance_m: float | None = None,
    settings: Settings | None = None,
) -> list[FloodZone]:
    """Flood-hazard polygons matching ``where`` and (optionally) a WGS84 geometry.

    Pass ``rings`` (polygon, lon/lat) or ``point`` (``(lon, lat)``); the service reprojects
    from ``inSR=4326``. A truthy ``distance_m`` buffers the geometry so "within N metres" can
    be answered (omit/0 = exact intersect — ArcGIS rejects a literal ``distance=0``). Paged to
    completion.
    """
    settings = settings or get_settings()
    schema = _flood_schema(settings)
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
        page = _query(
            {
                "where": where,
                "outFields": ",".join(schema.out_fields),
                "resultOffset": offset,
                "resultRecordCount": schema.page_size,
                "orderByFields": schema.object_id_field,
                **spatial,
            },
            settings=settings,
            url=settings.floodzone_url,
            connector=schema.connector,
            method=schema.http_method,
        )
        features = page.get("features") or []
        out.extend(FloodZone.from_attrs(f.get("attributes", {}), schema) for f in features)
        if not page.get("exceededTransferLimit") or not features:
            return out
        offset += len(features)


def floodzone_catalog(*, settings: Settings | None = None) -> list[FloodZoneClass]:
    """The flood-zone catalog: each (zone, subtype, SFHA) and its polygon count."""
    settings = settings or get_settings()
    schema = _flood_schema(settings)
    group_fields = ",".join((schema.fld_zone_field, schema.zone_subtype_field, schema.sfha_field))
    stats = [
        {
            "statisticType": "count",
            "onStatisticField": schema.object_id_field,
            "outStatisticFieldName": "n",
        }
    ]
    page = _query(
        {
            "where": "1=1",
            "outFields": group_fields,
            "groupByFieldsForStatistics": group_fields,
            "outStatistics": json.dumps(stats),
        },
        settings=settings,
        url=settings.floodzone_url,
        connector=schema.connector,
        method=schema.http_method,
    )
    classes = [
        FloodZoneClass(
            fld_zone=str(a.get(schema.fld_zone_field) or "").strip(),
            zone_subtype=_s(a.get(schema.zone_subtype_field)),
            sfha=str(a.get(schema.sfha_field) or "").strip().upper()
            == schema.sfha_true_value.strip().upper(),
            polygon_count=int(a.get("n") or 0),
        )
        for a in (f.get("attributes", {}) for f in page.get("features") or [])
        if _s(a.get(schema.fld_zone_field))
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


def write_floodzone_catalog(
    classes: list[FloodZoneClass], out_dir: Path, *, settings: Settings | None = None
) -> Path:
    """Write the flood-zone catalog to one YAML file with provenance ``meta``."""
    settings = settings or get_settings()
    meta = _flood_schema(settings).meta
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "floodzones.yaml"
    doc = {
        "meta": {
            "subject": meta.subject,
            "source": meta.source,
            "source_url": meta.source_url,
            "class_count": len(classes),
            "polygon_total": sum(c.polygon_count for c in classes),
            "caveats": list(meta.caveats),
        },
        "classes": [c.model_dump() for c in classes],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
