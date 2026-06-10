# CLAUDE.md — `bosc.gis`

Geospatial subsystem: tracking sites + satellite imagery. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md). Design + roadmap:
[`docs/imagery-subsystem.md`](../../../docs/imagery-subsystem.md).

- **Tracking sites come from the POI store — `bosc.gis` is a consumer of `bosc.poi`.**
  `load_tracking_sites` reads `tracked_pois()` (POIs at `depth: watched` with
  `track.enabled` + a `location.bbox`) and projects each to a `TrackingSite` (id = the
  POI slug, `bbox` = the AOI). The `track` flag in `data/poi/<slug>.md` is the single
  source of truth — **not** a `gis-findings.geojson` layer (that grouping, and
  `gis_tracking_layers`, were retired). To add a tracking site, curate a POI and promote
  it to `watched` with a `bbox`; don't author geometry here.
- **Imagery is `search → materialize`; both layers exist.**
  - *Search* (`imagery.search_scenes`) is a pure connector: a single `httpx` POST to
    the Planetary Computer STAC `/search`, wrapped in the shared neutral
    `bosc.connectors.cached_get` (the same layer `civic`/`economics` use) against the
    GIS cache root. STAC fields are read **by name**, never index; an offline miss
    raises `ImageryOfflineError` (a `bosc.connectors.OfflineError`) naming the key.
    Search is **collection-agnostic** — `sentinel-2-l2a`, `naip`, `landsat-c2-l2` all
    go through the one path. NAIP carries no `eo:cloud_cover`, so don't pass
    `--max-cloud` for it.
  - *Materialize* (`raster.pull_capture`) signs the asset (`planetary_computer`, lazy
    import) and does a windowed `rasterio` read **clipped to the AOI in the scene's
    native CRS — no resampling**, writing a dated GeoTIFF + a `.yaml` provenance
    sidecar (sensing vs. retrieval date, `scene_id`, unsigned `source_url`, sha256).
    Per-collection default asset lives in `raster._DEFAULT_ASSET`
    (`raster.default_asset`); an offline fixture-COG miss raises `ImageryOfflineError`.
  - *Analyze* (`analysis.compute_index`) reuses `raster.clip_asset` to read the band
    COGs and compute **NDVI/NDWI** → a `derived` float32 raster + stats (mean, NDWI
    **water fraction**). Bands per `(collection, index)` come from `analysis._BANDS`,
    never hardcoded in the math. `bosc imagery index`.
- **Pixels are verbatim, output is evidence.** Captures land under
  `data/reference/imagery/<site>/<collection>/` (GeoTIFFs are Git LFS — see
  `.gitattributes`). Never resample or alter beyond the logged clip; keep the
  `scene_id` so any capture is re-pullable from the archive.
- **A new collection/AOI needs committed fixtures.** Search: a real STAC response at
  `tests/fixtures/gis/pc_stac_search/<key>.json`. Pull: a **small real** COG at
  `tests/fixtures/gis/imagery_cog/<scene_id>.<asset>.tif` — these stay in-repo (not
  LFS) so tests are hermetic. High-res collections (NAIP 0.3 m) make a full-AOI clip
  huge, so record the pull fixture against a **small sub-AOI**. Record live once;
  don't hand-edit recorded JSON/COGs.
- Sync throughout (`httpx`/`rasterio`), matching the rest of the pipeline.
