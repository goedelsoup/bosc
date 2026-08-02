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
- [**`champaign.yaml`**](champaign.yaml) — Champaign County, OH (Urbana — the Thor
  Equities "Urbana Technology Hub" at SR-55 / US-68). 31 registered facilities, 25
  active, 20 with a 2015+ report. Pulled for the B4 (#1684) review of the origin
  closed-loop claim; the campus does **not** appear in it (caveat 6), and what does is
  its *supplier* — the City of Urbana's public water system (caveat 8).
- [**`wood.yaml`**](wood.yaml) — Wood County, OH (Bowling Green — the Meta "Project
  Accordion" campus and the Apollo generating plant, both in Middleton Township). 36
  registered facilities, 26 active, 31 with a 2015+ report. Pulled for the B5 (#1685)
  dry-cooler review; see the blind-spot caveat below and caveat 7.

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

## Headline (Champaign County, last pull)

**31** registered facilities — **25 active**, **20** with a 2015+ annual report. By
declared primary use: 12 Agriculture, 10 Public, 3 Mineral Extraction, 3 Misc, 2 Golf
Course, 1 Industry. The county was pulled for the B4 (#1684) review of the Urbana
Technology Hub, and the first finding is an **absence**: no Thor Equities, Highland55,
Urbana Owner, or Urbana Technology Hub registration exists. That is caveat 6 again — the
campus is contracted onto the City's water and sewer (Ord. 4612-24's Pre-Annexation
Agreement obliges the City to "provide water and sewer"), so it withdraws nothing from
waters of the state and the registry never sees it. What the registry *does* see is its
supplier:

| reg# | facility | use | registered | 2024 MG | 2024 MGD |
|------|----------|-----|-----------:|--------:|---------:|
| 01223 | Michael Farms-East | Agriculture | 11.78 MGD | 940.01 | 2.57 |
| **00837** | **Urbana City PWS OTP** (Old Troy Pike, 6 wells) | Public | **5.76 MGD** | **644.99** | **1.76** |
| 02036 | Freshwater Farms of Ohio | Misc | 0.11 MGD | 296.40 | 0.81 |
| 01704 | J. Rettenmaier USA, LP | Industry | 2.32 MGD | 292.00 | 0.80 |
| **03719** | **Urbana City PWS 29 WTP** (2047 State Rte 29 W, 3 wells) | Public | **3.00 MGD** | *no report yet* | — |

The City runs the two plants on the same high-yield buried-valley aquifer (its own water
division page describes both). Registration **03719 is dated 2026-03-26 and has filed no
annual report** — it brings the City's *registered* capacity to **8.76 MGD** against
**1.76 MGD** actually reported in 2024. Do **not** read that registration as capacity
added for the data center: the SR-29 plant is a long-standing City facility with its own
NPDES permit (**OH0137618**, effective, expiring 2027-12-31), so the 2026 date is a
registry event whose occasion is `[open]` — a records-request item, not a finding.

## Headline (Wood County, last pull)

**36** registered facilities — **26 active**, **31** with a 2015+ annual report. By
declared primary use: 9 Agriculture, 7 Mineral Extraction, 7 Misc, 7 Public, 5 Golf
Course, 1 Industry. Here the *absence* is the finding — no registration exists in this
county under Meta, Liames LLC, "Project Accordion", the Northwestern Water & Sewer
District, or any data-center name:

| reg# | facility | registered | 2024 MG | note |
|------|----------|-----------:|--------:|------|
| 00251 | BOWLING GREEN CITY PWS | 32.0 MGD (2 surface intakes) | 2,103.37 | ≈5.75 MGD; **the only registration in this county anywhere upstream of the campus** |
| 03717 | Apollo Power Generation Facility - TEMP | 0.27 MGD (1 surface intake) | — | registered **2026-03-26**, no annual report yet; HUC-12 `041000100703` — the campus's own |
| 02259 | CARDINAL AGGREGATE INC | 8.64 MGD | 365.10 | quarry dewatering; returns the same 365.10 MG |
| — | *Meta / Liames / Project Accordion* | **not registered** | — | buys finished water from NWWSD → the WWFRP never sees it (caveat 6) |

The Apollo row is what makes the Meta row readable: the register is demonstrably live at
this site in 2026, so the campus's non-appearance is a **route**, not a hole in coverage.

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

   Champaign County is the same shape at Urbana: the campus is absent from all 31
   registrations because the City's own Pre-Annexation Agreement obliges it to
   "provide water and sewer", so the campus withdraws nothing itself.

   Wood County adds the *control* for that caveat. Bowling Green's campus is likewise
   absent — but "Apollo Power Generation Facility - TEMP" (03717) registered a 0.27 MGD
   surface intake in the campus's own HUC-12 on **2026-03-26**. The register is live at
   this site; the campus is simply not in its reach.

7. **A public system's `returns` series is plant backwash, not a customer's discharge.**
   Bowling Green City PWS (00251) reports a 2024 return of **220.84 MG ≈ 0.605 MGD**,
   which numerically resembles the disputed ~600,000 gpd Meta demand figure that the B5
   review (#1685) turns on. It is not that figure and cannot settle it: it is the water
   treatment plant's own filter-backwash and residuals return — the plant discharges it
   under its own NPDES permit (`OH0030848`, McDowell WTP) — and every reported year in
   this file sits in a narrow **206–235 MG** band, the earliest of them **2016**, years
   before the campus existed. (The series is reported for 2016 and 2018–2024; 2015 and
   2017 carry no return row, so read it as a *stable reported band*, not as continuous
   annual coverage.) Read a `returns` row against the facility that reports it, never
   against one of its customers.

8. **The supplier is in here even when the facility is not — and it is the denominator
   (#1684).** Champaign County is the clean case: the Urbana campus is absent, but the
   City of Urbana's public water system is registered and reporting, so the registry
   still fixes the *scale* the claim has to be read against. The A3 harness carries that
   figure on its own `supplier_withdrawal` slot precisely so it is never mistaken for the
   facility's makeup — it is the *system's* account. Two rules follow. A supplier's
   withdrawal never corroborates or contradicts a facility's cooling claim (it aggregates
   every customer on the system). And a county's largest reported withdrawer is often not
   its city: Champaign's is an agricultural irrigator (Michael Farms-East, 940 MG in
   2024), 46% above the City PWS.

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

### `ohio-water-withdrawal-champaign` — Champaign County, OH water-withdrawal registry (Ohio DNR WWFRP)

Source: Ohio DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + annual water-use reports) · License: Ohio public record · Access: public · Site scope: site:urbana · Refresh: annual (ttl 365d)

Regenerate: `watermark water-withdrawal --county Champaign`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-water-withdrawal/champaign.yaml` | application/x-yaml | no |

### `ohio-water-withdrawal-licking` — Licking County, OH water-withdrawal registry (Ohio DNR WWFRP)

Source: Ohio DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + annual water-use reports) · License: Ohio public record · Access: public · Site scope: site:new-albany · Refresh: annual (ttl 365d)

Regenerate: `watermark water-withdrawal --county Licking`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-water-withdrawal/licking.yaml` | application/x-yaml | no |

### `ohio-water-withdrawal-wood` — Wood County, OH water-withdrawal registry (Ohio DNR WWFRP)

Source: Ohio DNR, Division of Water Resources — Water Withdrawal Facilities Registration Program (WWFRP), R.C. 1521.16 (>100,000 gpd registration + annual water-use reports) · License: Ohio public record · Access: public · Site scope: site:bowling-green · Refresh: annual (ttl 365d)

Regenerate: `watermark water-withdrawal --county Wood`

| file | type | lfs |
| --- | --- | --- |
| `reference/ohio-water-withdrawal/wood.yaml` | application/x-yaml | no |

<!-- catalog:end -->
