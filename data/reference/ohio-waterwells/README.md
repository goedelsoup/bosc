---
scope: site:lima
scope_note: >-
  The committed censuses are Allen County's well census and the Lima campus dewatering wellfield,
  both owned by the reference build alone. The R.C. 1521.05 source and the pull method are
  statewide: a peer that pulls its own county's census registers it and gets its own page.
---

# Ohio water-well-log census (Ohio DNR, Division of Water Resources)

Per-county censuses of logged water wells, pulled from the **Ohio DNR, Division of
Water Resources** well-log database. Under **R.C. 1521.05** every water-well
contractor files a **completion / sealing log** with the Division; the (nightly-
refreshed) database is published as a public **ArcGIS MapServer** — one point per
well. Every location, depth, aquifer, static level, and reported yield here was
returned by the DNR's own public service — nothing is fabricated, inferred, or
backfilled. Regenerate a county with `watermark waterwells --county <name>`
(defaults to the active site's county).

This is the **groundwater** peer of the surface-water supply model
(`watermark.hydrology.supply`). The census is the population of private and public
wells whose **static water levels** and **reported yields** are the empirical basis
for an `[inference]` aquifer-parameter estimate (`watermark.hydrology.aquifer`) and
the well-**drawdown** ("cone of depression") thread the data-center cooling
withdrawal implicates — the "area well concerns" that surface in the PAAC board
record (2026-03-30). It is **not** a withdrawal registry: for who is *licensed* to
withdraw >100,000 gpd, see the sibling `data/reference/ohio-water-withdrawal/`.

## Source

The DNR publishes the well-log database as a public **ArcGIS MapServer**:

```text
https://gis2.ohiodnr.gov/arcgis/rest/services/DSW_Services/waterwells/MapServer
```

with a single well-point layer:

| id | role |
|----|------|
| 0 | well-log points — use type, aquifer, total depth, static water level, reported test yield, casing, coordinates |

The interactive **Water Well Locator** at `waterwells.ohiodnr.gov` is the human
front-end over the same well-log database (and links each well to its scanned
drilling-report PDF).

## Method

`fetch_county(county)` runs one query: layer 0 filtered to `COUNTY = '<COUNTY>'`
(the service stores the county uppercase), fields selected **by name** (never
index), paged at 1,000 (the hosted `maxRecordCount`) to completion on
`exceededTransferLimit`. Values are passed through verbatim; a blank field is an
empty cell, never a fabricated 0. Wells are OBJECTID-sorted, so an unchanged pull
regenerates byte-identical CSV.

## Files

A flat well census is naturally tabular, so it lands as **CSV** (one row per well,
provenance in this README) — the EPA-ECHO reference-dataset convention, not the
nested-YAML shape the WWFRP registry needs.

- [**`allen.csv`**](allen.csv) — Allen County, OH (the Lima reference build). 6,864
  logged wells.

## Headline (Allen County, last pull)

**6,864** logged wells (all record-type `W`, well). Completion dates span
**1925 → 2020**. All 6,864 carry coordinates (NAD83); locational quality varies —
1,061 surveyed GPS, 2,626 digitized, 2,360 address-geocoded, 37 digital-map, 770
unrecorded (see caveat 3).

By **use** (top): 5,808 Domestic · 331 Monitor · 105 Public/Semi-Public · 47
Agric/Irrig · 21 Commercial · 17 Municipal · 10 Industrial · 5 Heating/Cooling ·
493 unrecorded. **5,808 domestic wells is the private-well population behind the
"area well concerns."**

By **aquifer**: 4,441 Limestone · 1,216 Gravel · 376 Sand & Gravel · 160 Shale ·
101 Sand · 158 unrecorded — a bedrock-carbonate-dominated system, consistent with
the Lima area's limestone aquifer.

Reported ranges (p50 / p90): **total depth** 70 / 160 ft (max 1,310) · **static
water level** 27 / 59 ft below surface (n=6,331) · **test yield** 15 / 25 gpm
(n=5,833).

## Known gaps & caveats (read before using)

1. **Ohio only.** This is Ohio's well-log service. A non-Ohio watershed point (Fort
   Wayne, IN) has its own state service — the connector/CLI refuses cleanly rather
   than query the wrong state.

2. **No pumping-water-level column — so no true specific capacity.** The service
   reports a **static** (rest) level and a **test yield** (gpm), but **not** the
   pumping water level during the yield test. Specific capacity (yield ÷ drawdown)
   and therefore a per-well transmissivity are **not** derivable from a single
   record. The aquifer-parameter layer (`watermark.hydrology.aquifer`) leans instead
   on the static-water-level surface, the yield distribution, and **cited literature**
   aquifer properties by aquifer type — all `[inference]`, never presented as
   measured.

3. **Self-reported, and locational quality varies.** Every figure is the drilling
   contractor's own log entry — `[verified]` for *what the log states*, which is not
   the same as field-verified truth (a transcription can be wrong). `coord_source`
   records how each point was located: a `GEOCODE`d address or `DIGITIZED` point is
   coarser than a `GLOBAL POSITIONING SYSTEM` fix, and gates spatial confidence for
   any drawdown-cone intersection.

4. **Owner / name / street columns are not ingested.** The service exposes
   `OWNER` / `LAST_NAME` / `STREETNAME` / `HOUSE_NO` — private residents' PII the
   model does not need. The connector selects only locations and hydraulics; the
   committed CSV carries no personal identifiers.

