# CLAUDE.md — `bosc.connectors`

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
  `HydroOfflineError` (`bosc.hydrology.connectors`), `ImageryOfflineError`
  (`bosc.gis.raster`). Hydrology's flavored `cached_get`
  (`bosc.hydrology.connectors._cache`) wraps this one with the `hydro_*` defaults.
- **No `os.environ`, no config import here.** This module is pure machinery; all
  configuration arrives as explicit arguments from the calling subsystem.
- Don't put a `fetch`'s HTTP call here — that lives in the connector. Keep this layer
  about caching and the offline contract only.
