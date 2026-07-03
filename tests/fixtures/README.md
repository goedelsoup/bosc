# tests/fixtures/

Committed fixtures that make the test suite **hermetic** — tests run fully offline
against these instead of the network or the git-ignored `data/cache/`.

## Layout

| Path | What |
|---|---|
| `hydrology/<connector>/<key>.json` | Recorded connector responses (USGS NWIS, EPA ECHO, NOAA Atlas-14, Allen/Lima GIS, ORC, LSC). The `<key>` is the request hash `cached_get` computes; `conftest.py` points `hydro_fixtures_dir` here and sets `hydro_offline=True`. |
| `periplus-bosc-parcels.geojson` | Parcel geometry fixture for the Periplus cross-check test. |

## Adding a fixture

When a new connector call or key is exercised, the offline cache miss raises
`HydroOfflineError` naming the exact key. Record the live response once and commit it
as `hydrology/<connector>/<key>.json`. Fixtures are committed reference data — keep
them minimal (just enough rows to exercise the code path) and don't hand-edit the
recorded JSON. See [`../../src/watermark/hydrology/connectors/CLAUDE.md`](../../src/watermark/hydrology/connectors/CLAUDE.md).
