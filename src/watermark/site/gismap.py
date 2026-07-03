"""Typed GIS feeds for the frontend — lift the committed findings GeoJSON into feeds.

:func:`export_geo` splits ``data/site/gis-findings.geojson`` into typed per-layer
:class:`GeoFeatureCollection` feeds (campus, jsmc, femaflood, corridor, wwtp, rsei) for
the frontend's DeckGL map; :func:`export_watershed_geo` and :func:`export_imagery_geo`
add the WBD watershed and imagery-AOI feeds. :func:`merge_rsei_layer` /
:func:`merge_corridor_layer` fold the RSEI facility points and the frozen-Periplus
corridor geometry into the findings collection before export. Geometry is carried WGS84
verbatim (display-only, no reprojection).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watermark.config import Settings, get_settings
from watermark.site.feeds import GeoFeature, GeoFeatureCollection, GeoProperties
from watermark.sites import active_profile, site_scoped_path

if TYPE_CHECKING:
    from watermark.hydrology.toxics import ToxicDischargeInventory
    from watermark.rsei import RseiInventory

_RSEI_LAYER = "rsei"
_CORRIDOR_LAYERS = ("corridor", "roadwork")
_LAYER_COLORS = {
    "campus": "#3f51b5",
    "jsmc": "#6d4c41",
    "wwtp": "#00897b",
    "corridor": "#f9a825",
    "roadwork": "#e64a19",
    "floodway": "#d32f2f",
    "floodplain": "#1976d2",
    "rsei": "#8e24aa",
}
# Feeds assembled outside gis-findings (issue #61): the WBD watershed boundaries and
# the imagery tracking-AOI footprints. Their colors live here so a feed and the legend
# stay in sync, like the gis-findings layers above.
_WATERSHED_COLOR = "#0097a7"  # cyan — the watershed boundary fill/outline
_IMAGERY_AOI_COLOR = "#37474f"  # blue-grey — a neutral footprint frame for the AOI


def _rsei_radius(score: float) -> int:
    """Circle radius (px) graduated by RSEI Score on a log scale; unscored -> small."""
    if score <= 0:
        return 4
    return max(5, min(22, round(3.0 + 2.4 * math.log10(score))))


def merge_rsei_layer(
    fc: dict[str, Any],
    inv: RseiInventory,
    screen: ToxicDischargeInventory | None = None,
    *,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], int]:
    """Idempotently add the RSEI facility point layer to a findings FeatureCollection.

    Built from the committed RSEI inventory (no live GIS): existing ``rsei`` features
    are dropped first, then one Point per facility with coordinates, sized by Score.
    When ``screen`` (the toxic-discharge screen) is supplied, facilities that release
    to a near-undiluted reach are tagged ``water_flag`` (critical/elevated) so the map
    rings them. Returns the updated collection and the number of points added.
    """
    county = active_profile(settings or get_settings()).county_name
    by_id = {s.rsei_facility_id: s for s in (screen.screens if screen else [])}
    feats = [
        f for f in fc.get("features", []) if f.get("properties", {}).get("layer") != _RSEI_LAYER
    ]
    added = 0
    for fac in inv.facilities:
        if fac.latitude is None or fac.longitude is None:
            continue
        scored = fac.score > 0
        cpct = (
            f"{100 * fac.cancer_score / fac.score:.0f}% cancer"
            if scored
            else "reported pounds, no modeled Score"
        )
        top = fac.top_chemicals[0].chemical if fac.top_chemicals else None
        yrs = f"{fac.first_year}-{fac.last_year}" if fac.first_year else ""
        label = (
            f"<b>{fac.name}</b><br>RSEI Score {fac.score:,.0f} ({cpct})"
            + (f"<br>top: {top}" if top else "")
            + (f"<br>{yrs}" if yrs else "")
        )
        props: dict[str, Any] = {
            "layer": _RSEI_LAYER,
            "label": label,
            "score": round(fac.score),
            "radius": _rsei_radius(fac.score),
            "scored": scored,
        }
        sc = by_id.get(fac.facility_id)
        if sc and sc.flag in ("critical", "elevated"):
            props["water_flag"] = sc.flag
            conc = (
                f", ~{sc.screening_concentration.value:g} mg/L"
                if sc.screening_concentration
                else ""
            )
            cite = "ECHO-cited" if sc.receiving_water_source == "connector" else "corridor-inferred"
            props["label"] = label + (
                f"<br><b>toxic water discharger → {sc.receiving_water}</b> "
                f"({sc.flag}{conc} at the {sc.low_flow_7q10.value:g} cfs 7Q10; {cite})"
                if sc.low_flow_7q10
                else ""
            )
        feats.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(fac.longitude, 6), round(fac.latitude, 6)],
                },
                "properties": props,
            }
        )
        added += 1
    fc["features"] = feats
    meta = fc.setdefault("meta", {})
    sources = meta.setdefault("sources", [])
    note = f"EPA RSEI Public Data Set — {county} facility points, sized by RSEI Score"
    if note not in sources:
        sources.append(note)
    return fc, added


def merge_corridor_layer(
    fc: dict[str, Any], *, settings: Settings | None = None
) -> tuple[dict[str, Any], int]:
    """Idempotently add the corridor study-area + roadwork layers to the findings.

    Draws the frozen Periplus corridor geography verbatim (WGS84, no reprojection — the
    map is display-only): the ``corridor_of_interest`` study-area polygon (layer
    ``corridor``) and the road-role centerline route the roundabouts OPC prices (layer
    ``roadwork``). Existing corridor/roadwork features are dropped first so re-running is
    a no-op. The numeric facilities↔corridor join lives in :func:`watermark.gis.corridor`;
    this is its visual frame. Returns the updated collection and the feature count added.
    """
    settings = settings or get_settings()
    prof = active_profile(settings)
    feats = [
        f
        for f in fc.get("features", [])
        if f.get("properties", {}).get("layer") not in _CORRIDOR_LAYERS
    ]
    if prof.corridor_geo_relpath is None:
        # No corridor geometry registered for this site — drop any stale features and stop.
        fc["features"] = feats
        return fc, 0
    ref = settings.data_dir / prof.corridor_geo_relpath
    added = 0

    study = ref / "corridor.geojson"
    if study.is_file():
        for f in json.loads(study.read_text(encoding="utf-8")).get("features", []):
            if not f.get("geometry"):
                continue
            feats.append(
                {
                    "type": "Feature",
                    "geometry": f["geometry"],
                    "properties": {
                        "layer": "corridor",
                        "label": f"{prof.corridor_name} — study area",
                    },
                }
            )
            added += 1

    centerline = ref / "corridor-centerline.geojson"
    if centerline.is_file():
        for f in json.loads(centerline.read_text(encoding="utf-8")).get("features", []):
            props = f.get("properties") or {}
            geom = f.get("geometry") or {}
            if props.get("role") != "road" or geom.get("type") not in (
                "LineString",
                "MultiLineString",
            ):
                continue
            feats.append(
                {
                    "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "layer": "roadwork",
                        "label": str(props.get("Name") or "Corridor road route"),
                    },
                }
            )
            added += 1

    fc["features"] = feats
    sources = fc.setdefault("meta", {}).setdefault("sources", [])
    note = (
        f"{prof.corridor_name} — frozen corridor study area + roadwork centerline "
        f"({prof.corridor_geo_relpath}/) — external corroboration"
    )
    if note not in sources:
        sources.append(note)
    return fc, added


# Esri **Wayback** dated World-Imagery releases (releaseNum from the Wayback config) —
# a curated historical ladder carried in the imagery feed's meta. View-only supplement:
# the browser loads Esri's tiles directly (no redistribution), so a viewer can flip the
# AOI between dates and see the data-center land before / during / after development.
_WAYBACK: list[tuple[str, int]] = [
    ("2014-12", 5844),
    ("2018-12", 23448),
    ("2020-12", 29260),
    ("2021-12", 26120),
    ("2022-12", 45134),
    ("2023-12", 56102),
    ("2024-12", 16453),
]
_WAYBACK_BASE_URL = (
    "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/"
    "WMTS/1.0.0/default028mm/MapServer/tile"
)


# Which findings layer rolls up into which typed GeoJSON feed (issue #61). FEMA's two
# zones and the corridor study-area + roadwork are paired into one feed each, mirroring
# how the map legend groups them.
_LAYER_TO_FEED: dict[str, str] = {
    "campus": "campus",
    "jsmc": "jsmc",
    "floodway": "femaflood",
    "floodplain": "femaflood",
    "corridor": "corridor",
    "roadwork": "corridor",
    "wwtp": "wwtp",
    "rsei": "rsei",
}


def _geometry_role(geometry: dict[str, Any]) -> str:
    """The display role of a geometry — area | line | point — for the feature properties."""
    gtype = str(geometry.get("type", ""))
    if gtype in ("Polygon", "MultiPolygon"):
        return "area"
    if gtype in ("LineString", "MultiLineString"):
        return "line"
    return "point"


def export_geo(geojson_path: Path) -> list[GeoFeatureCollection]:
    """Split the committed findings GeoJSON into typed per-layer feeds for DeckGL (#61).

    Lifts geometry out of the findings collection into clean :class:`GeoFeatureCollection`
    feeds — one per logical layer (campus, jsmc, femaflood, corridor, wwtp, rsei). Geometry
    is carried **WGS84 verbatim** (display-only, no reprojection); each feature keeps its
    source ``label`` and popup fields and gains ``color`` + ``role`` layer metadata so the
    frontend styles a feed without re-deriving anything. Returns feeds in stable order.
    """
    fc = json.loads(geojson_path.read_text(encoding="utf-8"))
    crs = fc.get("meta", {}).get("crs", "WGS84 (EPSG:4326)")
    grouped: dict[str, list[GeoFeature]] = {}
    for feat in fc.get("features", []):
        props = dict(feat.get("properties") or {})
        layer = str(props.get("layer", ""))
        feed = _LAYER_TO_FEED.get(layer)
        geometry = feat.get("geometry")
        if feed is None or not geometry:
            continue
        props.setdefault("color", _LAYER_COLORS.get(layer))
        props["role"] = _geometry_role(geometry)
        grouped.setdefault(feed, []).append(
            GeoFeature(geometry=geometry, properties=GeoProperties.model_validate(props))
        )
    return [
        GeoFeatureCollection(
            feed=feed,
            meta={"crs": crs, "layers": sorted({f.properties.layer for f in feats})},
            features=feats,
        )
        for feed, feats in sorted(grouped.items())
    ]


def campus_from_parcels(settings: Settings | None = None) -> GeoFeatureCollection | None:
    """The ``campus`` geo feed built from the **active site's** parcel assemblage (#762).

    The frozen ``gis-findings.geojson`` is a Lima artifact, so a non-Lima site's campus must come
    from its own committed parcels (``active_profile().parcels_relpath`` — e.g. Fort Wayne's
    Hatchworks/Project Zodiac assemblage), not Lima's Bistrozzi parcels. Reads that GeoJSON, maps
    each parcel polygon to a ``campus``-layer feature (WGS84 verbatim, display-only), and carries
    the parcel's popup fields through (``extra="allow"``). Returns ``None`` if the site has no
    committed parcels file. Tolerant of the ``bosc:provenance`` foreign member (non-Feature entries).
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).parcels_relpath
    if not path.is_file():
        return None
    fc = json.loads(path.read_text(encoding="utf-8"))
    features: list[GeoFeature] = []
    for feat in fc.get("features", []):
        geometry = feat.get("geometry")
        if not geometry:
            continue
        src = dict(feat.get("properties") or {})
        # Map to the campus popup shape; pass source fields through (owner/situs/transfer_date, or
        # Lima's grantee/acreage). `grantee` is the owner of record; `label` is a human handle.
        props: dict[str, Any] = {
            "layer": "campus",
            "label": src.get("situs_address") or src.get("label") or src.get("parcel_id"),
            "color": _LAYER_COLORS["campus"],
            "role": _geometry_role(geometry),
            "grantee": src.get("grantee") or src.get("owner"),
            **{k: v for k, v in src.items() if k not in {"label", "grantee", "color", "role"}},
        }
        features.append(
            GeoFeature(geometry=geometry, properties=GeoProperties.model_validate(props))
        )
    if not features:
        return None
    return GeoFeatureCollection(
        feed="campus",
        meta={"crs": "WGS84 (EPSG:4326)", "layers": ["campus"]},
        features=features,
    )


