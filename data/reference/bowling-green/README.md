# Bowling Green · Middleton Twp (bowling-green) — reference data

Per-site onboarding tree for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard bowling-green` (#326). Values come from the portable onboard connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard bowling-green` over the Bowling Green · Middleton Twp `SiteProfile` — per-site authored reference inputs + per-jurisdiction connectors (site geometry, parcels/zoning).

## Committed datasets

- **`parcel-assemblage.geojson`** — the **Meta "Bowling Green Data Center" / "Project Accordion"
  land assembly** in Middleton Township (#1436): **fifteen** Wood County parcels in **four
  roles**, which the file keeps apart with a `parcel_role` property. Read it before quoting an acreage.

  **`liames_assembly`** — recorded ownership, and the only role that is the campus. **Twelve
  contiguous parcels deeded to LIAMES, LLC**, **775.020 ac deeded / 774.878 ac planar**. Four
  tracts over 50 ac carry 753.65 ac of it: `611190000003500` (322.5 ac, 0 Mercer Rd),
  `611190000029510` (196.5 ac, 0 Dixie Hwy), `611300000001000` (160 ac, 12279 Middleton Pike)
  and `611300000002000` (74.65 ac, 12499 Middleton Pike). The other 21.37 ac are eight small
  parcels along SR-25, Mercer Rd and Middleton Pike whose houses and a strip of motel rooms have
  been razed.

  **`rezoning_pending`** — `611190000006000`, 64.55 ac still deeded to **A. Schaller Limited
  Partnership** since 1999, abutting the campus. The county planning commission recommended
  rezoning **39.265 ac of it** A-1 → M-1 **6–2 on 2026-07-07** for Liames construction parking,
  township action pending; Liames is in contract to purchase. Ownership unchanged.

  **`apollo_permit_situs`** — `611200000011000`, 79.07 ac at **11902 Middleton Pike**, the
  address on the Apollo Power Generation Facility's Ohio EPA air permit — still deeded to **JJJ
  Family Properties LLC** since 2008. **Will-Power OH, LLC owns no land in Wood County**; a
  countywide owner scan returns zero rows. This is not the plant's project boundary.

  **`oppidan_colo`** — `511210000002003`, **11.80 ac** deeded to **CLOP Bowling Green OH LLC**
  on 2025-02-03 for **$1,105,000**, in the Woodbridge Business Park **inside the city** and
  **7,771 m (4.83 mi)** from the nearest campus boundary. The owner's mailing address is
  Oppidan Investment Company's own headquarters in Excelsior MN. A separate facility with a
  separate developer — never fold its acreage or load into the Meta campus.

  **The "~750-acre assembly" is now a measurement.** The union of the twelve Liames parcels is a
  **single** polygon, 774.878 ac against a 774.883-ac sum of the parts. That 0.004764-ac
  (~19 m²) difference **is** the total pairwise intersection, across a 1,821 m × 2,489 m
  extent — so they abut along shared boundaries that overlap by slivers at that scale. The
  claim is "one contiguous block", never "they do not overlap". The register had the acreage as
  `[reference]` press; the land of record is 775.020 ac deeded and it is one block.

  **The county tax roll mails Liames' bills to Meta's headquarters.** Eight of the twelve
  parcels carry the owner mailing address `1 META WAY, MENLO PARK, CA 94025` (served
  `MENLOW PARK` on four); the other four go to `52 E GAY ST, COLUMBUS, OH 43215`. Meta's
  operator role was already `[verified]` from its own 2025-04-09 announcement — this is an
  independent documentary corroboration in the tax record, not the source of it, and a billing
  address is not a certificate of ownership of the LLC.

  **Zoning rides with the geometry, and one thing is not published at all.** The four campus
  tracts read **99.8–100% `M-1: Light Industrial`** in the township's own layer (content built
  2025-11-13). The eight small parcels read `A-1` and `R-4` — their **pre-rezoning** districts.
  Middleton Township trustees rezoned those thirteen parcels / 31.82 ac to M-1 by **2–1 on
  2026-07-07**, over their own zoning commission's rejection of 2026-06-10, and **no published
  Wood County layer carries that change** as of 2026-08-01.

  **The referendum window was still open at pull time.** R.C. 519.12 gives 30 days from the
  trustees' vote — closing about **2026-08-06** — and a petition drive needing **971 valid
  signatures** for the November 2026 ballot was circulating as of 2026-07-18 `[reference]`. The
  outcome is **`[open]`, not captured**; the eight affected parcels are flagged
  `rezoning_contestable_2026_07_07`.

  Full detail in the geojson `bosc:provenance` and
  [`data/extracted/bowling-green/bosc-site-footprint.yaml`](../../extracted/bowling-green/bosc-site-footprint.yaml).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`data/sites.yaml` + `web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).
- **Parcel** GIS is now wired (`WOOD_PARCEL_SCHEMA` / the `wood_gis` connector — Wood County's own `Services_for_Web_Apps/Vision_Parcels` MapServer layer 0, the Vision Government Solutions auditor CAMA joined to parcel geometry, 73,839 features). **Its vintage is not published and has to be probed**: this server exposes no `editingInfo`, so the currency read is `max(Sale_Date)` over the whole layer, which is **2025-07-25**, with zero rows after 2026-05-01. It is a ~2025-07 snapshot, and a negative owner result is a statement about July 2025. The sibling `Services_for_Web_Apps/Parcels` layer is the ArcGIS **parcel fabric** (PLSS, misclose, legal acreage) and carries no owner at all — not a stale twin, a different kind of layer.
- **The layer serves one row per polygon PART, not per parcel, and both obvious fixes are wrong.** Twelve of the 774 parcels in the Middleton neighbourhood come back on 2–6 rows with identical attributes. All twelve repeat sets are pairwise **disjoint** (0.000 ac of overlap) and the parts sum to the deeded acreage — `611190000006000` is 39.621 + 25.294 = 64.915 ac planar against 64.55 ac deeded. Deduping on the id **drops land**; summing `Land_Acres` over raw rows **double-counts**. Union the geometry per id and take the acreage once.
- **`Prc_Ttl_Apprais_Lnd_Alt` is the CAUV land value**, and its name says nothing of the kind: 0 on 493 of the 774 neighbourhood parcels and strictly below `Total_Land` on 270 of the remaining 281, running ~35–40% of market on enrolled farmland. **0 means not enrolled, not unvalued.** The layer publishes **no total-value column** — `Total_Land` and `Total_Improved` and nothing that sums them.
- **Zoning** GIS is now wired, and it is the **township's**, not the city's (`MIDDLETON_ZONING_SCHEMA` — Wood County ArcGIS `Hosted/Middleton_Twp_Zoning_Viewer26` layer 1, the township's parcel-joined districts). The campus is in **Middleton Township ~6 mi north of the corporation limits**, so the City of Bowling Green's `Current Zoning` layer covers the Oppidan colo and **not** the campus. Two other candidates were rejected: the **countywide** township layer (`Services_for_Web_Apps/Zoning_Districts` layer 1) is a **2013 snapshot** — `LASTUPDATE` 2013-07-18…2013-08-08 on 1,338 of its 1,339 polygons — and predates every rezoning this site is about; the hosted twin `Middleton_twp_zoning_WFL1` is stale at 2025-11-03 against the wired layer's 2026-07-14. Read `lastEditDate` before picking one — noting that it is **layer metadata, not a row**, so it does not by itself say what changed.
- **Zoning reads here are GEOMETRIC, never an id join.** The zoning layer rides an **older parcel fabric**: `611190000003500` and `611190000029510` are 2025-04-09 consolidations, and their eleven predecessors still populate it, summing to 319.99 ac and 195.86 ac. An id join between the two layers silently misses the campus.
- **The `zone` string is code *and* label** (`M-1: Light Industrial`), the `resolution` column that would carry the trustees' resolution number is **empty on every row**, and **rows repeat per parcel — but not uniformly.** The full layer is 6,816 rows over 3,409 distinct `name` values (6,816/3,409 = 1.9994, *not* 2), and the committed campus-envelope fixture is 296 rows over 145 names: 142 names on two rows and **three on four**. Aggregate per name; never halve a row count to get a parcel count.
- **The record shows 8 of the 13 rezoned parcels** (21.37 of 31.82 ac). The press reports all thirteen as already owned by Meta; the missing 5 parcels / 10.45 ac are invisible because of the layer's 2025-07-25 vintage. The rezoning application's parcel schedule at the county planning commission is the instrument. `[open]`
- **The Apollo project boundary is not a parcel.** The OPSB staff report's ~146.84-ac project area reconciles to no parcel or contiguous parcel group in this layer — no combination of JJJ Family Properties' four parcels or the abutting Dauer tracts lands within 3 ac of it — and the report itself gives 146.84 / 163 / 165.11 ac for three different boundaries. `[open]` (#1437)
- **CAUV reads 0 on the two consolidated campus tracts** while the 2023 acquisitions still carry $585,960 and $255,360. Seven of the eight fringe parcels also read 0 — but `611190000009000` (1.01 ac, 21630 Dixie) reads **$46,750**, so "the fringe is off CAUV" is not a rule. Either the core came off current agricultural use valuation or the new parcel numbers have not been re-valued at this extract; the auditor's recoupment record settles it and is not in the corpus. Do not report the zeros as a documented removal. `[open]`
- **The neighbours include a `LIMES` family** (Dale Limes LLC, Limes Real Estate Holdings LLC, Limes Galen E) holding several hundred acres on Devils Hole Rd and Dixie Hwy — one letter from `LIAMES`. The register's "Devils Hole Rd ~112 ac" rezoning item was **not** resolved here and stays `[reference]`/`[open]`.
- The **grantor** and any recorded easements remain `[open]`: the CAMA gives deed and conveyance numbers but not the grantor, and the 2025-04-09 consolidation quitclaims erased the predecessor tracts' purchase prices from the layer. The Wood County Recorder deed chain from 2023-09-05 is the pull.

## Regenerate

- Reach connectors: `watermark onboard bowling-green`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
- `parcel-assemblage.geojson`, in four steps (the Ottawa/Wilmington reviewed-assemblage recipe — the file spans **four unrelated owners**, so the `parcels --owner` path cannot pull it in one call):
  1. `watermark.hydrology.connectors.allen_gis.query_parcels_geojson("Name IN ('611190000003500','611190000029510','611300000001000','611300000002000','611190000037000','611190000033000','611190000036001','611190000034000','611190000008000','611190000035000','611190000009000','611190000025000','611190000006000','611200000011000','511210000002003')", settings=Settings(site="bowling-green"))` pulls the geometry + the base props (`parcel_id` / `owner` / `situs_address` / `owner_mailing_address` / `transfer_date`) through the `wood_gis` connector, with the schema's full `out_fields` in the same cached raw response. **Union the repeated rows per `parcel_id`** — they are disjoint parts, not duplicates.
  2. The remaining CAMA columns — the ones outside `WOOD_PARCEL_SCHEMA.out_fields` (`Identification__`, `Old_CAMA_Id`, `Legal_Description`, `Instrument_Code`, `Conveyance__`, `Deed_Number`, `Num_Transferred`, `Prc_Assng_Dist`) — are read as a second cached request against the same layer. `parcel_id_auditor` is the layer's own `Identification__`, the auditor's printed form (`J36-611-190000003500`); no per-parcel auditor URL is constructed, because the county's Schneider Beacon application is 403 to automated fetch and an unverified URL would not resolve.
  3. `township_zoning_2025_11_13` is a third cached request — the Middleton zoning polygons over the tightest envelope containing every committed Middleton parcel (`-83.6555,41.4455,-83.6220,41.4775`; an envelope-intersects query returns any polygon touching the box, so it cannot clip one that overlaps a parcel) — intersected **by area** with each parcel and aggregated **by district**, not by fabric parcel. A single "majority district" would report the 322.5-ac tract as 24.76% M-1, which is one of the seven old-fabric parcels under it rather than the parcel's zoning.
  4. `planar_acres` is measured in UTM 17N (EPSG:32617), plus the contiguity measurement and the detailed `bosc:provenance`. The connector's `transfer_date` is renamed `last_sale_date` in the same step, matching the other committed assemblages.
- `dominant_hsg` (profile + footprint record): `watermark.hydrology.connectors.ssurgo.dominant_hsg(<the parcel_role=liames_assembly subset>, grid_n=<n>, settings=Settings(site="bowling-green"))`. Run it on the **campus subset**, not the whole file — the Oppidan parcel is 4.83 mi away in a different landscape position. It returns **`C/D` at 6×6, 8×8, 10×10, 12×12 and 16×16**, with **428 of 428** interior points agreeing and no other group appearing at any density, so the letter is not a grid artefact. That dual rating **replaces** the profile's prior `[inference]` plain `D`.
