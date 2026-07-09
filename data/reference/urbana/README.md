# Urbana (urbana) — reference data

Per-site onboarding tree for the Urbana watershed point (basin: great-miami), scaffolded by `watermark onboard urbana` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard urbana` over the Urbana `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **Urbana Technology Hub** (Thor Equities) land assembly:
  the four Champaign County parcels now deeded to the three developer single-purpose entities
  (Urbana Owner I LLC, Urbana Owner II LLC, Highland55 Investments LLC), ~230 ac at the corner of
  SR-55 & S US-68 south of Urbana (#1326 / lead #1263). Geometry + owner/acreage/sale are `[verified]`
  from the CCEO auditor CAMA layer (`parcel_joined` FeatureServer 0) via the `champaign_cceo`
  connector. 5 features / **4 distinct parcels** (Highland55 `K48-25-11-01-32-005-00` is multipart);
  230.346 ac CAMA / 232.07 ac planar. Seller-residual parcels still held by Brand Investments LTD
  (`…32-021-00`, ~22.5 ac) and Organ Farms LLC are **excluded** — not transferred. Deed book/page
  references are `[open]`, deferred to the recorder pull (#1328).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City **zoning** GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`). The **parcel** GIS is now wired (`CHAMPAIGN_PARCEL_SCHEMA`).

## Regenerate

- Reach connectors: `watermark onboard urbana`  (or `derive-low-flows`, `nasa-power --write`, etc.).
- `parcel-assemblage.geojson`: a `champaign_cceo` connector query (`allen_gis.query_parcels_geojson`)
  over the four assembly parcel ids under `WATERMARK_SITE=urbana`, then `write_parcels_geojson`; the
  provenance foreign member lists the ids and the assembly definition.
