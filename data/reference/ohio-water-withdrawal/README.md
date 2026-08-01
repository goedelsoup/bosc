# Ohio water-withdrawal registry (Ohio DNR WWFRP)

Per-county registries of large water-withdrawal facilities, pulled from the **Ohio
DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program
(WWFRP)**. Under **R.C. 1521.16**, any facility (or combination of facilities) able
to withdraw **more than 100,000 gallons/day** (70 gpm) must register and file an
**annual water-use report**. Every facility, capacity, and monthly/annual amount
here was returned by the DNR's own public service — nothing is fabricated, inferred,
or backfilled. Regenerate a county with `watermark water-withdrawal --county <name>`
(defaults to the active site's county).

This is the **makeup-side** source for the cooling-water account (epic #1676). A
data-center facility modeled as "closed-loop-dry" (~0 water,
`watermark.hydrology.cooling_models`) that nonetheless reports a large annual
withdrawal is spending that water on evaporation + blowdown — so the reported
withdrawal is the single strongest tell of over-cycling, and the reported **return**
is its discharge peer (makeup − return ≈ consumptive).

## Source

The DNR publishes the registry as a public **ArcGIS FeatureServer**:

```text
https://services5.arcgis.com/ajRlmtxbNBjZggOT/arcgis/rest/services/Water_Withdrawal_Facility/FeatureServer
```

with one facility point layer, one-to-many to three annual-total tables (values in
**million gallons, MG**), joined on `RegistrationNumber`:

| id | name | role |
|----|------|------|
| 0 | `DSW_WaterWithdrawalFacility_A_GIS` | facility registry (point) |
| 3 | `DSW_waterwithdrawal_I_GW_Totals` | ground-water withdrawal, `Year` + Jan–Dec + `Total` |
| 2 | `DSW_waterwithdrawal_J_SW_Totals` | surface-water withdrawal, same shape |
| 1 | `DSW_waterwithdrawal_K_Return_Totals` | water **returned** to source, same shape |

The interactive **Water Withdrawal Facility Viewer** at `ohiodnr.gov/wwfacilitylocator`
is the human front-end over the same service.

## Method

`fetch_county(county)` runs four queries: the facility layer filtered to
`CountyName = '<county>'` (fields selected **by name**, never index), then each
annual-total table filtered to `RegistrationNumber IN (…) AND Year >= <since_year>` —
three fetches for the whole county, not three per facility. The layer id is part of
the cache key (it lives in the URL path, not the query string, so the three totals
tables share a `where` clause and would otherwise collide). Amounts are passed
through verbatim; a blank month is `null`. The facility **registry is kept in full**;
only the annual series are floored at `since_year` (default 2015).

## Files

Structured YAML, one per county, each with a `meta:` provenance block. `null` is a
genuine empty cell (never an estimate).

- [**`allen.yaml`**](allen.yaml) — Allen County, OH (the Lima reference build). 33
  registered facilities; the `meta:` block carries the facility / active / reporting
  counts and the per-use-type breakdown.
- [**`licking.yaml`**](licking.yaml) — Licking County, OH (New Albany — the Beech Road /
  Jersey Township data-center cluster, which sits in Licking 39089 rather than the
  Franklin-County city core). 55 registered facilities, 35 active, 46 with a 2015+
  report. Pulled for the B6 (#1686) positive-control review; see the blind-spot caveat
  below.

## Headline (Allen County, last pull)

**33** registered facilities — **21 active**, **25** with a 2015+ annual report.
By declared primary use: 7 Public, 7 Golf Course, 6 Industry, 5 Mineral Extraction,
4 Agriculture, 4 Misc. The largest reported 2024 withdrawers:

| reg# | facility | use | 2024 MGD | note |
|------|----------|-----|---------:|------|
| 01320 | Lima City PWS-Auglaize | Public | 16.70 | surface water |
| 01321 | Lima City PWS-Metzger & Lost Creek | Public | 3.61 | surface water |
| 01769 | PCS Nitrogen Ohio | Industry | 3.08 | ground water; **return 1,236 MG > withdrawal** |
| 01079 | National Lime & Stone-Lima Plant 1 | Mineral Extraction | 1.51 | ground water |
| 00386 | Lima Refining Company | Industry | 0.86 | ground water; return 1.3 MG |

## Headline (Licking County, last pull)

**55** registered facilities — **35 active**, **46** with a 2015+ annual report. By
declared primary use: 15 Golf Course, 13 Public, 10 Agriculture, 8 Misc, 7 Industry,
1 Mineral Extraction, 1 Hydro Fracturing. The three data-center-era registrations —
the reason this county was pulled (B6, #1686) — are the finding, not the volumes:

| reg# | facility | registered | 2024 MG | note |
|------|----------|-----------:|--------:|------|
| 03498 | Intel Corporation - New Albany, Ohio | 1.43 MGD (7 wells) | 15.91 | **14.11 MG returned (~89%)**; peaks May–June, troughs July–August |
| 03401 | AMAZON DATA SERVICES - CMHO50 NEW ALBANY | 0.15 MGD (1 well) | 0.02 | an *operating* hyperscale campus reporting ~nothing |
| 03575 | Amazon Data Services - Newton Court Site | 0.18 MGD (1 well) | 0.00 | registered 2024-04-20 |

Read caveat 6 before treating any of those as a cooling-water account.

## Known gaps & caveats (read before using)

1. **Ohio only.** The WWFRP is Ohio's registry. A non-Ohio watershed point (Fort
   Wayne, IN) has its own state service — the connector/CLI refuses cleanly rather
   than query the wrong state. The regional **Great Lakes–St. Lawrence River Water
   Use Database** (`waterusedata.glc.org`) is a *secondary, aggregate* source
   (basin / jurisdiction / use sector, **not** facility-level, for confidentiality),
   left as a documented lead — it cannot feed a per-facility water account.

2. **Self-reported.** Registration and the annual amounts are the registrant's own
   filings. A "primary use type" is the registrant's declared category. The reported
   quantity is `[verified]` for *what was reported*; anything derived from it (implied
   blowdown, cycles-of-concentration, or the once-through IT-load inversion via
   `implied_it_load_mw`) is `[inference]`.

3. **Registered capacity ≠ reported withdrawal.** `total_capacity_mgd` and the
   `*_capacity_mgd` fields are the *registered* capacity that triggered registration,
   not the amount actually withdrawn. The reported withdrawal lives on the annual
   `ground_water` / `surface_water` series.

4. **Return can exceed withdrawal.** Some facilities report returning more water than
   their metered withdrawal (e.g. PCS Nitrogen 2024: 1,236 MG returned vs 1,129 MG
   withdrawn) — non-contact cooling sourced elsewhere, multi-intake accounting, or a
   reporting artifact. Both figures are preserved verbatim; the A3 reconciliation
   (#1679) is what flags the anomaly. Never reconcile it away here.

5. **Annual window.** Series are floored at `since_year` (default 2015); older years
   remain live at the source (Lima City PWS surface-water records reach back to 1991).
   Raise the floor with `watermark water-withdrawal --since <year>`.

6. **A municipally-supplied facility is invisible here — a ~0 is not a dry loop
   (#1686).** The WWFRP registers withdrawals *from waters of the state*. A facility
   that **buys** its water from a public system withdraws nothing itself, so it either
   never appears or appears with a token registration and a ~0 annual report — while
   the city meter behind it records the real consumption. Licking County proves the
   point twice over: the *operating* Amazon Data Services campus at 2570 Beech Rd
   (03401) reports **0.02 MG for all of 2024**, and Intel — whose disclosed operating
   draw is ~5 MGD of **City of Columbus** water — reports 15.91 MG of construction-phase
   groundwater instead. Neither figure is that facility's cooling account. Reading a
   WWFRP ~0 as "documented ≈ 0 makeup" would silently corroborate every closed-loop
   claim in the network; the A3 harness therefore carries a `WaterRoute` and classifies
   such a facility **`route_blind`**, not `corroborated`
   (`watermark.hydrology.cooling_reconcile`). The record that *would* answer it is
   City-held (metered water-service consumption; the industrial pretreatment / IU
   permit), which is the C2 (#1688) records request.

## Field reference

Each entry under `facilities:` (`null` = the service returned nothing):

| field | source field | note |
|-------|--------------|------|
| registration_number | RegistrationNumber | the join key |
| name | Name | |
| county | CountyName | |
| primary_use_type | FacilityPrimaryUseType | Public / Industry / Agriculture / … |
| status | Status | Active / Inactive |
| total_capacity_mgd | FacilityTotCapacity | registered capacity, not withdrawal |
| gw_wells / sw_intakes | GWSTotNumWells / SWSTotNumIntakes | source-point counts |
| gw_capacity_mgd / sw_capacity_mgd | GWSTotWellsWithdrawalCap / SWSTotIntakesWithdrawalCap | |
| huc12 | HUC12 | |
| latitude / longitude | Latitude / Longitude | |
| registration_date / inactive_date | RegistrationDate / InactiveDate | ISO date |
| last_annual_report_year | LastAnnualReportYear | data-currency marker |
| ground_water / surface_water / returns | GW / SW / Return totals tables | `year`, `total_mg`, `count`, `monthly_mg` (MG) |

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `ohio-water-withdrawal-allen` — Allen County, OH water-withdrawal registry (Ohio DNR WWFRP)

Source: Ohio DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + annual water-use reports) · License: Ohio public record · Access: public · Site scope: site:lima · Refresh: annual (ttl 365d)

Regenerate: `watermark water-withdrawal --county Allen`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-water-withdrawal/allen.yaml` | application/x-yaml | no |

### `ohio-water-withdrawal-licking` — Licking County, OH water-withdrawal registry (Ohio DNR WWFRP)

Source: Ohio DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + annual water-use reports) · License: Ohio public record · Access: public · Site scope: site:new-albany · Refresh: annual (ttl 365d)

Regenerate: `watermark water-withdrawal --county Licking`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-water-withdrawal/licking.yaml` | application/x-yaml | no |

<!-- catalog:end -->
