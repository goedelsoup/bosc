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
from collections import Counter
from pathlib import Path

_LAYER_LABELS = {
    "campus": "Campus footprint (recorded Bistrozzi parcels)",
    "jsmc": "JSMC / Lima Army Tank Plant (United States-owned)",
    "wwtp": "County WWTP discharge points (NPDES)",
    "floodway": "FEMA regulatory floodway (Zone AE)",
    "floodplain": "FEMA 1%-annual-chance floodplain (Zone A/AE)",
}
_LAYER_COLORS = {
    "campus": "#3f51b5",
    "jsmc": "#6d4c41",
    "wwtp": "#00897b",
    "floodway": "#d32f2f",
    "floodplain": "#1976d2",
}

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
    osm.addTo(map);
    L.control.layers({ "Street (OSM)": osm, "Aerial (Esri)": aerial }).addTo(map);
    fetch("assets/gis-findings.geojson").then(function (r) { return r.json(); }).then(function (fc) {
      var layer = L.geoJSON(fc, {
        style: function (f) { return STYLES[f.properties.layer] || { color: "#555", weight: 1 }; },
        pointToLayer: function (f, latlng) {
          return L.circleMarker(latlng, { radius: 7, color: "#00695c", weight: 2, fillColor: "#26a69a", fillOpacity: 0.9 });
        },
        onEachFeature: function (f, l) { if (f.properties && f.properties.label) l.bindPopup(f.properties.label); }
      }).addTo(map);
      try { map.fitBounds(layer.getBounds(), { padding: [20, 20] }); }
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
        "floodway": {"color": "#d32f2f", "weight": 1, "fillOpacity": 0.40},
        "floodplain": {"color": "#1976d2", "weight": 1, "fillOpacity": 0.15},
    }
    return json.dumps(styles)


def render_gis_map(geojson_path: Path) -> str:
    """Render the GIS map page markdown from the committed findings GeoJSON."""
    fc = json.loads(geojson_path.read_text(encoding="utf-8"))
    counts = Counter(f.get("properties", {}).get("layer") for f in fc.get("features", []))
    sources = fc.get("meta", {}).get("sources", [])

    lines = [
        "# GIS findings — one map",
        "",
        "Three corridor findings on a single map: the recorded **data-center campus** "
        "footprint, the federally-held **JSMC / Lima Army Tank Plant** land (Allen "
        "County's documented defense-industry footprint), and the **FEMA floodplain / "
        "floodway**. Pan/zoom and click a shape for its label.",
        "",
        '!!! note "What the map shows"',
        "    Geometry is verbatim from the county/FEMA GIS (WGS84). The campus parcels "
        "sit *just outside* the Special Flood Hazard Area, with the regulatory floodway "
        "reaching within ~50 m — see the [hydrology dossier](docs/HYDROLOGY.md) and "
        "[defense contractors](defense-contractors.md).",
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
        _MAP_HTML.replace("__STYLES__", _style_js()).strip(),
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
