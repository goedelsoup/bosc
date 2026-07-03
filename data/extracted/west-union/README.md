# West Union · Adams Co (west-union) — extractions

Per-site onboarding tree for the West Union · Adams Co watershed point (basin: ohio-brush-creek), scaffolded by `bosc onboard west-union` (#326). Values come from the portable onboard connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`bosc onboard west-union` over the West Union · Adams Co `SiteProfile` — the ingest→extract corpus pipeline over this site's source documents.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`bosc onboard west-union`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
