# Fort Wayne (fort-wayne) — reference data

Per-site onboarding tree for the Fort Wayne watershed point (basin: maumee), scaffolded by `watermark onboard fort-wayne` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard fort-wayne` over the Fort Wayne `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Files

- `bosc-parcels.geojson` — the **Project Zodiac parcel assemblage**: the 11 parcels owned by
  Hatchworks LLC (the Google land-assembly shell; mailing Mountain View CA / Wilmington DE) pulled
  from the Allen County, IN iMap GIS (`gis1.acimap.us`, parcel layer 10) as WGS84 GeoJSON. The anchor
  is 6015 Adams Center Rd (transferred 2024-01-10); the Tillman Rd cluster fills out the assemblage
  (Jan-2024 + a second wave 2025-10-31). Measured planar acreage ~856 ac (UTM 16N). Catalogued as
  `fort-wayne-parcels`. **This is the recorded ownership assemblage, NOT a surveyed facility
  boundary** — the developed/impervious footprint stays pending the deed/rezoning/stormwater-permit
  extraction (#360/#362).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- Parcel GIS is now wired (the file above). Zoning GIS is the Allen County (IN) county-wide catalog
  (`gis_zoning`); per-parcel zoning joins are unavailable (polygon-only layer).

## Regenerate

- Parcels: `watermark --site fort-wayne parcels --owner Hatchworks --geojson data/reference/fort-wayne/bosc-parcels.geojson`
  (re-run to catch new Hatchworks acquisitions).
- Reach connectors: `watermark onboard fort-wayne` (or `derive-low-flows`, `nasa-power --write`, etc.).

> The `bosc-parcels.geojson` file is catalogued by the slug-scoped `bosc-parcels` entry
> (`data/catalog/reference/bosc-parcels.yaml`), not a per-site README block.