def export_watershed_geo(settings: Settings | None = None) -> GeoFeatureCollection | None:
    """The ``watershed`` feed — USGS WBD HU boundaries framing the campus AOI (#61).

    Reads the committed reference boundaries (``data/reference/hydrology/wbd/*.geojson``,
    regenerable via ``watermark wbd``) and assembles one typed feed. Geometry is WGS84
    verbatim; each feature carries its HU attributes (``huc``/``level``/``name``/…) plus
    the ``layer``/``color``/``role`` styling metadata. Features are ordered coarsest →
    finest so the finer subwatershed draws on top. ``None`` when no boundaries exist.
    """
    settings = settings or get_settings()
    # Per-site (#762): Lima reads the flat `reference/hydrology/wbd/`; a sibling site reads its own
    # `reference/<slug>/hydrology/wbd/` (absent today => no watershed feed, not Lima's Ottawa HUCs).
    wbd_dir = (
        site_scoped_path(settings.reference_dir, settings.site, is_dir=True) / "hydrology" / "wbd"
    )
    if not wbd_dir.is_dir():
        return None
    ranked: list[tuple[int, GeoFeature]] = []
    for path in sorted(wbd_dir.glob("*.geojson")):
        fc = json.loads(path.read_text(encoding="utf-8"))
        for feat in fc.get("features", []):
            geometry = feat.get("geometry")
            if not geometry:
                continue
            src = dict(feat.get("properties") or {})
            level = int(src.get("level") or 0)
            name, huc = str(src.get("name") or ""), str(src.get("huc") or "")
            hu_label = str(src.get("hu_label") or "")
            props: dict[str, Any] = {
                "layer": "watershed",
                "label": f"{name} — {hu_label} (HU{level} {huc})",
                "color": _WATERSHED_COLOR,
                "role": "area",
                "huc": huc,
                "level": level,
                "name": name,
                "hu_label": hu_label,
                "area_sqkm": src.get("area_sqkm"),
                "to_huc": src.get("to_huc"),
            }
            ranked.append(
                (
                    level,
                    GeoFeature(geometry=geometry, properties=GeoProperties.model_validate(props)),
                )
            )
    if not ranked:
        return None
    ranked.sort(key=lambda r: r[0])  # coarsest (smaller HU level) first → finer on top
    return GeoFeatureCollection(
        feed="watershed",
        meta={
            "crs": "WGS84 (EPSG:4326)",
            "subject": "USGS WBD watershed boundaries framing the data-center campus AOI",
            "source": "USGS National Map Watershed Boundary Dataset (WBD)",
            "levels": sorted({lvl for lvl, _ in ranked}),
        },
        features=[f for _, f in ranked],
    )


