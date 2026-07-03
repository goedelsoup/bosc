# Fort Wayne (fort-wayne) — extractions

Per-site onboarding tree for the Fort Wayne watershed point (basin: maumee), scaffolded by `watermark onboard fort-wayne` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Contents

- `ONBOARDING.md` — living onboarding record + review gate.
- `datacenter-facility.md` — public-record discovery of the disclosed data-center facility (Google "Project Zodiac", #360).
- `wwtp-receiving-water.md` — reviewed receiving-water characterization of the Fort Wayne WWTP (IN0032191) against the derived headwaters 7Q10 (#358/#359).
- `wwtp-in0032191.dmr.yaml` — the plant's reported effluent record (EPA ECHO DMR), regenerable via `watermark dmr IN0032191`.

## Source

`watermark onboard fort-wayne` over the Fort Wayne `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER). The WWTP DMR artifact is an EPA ECHO `eff_rest_services` pull (`watermark dmr`).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard fort-wayne`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
