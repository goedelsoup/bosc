"""Render the GIS findings as one Leaflet map page (+ a no-JS summary fallback).

Draws three committed layers from ``data/site/gis-findings.geojson`` on one map:
the recorded campus footprint, the federally-held JSMC / Lima Army Tank Plant
land, and the nearby FEMA floodplain/floodway. The GeoJSON is copied into the
site as a static asset; the page fetches it client-side (Leaflet from a CDN). A
markdown summary table renders even if scripting is off, so the page is never
blank.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bosc.config import Settings, get_settings

if TYPE_CHECKING:
    from bosc.hydrology.toxics import ToxicDischargeInventory
    from bosc.rsei import RseiInventory

_RSEI_LAYER = "rsei"
_CORRIDOR_LAYERS = ("corridor", "roadwork")
_LAYER_LABELS = {
    "campus": "Campus footprint (recorded Bistrozzi parcels)",
    "jsmc": "JSMC / Lima Army Tank Plant (United States-owned)",
    "wwtp": "County WWTP discharge points (NPDES)",
    "corridor": "North Cole Street corridor — study area (Periplus)",
    "roadwork": "Corridor roadwork — road centerline (the roundabouts OPC corridor)",
    "floodway": "FEMA regulatory floodway (Zone AE)",
    "floodplain": "FEMA 1%-annual-chance floodplain (Zone A/AE)",
    "rsei": "RSEI toxic-release facilities — sized by Score (overlay, off by default)",
}
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


def _rsei_radius(score: float) -> int:
    """Circle radius (px) graduated by RSEI Score on a log scale; unscored -> small."""
    if score <= 0:
        return 4
    return max(5, min(22, round(3.0 + 2.4 * math.log10(score))))


def merge_rsei_layer(
    fc: dict[str, Any],
    inv: RseiInventory,
    screen: ToxicDischargeInventory | None = None,
) -> tuple[dict[str, Any], int]:
    """Idempotently add the RSEI facility point layer to a findings FeatureCollection.

    Built from the committed RSEI inventory (no live GIS): existing ``rsei`` features
    are dropped first, then one Point per facility with coordinates, sized by Score.
    When ``screen`` (the toxic-discharge screen) is supplied, facilities that release
    to a near-undiluted reach are tagged ``water_flag`` (critical/elevated) so the map
    rings them. Returns the updated collection and the number of points added.
    """
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
    note = "EPA RSEI Public Data Set — Allen County facility points, sized by RSEI Score"
    if note not in sources:
        sources.append(note)
    return fc, added


# Inlined so only this page pays for the Leaflet CDN load.
_MAP_HTML = """
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<div id="bosc-map" style="height:560px;border:1px solid #ccc;border-radius:4px;"></div>
<script>
(function () {
  var STYLES = __STYLES__;
  function init() {
    if (typeof L === "undefined") { return setTimeout(init, 200); }
    var el = document.getElementById("bosc-map");
    if (!el) { return setTimeout(init, 200); }
    var map = L.map(el);
    var osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; OpenStreetMap contributors"
    });
    var aerial = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Imagery &copy; Esri" }
    );
    __WAYBACK_VARS__
    osm.addTo(map);
    function popup(f, l) { if (f.properties && f.properties.label) l.bindPopup(f.properties.label); }
    fetch("assets/gis-findings.geojson").then(function (r) { return r.json(); }).then(function (fc) {
      var feats = (fc.features || []);
      var isRsei = function (f) { return (f.properties || {}).layer === "rsei"; };
      // Corridor findings (polygons + WWTP points) — the default view.
      var corridor = L.geoJSON({ type: "FeatureCollection", features: feats.filter(function (f) { return !isRsei(f); }) }, {
        style: function (f) { return STYLES[f.properties.layer] || { color: "#555", weight: 1 }; },
        pointToLayer: function (f, latlng) {
          return L.circleMarker(latlng, { radius: 7, color: "#00695c", weight: 2, fillColor: "#26a69a", fillOpacity: 0.9 });
        },
        onEachFeature: popup
      }).addTo(map);
      // RSEI toxic-release facilities — county-wide overlay, OFF by default (keeps the
      // corridor in frame); sized by Score, hollow when reported-but-unscored.
      var rsei = L.geoJSON({ type: "FeatureCollection", features: feats.filter(isRsei) }, {
        pointToLayer: function (f, latlng) {
          var p = f.properties || {};
          // Toxic water dischargers on a near-undiluted reach get a red/orange ring.
          var ring = p.water_flag === "critical" ? "#c62828"
                   : p.water_flag === "elevated" ? "#ef6c00" : "#6a1b9a";
          return L.circleMarker(latlng, {
            radius: p.radius || 5, color: ring, weight: p.water_flag ? 3 : 1,
            fillColor: "#8e24aa", fillOpacity: p.scored ? 0.55 : 0.12
          });
        },
        onEachFeature: popup
      });
      L.control.layers(
        { "Street (OSM)": osm, "Aerial (Esri, current)": aerial, __WAYBACK_BASE__ },
        { "RSEI toxic-release facilities": rsei }
      ).addTo(map);
      try { map.fitBounds(corridor.getBounds(), { padding: [20, 20] }); }
      catch (e) { map.setView([40.792, -84.122], 14); }
    });
  }
  init();
})();
</script>
"""


def _style_js() -> str:
    styles = {
        "campus": {"color": "#3f51b5", "weight": 2, "fillOpacity": 0.25},
        "jsmc": {"color": "#6d4c41", "weight": 2, "fillOpacity": 0.30},
        "corridor": {"color": "#f9a825", "weight": 1, "fillOpacity": 0.06, "dashArray": "6 4"},
        "roadwork": {"color": "#e64a19", "weight": 4, "opacity": 0.9},
        "floodway": {"color": "#d32f2f", "weight": 1, "fillOpacity": 0.40},
        "floodplain": {"color": "#1976d2", "weight": 1, "fillOpacity": 0.15},
    }
    return json.dumps(styles)


def merge_corridor_layer(
    fc: dict[str, Any], *, settings: Settings | None = None
) -> tuple[dict[str, Any], int]:
    """Idempotently add the corridor study-area + roadwork layers to the findings.

    Draws the frozen Periplus corridor geography verbatim (WGS84, no reprojection — the
    map is display-only): the ``corridor_of_interest`` study-area polygon (layer
    ``corridor``) and the road-role centerline route the roundabouts OPC prices (layer
    ``roadwork``). Existing corridor/roadwork features are dropped first so re-running is
    a no-op. The numeric facilities↔corridor join lives in :func:`bosc.gis.corridor`;
    this is its visual frame. Returns the updated collection and the feature count added.
    """
    settings = settings or get_settings()
    ref = settings.reference_dir / "periplus"
    feats = [
        f
        for f in fc.get("features", [])
        if f.get("properties", {}).get("layer") not in _CORRIDOR_LAYERS
    ]
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
                        "label": "North Cole Street corridor — Periplus study area",
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
        "Periplus frozen corridor study area + roadwork centerline "
        "(data/reference/periplus/) — external corroboration"
    )
    if note not in sources:
        sources.append(note)
    return fc, added


# Esri **Wayback** dated World-Imagery releases (releaseNum from the Wayback config) —
# a curated historical ladder. View-only supplement: the browser loads Esri's tiles
# directly (no redistribution), so a viewer can flip the AOI between dates and see the
# data-center land before / during / after development. (EarthExplorer historical
# aerials need an M2M login — a different access pattern — and are deferred.)
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


def _wayback_layers_js() -> str:
    """JS defining the dated Esri Wayback tile layers (view-only historical aerials)."""
    lines = [
        f"var wb_{rel} = L.tileLayer("
        f'"{_WAYBACK_BASE_URL}/{rel}/{{z}}/{{y}}/{{x}}", '
        f'{{maxZoom: 19, attribution: "Imagery &copy; Esri — Wayback {label}"}});'
        for label, rel in _WAYBACK
    ]
    return "\n    ".join(lines)


def _wayback_base_js() -> str:
    """The base-layer control entries for the dated aerials (newest first)."""
    return ", ".join(f'"Aerial {label}": wb_{rel}' for label, rel in reversed(_WAYBACK))


def render_gis_map(geojson_path: Path) -> str:
    """Render the GIS map page markdown from the committed findings GeoJSON."""
    fc = json.loads(geojson_path.read_text(encoding="utf-8"))
    counts = Counter(f.get("properties", {}).get("layer") for f in fc.get("features", []))
    sources = fc.get("meta", {}).get("sources", [])

    lines = [
        "# GIS findings — one map",
        "",
        "The corridor findings on a single map: the recorded **data-center campus** "
        "footprint, the federally-held **JSMC / Lima Army Tank Plant** land (Allen "
        "County's documented defense-industry footprint), the **FEMA floodplain / "
        "floodway**, and the frozen-Periplus **North Cole Street corridor** study area "
        "with its **roadwork** centerline (the roadway the roundabouts OPC prices). A "
        "toggleable **RSEI toxic-release** overlay adds the county's TRI facilities, "
        "sized by Risk-Screening Score. Pan/zoom and click a shape for its label. The "
        "numeric facilities↔corridor join (distance, station) is `bosc corridor`.",
        "",
        '!!! note "What the map shows"',
        "    Geometry is verbatim from the county/FEMA GIS (WGS84). The campus parcels "
        "sit *just outside* the Special Flood Hazard Area, with the regulatory floodway "
        "reaching within ~50 m — see the [hydrology dossier](docs/HYDROLOGY.md) and "
        "[defense contractors](defense-contractors.md). Switch on **RSEI toxic-release "
        "facilities** (layer control, top-right; off by default) for the county-wide "
        "[toxic-release context](rsei.md) — markers scale with Score, hollow where a "
        "facility reported pounds but no modeled Score.",
        "",
        '!!! tip "Dated aerials (before / during / after)"',
        "    The layer control (top-right) also carries **dated Esri *Wayback* aerials** "
        "(2014 → 2024) — flip between years over the campus to watch the land change "
        "through the data-center buildout. These are a *view-only* historical supplement "
        "(tiles load from Esri); the analysis-grade, publishable imagery is the "
        "free/open Sentinel-2 / NAIP / Landsat series pulled by `bosc imagery` (see the "
        "[imagery subsystem](docs/imagery-subsystem.md)).",
        "",
        "## Legend",
        "",
    ]
    for key, label in _LAYER_LABELS.items():
        n = counts.get(key, 0)
        if n:
            sw = f'<span style="display:inline-block;width:12px;height:12px;background:{_LAYER_COLORS[key]};border-radius:2px;"></span>'
            lines.append(f"- {sw} **{label}** — {n} feature(s)")
    lines += [
        "",
        _MAP_HTML.replace("__STYLES__", _style_js())
        .replace("__WAYBACK_VARS__", _wayback_layers_js())
        .replace("__WAYBACK_BASE__", _wayback_base_js())
        .strip(),
        "",
        "## Layers",
        "",
        "| Layer | Features | What |",
        "|---|---|---|",
    ]
    for key, label in _LAYER_LABELS.items():
        if counts.get(key):
            lines.append(f"| {key} | {counts[key]} | {label} |")
    lines += ["", "## Sources", ""]
    lines += [f"- {s}" for s in sources]
    lines.append("")
    return "\n".join(lines)
