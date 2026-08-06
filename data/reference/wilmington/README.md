# Wilmington (wilmington) — reference data

Per-site onboarding tree for the Wilmington watershed point (basin: little-miami), scaffolded by `watermark onboard wilmington` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard wilmington` over the Wilmington `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **US-68 S / SR-730 data-center corridor** (#1470): **seven
  contiguous** Clinton County parcels, **1,023.764 ac deeded / 1,023.786 ac planar (UTM 17N)**,
  in **two legally distinct groups** the file keeps apart with a `corridor_role` property. Read it
  before quoting an acreage.

  **`campus_holding`** — recorded ownership. Three parcels deeded to **AMAZON DATA SERVICES INC**
  on **2025-12-10** by one recorder instrument, **2025-00005287**, for a single **$86,436,000**
  consideration: the **471.609 ac** campus tract `285-13-02-01-0000-00` (situs **1488 S US 68**,
  the former Cosler Farm) plus two right-of-way strips, `290-26-01-12-0000-00` (7.040 ac on US 68)
  and `270-13-02-01-0000-00` (0.236 ac on SR 730) — **478.885 ac** in total. The consideration is
  the **whole deed's**, repeated on each parcel; summing it across the three triples the price.

  **`petitioned_rezoning`** — a legislative schedule, not an assemblage. The four tracts City
  Council rezoned **5–2 on 2026-02-19/20**: **O-26-04** L T Land Development LLC (119.375 ac),
  **O-26-05** Matthew E Thompson (65.323 ac, situs 1957 SR 730), **O-26-06** June 11 2001 Ralph
  Larry Roberts II FT (190.065 ac) and **O-26-07** Jack L Webb RLT (170.116 ac) — **544.879 ac**,
  ownership unchanged. **No Ardent/TAC entity holds any land in Clinton County**; a countywide
  owner scan returns only unrelated surname matches. This is the Mansfield (#1431) rezone-footprint
  shape.

  **The "~1,000-acre corridor" is now a measurement.** The union of the seven polygons is a
  **single** polygon whose area equals the sum of the parts to three decimals (1,023.786 ac) across
  a 3,185 m × 3,126 m extent — so they abut without overlapping. The register had that figure as
  `[inference — the ~471-ac and 545.893-ac press acreages summed]`; it is now `[verified]`.

  **Two figures deliberately left unreconciled.** The annexation split: the campus tract's legal
  reads `SPLIT/FR 270130201000000(480.202AC) 25DUP DUE TO TYPE II ANNEX` and the residual's reads
  `REM 8.593AC RW SR 730`, against an arithmetic 8.357 ac — a 0.236-ac gap the annexation plat
  would close (`[open]`, #1471). And the petitioned acreages: the wnewsj figures sum to 545.893 ac
  against the auditor's 544.879 ac, a 1.014-ac gap that is **entirely** the Roberts tract, where
  the petition quotes the parent `270-13-05-01` (191.117 ac) and the auditor carries the 190.065 ac
  that actually annexed. Cite **544.879 ac** for the rezoned land of record.

  **Legal status rides with the geometry.** The campus map rezoning is one of three ordinances a
  federal court ordered the City to redo for defective 30-day notice (*Sharp v. City of
  Wilmington*, S.D. Ohio 1:26-cv-00448, ~2026-07-09/10 `[reported]`), and the four-tract rezoning
  is the subject of a **November 2026 referendum** `[reported]`. These are disclosed and petitioned
  footprints, not settled entitlements.

  Full detail in the geojson `bosc:provenance` and
  [`data/extracted/wilmington/bosc-site-footprint.yaml`](../../extracted/wilmington/bosc-site-footprint.yaml).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **Parcel** GIS is now wired (`CLINTON_PARCEL_SCHEMA` / the `clinton_gis` connector — the Clinton County GIS Department's `cntyparcelsRealPropData_gdb` layer 0, the full auditor CAMA join). It **replaced** the OGRIP statewide substitute this profile had carried, which is owner-redacted by construction and, for Clinton, reports a **null `CurrentTo`** — no stated export date at all — with situs and land area null on a large share of rows. That combination returns a *silent* false negative: it can name no grantee, so the entire Cosler Farm / Ardent-TAC corridor was invisible through it. Two older twins of the county layer are also stale — `cntyparcels` on the CCRPC org (`services7/5ML1cxkkvVfOhDrS`) is a **tax-year-2022** snapshot last edited 2023-08-28 and returns **zero** rows for "AMAZON". Check `editingInfo.dataLastEditDate` before believing a negative.
- **Zoning** GIS is now wired (`WILMINGTON_ZONING_SCHEMA` — the CCRPC `ProposedZoning9` layer 0, which is the Zoning layer of the City's own *Wilmington Zoning Map 2024* application; 13 districts over 29 polygons, city limits only, polygon-only so per-parcel joins are unsupported — the Findlay/Sidney shape). The **campus tract's district is `[verified]` `LI` (Light Industrial)**: a discrete **471.27-ac** LI polygon covers 99.73% of it, and the City Planning Commission agendas of 2026-01-06 and 2026-03-25 independently print the application's zoning as "Light Industrial". The **four petitioned tracts' district stays `[open]`** — their interior points fall in no city polygon and still read the county's `S-R`, because the layer was last edited **2026-02-10** and Council passed their rezonings **nine days later**. That is a publication lag, not a finding; the instruments are the ordinances themselves (#1471). Note the press describes the change as "Rural Residential → Light Industrial" while the county's pre-annexation district on all four is **S-R, Suburban Residential** — resolve the *from*-district from the ordinances, not the press.
- The **site-plan PDFs** (the 9-building original and the 12-building revision tabled 2026-03-27) are **not obtainable from the published record** as of 2026-08-01 and the building count stays `[open]`. The City's site publishes Planning Commission **agendas** but no exhibits and no 2026 Planning Commission **minutes**; the county GIS site-plan layers (`Clinton_County_Site_Plans`, `Wilmington_Staff_Reports`) stop at 2024. The pull is an **R.C. 149.43 request** to City Planning & Zoning for the submittals of the 2026-01-06 and 2026-03-25 hearings.
- The **grantor** and any recorded easements remain `[open]` — the auditor CAMA gives the recorder instrument number (2025-00005287) but not the grantor (#1471).
- Three of the four petitioned tracts show `appraised_total_value` 0 and `current_tax` 0: they are unvalued **new split** parcels at this extract, not $0 properties. The campus tract's `has_abatement` reads `NO` while its own legal description carries `TY26 TIF 100% 30YRS -FINAL` — a TIF is not a real-property abatement, so that flag is not "no incentive".

## Regenerate

- Reach connectors: `watermark onboard wilmington`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
- `parcel-assemblage.geojson`, in two steps (the Ottawa/Mansfield reviewed-assemblage recipe — the corridor has **five unrelated owners**, so the `parcels --owner` path cannot pull it in one call):
  1. `watermark.hydrology.connectors.allen_gis.query_parcels_geojson("PIN IN ('285-13-02-01-0000-00','290-26-01-12-0000-00','270-13-02-01-0000-00','285-13-02-02-0000-00','285-13-04-01-0000-00','285-13-11-02-0000-00','285-13-03-01-0000-00')", settings=Settings(site="wilmington"))` pulls the geometry + the base props (`parcel_id` / `owner` / `situs_address` / `owner_mailing_address` / `transfer_date`) through the `clinton_gis` connector, with the schema's full `out_fields` in the same cached raw response.
  2. The remaining CAMA columns — the ones outside `CLINTON_PARCEL_SCHEMA.out_fields` (`Parcel_Number`/`PARCELID`, `District_Code`, `Land_Use_Name`, `Class`, `Legal_Description`, `Deed_Volume`/`Deed_Page`, `Has_CAUV`/`Has_Exemption`/`Has_Abatement`, `Current_Tax`, `Tax_Year`, `AudWeb`, `ZoningDist`/`ZoningDi_1`) — are read as a second cached request against the same layer, plus `planar_acres` (measured in UTM 17N), the `corridor_role` / `rezoning_ordinance` classification, and the detailed `bosc:provenance`. `auditor_url` is the layer's own `AudWeb` column, **not** a constructed URL: the sibling `Auditor_Link` column ships with an unsubstituted `{Property ID}` placeholder and does not resolve. The connector's `transfer_date` is renamed `last_sale_date` in the same step, matching the other committed assemblages.
- `dominant_hsg` (profile + footprint record): `watermark.hydrology.connectors.ssurgo.dominant_hsg(Path("data/reference/wilmington/parcel-assemblage.geojson"), grid_n=<n>, settings=Settings(site="wilmington"))`. The **campus tract alone** returns `C` at 8×8 / 10×10 / 12×12 / 16×16, so the letter is not a grid artefact; the **whole corridor** returns `C/D` at 8×8–12×12 and `C` at 6×6 and 16×16, because the four petitioned tracts pull it wetter. The profile characterizes the campus. onboard's default 6×6 over the corridor replays from the committed fixture and reports `HSG C; matches profile`.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `wilmington-watch-items` — Wilmington site watch-items (WWTP infrastructure geometry)

Source: Derived from Ohio EPA NPDES fact sheet 1PD00013.fs (City of Wilmington WWTP) and ECHO POTW inventory; coordinates from EPA FRS (ECHO lat/lon 39.4391, -83.85132). Clinton Substation added at #1469 — parcel geometry from the Clinton County auditor's CAMA layer (parcel 270-12-10-35-0000-00, DAYTON POWER & LIGHT COMPANY, 25.29 ac; centroid 39.39796, -83.85464), corroborated by OpenStreetMap way/36923781 (name="Clinton Substation", substation=transmission, voltage="345000;69000") 57 m away. · License: Public record (Ohio R.C. 149.43 / U.S. Government work) · Access: public · Site scope: site:wilmington · Refresh: static

| file | type | lfs |
| --- | --- | --- |
| `reference/wilmington/watch-items.geojson` | application/geo+json | no |

<!-- catalog:end -->
