# Fort Wayne (fort-wayne) — RSEI toxics outputs

Per-site onboarding tree for the Fort Wayne watershed point (basin: maumee), scaffolded by `watermark onboard fort-wayne` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard fort-wayne` over the Fort Wayne `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard fort-wayne`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
