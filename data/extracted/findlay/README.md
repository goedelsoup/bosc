# Findlay (findlay) — extractions

Per-site onboarding tree for the Findlay watershed point (basin: maumee), scaffolded by `watermark onboard findlay` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard findlay` over the Findlay `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Flood-mitigation instrument chain (`flood/` + `flood-mitigation.md`)

Hand-curated primary-source evidence (issue #1465), **not** connector output — `watermark onboard`
does not produce or regenerate it, so re-onboarding must not clobber it. `flood/` holds the two
structured `permits-epa` record rows (the FEMA Flood Mitigation Assistance $24M obligation and the
USACE Blanchard-watershed feasibility Review Plan) that lift Findlay's `record` domain to `live`
(tier `backdrop → case`), plus the Eagle Creek basin + benching footprint descriptor handed to the
places sub-issue (#1462). `flood-mitigation.md` is the narrative record; open threads are in
`data/site/findlay/leads.yaml`; the set is catalogued as `findlay-flood`. Several primary pages 403'd
and are search-rendered — see the per-file `warnings` and the `flood-mitigation.md` sourcing note.

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard findlay`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
