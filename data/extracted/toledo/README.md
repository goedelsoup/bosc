# Toledo (toledo) — extractions

Per-site onboarding tree for the Toledo watershed point (basin: maumee), scaffolded by `watermark onboard toledo` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard toledo` over the Toledo `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Event reads

- `napoleon-spill/waterville-monitor-read.md` — the Maumee-at-Waterville (USGS 04193500)
  continuous-monitor read against the Napoleon / Huston Creek fertilizer spill (#1498, parent
  #1497). Machine-readable peer: `reference/hydrology/toledo/waterville-spill-monitor-read.yaml`
  (`watermark waterville-monitor`).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard toledo`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
