# CLAUDE.md — `watermark.connectors`

Neutral, subsystem-agnostic connector plumbing. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md).

- **One cache/offline/fixture path for every subsystem.** `_cache.cached_get` is the
  single primitive the hydrology, economics, gis, poi, and civic connectors all call.
  It holds no subsystem logic: the caller passes its own `cache_dir`
  (`settings.<x>_cache_dir`), `offline` flag, `fixtures_dir`, and `ttl_hours`.
- **Resolution order:** fresh on-disk cache → committed fixture (offline) → live
  fetch (cached). An offline miss raises `offline_error` naming the exact key to
  record — so a fixture gap is actionable, never a silent empty.
- **Offline errors are subsystem-specific.** `OfflineError` is the neutral base;
  each subsystem may pass a subclass so callers can catch precisely:
  `HydroOfflineError` (`watermark.hydrology.connectors`), `ImageryOfflineError`
  (`watermark.gis.raster`). Hydrology's flavored `cached_get`
  (`watermark.hydrology.connectors._cache`) wraps this one with the `hydro_*` defaults.
- **No `os.environ`, no config import here.** This module is pure machinery; all
  configuration arrives as explicit arguments from the calling subsystem.
- Don't put a `fetch`'s HTTP call here — that lives in the connector. Keep this layer
  about caching and the offline contract only.
- **`federal.py` is the exception that proves the "neutral plumbing" rule** — it *is* a
  connector, and it lives here rather than under `hydrology/connectors/` because a federal
  enclave is not a hydrology subject (#1664). It wraps three keyless, public-domain registers
  that exist precisely because the county-scoped instruments the rest of the platform uses
  cannot see a military base: **DoD MIRTA** (site boundaries — the enclave is off the county
  tax rolls, so no CAMA parcel layer will ever carry it), **EPA SDWIS** (the base's own
  community water systems), and **EPA ECHO CWA** (its own NPDES discharges). Fixtures live at
  `tests/fixtures/federal/<connector>/`; the offline error is `FederalOfflineError`.
  ECHO columns are selected **by ObjectName** against the verified `cwa_rest_services.metadata`
  and mapped to their ColumnID — never by index, the same repo-wide ECHO rule as
  `hydrology/connectors/echo.py`. Acreage is the one derived value and is measured from the
  published geometry in the **site's own UTM zone**, never transcribed.
