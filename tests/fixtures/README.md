# tests/fixtures/

Committed fixtures that make the test suite **hermetic** — tests run fully offline
against these instead of the network or the git-ignored `data/cache/`.

## Layout

| Path | What |
|---|---|
| `hydrology/<connector>/<key>.json` | Recorded connector responses (USGS NWIS, EPA ECHO, NOAA Atlas-14, Allen/Lima GIS, ORC, LSC). The `<key>` is the request hash `cached_get` computes; `conftest.py` points `hydro_fixtures_dir` here and sets `hydro_offline=True`. |
| `air/isd/<key>.json`, `air/igra/<key>.json` | AERMET met pulls — NOAA ISD surface (ISHD) and IGRA v2 upper-air, as `cached_get` JSON payloads (`air_settings` fixture, `air_offline=True`). Trimmed to a few days/soundings; the `igra` payload is already year-filtered (what `fetch()` caches). |
| `air/ned/<key>.tif` | AERMAP terrain — a small decimated USGS 3DEP/NED DEM GeoTIFF (raster, not JSON — the committed-fixture-GeoTIFF discipline of `gis/raster.py`). |
| `periplus-bosc-parcels.geojson` | Parcel geometry fixture for the Periplus cross-check test. |

## Adding a fixture

When a new connector call or key is exercised, the offline cache miss raises
`HydroOfflineError` naming the exact key. Record the live response once and commit it
as `hydrology/<connector>/<key>.json`. Fixtures are committed reference data — keep
them minimal (just enough rows to exercise the code path) and don't hand-edit the
recorded JSON. See [`../../src/watermark/hydrology/connectors/CLAUDE.md`](../../src/watermark/hydrology/connectors/CLAUDE.md).
