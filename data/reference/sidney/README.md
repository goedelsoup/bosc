# Sidney (sidney) — reference data

Per-site onboarding tree for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard sidney` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard sidney` over the Sidney `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **AWS "Project Galaxy"** data-center campus land holding
  (#1379): the **single Shelby County parcel deeded to Amazon Data Services, Inc.**,
  `26-03-201-002` (auditor number `01-2603201.002`), at the northwest corner of S Vandemark Rd &
  W Millcreek Rd in Clinton Township / the City of Sidney corporate limits. **243.092 ac deeded /
  235.468 ac planar (UTM 16N)**; geometry + owner / acreage / land use / conveyance / deed
  book-page / legal description / CAUV-exemption-abatement flags are `[verified]` from the Shelby
  County Auditor CAMA via the new `shelby_gis` connector (`SHELBY_PARCEL_SCHEMA`). Conveyed
  **2025-11-24 for $5,621,490** at **OR2329/454**; Amazon's auditor mailing is PO Box 80416,
  Seattle WA. A countywide owner scan returns **exactly this one parcel** — no nominee holding was
  found (that absence is `[open]`, not a negative finding).

  **The register's street address is retired, not wrong.** The #511 register carries
  "2388 W. Millcreek Road"; that situs belonged to parcel `26-03-226-001` (77.6 ac), one of
  **five predecessor tracts** consolidated into this parcel by *Lot 7658 Consolidation & Roadway
  Dedication Plat, Plat V37 P50*. The other four are `26-03-126-001` (78.26 ac),
  `26-03-201-001` (56.14 ac), `26-03-251-001` (21.24 ac) and `26-03-251-002` (2 ac, situs
  "2522 Millcreek Rd"). All five stand in the 2023-05-23 OGRIP statewide extract, lie 85–99%
  inside this polygon, and are gone from the current CAMA — `[verified]` as a geometric
  containment test of the two layers. Their planar areas sum to 239.524 ac against this parcel's
  235.468 ac, a ~4-ac loss consistent with the plat's roadway dedication (`[inference]`; Plat
  V37 P50 is not in the corpus). The parcel of record today is situs **1151 S Vandemark Rd**.

  **Adjacent lead, deliberately excluded** (not Amazon-owned): **Dayton Power & Light Co.** took
  `26-03-429-009` (7.305 ac, "Fair & Vandemark Rd") from the Shelby County Commissioners on the
  **same day**, 2025-11-24, for $547,875 at **OR2329/497** — 43 pages after the Amazon deed in the
  same record volume. A campus substation is the obvious reading and stays `[inference]`: the
  parcel also abuts DP&L's pre-existing `26-03-429-008` (2305 Fair Rd, held since 2006), so an
  unrelated substation expansion is not excluded, and no PJM interconnection or OPSB siting
  instrument is public.

  Full detail in the geojson `bosc:provenance` and
  [`data/extracted/sidney/bosc-site-footprint.yaml`](../../extracted/sidney/bosc-site-footprint.yaml).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **Parcel** GIS is now wired (`SHELBY_PARCEL_SCHEMA` — the Shelby County Engineer's Office AGOL `Parcels` layer, the full auditor CAMA join). It **replaced** the OGRIP statewide substitute the profile had carried, which for Shelby is both owner-redacted *and* a **2023-05-23** extract — it predates the entire Project Galaxy transfer and can name no grantee.
- **Zoning** GIS is now wired (`SIDNEY_ZONING_SCHEMA` — City of Sidney `SidneyGIS_AllLayers` layer 270, 9 districts) but the **campus parcel's zoning district stays `[open]`**. The layer is polygon-only (no parcel id, so per-parcel joins are unsupported — the Findlay shape), city-limits-only, and "officially adopted on October 24, 2016". The campus falls in a **hole** in it: the zoning, corp-limits *and* annexation layers all miss the parcel's interior point, while its two district-01 neighbours hit all three (SEMCORP `26-03-301-001` → `IIM`; DP&L `26-03-429-009` → `CC`). The annexation layer stops at ordinance **A-3145, 2023-08-28**. The auditor's TY2025 tax district `01` ("Clinton Twp **Sidney Corp** Sidney SD", against district `02` "Clinton Twp …" for the unincorporated township) does place the parcel inside the corporate limits — so this is a **currency gap** in the city's published layers, not an unzoned or extraterritorial site. The instrument to pull is the annexation/rezoning ordinance itself (#1380).
- The recorder's sequential **deed instrument number**, the **grantor**, and any recorded easements remain `[open]` — the auditor CAMA gives the Official-Record book/page locator (OR2329/454) but not the instrument number (#1380).
- The consolidated parcel's **appraised values and current/prior tax are all 0** in the TY2025 extract: it is an unvalued *new* parcel, not a $0 property. `has_abatement` reads `NO` for the same reason — the 30-year 100% CRA (Resolution 18-25) exempts real-property *improvements* per building on completion, and no improvement is on the tax record yet.

## Regenerate

- Reach connectors: `watermark onboard sidney`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
- `parcel-assemblage.geojson`, in two steps (the Troy·Piqua / Urbana assemblage recipe):
  1. `WATERMARK_SITE=sidney watermark parcels --owner "AMAZON DATA SERVICES" --geojson data/reference/sidney/parcel-assemblage.geojson` pulls the geometry + the base props (`parcel_id` / `owner` / `situs_address` / `owner_mailing_address` / `transfer_date`) through the `shelby_gis` connector.
  2. The remaining CAMA columns — the ones `GisParcelSchema` has no slot for (`deed_reference` from `Deed_Volume`/`Deed_Page`, `legal_description`, the `Has_CAUV`/`Has_Exemption`/`Has_Abatement` flags, `class`, `land_use_name`, `parcel_number`, `tax_district*`, `school_district`, the appraised values) plus `planar_acres` (measured with `watermark.hydrology.geo.parcels_total_acres`) and the detailed `bosc:provenance` are added per this recipe. **The connector's `transfer_date` is renamed `last_sale_date` in the same step** — the committed file carries `last_sale_date`, not `transfer_date`, matching the Troy·Piqua / Urbana / Mansfield assemblages (it is the auditor's `Date_Conveyed`, decoded from Esri epoch-millis). Auditor vintage 2026-07-31, `Extract_ID` 5966, tax year 2025.
- `dominant_hsg` (profile + footprint record): `watermark.hydrology.connectors.ssurgo.dominant_hsg(Path("data/reference/sidney/parcel-assemblage.geojson"), grid_n=8, settings=Settings(site="sidney"))` — the 64-point grid replays from the committed fixture `tests/fixtures/hydrology/ssurgo/b24d12cce45e748c.json`.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `sidney-watch-items` — Sidney site watch-items (WWTP infrastructure geometry)

Source: Derived from Ohio EPA "Fact Sheet for NPDES Permit Renewal, City of Sidney WWTP, 2022" (permit 1PD00009*SD / application OH0027421) and the ECHO Great Miami POTW inventory; coordinates from EPA FRS (ECHO lat/lon 40.2709, -84.15031, FRS Registry ID 110002345597) · License: Public record (Ohio R.C. 149.43 / U.S. Government work) · Access: public · Site scope: site:sidney · Refresh: static

| file | type | lfs |
| --- | --- | --- |
| `reference/sidney/watch-items.geojson` | application/geo+json | no |

<!-- catalog:end -->
