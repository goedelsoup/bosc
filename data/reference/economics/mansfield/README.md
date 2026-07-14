# Mansfield (mansfield) — economics baseline outputs

Per-site onboarding tree for the Mansfield watershed point (basin: muskingum), scaffolded by `watermark onboard mansfield` (#326). Values come from the portable onboard connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard mansfield` over the Mansfield `SiteProfile` — US Census · BLS QCEW (county economic baseline).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard mansfield`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
