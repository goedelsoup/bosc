# Findlay (findlay) — reference data

Per-site onboarding tree for the Findlay watershed point (basin: maumee), scaffolded by `watermark onboard findlay` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard findlay` over the Findlay `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## Committed datasets

Both GeoJSONs below come from the **same** source — the OGRIP Ohio statewide parcels public view
scoped `County='Hancock'`, read through the `ohio_parcels` connector — and carry the **same
vintage caveat**. Read that first.

> ⚠️ **The Hancock slice is a 2023-05-08 export, and no current county source is machine-readable.**
> Hancock County publishes no county parcel ArcGIS REST. The Auditor's live CAMA is
> Beacon/Schneider-only (`beacon.schneidercorp.com` AppID 1128, also fronted at
> `regis.co.hancock.oh.us`) and returns **Cloudflare HTTP 403** to every non-browser request; the
> Recorder's index is **Kofile CountyFusion** (`countyfusion2.kofiletech.us`,
> `countyname=HancockOH`), whose "Login as Guest" POST target **404s outside a browser session**.
> Both were probed 2026-08-02. So the deed chain — grantor, grantee vehicle, instrument number,
> consideration, recorded easements — is `[open]` as **unsearched, not empty**, and everything here
> is stated as the record *as of 2023-05-08*.

### `parcel-assemblage.geojson` — the Megawatt Hub holding (#1462)

The **One Power Co "Findlay Megawatt Hub" (MWHub 01)** land holding in **Allen Township**: eight
parcels, **108.65 ac CAMA / 105.873 ac planar** (UTM 17N), standing in **three One Energy
vehicles** — `ONE ENERGY ENTERPRISES LLC` (`020001001794`, the 4.07-ac office at 12411 TR 215),
`OEE XX LLC` (`020000004530`, 69.82 ac at CR 216) and `OEE XXX LAND LLC` (the six TR 99 parcels).
This is the file `SiteProfile.parcels_relpath` points at, so it drives the `geo/campus` feed, the
SSURGO dominant-HSG sample and the stormwater screen's area.

- **Two blocks, not one campus.** Each block's polygons abut without overlapping (north union
  71.857 ac vs parts-sum 71.858; south 34.016 vs 34.015), but the blocks themselves are
  **200.2 m apart**. Don't quote 108.65 ac as contiguous.
- **The north block is the press's "74-acre wind campus."** 73.89 CAMA ac against The Ohio
  Register's "a 74-acre wind energy campus along Interstate 75" — `[verified]` on the acreage,
  `[inference]` on the identification. **"Along I-75" is corridor language, not frontage:** the
  block's nearest boundary is **1,224 m (0.76 mi)** east of the interstate centerline (Census
  TIGER, measured in UTM 17N); the south block is 1,794 m out.
- **Seven of the county's ten wind turbines stand on this land** — a point-in-polygon test against
  the USGS **USWTDB** (read 2026-08-02), recorded per parcel in `turbines_contained`. The register's
  "already includes 10 utility-scale turbines" is a **county** count, not a count on this holding,
  and the 7-vs-10 gap is itself evidence that the 2023 holding is not the whole campus. Note what
  the containment shows about the business model: both turbines branded for **Whirlpool's** Findlay
  plant stand on **One Energy's** ground, not Whirlpool's.
- **The S-1's "~170-acre campus" is not reconciled to this holding and is not forced to be.** The
  61-ac gap is consistent with the 2025 40-ac purchase plus land held by lease, option, or a vehicle
  whose mailing label reads neither `OEE` nor `ONE ENERGY`. No parcel was added to close it.
- **The hub's own address is not in the extract.** One Power's SEC filings give **12385 TR 215**;
  no parcel in the 2023-05-08 slice carries that situs. Whether it is a post-2023 split, a building
  address, or a renumbering is `[open]` — and the road itself was contested (One Energy petitioned
  to rename TR 215 "Electric Avenue" on 2023-12-05, *One Energy Ents., Inc. v. Allen Twp. Bd. of
  Trustees*, 2026-Ohio-405).

### `civic-and-flood-places.geojson` — the site's public places (#1462)

The three **civic/flood** holdings the Blanchard story walks: 26 parcels, **1,921.77 ac CAMA /
1,870.83 ac planar**, split by a `place_role` property.