def export_imagery_geo(settings: Settings | None = None) -> GeoFeatureCollection | None:
    """The ``imagery`` feed — tracking-AOI footprints + the dated Wayback ladder (#61).

    One footprint polygon per imagery tracking site (a watched POI's bbox; see
    :func:`watermark.gis.sites.load_tracking_sites`), plus the dated Esri **Wayback** aerial
    releases in ``meta`` so the before/during/after slider has its layers without new
    binary data (the tiles load view-only from Esri). ``None`` when no AOI is tracked.
    """
    settings = settings or get_settings()
    from watermark.gis.sites import load_tracking_sites

    sites = load_tracking_sites(settings=settings)
    if not sites:
        return None
    features: list[GeoFeature] = []
    for site in sites:
        minx, miny, maxx, maxy = site.bbox
        ring = [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
        props: dict[str, Any] = {
            "layer": "imagery",
            "label": f"{site.name} — imagery AOI",
            "color": _IMAGERY_AOI_COLOR,
            "role": "area",
            "site": site.id,
            "bbox": [minx, miny, maxx, maxy],
            "parcels": len(site.parcels),
        }
        features.append(
            GeoFeature(
                geometry={"type": "Polygon", "coordinates": [ring]},
                properties=GeoProperties.model_validate(props),
            )
        )
    return GeoFeatureCollection(
        feed="imagery",
        meta={
            "crs": "WGS84 (EPSG:4326)",
            "subject": "Imagery tracking AOIs + the dated Esri Wayback aerial ladder",
            "wayback": {
                "tile_url_template": f"{_WAYBACK_BASE_URL}/{{release}}/{{z}}/{{y}}/{{x}}",
                "attribution": "Imagery © Esri — World Imagery Wayback",
                "note": (
                    "View-only Esri World Imagery Wayback releases (tiles load from Esri; "
                    "not redistributed). The publishable analysis-grade series is the "
                    "free/open Sentinel-2 / NAIP pulled by `watermark imagery`."
                ),
                "releases": [{"date": label, "release": rel} for label, rel in _WAYBACK],
            },
        },
        features=features,
    )
