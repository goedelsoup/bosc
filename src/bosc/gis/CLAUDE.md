# CLAUDE.md — `bosc.gis`

Geospatial subsystem: tracking sites + satellite imagery. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md). Design + roadmap:
[`docs/imagery-subsystem.md`](../../../docs/imagery-subsystem.md).

- **Tracking sites are assembled, never authored.** A `TrackingSite` is a group of
  features already committed to `data/site/gis-findings.geojson`, grouped by the
  GeoJSON `layer` (config: `settings.gis_tracking_layers`, default `["campus"]`).
  Don't draw new AOI geometry — that would be fabricated evidence. To add a site,
  add its geometry to the findings (e.g. a warehouse parcel via `bosc parcels`,
  the reservoir footprint) and tag the layer.
- **Imagery is `search → materialize`, and only *search* exists today.**
  `imagery.search_scenes` is a pure connector: a single `httpx` POST to the
  Planetary Computer STAC `/search`, wrapped in the shared
  `bosc.hydrology.connectors._cache.cached_get` (the same cross-subsystem reuse
  `civic`/`economics` do) against the GIS cache root. STAC fields are read **by
  name**, never index; an offline miss raises `HydroOfflineError` naming the key.
  The raster-clip / GeoTIFF layer (rasterio + asset signing) is a later increment —
  **do not add `rasterio`/`pystac` for search.**
- **A new collection/AOI needs a committed fixture** under
  `tests/fixtures/gis/<connector>/<key>.json` (connector is `pc_stac_search`).
  Record the live response once; don't hand-edit recorded JSON.
- Sync throughout (`httpx`), matching the rest of the pipeline.
