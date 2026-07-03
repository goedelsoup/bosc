# Hamilton · Middletown (hamilton-middletown) — economics baseline outputs

Per-site onboarding tree for the Hamilton · Middletown watershed point (basin: great-miami), scaffolded by `watermark onboard hamilton-middletown` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard hamilton-middletown` over the Hamilton · Middletown `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard hamilton-middletown`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
