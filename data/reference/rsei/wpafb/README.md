# Wright-Patterson AFB (wpafb) — RSEI toxics outputs

Per-site onboarding tree for the Wright-Patterson AFB watershed point (basin: great-miami), scaffolded by `watermark onboard wpafb` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard wpafb` over the Wright-Patterson AFB `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## `enclave.yaml` — the base's own row, from the *other* county (#1664)

`inventory.yaml` covers **Montgomery County (39113)**, this site's economic/RSEI unit. Wright-Patterson
AFB itself reports TRI as **`45433SDDSFDEPAR`** from **Greene County (39057)** — the other county it
straddles — so it appears nowhere in that inventory. That is **out of scope by construction, not a
gap in the data**, and widening the county scope would silently re-base the economic unit.

`enclave.yaml` is therefore a **second, one-facility reduction** against Greene County, written by
`watermark --site wpafb enclave`. It carries the same joins and the same caveats as the county
inventory, plus a `facility_id_filter` recording the selector. It does **not** replace
`inventory.yaml`: the county inventory remains the site's toxics backdrop and its readiness floor
signal.

RSEI tracks TRI *reporting* and so cannot carry the base's CERCLA mass — the ≥58 waste-disposal
sites and the VOC plume predate TRI. See `data/extracted/wpafb/cercla-ffa-1991.epa.yaml`.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard wpafb`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
