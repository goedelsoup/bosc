# Bowling Green · Middleton Twp (bowling-green) — RSEI toxics outputs

Per-site onboarding tree for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard bowling-green` (#326). Values come from the portable onboard connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard bowling-green` over the Bowling Green · Middleton Twp `SiteProfile` — EPA RSEI (county toxics release inventory).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard bowling-green`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
