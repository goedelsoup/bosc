# Van Wert (van-wert) — reference data

Per-site onboarding tree for the Van Wert watershed point (basin: maumee), scaffolded by `watermark onboard van-wert` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard van-wert` over the Van Wert `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **QTS "Van Wert Mega Site"** data-center campus land
  holding (#1403): the **five Van Wert County parcels deeded to `QTS VAN WERT LLC`**, north of
  U.S. Route 30 between Stripe Road and Mendon Road. **900.59 ac deeded / 901.502 ac planar
  (UTM 16N)**, and the five are **contiguous** — their union is a single polygon. Geometry +
  owner / acreage / land use / appraised values / conveyance date-consideration-type / CAUV flag /
  county survey references are `[verified]` from the Van Wert County Auditor CAMA via the
  `van_wert_gis` connector (`VAN_WERT_PARCEL_SCHEMA`, the county's AGOL `parcel_joinedVWOH`
  layer 0, #421). A countywide owner scan returns **exactly these five** — and returns **zero**
  parcels for `THOR`, `FORM8TION`, `VAN WERT EAST` or `EQUITIES`.

  **The roll refreshed under the issue.** #1403 was written against a 2026-07-10 probe in which
  the 221.15-ac anchor `17-034718.0100` stood in the name of **VAN WERT EAST OWNER LLC** (a Thor
  SPE), sold 2025-08-22 for **$10,394,000**; the issue anticipated the assemblage firming up "as
  the roll refreshes". It has — the AGOL item was last modified **2026-07-31T03:52Z** and now
  carries the **June 2026 conveyances to QTS directly**: four parcels (679.44 ac) on **2026-06-16**
  at a recorded **$39,117,825**, and the anchor on **2026-06-18** at **$110,575,000**, all warranty
  deeds. So the deed grantee the register had as `[open]` is now `[verified]`; the **grantor**, the
  recorder instrument numbers and therefore the Marsh Foundation → Thor → QTS chain itself stay
  `[open]` (this layer carries no grantor field and no deed book/page — #1401).

  **Two figures that do not average away.** The anchor's June price is **exactly $500,000 × its
  221.15 CAMA acres** — a **10.6×** step over the ~$47,000/ac Thor paid ten months earlier. And the
  four same-day parcels carry **one** date and **one** consideration across all four, the signature
  of a single multi-parcel deed, so that amount is recorded verbatim per parcel and deliberately
  **not summed**; the campus's total consideration stays `[open]`.

  **The acreage reconciles to QTS's own figure — and, since #1401, to the annexation's too.**
  900.59 ac deeded is **0.16%** off the **902-acre** campus footprint QTS quotes, the first
  independent instrument to confirm it.

  > ⚠️ **Corrected against #1401**, which landed after this file was written. The annexed and zoned
  > area is **901.698 ± ac**, read off Ordinance 26-05-028's Exhibit A, whose four component
  > acreages sum exactly to the figure printed in both ordinance titles. The **~962 ac** this
  > section reconciled against was a press number with no support anywhere in the record. The
  > holding is therefore **1.108 ac (0.12%)** under the zoned area, not "61.4 ac (6.4%) short" —
  > and the two explanations that shortfall used to require (road right-of-way inside the annexed
  > area, non-QTS parcels inside the annexation description) are no longer load-bearing at that
  > magnitude. The residual 1.1 ac stays `[open]` and is still not attributed to right-of-way. The
  > ordinances' legal descriptions **are** now in the corpus
  > (`data/extracted/van-wert/mega-site-instruments.yaml`).

  Three independent acreages now agree to within ~1.1 ac: **901.698** zoned (ordinance Exhibit A),
  **901.502** planar (this geometry, UTM 16N), **900.59** deeded (auditor CAMA). The boundary
  committed here is the recorded **ownership** holding, not the annexation boundary and not a
  surveyed earth-disturbance footprint.

  **The campus straddles two school districts**, which the register did not have: **772.46 ac
  Lincolnview** (the four Ridge/Hoaglin parcels) and **128.13 ac Van Wert City**
  (`12-034459.0000`). A CRA school-compensation agreement would have to reach both boards.

  **Adjacent leads, deliberately excluded** (not QTS-owned, no instrument ties them to the campus):
  the Marsh Foundation still holds `19-041272.0000` (200.83 ac, Stripe Rd, ~69 m away across
  Stripe Road), `12-031248.0200` (93.62 ac) and `12-031252.0000` (49.35 ac). Reading those as the
  remainder of the register's ~1,500-ac Mega Site is `[inference]`. **No** parcel that actually
  adjoins the campus is Marsh- or QTS-owned, and **no** utility parcel appears next door — unlike
  Sidney, there is no same-day substation conveyance to record, so the campus substation site is
  `[open]`.

  Full detail in the geojson `bosc:provenance` and
  [`data/extracted/van-wert/bosc-site-footprint.yaml`](../../extracted/van-wert/bosc-site-footprint.yaml).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **Parcel** GIS is wired (`VAN_WERT_PARCEL_SCHEMA` — the county's AGOL `parcel_joinedVWOH` auditor CAMA join, #421, which replaced the dead `ags.bhamaps.com` PAT MapServer). It is **thinner than Shelby's or Champaign's**: no owner mailing address, no legal description, no grantor, no deed book/page. Everything that would close the deed chain has to come from the Van Wert County **Recorder** (#1401).
- **Zoning** GIS is a **confirmed negative** — Van Wert publishes no zoning REST endpoint anywhere (`gis_zoning is None`, `zoning_url="TODO"`; map-only/PDF). Unlike Sidney there is no layer to test the parcel against, so the site's I-2 General Industrial + conditional data-center zoning is `[verified]` from the **public record** (City Council emergency ordinances, 2026-05-11) and the ordinance text — now pulled and committed (#1401) — is the instrument. ⚠️ This line carried "6–0"; the minutes record **no numeric tally** for any of the three ordinances, only "all concurred", and Roberts abstained as a Marsh Foundation employee. "6-0" is a press reconstruction.
- **Tax-district currency gap.** The auditor has all five parcels in Van Wert **Corporation** districts (12, 17, 33), while the county's published `TaxDistrict` **polygon** layer still shows them in townships (11-Pleasant, 19-Ridge, 15-Hoaglin) — carried per feature as `tax_district_gis_layer`. District **33** is absent from that layer's district table entirely and has **exactly one parcel countywide**, this assemblage's 31.24-ac Hoaglin tract, so it is a district created after the layer's vintage (which is why `tax_district` is null there). The roll is the current record; reading the corporation-district placement as the effect of the 2026-05-11 annexation is `[inference]`.
- **Two parcels are unvalued, not valueless**: `17-034718.0200` and `12-034459.0000` carry null appraised values and a null CAUV flag — new splits the auditor had not valued at this extract.
- The county stores one parcel as several polygon rows; the raw connector pull returns **11 rows for these 5 PINs**. The committed file dissolves them per parcel (`gis_row_count` records how many), an **area-lossless** merge — per parcel the part areas sum to the union area to four decimal places.

## Regenerate

- Reach connectors: `watermark onboard van-wert`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
- `parcel-assemblage.geojson`, in two steps (the Sidney / Troy·Piqua / Urbana assemblage recipe):
  1. `WATERMARK_SITE=van-wert watermark parcels --owner "QTS VAN WERT" --geojson data/reference/van-wert/parcel-assemblage.geojson` pulls the geometry + the base props (`parcel_id` / `owner` / `situs_address` / `owner_mailing_address` / `transfer_date`) through the `van_wert_gis` connector. It writes **11 features** — the county's split rows.
  2. The remaining CAMA columns — the ones `GisParcelSchema` has no slot for (`class` from `PPClassCode`, `conveyance_type` from `PPSalesType`, `has_cauv` from the `PPOnCauv` string flag, `survey_reference`/`prior_survey_reference` from `Survey`/`OldSurveys`, `year_built`, the appraised values, the dashed `parcel_id` from `Parcel`) — plus `planar_acres` (measured in UTM 16N, the site's `hydro_utm_epsg`), the per-parcel dissolve, the `tax_district` / `school_district` joins against the county's own `TaxDistrict` and `SchoolDistrict` layers, and the detailed `bosc:provenance` are added per this recipe. **The connector's `transfer_date` is renamed `last_sale_date` in the same step** — the committed file carries `last_sale_date`, matching the Sidney / Troy·Piqua / Urbana / Mansfield assemblages (it is the auditor's `PPSaleDate`, decoded from Esri epoch-millis). AGOL item last-modified 2026-07-31T03:52Z.
- `dominant_hsg` (profile + footprint record): `watermark.hydrology.connectors.ssurgo.dominant_hsg(Path("data/reference/van-wert/parcel-assemblage.geojson"), grid_n=8, settings=Settings(site="van-wert"))` — the 45-point grid replays from the committed SSURGO fixture.
