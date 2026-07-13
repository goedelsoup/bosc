# Mansfield (mansfield) — reference data

Per-site reference tree for the Mansfield watershed point (Rocky Fork → Mohican → Walhonding
→ Muskingum; basin `muskingum`), Richland County OH (FIPS 39139). Nothing here is fabricated —
values are pulled from cited public sources; regenerate, don't hand-edit.

## Committed datasets

- **`parcel-assemblage.geojson`** — the **Airport West I-1→I-2 rezone footprint** (the site's
  first committed footprint geometry, `places` domain, #1431). City of Mansfield **Ordinance
  25-086** (Bill 25-087; City Planning Commission **Petition #561**), passed as an emergency
  **2025-06-03**, amended the City Zoning Districts Map (Ord. #04-208) to rezone **16 lots** at
  and around **Airport West Parkway & Cairns Road** from **I-1** (Limited Impact Industrial
  District) to **I-2** (General Impact Industrial District) — "as recorded in the Richland County
  Auditor's Office." Geometry + owner/acreage/class/value are `[verified]` from the **Richland
  County Auditor CAMA** (`Parcel_CAMA` MapServer layer 0) via `RICHLAND_PARCEL_SCHEMA`.

  **10 of the 16 ordinance lots resolve in the current auditor parcel fabric** (~**309.1**
  recorded legal acres, reconciling with the ~321 ac reported for the full 16-lot schedule). The
  other **6** (`028-90-500-93-002/003/004/006/007` and `028-90-150-51-001`) no longer resolve as
  separate parcels — they were **consolidated or renumbered** at some point after the ordinance was
  drawn. The **specific successor parcel(s) are `[inference]`** — not confirmed against an auditor
  parcel-history / split-merge or deed record; the large adjacent City lot `028-90-500-93-000`
  (129.53 ac) is the most likely absorber but is **not verified** as such. The retired IDs are
  preserved in the file's `bosc:provenance` (`retired_parcel_ids`); their geometry is **not
  fabricated**. The City of Mansfield owns 7 of the 10 resolved lots; 37 East Fourth Street LTD
  (an Ohio LLC) owns 3. **Adena Development Corp** — the city-affiliated CIC named in press
  coverage — is not a current owner-of-record on the resolved 10; its historical interest and the
  disposition of any holdings are **unknown here** (no deed / parcel-history record was pulled), so
  the Adena attribution stays `[reference]` (press), not confirmed against the recorder.

## Known gaps & caveats

- **Auditor `ZONING`/`USEDSCRP` columns are unpopulated** on `Parcel_CAMA` layer 0 — the
  I-1→I-2 status is the **Ordinance 25-086 instrument**, never an auditor attribute. Each feature
  carries `zoning_change`/`ordinance` as the instrument citation, not a CAMA field.
- `acres` is the recorded `LEGAL_ACRES`; `calculated_acres` (planar) is carried only where it
  differs. Multipart parcels (`028-90-500-48-000` = 4 parts, `028-90-500-93-000` = 2 parts) are
  returned by the service as repeated single-ring features and assembled here into one
  MultiPolygon per parcel — sum the 10 committed parcels, not the raw service features.
- **Right-state guard:** Richland County **OHIO** (FIPS 39139), owner city Mansfield OH 449xx,
  WKID 3734 (NAD83 Ohio North ftUS) reprojected to WGS84. Not the same-named Richland Co WI/SC/IL.
- Onboarding/first-footprint seed — **review every value against a cited source before promotion**
  (`web/src/lib/sites.ts` `status`/`selectable` is parity-gated).

## Regenerate

The Richland County GIS is an **on-prem ArcGIS Server 10.3**, which does **not** support
`f=geojson` (only Esri `f=json`) — so the schema-driven `query_parcels_geojson` connector path
does not run here. Owner/attribute queries via `f=json` (`query_parcels`) work unchanged. The
committed geojson is pulled with the following recipe (esri rings → GeoJSON):

1. Query `Parcel_CAMA/MapServer/0` with `where=PARCELID IN (<the 16 schedule ids>)`,
   `outFields=<the CAMA field set>`, `returnGeometry=true`, `outSR=4326`, `f=json`.
2. Group the returned single-ring features by `PARCELID` (multipart parcels repeat), assemble one
   `Polygon`/`MultiPolygon` per parcel, and orient exterior rings counter-clockwise (RFC 7946).
3. Re-key attributes to the friendly property names and write the `FeatureCollection` with the
   `bosc:provenance` foreign member (schedule/committed/retired parcel ids + caveats).

Endpoint: <https://maps.richlandcountyoh.us/richlandgis/rest/services/Parcel_CAMA/MapServer/0>
Instrument: City of Mansfield Ordinance 25-086, passed 2025-06-03 —
<https://ci.mansfield.oh.us/wp-content/uploads/2025/06/Passed-Legislation-06-03-25.pdf>
