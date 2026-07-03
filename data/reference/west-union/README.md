# West Union · Adams Co (west-union) — reference data

Per-site onboarding tree for the West Union · Adams Co watershed point (basin: ohio-brush-creek), scaffolded by `bosc onboard west-union` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`bosc onboard west-union` over the West Union · Adams Co `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`bosc onboard west-union`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