| `place_role` | parcels | CAMA ac | what it is |
| --- | ---: | ---: | --- |
| `flood_storage_basin` | 18 | 795.35 | Maumee Watershed Conservancy District — the **Eagle Creek Dry Storage Basin** acquisition, Eagle Township |
| `water_supply_reservoir` | 6 | 1,048.57 | City of Findlay **upground reservoir** holding, TR 207/205, Marion Township |
| `wwtp` | 2 | 77.85 | City of Findlay **Water Pollution Control Center**, 1201 S River Rd |

- **This file is deliberately NOT wired to `parcels_relpath`.** Folding 1,921 ac of reservoir, WWTP
  and flood-basin ground into the campus path would draw public infrastructure as "campus", sample
  soils 13 km from the hub, and inflate a runoff denominator.
- **It closes the polygon `#1465` had to leave `[open]`.** The Eagle Creek handoff
  ([`eagle-creek-basin-footprint.handoff.yaml`](../../extracted/findlay/flood/eagle-creek-basin-footprint.handoff.yaml))
  found only verbal bounds in the public record and committed no geometry. The county parcel record
  carries it: 18 MWCD parcels with situs on exactly the four roads the handoff and the issue name
  (TR 76, TR 77, TR 49, US-68). Their **polygon extent** spans 40.9681–40.9902 N and their parcel
  **centroids** 40.9738–40.9890 N — 3.0–4.6 mi south of downtown by extent, 3.4–4.5 by centroid,
  so it is the centroid span that reads as the published "~4 miles south". Seven **Eagle Creek**
  flowline segments run through the block (USGS NHD) and the township is confirmed via Census
  TIGER.
- **765 ac and 795 ac are different measurements.** `hancockcountyflooding.com` publishes
  "approximately 765 acres" for the area **within the dam alignment**; this file carries 795.35 ac
  of **land acquired** in three non-contiguous blocks. Acquired land properly exceeds the
  impoundment, so the two are consistent — but neither is derived from the other, and **the dam
  alignment itself stays `[open]`** (no surveyed polygon, no ODNR Dam Safety exhibit in the corpus).
  Because the export predates the completed acquisition, 795.35 ac is a **floor**.
- **The WPCC parcel contains the permitted outfall** — a point-in-polygon `[verified]`: outfall
  `2PD00008001` at Blanchard River RM 56.42 (41.049722/−83.667778, Ohio EPA fact sheet
  `2PD00008*UD` p. 7) falls inside `610000926490`. ⚠️ That parcel's served geometry measures only
  **39.758 planar ac against 50.52 CAMA** — a 10.76-ac, **−21.3%** shortfall, the largest gap in
  the file. It is **not a lone outlier**, and the spread it sits in is worth reading before
  trusting any single planar figure here: `200001032776` is **−17.5%**, and the other 24 parcels
  run **−7.2% to +5.2%**. Two readings fit that spread and this file does not choose between them: served
  geometry that under-covers the deed, or CAMA acreages never re-surveyed. Cite the deeded
  acreage; don't use the polygon as a plant-area measurement.
