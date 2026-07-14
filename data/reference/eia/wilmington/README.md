# Wilmington (wilmington) — energy / grid outputs

Per-site onboarding tree for the Wilmington watershed point (basin: little-miami), scaffolded by `watermark onboard wilmington` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard wilmington` over the Wilmington `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Files

- `consumer-energy.yaml`, `grid-profile.yaml` — state-level EIA consumer costs + the AES Ohio (DP&L) grid profile (onboarding floor).
- `demand-pressure.yaml` — the **facility-gated** data-center demand → consumer-price-pressure sensitivity (#1468). Present because the Wilmington `SiteProfile.facility` is now populated (the disclosed AWS "Cosler Farm" campus); derived from the committed OH consumer-energy figures × the facility power basis (`watermark.facility.power`). The demand share + households-equivalent are EIA-cited; the price-pressure band is a **stylized screening sensitivity, not a forecast**.

## Regenerate

`watermark onboard wilmington`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.). The `demand-pressure.yaml` is written by `watermark --site wilmington eia --write` (facility-gated — it needs `SiteProfile.facility`).
