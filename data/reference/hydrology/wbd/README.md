---
scope: site:lima
scope_note: >-
  The committed HUC boundaries frame the reference build's own campus AOI, so the catalog entry
  belongs to that site alone and no peer renders this page. The WBD itself is national — a peer
  pulls the HUCs framing its own AOI.
---

# `wbd/` — USGS Watershed Boundary Dataset (HUC boundaries)

Authoritative Hydrologic Unit (HU) polygon boundaries framing the data-center
campus AOI, pulled from the **USGS National Map Watershed Boundary Dataset (WBD)**
ArcGIS REST service. These are the source geometry the bundle's `watershed`
GeoJSON feed (issue #61) is assembled from, for the watershed map (#72).

## Source

- **USGS National Map WBD** — `https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer`
  (the seamless national WBD; HU-level sublayers keyed by digit count: layer 6 =
  12-digit Subwatershed, layer 5 = 10-digit Watershed, layer 4 = 8-digit Subbasin).
- Pulled by the `watermark.hydrology.connectors.wbd` connector; **regenerable** with:

  ```sh
  watermark wbd --write              # the campus AOI's HU12 + HU10, default
  watermark wbd --levels 12,10,8 --write   # add the coarser HU8 Subbasin too
  watermark wbd --point -84.1234,40.7969 --write   # any WGS84 point
  ```

  The AOI defaults to the `data-center-campus` tracking-site POI's bbox centroid
  (`data/entities/poi/data-center-campus.md`); the connector selects the HU **containing**
  that point at each level. Raw responses cache under the git-ignored
  `data/cache/hydrology/wbd/`; the committed fixture for the offline test lives at
  `tests/fixtures/hydrology/wbd/`.

## Files

| File | HUC | HU level | km² | Notes |
|---|---|---|---|---|
| `041000070404-pike-run.geojson` | `041000070404` | HU12 Subwatershed | 34.3 | the campus's immediate subwatershed; drains to `041000070406` |
| `0410000704-middle-ottawa-river.geojson` | `0410000704` | HU10 Watershed | 272.5 | the Ottawa River watershed through Lima |

Each file is a one-feature GeoJSON `FeatureCollection`; the HU attributes (`huc`,
`name`, `area_sqkm`, `to_huc`, …) ride on the feature `properties`, with full
provenance in the top-level `meta`.

## Scope / gaps

- **The campus sits in the Pike Run subwatershed (HU12) of the Middle Ottawa River
  watershed (HU10).** The hydrologic lineage continues outward —
  Ottawa River → **Auglaize** subbasin (HU8 `04100007`) → **Maumee** subregion
  (HU4 `0410`) → Lake Erie. The coarser Subbasin/basin polygons are **not committed
  here**: a ~1 MB Subbasin outline adds little to a campus-scale map. Pull them on
  demand with `--levels 12,10,8` (or query the WBD service directly) if needed.
- Geometry is **verbatim** from the WBD (WGS84 / EPSG:4326), display-only — never
  reprojected or simplified. The names ("Pike Run", "Middle Ottawa River") are the
  USGS WBD names; the project's informal "Lost Creek / Maumee watershed" framing maps
  to this real HU nesting.
