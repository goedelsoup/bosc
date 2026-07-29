# CLAUDE.md — `watermark.hydrology.connectors`

Live public-data connectors (USGS NWIS, NOAA Atlas-14, EPA ECHO, USDA SSURGO/SDA, County/City
GIS, FEMA NFHL, ORC, LSC). Defers to the root [`CLAUDE.md`](../../../../CLAUDE.md).

- **GIS is schema-driven, not jurisdiction-hardcoded (#237).** `allen_gis.py` (parcel/CAMA)
  and `lima_gis.py` (zoning + floodzone) read their ArcGIS **field names + encodings** from the
  active site's `GisParcelSchema`/`GisZoningSchema`/`GisFloodSchema`
  (`watermark.connectors.gis_schema`), carried on `SiteProfile.gis_parcel`/`gis_zoning`/`gis_flood`
  (the *instances* live in `watermark.sites`). A new jurisdiction is config — register a schema; do
  **not** copy a connector or hardcode a field. A `None` schema makes the connector/CLI refuse
  cleanly (no fabricated cross-jurisdiction query). The endpoint URL is the per-site
  `parcels_url`/`zoning_url`/`floodzone_url`. The FEMA NFHL is the *shared national* flood
  field-map (`NATIONAL_NFHL_FLOOD_SCHEMA`), so any US site's floodzone is one connector.
  `OHIO_STATEWIDE_PARCEL_SCHEMA` is the analogous *shared statewide* parcel field-map for an Ohio
  county with no parcel REST of its own (e.g. Findlay/Hancock) — each site `model_copy`s it with a
  per-county `query_scope` (`County='Hancock'`, ANDed into every query) and its own `reference_dir`.
  It is a partial, owner-redacted layer: an empty `owner_field` makes owner/defense search refuse,
  and land use is decoded `leading_int` (`"511: Res-Custom Code"` -> `511`).

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
- **A document-cited correction to connector output is an OVERLAY, never a hand edit.**
  `echo_curation.py` is the pattern (#1698): *not* a connector (no network, no
  `cached_get`), it loads a committed, cited overlay
  (`data/reference/echo/curation/<basin>-wwtp.receiving-water.yaml`) and `echo.py` merges it
  into every pull, so a refresh can't clobber reviewed data. A hand edit inside regenerated
  output is silently reverted by the next pull — that's the bug this replaced. The overlay
  never overrides live data silently either: each entry pins the FRS id and records the
  upstream value observed at review time. A pull whose upstream has moved off it **refuses
  to write** when the disagreement is real — `conflict` (upstream now says something else)
  or `stale` (the record is gone from a pull that covered it) — rather than paper over it.
  `superseded` (upstream caught up and now says the same thing) is **not** a refusal: the
  write proceeds on upstream's own value and the run reports the entry as retirable.
  `mode: caveat` records a correction without touching the field. Reuse this
  shape for any other connector that needs a reviewed correction; don't invent a second one.
- **Water temperature lives under TWO NPDES parameter codes, and a permit uses one or the
  other** (`echo_dmr.py`, #1718): **00010** is degrees Celsius, **00011** degrees Fahrenheit.
  Both are live in the same Lima corridor — the WWTP (OH0026069) reports 00010 while the Lima
  Refinery (OH0002623) and PCS Nitrogen (OH0002615) report 00011 — so watching only the 00010
  the epic named would have found *none* of the industrial dischargers. `fetch_thermal_record`
  pulls both plus the flow (50050) and merges. Reduction rules: a value converts by **its own**
  stated unit and a stated-but-unrecognized unit **drops** the row (never read as if it were
  already °C); only a value with no unit label at all falls back to the parameter code's
  definitional unit. Keep the daily-maximum ("DD") rows apart from the monthly averages ("MK") —
  Ohio's criterion is itself a daily maximum. A numeric permit limit converts by
  `LimitUnitDesc` (a permit may cap in a unit the permittee doesn't report in) and is
  **seasonal**, so the reported figure is the warm-season ceiling with `limit_seasonal` set;
  a permit with no numeric limit at all is `monitor_only` — a cited absence, not a clean bill.
  An `Upstream/Downstream Monitoring` location is an **in-stream** (receiving-water) reading,
  categorically different from an effluent one, and is never averaged in with one.
- **`fetch_effluent_chart(parameter_code=...)` narrows the pull server-side.** A whole-permit
  chart for a major industrial permit is enormous (the Lima Refinery's three-year chart is
  ~19k DMR rows / 22 MB) — unreviewable as a committed fixture. ECHO accepts exactly **one**
  code (a comma-separated list silently returns nothing), so a caller wanting several makes one
  call per code and merges. The filter is added to the request only when set, so an unfiltered
  pull keeps its existing cache key and the pre-#1718 fixtures stay valid.
- Committed reference datasets a connector regenerates live under
  `data/reference/<source>/` (each with a README naming its source and gaps); raw
  responses cache under the git-ignored `data/cache/`.