5. **A census, not a time series.** Each row is the well's completion-log snapshot,
   not repeat water-level measurements. For monitoring-well water-level *history*,
   USGS NWIS groundwater (`countyCd=39003`) is the complementary source.

6. **`TOTAL_DEPTH = 0` and blank aquifers appear** for some non-standard logs
   (dry holes, sealings, incomplete transcriptions). Preserved verbatim; downstream
   code filters on `record_type` / non-null fields rather than mutating the census.

## Field reference

CSV columns (an empty cell = the service returned nothing):

| column | source field | note |
|--------|--------------|------|
| object_id | OBJECTID | stable id / sort key |
| record_type | TYPE | `W` = well |
| well_use | WELL_USE | Domestic / Monitor / Public / Heating-Cooling / … |
| longitude / latitude | LONG83 / LAT83 | NAD83 decimal degrees |
| coord_source | SOURCE_OF_COORD | GPS / digitized / geocoded — locational quality |
| county | COUNTY | stored uppercase |
| township | TOWNSHIP | |
| completion_date | COMPLETION_DATE | ISO date (from epoch-ms) |
| total_depth_ft | TOTAL_DEPTH | reported total depth |
| dem_elev_ft | DEM_ELEV | DEM-sampled ground elevation |
| aquifer_type | AQUIFER_TYPE | Limestone / Gravel / Sand & Gravel / Shale / … |
| drill_type | DRILL_TYPE | |
| test_rate_gpm | TEST_RATE_GPM | reported yield-test rate |
| static_water_level_ft | STATIC_WATER_LEVEL_FT | rest level below surface |
| case_length_ft | CASE_LENGTH | |
| bedrock_depth_ft | BEDROCK_DEPTH | |
| well_no | WELL_NO | DNR well number |

## Campus dewatering wellfield (`lima-campus-dewatering.csv`)

A distinct, curated companion dataset: the **44 construction-dewatering wells** the
developer ("LMA") installed along **North Cole Street at the BOSC/data-center campus**
(American Township) to lower the water table for **site grading**. All shallow (23–41 ft)
in the unconfined **sand & gravel** aquifer, pumping **75–100 gpm** each (~4.9 MGD of
combined capacity). Installed **Dec 16 2025 – Feb 12 2026**; **43 were sealed May 26–28,
2026**, leaving **one active well** (record `3027949`).

This is the documented groundwater stress behind the residents' "area well concerns" —
distinct from the county census above (the *population* of wells) and from the hypothetical
cooling-makeup drawdown scenario (`watermark.hydrology.drawdown`). Its cone of impact is
modeled by `watermark.hydrology.dewatering` (per-well Cooper-Jacob cones superimposed).

- **Source:** Ohio DNR Water Well Locator (`waterwells.ohiodnr.gov`) — the well-log
  export (`WaterWell_CSV`) reconciled with the **sealing-report export**
  (`SealingReport_CSV`), both pulled **2026-07-28**. **Not connector-regenerable:** the
  live ArcGIS MapServer the `ohio_waterwells` connector reads now shows only the **1 active**
  `DEWATERING WELL` in Allen County — the 43 sealed wells have dropped off the active layer,
  so only this manual export preserves the full operation. Owner is the operator company
  ("LMA"), not a private resident; no personal PII.
- **Method:** each well is matched to its sealing record by nearest coordinate (≤ 50 ft);
  the one well with no sealing within 50 ft (`3027949`, 58 ft to the nearest) is the active
  one. `sealed_date` is that nearest sealing's date; empty = active.
- **Caveats:** driller-reported figures are `[verified]` for *what the log states*; the
  cone-of-impact drawdowns derived from them are `[inference]` (literature K, Cooper-Jacob
  screening on an unconfined aquifer). `test_rate_gpm` is the well's yield-test capacity, an
  **upper bound** on the sustained dewatering rate; installs and sealings were staged, so a
  simultaneous-full-rate composite is a bound on concurrency.
- **Columns:** `record_no`, `operator`, `township`, `aquifer_type`, `well_use`,
  `static_water_level_ft`, `test_rate_gpm`, `total_depth_ft`, `completion_date`,
  `sealed_date` (empty = active), `longitude`, `latitude` (NAD83).

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `lima-campus-dewatering` — Lima campus construction-dewatering wellfield (Ohio DNR)

Source: Ohio DNR Water Well Locator (waterwells.ohiodnr.gov) — well-log export reconciled with the sealing-report export, both pulled 2026-07-28. Not connector-regenerable: the live MapServer now shows only the 1 active DEWATERING WELL (the 43 sealed wells dropped off the active layer). · License: Ohio public record · Access: public · Site scope: site:lima · Refresh: on-demand, last 2026-07-28

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-waterwells/lima-campus-dewatering.csv` | text/csv | no |

### `ohio-waterwells-allen` — Allen County, OH water-well-log census (Ohio DNR)

Source: Ohio DNR, Division of Water Resources — water-well-log database, R.C. 1521.05 (contractor completion/sealing logs), public ArcGIS MapServer (layer 0) · License: Ohio public record · Access: public · Site scope: site:lima · Refresh: annual (ttl 365d)

Regenerate: `watermark waterwells --county Allen`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-waterwells/allen.csv` | text/csv | no |

<!-- catalog:end -->
