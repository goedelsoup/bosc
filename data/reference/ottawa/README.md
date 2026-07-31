# Ottawa (ottawa) — reference data

Per-site onboarding tree for the Ottawa watershed point (basin: maumee), scaffolded by `watermark onboard ottawa` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard ottawa` over the Ottawa `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **former Sylvania / GTE / Philips Display Components
  (LG.Philips Displays USA) CRT plant campus** (#1420): the **two contiguous Putnam County
  parcels** the works was subdivided into and sold as in the 2006 Chapter 11, at 700 and 804
  North Pratt Street in the Village of Ottawa. **38.234 ac deeded / 38.293 ac planar (UTM 16N)**;
  geometry, owner of record, deeded acreage, land-use code, legal description, inlot number, the
  auditor's land/building appraised values, half-year tax and the conveyance date/amount/type are
  `[verified]` from the Putnam County Auditor CAMA via the `putnam_gis` connector
  (`PUTNAM_PARCEL_SCHEMA`, #420). Each parcel cites its own auditor page.

  | parcel | inlot | situs | acres | owner of record | conveyed |
  |---|---|---|---|---|---|
  | [32-222000.0000](https://auditor.putnamcountyohio.gov/Parcel?Parcel=322220000000) | IL 1540 | 700 N Pratt St — the remediation property | 22.842 | OTTAWA OH LLC (mail c/o APTM INC, Long Beach CA) | 2006-12-21, $500,000, warranty deed |
  | [32-226000.0000](https://auditor.putnamcountyohio.gov/Parcel?Parcel=322260000000) | IL 1544 | 804 N Pratt St — the Endera EV-bus plant | 15.392 | VERHOFF PROPERTIES LLC (Continental OH) | 2006-07-11, $350,000, warranty deed |

  **This is not a data-center campus.** It is a closed industrial works — the county's largest
  employer until 2002-12-31 — now the subject of a **$4,571,596** three-round Ohio Brownfield
  Remediation Program remediation. Ottawa's `SiteProfile` carries `facilities=()`. The geometry is
  committed as the site's anchor **place**, and activates the `places` readiness domain as
  committed campus geometry — never read it as a siting.

  **The two parcels are contiguous**: their union is a single polygon, the shared-boundary
  distance is 0.0 m, and the union area equals the sum of the parts to five decimal places. Both
  are auditor use code **350** (industrial/manufacturing) and both were conveyed by **warranty
  deed in 2006**, the year the campus was broken up.

  **The issue's parcel table is wrong in two places** and both are recorded rather than quietly
  corrected. It renders the parcel numbers `3-2222.00.0000` / `3-2226.00.0000`; the layer stores
  `322220000000` / `322260000000` and the auditor displays `32-222000.0000` / `32-226000.0000`
  (confirmed against the county's `ParcelsJoined` `Parcel` column — the auditor **URLs** in the
  issue are correct, only the dashed renderings are not). And it lists **inlots 1541, 1542 and
  1543** as the rest of the subdivided campus in third-party hands: they are **not part of it and
  not adjacent to it**. Measured from the campus boundary in UTM 16N, IL 1543 (Trinity United
  Methodist Church) is **206.95 m** away, IL 1542 **559.72 m** and IL 1541 (Ormsby trust)
  **1,090.26 m**; none is industrial-class and none has a Pratt St situs. Putnam issues inlot
  numbers in **platting order, not geographic order**, so an adjacent inlot number is no evidence
  of adjacent ground.

  **Adjacent lead, deliberately excluded**: **IL 1536**
  ([32-218000.0000](https://auditor.putnamcountyohio.gov/Parcel?Parcel=322180000000), 615 N Agner
  St, 16.47 ac, use code 350) sits **20.13 m** from the campus — 66.0 ft, exactly one platted
  street right-of-way, i.e. directly across the street. AGNER ROAD INVESTMENTS LLC (mailing PO Box
  810, Royal Oak MI) took it on 2022-07-07 with IL 1548 and IL 1549 for a single recorded
  **$3,950,000** repeated across all three rows. Whether that ground was ever part of the works is
  `[open]` — no deed, plat or site plan settles it.

  **The grantor and the deeds are `[open]`.** This layer carries no grantor, no deed book/page and
  no instrument number, so the Sylvania → GTE → Philips → LG.Philips → 2006 Chapter 11 →
  OTTAWA OH LLC / VERHOFF PROPERTIES LLC chain is **not** closed by it; the Putnam County Recorder
  instruments are the pull (#1421). Nor is either owner the **brownfield grantee** — the three BRP
  awards went to the Port Authority of Northwestern Ohio (Rounds 1 and 11) and the Putnam County
  Land Reutilization Corp (Round 5).

  Full detail in the geojson `bosc:provenance` and
  [`data/extracted/ottawa/bosc-site-footprint.yaml`](../../extracted/ottawa/bosc-site-footprint.yaml).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **Parcel** GIS is wired (`PUTNAM_PARCEL_SCHEMA` — the county's self-hosted `Parcels/Parcels` layer 0, owner + auditor CAMA values on one layer). Two traps on it, both found while committing the assemblage:
  - The **`District` and `Class` columns are unreliable**. Both read `0` on *both* campus parcels while the neighbouring IL 1536 reads `District 32` / `Class 3`, so a `District = 32` filter **silently drops the campus**. Filter on `PIN` or on the populated `CLASS_1` column — never on `District` or `Class`.
  - The wired layer **lags its own sibling on ownership**. `Parcels/ParcelsJoined` carries conveyances layer 0 has not picked up (237 N Pratt St: `HEEBSH`/2021-06-30 on layer 0 vs `FAWCETT`/2026-06-02 on ParcelsJoined; IL 1542: `MELISA WAY LLC` vs `MEYER PROPERTIES LLC`). For **both** campus parcels the two services **agree**, so the committed record is corroborated across both and unaffected. ParcelsJoined is not the wired source because it is thinner where it matters — no appraised values, no sale date/amount, acreage rounded to 2 dp — and it keys on `Parcel2` (dashless) / `Parcel` (dashed), so a PIN-shaped query against `Parcel` returns **zero rows rather than an error**. Re-checking the two owners against ParcelsJoined on each re-pull is the standing follow-up.
- **Zoning** GIS is a **searched negative**, not an undiscovered layer (`gis_zoning=None`, `zoning_url="TODO"`). The Village publishes none: ordinances are text-only on American Legal, its own site offers no mapping application, and an ArcGIS Online org search for Putnam/Ottawa zoning returns four items, none of them zoning. The county server publishes only `Parcels`, `Sections` and an `Ottawa` water-utility folder; its `/services/Zoning` path answers **`499 Token Required`** — but so does a folder name that certainly does not exist, so that 499 is **not** evidence of a secured zoning service. The posture is also **in flux**: the Village issued an RFP for *"Zoning, Development, and Related Regulatory Code Modernization Services"* on **2026-06-23** (questions due 2026-07-14, proposals due **2026-08-04 16:00**), so the code is under procurement to be rewritten. Re-check after that award.
- The campus's **impervious fraction, building footprint and any remediation boundary** stay `[open]` — no site plan, Rule-5 SWPPP, BRP work plan or No Further Action letter is in the corpus (#1421).

## Regenerate

- Reach connectors: `watermark onboard ottawa`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
- `parcel-assemblage.geojson`, in two steps (the Mansfield/Sidney reviewed-assemblage recipe — the campus has **two unrelated owners**, so the `parcels --owner` path cannot pull it in one call):
  1. `watermark.hydrology.connectors.allen_gis.query_parcels_geojson("PIN IN ('322220000000','322260000000')", settings=Settings(site="ottawa"))` pulls the geometry + the base props (`parcel_id` / `owner` / `situs_address` / `owner_mailing_address` / `transfer_date`) through the `putnam_gis` connector, along with the schema's full `out_fields` in the cached raw response.
  2. The remaining CAMA columns — the ones outside `PUTNAM_PARCEL_SCHEMA.out_fields`, because changing that tuple would move the connector cache key the #420 param-stability guard pins (`LEGALDESC`, `LOT`, `PURCOD`, `HALFTAX`) — are read as a second cached request against the same layer, plus `planar_acres` (measured with `watermark.hydrology.geo.parcels_total_acres`) and the detailed `bosc:provenance`. `auditor_url` is **derived** as `https://auditor.putnamcountyohio.gov/Parcel?Parcel=<PIN>` and **asserted equal** to the layer's own `PARCELURL` column on both parcels, so it is the layer's citation rather than a constructed one. The connector's `transfer_date` is renamed `last_sale_date` in the same step, matching the other committed assemblages.
- `dominant_hsg` (profile + footprint record): `watermark.hydrology.connectors.ssurgo.dominant_hsg(Path("data/reference/ottawa/parcel-assemblage.geojson"), grid_n=8, settings=Settings(site="ottawa"))` — the 8×8 grid (59 interior points) replays from the committed fixture `tests/fixtures/hydrology/ssurgo/a001f6fab82a1a50.json`. Two coarser grids replay from committed fixtures too and return the same `C/D`, so the answer is not a grid artefact: the onboard step's default 6×6 (35 points, 14 of them rated) from `110afdaec575ec70.json`, and a 4×4 (15 points, 5 rated) from `58c15307a960eac5.json`.
