# CLAUDE.md — `bosc.hydrology.connectors`

Live public-data connectors (USGS NWIS, NOAA Atlas-14, EPA ECHO, USDA SSURGO/SDA, Allen/Lima GIS,
ORC, LSC). Defers to the root [`CLAUDE.md`](../../../../CLAUDE.md).

- **A connector is a pure sync `fn(..., settings) -> pydantic`.** Keep the network
  call inside the `fetch` callable you hand to `_cache.cached_get` — never call
  `httpx` directly past the cache, and never read `os.environ` (use `settings`).
- **`cached_get` resolves: fresh on-disk cache → committed fixture (offline) → live
  fetch.** So tests never hit the network. A fresh connector/key needs a committed
  fixture under [`tests/fixtures/hydrology/<connector>/<key>.json`](../../../../tests/fixtures/hydrology/);
  an offline miss raises `HydroOfflineError` naming the exact key to record.
- **Select API columns/fields by name, never by index** (ECHO by **ObjectName**;
  same discipline for the GIS/portal connectors). Column order is not stable.
- **Never fabricate or backfill.** A `null` from the API stays `null`; a derived
  flag is tagged `derived`. The headline-count and caveat discipline in
  [`data/reference/echo/README.md`](../../../../data/reference/echo/README.md) is the
  model to follow.
- Committed reference datasets a connector regenerates live under
  `data/reference/<source>/` (each with a README naming its source and gaps); raw
  responses cache under the git-ignored `data/cache/`.