- **The two reservoirs are named by NHD, not by the parcel layer.** The USGS NHD Waterbody
  (Large Scale) layer carries **Findlay Reservoir** (177.9 ac) and **Findlay Upground Reservoir
  Number Two** (628.9 ac) over this block — 806.8 ac of water surface inside 1,048.57 ac of city
  land. Which parcel underlies which reservoir is **not asserted**. ⚠️ This is the same Findlay
  Reservoir whose diversion and low-flow augmentation release make USGS gage `04189000` a
  **regulated** station — the defect that retired the derived 8.67 cfs 7Q10 for the WPCC reach
  (#1458).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion**
  (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **There is no owner field here, and the property names say so.** The OGRIP public view is
  owner-redacted (`OHIO_STATEWIDE_PARCEL_SCHEMA` sets `owner_field=""`, and the connector's `owner`
  decodes to `null`). Both files therefore carry **`owner_mailing_name`** — the recipient line of
  the tax-bill mailing label, trailing city/ZIP stripped — and deliberately **not** an `owner` or
  `owner_of_record` property, because a tax-bill recipient is the best available proxy for the
  owner of record and **is not the same thing as one**. `owner_mailing_address` carries the label
  verbatim. Consequence to expect downstream: the `geo/campus` feed's `grantee` reads `null` for
  every Findlay parcel, since `campus_from_parcels` fills it from `owner`. That is the correct
  reading — the grantee is exactly what is `[open]`.
- ⚠️ **The layer serves one row per polygon PART, not one row per parcel** (the Wood-County CAMA
  shape, #1436). Five of the 26 civic/flood parcels come back as 2–4 rows; each is merged into one
  MultiPolygon and `geometry_parts` records how many rows it took. Deduping the query result by
  parcel id — the obvious defensive move — would have silently dropped **220 ac**. The eight hub
  parcels are all single-part.
- **No value, sale, deed or tax-district columns exist to carry.** Unlike the Shelby / Clinton /
  Wood assemblages, the OGRIP public view has no market value, no conveyance date or amount, no
  deed book-page, no legal description and no CAUV/exemption/abatement flags. Those fields are
  absent from these files because the **source has none** — not because they were dropped.
- **Zoning stays `[open]` over the holding, and the reason is structural.** The City of Findlay
  zoning FeatureServer is city-limits-only and polygon-only (no parcel id, so per-parcel joins are
  unsupported here) and does not reach Allen Township; the township's own regime is new and its map
  is not published as a layer. See [`../findlay-gis/README.md`](../findlay-gis/README.md).
- `acres` is the county CAMA (auditor) figure from the OGRIP `LandArea` column; `planar_acres` is
  measured from the committed geometry in UTM 17N (EPSG:32617). The two are **not** reconciled and
  neither is adjusted to the other — cite CAMA for the record, planar for area/runoff modelling.

## Regenerate

- Reach connectors: `watermark onboard findlay` (or the per-connector commands:
  `derive-low-flows`, `nasa-power --write`, etc.)
- Both GeoJSONs, in two steps (there is no `--owner` path for this site — the OGRIP schema has no
  owner field, so the connector's owner scan refuses cleanly and the parcel set is id-driven):
  1. `watermark.hydrology.connectors.allen_gis.query_parcels_geojson("LocalParcelID IN (…)",
     settings=Settings(site="findlay"))` pulls WGS84 geometry plus the base props
     (`parcel_id` / `situs_address` / `owner_mailing_address`) through the `ohio_parcels` connector,
     which scopes the where-clause to `County='Hancock'` for you.
  2. The remaining OGRIP columns the `GisParcelSchema` decode drops or normalizes away
     (`StateParcelID`, `StateLUC` split into `land_use_code`/`land_use_name`, `LandArea` →
     `acres`, `CurrentTo`), plus `planar_acres` (UTM 17N), the per-parcel multi-part merge, the
     role tags (`assemblage_role`/`cluster`, `place_role`) and the cross-source enrichments
     (`turbines_contained` from USWTDB, `contains_wpcc_outfall`) are added per this recipe.
- `dominant_hsg` (profile + footprint record):
  `watermark.hydrology.connectors.ssurgo.dominant_hsg(Path("data/reference/findlay/parcel-assemblage.geojson"),
  grid_n=8, settings=Settings(site="findlay"))` — C/D at 23 of 23 interior points, and unanimous
  again at `grid_n=12` (53/53) and `grid_n=16` (89/89).

Raw API responses cache under the git-ignored `data/cache/`.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `findlay-civic-flood-places` — Findlay Civic & Flood Places — WPCC, Upground Reservoirs, Eagle Creek Dry Storage Basin

Source: OGRIP — Ohio Statewide Parcels Public View (owner ogrip_agol), FeatureServer layer 0, scoped County='Hancock' via the OHIO_STATEWIDE_PARCEL_SCHEMA field-map. Waterbody names/areas cross-checked against the USGS NHD Waterbody (Large Scale) layer; township attribution against the Census TIGER county-subdivision layer. · License: Public records (local government open data) · Access: public · Site scope: site:findlay · Refresh: on-demand, last 2026-08-02

Regenerate: `watermark --site findlay parcels --parcel 610000926490`

| file | type | lfs |
| --- | --- | --- |
| `reference/findlay/civic-and-flood-places.geojson` | application/geo+json | no |

<!-- catalog:end -->
