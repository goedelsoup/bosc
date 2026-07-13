# Troy · Piqua (troy-piqua) — reference data

Per-site onboarding tree for the Troy · Piqua watershed point (basin: great-miami), scaffolded by `watermark onboard troy-piqua` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard troy-piqua` over the Troy · Piqua `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## `watch-items.geojson` (hand-authored, not a connector output)

`watch-items.geojson` is the site-specific WWTP-infrastructure override consumed by `watermark.hydrology.balance` (it takes precedence over the Lima periplus import). Unlike the connector outputs above it is **manually authored from cited public records**, not regenerated:

- **Piqua WWTP** (`id=piqua-wwtp`) — outfall 001 → Great Miami River, average design flow **8.7 MGD** (13.46 cfs). NPDES **1PD00008 / OH0027049**; coordinates `[verified via EPA FRS 110000578919]` (ECHO 40.13128, -84.23466). Source: Ohio EPA NPDES fact sheet `1PD00008.fs` (PN 22-006-011, 2022-06-21).
- This unblocks `hydrology_balance` for troy-piqua (#829): the Piqua design discharge is screened against the cited **GMR-above-Sidney 7Q10 = 24.0 cfs** (USGS 03261500, `reference/hydrology/low-flow-7q10.yaml` key `upper great miami river`).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard troy-piqua`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
