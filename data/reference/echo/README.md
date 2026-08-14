---
scope: basin:maumee
scope_note: >-
  One NPDES inventory is pulled per basin and shared by every site that drains it, so this page
  documents the Maumee fileset for the Maumee sites reading it. The Lima-keyed columns it
  describes are fields of that shared basin file, not claims about the reading site.
---

# Network NPDES inventories (EPA ECHO)

Verified inventories of CWA-permitted facilities per watershed basin, pulled from
EPA's **ECHO Clean Water Act REST services** (`cwa_rest_services`). Every facility,
NPDES ID, and value here was returned by the ECHO API — nothing is fabricated or
inferred. The one exception is a **curated receiving water**, which is never invented
either: it is a document-cited correction declared in the
[curated overlay](#curated-receiving-water-the-refresh-path) and always marked as such on
the row. Five basins are committed today, each with its own
`<basin>-wwtp.*` fileset: the **Maumee** (`watermark npdes`, the default), the **Great
Miami** (`watermark npdes --basin great-miami`, the Miami-basin sites — Urbana, Springfield,
WPAFB, Troy-Piqua, Hamilton-Middletown), the **Little Miami** (`watermark npdes --basin
little-miami`, the Scenic-River sites Xenia and Wilmington / Todd Fork, a single HUC-8
`05090202`), **Ohio Brush Creek** (`watermark npdes --basin ohio-brush-creek`, the
direct-to-Ohio-River branch at West Union / Adams County — a single HUC-8 `05090201`; #1120),
and the **Portage** (`watermark npdes --basin portage`, the direct-to-Lake-Erie branch at
Bowling Green / Middleton Township — a single HUC-8 `04100010`; #1433).
One further basin is **registered in the connector but not yet committed**:
the **Scioto** (`--basin scioto`, the Columbus / New Albany data-center cluster) — deferred
on an ECHO 300/hr throttle (HTTP 429). Run `watermark npdes --basin scioto` to write its
`<basin>-wwtp.*` fileset when ECHO is healthy. Add a basin by registering it in
`watermark.hydrology.connectors.echo`; never hardcode one into the connector.

## What the watershed is

Seven USGS **HUC-8** subbasins (subregion 0410, Western Lake Erie), queried one at
a time via `p_huc`:

| HUC-8 | subbasin | states |
|-------|----------|--------|
| 04100003 | St. Joseph | IN, MI, OH |
| 04100004 | St. Marys | IN, OH |
| 04100005 | Upper Maumee | IN, OH |
| 04100006 | Tiffin | OH, MI |
| 04100007 | Auglaize | OH |
| 04100008 | Blanchard | OH |
| 04100009 | Lower Maumee | OH |

Adjacent WLE subbasins **04100001** (Ottawa-Stony), **04100002** (Raisin), and
**04100010** (Cedar-Portage) are *not* Maumee drainage and are excluded.

## Files

Structured YAML, each with a `meta:` provenance block. `null` is a genuine ECHO
null (never an estimate); `true`/`false` flags are booleans.

- [**`maumee-wwtp.all-npdes.yaml`**](maumee-wwtp.all-npdes.yaml) — `meta:` +
  `facilities:` list of all active CWA-permitted facilities ECHO returns for the
  seven HUC-8s, deduplicated to one record per facility by FRS Registry ID
  (POTW + non-POTW + federal + private/package).
- [**`maumee-wwtp.potw.yaml`**](maumee-wwtp.potw.yaml) — same shape, restricted to
  the subset flagged `POTW` by ECHO's `CWPFacilityTypeIndicator` (municipal plants).
- [**`maumee-wwtp.huc-counts.yaml`**](maumee-wwtp.huc-counts.yaml) — `huc_counts:`
  per-HUC manifest (ECHO's reported count vs. rows actually pulled — they match, no
  pagination loss) plus `totals:` (raw / deduped / potw).

The three files above are **regenerated output** — never hand-edit them, the next pull
overwrites the edit. Reviewed corrections go in the one hand-authored file here:

- [**`curation/maumee-wwtp.receiving-water.yaml`**](curation/maumee-wwtp.receiving-water.yaml)
  — the curated receiving-water overlay re-applied on every pull (see below).

## Method

Per HUC-8: `get_facilities` (`p_huc=<HUC8>`, `p_act=Y`) returns a QID + summary
count; `get_qid` pages the rows as JSON, columns selected **by name** (mapped to
ECHO ColumnIDs). Deduplication keys on **FRS Registry ID**; a facility holding
multiple permits keeps its primary NPDES ID with the rest in
`npdes_ids_secondary`. Two distinct FRS IDs sharing a name are never collapsed.

Verified against `cwa_rest_services` metadata **CWA v2017-10-13 1325** (260 result
columns). Numbers come from the API's structured fields, not any text layer.

## Curated receiving water (the refresh path)

ECHO's `CWPStateWaterBodyName` is null for most of the Ohio rows (66 of 832 carry one),
including plants whose receiving water an Ohio EPA permit names outright. Those
corrections used to be typed straight into the files above — so the next
`watermark npdes --basin maumee` silently reverted them and regressed every downstream
screen (Lima WWTP and Van Wert WWTP fell back to `no_receiving_water`, taking the basin's
two starkest effluent-dominance findings with them). That is why the basin inventory sat
un-refreshed: a re-pull cost reviewed data.

Corrections now live in
[`curation/maumee-wwtp.receiving-water.yaml`](curation/maumee-wwtp.receiving-water.yaml)
and the connector re-applies them on **every** pull, so a refresh is non-destructive. Each
entry carries the FRS Registry ID it pins, the document that names the receiving water, and
the ECHO value observed when it was reviewed. Two modes:

- **`mode: field`** — the curated value is written into `receiving_water` (so derived flags
  like `ottawa_discharge` and every downstream screen see it), with ECHO's verbatim value
  preserved alongside as `receiving_water_echo` and the row marked
  `receiving_water_source: curated`.
- **`mode: caveat`** — `receiving_water` keeps mirroring ECHO verbatim and the correction
  rides beside it on `receiving_water_documented`. This is the reviewed posture for
  OH0135569 (#379), whose correction comes from ECHO's own facility report rather than an
  independent regulatory document, and which nothing downstream screens on.

**The overlay never overrides live ECHO silently.** If ECHO has moved off the reviewed
`echo_value`, the pull names what changed — and whether it can still write depends on what
moved:

- **`conflict`** (ECHO now supplies a *different* water) and **`stale`** (the facility is
  gone from a pull that covered its subbasin — a terminated or re-keyed permit) **refuse the
  write**. Nothing is emitted until a human reconciles the document against ECHO.
- **`superseded`** (ECHO now supplies the *same* water itself) does **not** block: the
  refresh completes normally, ECHO's own value stands in the field, the row carries no
  curation provenance, and the run reports that the overlay entry is now redundant and can
  be retired.

Each pull prints an outcome table and records the applied set in every emitted file's
`meta.receiving_water_curation`.

Adding a basin's overlay is a new `curation/<basin>-wwtp.receiving-water.yaml` plus a
catalog entry — no code change. A basin with no overlay pulls exactly as before.

## Headline counts (last pull)

**2026-07-28** (whole-basin refresh, #1698): 1,662 active-permit rows across the 7 HUC-8s
→ **1,579 facilities** after FRS dedup: **130 POTW**, 1,447 non-POTW, 2 federal. POTW
design flow present for 113/130 (the 17 blanks are mostly Michigan general-permit
stabilization lagoons that don't report a design-flow number).

Up from 1,006 facilities / 129 POTW at the previous pull. Nearly all of the growth (591 of
593 new rows) is **General Permit Covered Facility** coverage ECHO's WATERS geocoding now
resolves into these HUC-8s — construction/industrial stormwater, concentrated in the Lower
Maumee — not new wastewater outfalls; 20 expired Indiana construction permits dropped out.
Movements worth knowing about on the POTW side:

- **Toledo Bay View Park WWTP** (OH0027740, → Maumee River) is new to the inventory. ECHO
  carries no design flow for it, so it is counted but not screened.
- **Shawnee II WWTP** (OH0022675) design flow moved 2.0 → **3.0 MGD**, converging on the
  figure the routed model already used from Ohio EPA fact sheet 2PK00002.
- **Harrison Lake State Park** was re-keyed from an individual permit (OH0036170) to a
  general permit (OHGC10322) and lost its receiving water; **Miller City HS** gained a
  design flow (0.008 MGD) and lost its receiving water. Both move to unscreened.

## Great Miami River basin (`great-miami-wwtp.*`, #446/#455)

The Great Miami (subregion 0508, an Ohio River tributary) is two Ohio HUC-8 subbasins —
same `p_huc` method and field shape as the Maumee, but the Lima-specific
`in_lima_subbasin` / `ottawa_discharge` flags are omitted (a Maumee-only concept):

| HUC-8 | subbasin |
|-------|----------|
| 05080001 | Upper Great Miami (includes the Mad River) |
| 05080002 | Lower Great Miami |

Whitewater (**05080003**) is predominantly Indiana drainage and is excluded (mirroring
the Maumee's excluded WLE neighbors). **Last pull:** 289 active-permit rows across the 2
HUC-8s → **286 facilities** after FRS dedup, **81 POTW**. The **City of Springfield WWTP**
(OH0027481, 25 MGD, → Mad River) is present, but ECHO carries no receiving-water value for
it, so the basin-screen reports it unscreened rather than guess — the same gap the Maumee's
curated overlay closes for Lima WWTP, and a candidate for a Great Miami overlay of its own
once its receiving water is document-cited. The **Hamilton WRF** (OH0025445, 32 MGD, the
basin's largest POTW) is a second such candidate for a different reason: ECHO gives it
`GREAT MIAMI RIVER, TWO MILE CREEK`, two different waters, and since #1120 a compound
receiving water is refused rather than resolved to the larger of the two — so it reports
`no_7q10`. The Little Miami's Lower East Fork Regional WWTP (OH0049379) and Yellow Springs
WWTP (OH0028215) are in the same position. A document-cited overlay entry naming the outfall's
actual water is what moves any of them back into the screened set.

Files: `great-miami-wwtp.all-npdes.yaml`,
`great-miami-wwtp.potw.yaml`, `great-miami-wwtp.huc-counts.yaml`. Those counts are from an
earlier pull; the Maumee refresh (#1698) did not re-pull this basin.

## Ohio Brush Creek basin (`ohio-brush-creek-wwtp.*`, #1120)

The network's first **direct-to-Ohio-River** branch — West Union / Adams County (#1117),
which drains straight to the Ohio with no Scioto or Miami loop. One HUC-8, same `p_huc`
method and field shape as the others, no Lima-specific flags:

| HUC-8 | subbasin |
|-------|----------|
| 05090201 | Ohio Brush-Whiteoak |

**Read the scope before reading the file.** Unlike every other basin here, this one's slug
is a part naming a whole. `maumee` covers seven subbasins because they are all one river's
tree; 05090201 is a WBD cataloging unit spanning **both banks of the Ohio River**, and the
pull says so without any outside dataset: its rows land in Kentucky counties (Campbell,
Pendleton, Bracken, Mason, Lewis) and Ohio ones (Clermont, Brown, Adams, Highland, Scioto),
which face each other across the river. Several separate creeks reach the Ohio inside the
unit — West Union's own receiver, Beasley Fork, drains to Ohio Brush Creek, while Whiteoak,
Twelve Mile, Four Mile and the rest reach the river independently. Each is therefore a
**sibling** of Ohio Brush Creek, not one of its headwaters: a discharger on one is neither
upstream nor downstream of a discharger on another.

> **No HUC-12 count or area is stated here.** The unit's WBD composition (how many HUC-12s
> it holds, how many of them are Ohio Brush Creek, its area) is not in the corpus — no WBD
> extract for 05090201 is committed, and `watermark wbd` has only ever been run for Lima's
> campus HUCs. Those figures were asserted in an earlier draft of this file and of the
> connector's caveats without a source behind them; they have been removed rather than
> given a citation they never had. Pulling the WBD HU12 sublayer for 05090201 would make
> them citable and is open work.

**Last pull (2026-08-05):** 273 active-permit rows in the one HUC-8 → **261 facilities**
after FRS dedup, **23 POTW** (17.87 MGD of design flow, present for 22 of 23). The
two-bank geography makes it **majority-Kentucky**: 168 of the 261 carry KY permits
(Campbell 111, Lewis 22, Mason 22, Bracken 11, Pendleton 2) against 93 Ohio ones (Clermont
20, Brown 15, Adams 11, Scioto 3, Highland 1, and 43 for which ECHO returned no county).
Completeness therefore needs a cross-check against **both** Ohio EPA and Kentucky DOW; only
what ECHO federalizes is reflected here.

### What screens, and what does not

`receiving_water` is null for **118 of the 261** rows in that pull, and for 13 of the 23
POTWs. The assimilative screen (`watermark --site west-union basin-screen`) reports:

| outcome | POTWs | why |
|---|---|---|
| screened | 5 | name the Ohio River and nothing else; dilution 1,799:1 (Maysville STP) to 95,570:1, all `ok` |
| no receiving water | 13 | ECHO carries no `CWPStateWaterBodyName` |
| no 7Q10 | 5 | a named receiver the screen cannot use — see below |

The five `no 7Q10` rows are three different failures, and conflating them would misread all
three. **Three are ungaged tributaries**: Felicity WWTP → Bear Creek, Georgetown WWTP → Town
Run, Lewis County SD #1 → Grog Branch. **One is not a water body at all**: Western Mason
County Sanitation District reads `DOWNING DRIVE, MAYSVILLE STP` — a street address and the
name of the plant it sends flow to, i.e. a sewer connection, which is why it also has no
design flow of its own. **One names two different waters**: New Richmond WWTP (OH0021156,
1.1 MGD) reads `OHIO RIVER, TWELVE MILE CREEK`, and ECHO's field is a permit-level aggregate
over every outfall, so nothing in it says which water carries the design flow. The screen
refuses that row rather than crediting it with the larger of the two — at the Ohio's 9,464
cfs it would have published a 5,560:1 `ok` for a plant that may discharge to the creek.

Two consequences worth stating plainly rather than leaving to be inferred:

1. **No facility in this inventory names Ohio Brush Creek as its receiving water.** The
   creek's committed 7Q10 (0.50 cfs, USGS 03237500) is a denominator standing ready, not one
   in use.
2. **The West Union WWTP (OH0028088, 0.7 MGD) does not screen**, and neither do Peebles,
   Seaman or Winchester — the four Adams County POTWs off the Ohio River mainstem are
   exactly the four ECHO leaves blank. The `SiteProfile` attributes West Union's discharge to
   **Beasley Fork** on the Ohio EPA NPDES service, but that is a live-service reading, not a
   committed document, so it cannot support a curated-overlay entry (each entry carries the
   instrument that names the water). The 1993 consent order in the corpus is explicit that it
   **never names a receiving water**. Closing this needs the Ohio EPA permit for `0PC00019`
   ingested — and even then Beasley Fork is ungaged, so the plant would move from
   `no_receiving_water` to `no_7q10`, not into the screened set. Both halves are open work;
   neither is closed by inference.

The screened five exist because #1120 added the **Ohio River** mainstem to
`data/reference/hydrology/mainstem-gages.yaml` — USGS 03216600 at Greenup Dam, chosen as the
*upstream-end* gage: it sits east of every facility in the pull, on a river that only gains
drainage area downstream, so its 62,000 mi² understates what each facility's own reach
carries and the screen cannot overstate dilution. That entry's note — copied into
`low-flow-7q10.derived.yaml`, the file the screen actually reads — records what a reader is
owed about it: the mainstem is navigation-regulated in fact and unannotated on the record,
and one gage standing for the unit's whole river frontage makes a dilution ratio a magnitude
check rather than a reach-specific finding. The entry is **scoped to this basin**
(`basins: [ohio-brush-creek]`), because that conservatism argument is geographic: the
Muskingum and Mahoning basins meet the Ohio hundreds of river miles above Greenup, where the
river carries a fraction of the drainage area gaged here, so serving this denominator on the
bare name `OHIO RIVER` network-wide would commit exactly the overstatement it avoids.

Files: `ohio-brush-creek-wwtp.all-npdes.yaml`, `ohio-brush-creek-wwtp.potw.yaml`,
`ohio-brush-creek-wwtp.huc-counts.yaml`. There is no curated receiving-water overlay for this
basin yet.

## Portage River basin (`portage-wwtp.*`, #1433)

The network's first **direct-to-Lake-Erie** branch that does not run through the Maumee —
Bowling Green / Middleton Township (#1433), whose Water Pollution Control plant discharges to
Poe Ditch and thence to the North Branch Portage River. One HUC-8, the same `p_huc` method
and field shape as the others:

| HUC-8 | subbasin |
|-------|----------|
| 04100010 | Cedar-Portage |

**Read the scope before reading the file.** Like Ohio Brush Creek above, this slug is a part
naming a whole: 04100010 "Cedar-Portage" is a WBD cataloging unit covering the Portage River
*and* the frontal Lake Erie drainage beside it, and the pull says so without any outside
dataset. Its rows include the Lake Erie islands — Put-in-Bay, Kelleys Island State Park,
ODNR's South Bass Island campground — plus Catawba Island and Oregon on Maumee Bay, none of
which are Portage River drainage at all. Each is a **sibling** of the Portage, not one of its
headwaters: neither upstream nor downstream of a Portage discharger, and never entitled to
borrow its low flow.

The split is live at the network's own watershed point. Bowling Green's data-center campus
sits in HUC-12 `041000100703` (Cedar Creek-Frontal Lake Erie) while the city's WPC plant
discharges in `041000100301` (N Br Portage/Poe Ditch), so campus construction runoff does not
reach the plant's receiving water — a fact established from the permits in #1439 and
reproduced by this unit's own composition.

**Last pull (2026-08-14):** 310 active-permit rows in the one HUC-8 → **296 facilities**
after FRS dedup, **26 POTW** (34.858 MGD of design flow, present for 23 of 26). Ohio-only,
spread across seven counties — for the POTWs, Ottawa 10, Wood 9, Seneca 2, Sandusky 2, Erie
1, Hancock 1, Lucas 1. **Bowling Green (OH0024139, 10.0 MGD) is the largest POTW in the
basin**, ahead of Fostoria's 8.25 and Oregon's 8.0.

> **ECHO's county spelling is not normalized in this pull.** Both `LUCAS` and `LUCAS COUNTY`
> come back, likewise Ottawa and Wood, and 154 of the 296 rows carry no county at all. A
> county tally taken off this file under-counts rather than resolving to zero, and must fold
> the two spellings together before it means anything.

### What screens, and what does not

`receiving_water` is null for **261 of the 296** rows in that pull, and for 21 of the 26
POTWs. The assimilative screen (`watermark --site bowling-green basin-screen`) reports:

| outcome | POTWs | why |
|---|---|---|
| screened | 1 | Bowling Green, on its own permit-bound at-outfall 7Q10 — **0.024:1, `violation`** |
| no receiving water | 21 | ECHO carries no `CWPStateWaterBodyName` |
| no 7Q10 | 4 | a named receiver the screen cannot use — see below |

The one screened row is Bowling Green itself, and it does **not** screen against a basin proxy:
`poe ditch (bowling green wpc outfall, rm 2.5)` in `low-flow-7q10.yaml` is `permits:`-bound to
`OH0024139` / `2PD00009`, so `screen_facility` takes the permit match ahead of any name match.
The binding is safe here in the way the Defiance entry's note requires — the fact sheet's 10 MGD
average design flow and the 10.0 MGD ECHO carries for this permit agree exactly, so a
permit-cited numerator is paired with a denominator that permit corroborates. The **bare** name
`poe ditch` deliberately resolves to nothing, so a future second discharger on the ditch cannot
inherit a low flow computed at this outfall alone.

The four remaining named receivers are Algire Creek (McComb), Wolf Creek (Evergreen Poplar),
Turtle Creek (Fenwick Marina) and `PORTAGE RIVER, URIE DITCH` (Bloomdale). Three are ungaged
tributaries with no NWIS daily-discharge record meeting the 20-climatic-year floor. The fourth
**names two different waters**, and ECHO's field is a permit-level aggregate over every outfall,
so nothing in it says which one carries the design flow — the screen refuses that row rather
than crediting it with the larger.

**No Portage mainstem gage is registered in `mainstem-gages.yaml`, and that is deliberate.**
Registering one would screen exactly zero rows today — the only mainstem-naming row is
Bloomdale's compound, which is refused on its own terms — while creating a live hazard: a
mainstem gage integrates a drainage area far larger than the North Branch or Poe Ditch above
it, so any later alias reaching Bowling Green's outfall would overstate its dilution by
orders of magnitude. That is the same defect class as the 17x overstatements found at Sidney
(#1992) and in #1995's routing table, and the cheapest place to not commit it is here.

**Bowling Green's own outfall is screened anyway, by the better number.** Ohio EPA's fact
sheet for `2PD00009` publishes a drainage-area-adjusted **7Q10 of 0.364 cfs** at the outfall
(Table 12, from USGS 04195500 over 1951-97) — the regulator's own denominator for this reach,
carried in `reference/hydrology/bowling-green/routing.yaml` with `source: document`. A cited
permit-scoped low flow beats a basin-wide screening proxy wherever one exists, which is why
this basin's zero screened rows are a statement about the other twenty-five plants and not
about the site.

One more property of the basin worth stating plainly: it drains a heavily tile-drained
lakebed plain (the Great Black Swamp), so summer low flows are small and a large share of the
receiving water below a POTW outfall is that plant's own effluent. Bowling Green's 15.47 cfs
design discharge against a 0.364 cfs 7Q10 is roughly **42x the river it enters**. Read an
assimilative ratio here as a statement about an effluent-dominated stream, not a diluted one.

Files: `portage-wwtp.all-npdes.yaml`, `portage-wwtp.potw.yaml`,
`portage-wwtp.huc-counts.yaml`. There is no curated receiving-water overlay for this basin
yet — closing the 21 null receivers means reading 21 permits' fact sheets, and each
correction needs its own citation.

## Known gaps & caveats (read before using)

1. **No CWNS ID.** The ECHO CWA facility service has *no* CWNS column, so the
   requested CWNS cross-check for POTWs is not available from this API. POTW
   classification here rests solely on `CWPFacilityTypeIndicator`. (CWNS IDs would
   have to come from the Clean Watersheds Needs Survey, separately.)

2. **HUC geocoding (WATERS).** ECHO links facilities to HUCs via WATERS; not every
   NPDES ID geocodes, so a pure watershed query can miss facilities whose
   coordinates didn't resolve. `RadWBDHu8` is frequently null in the raw data — we
   use `FacDerivedHuc` (which reliably reflects the queried HUC-8) instead.

3. **Cross-state completeness.** Four subbasins (St. Joseph, St. Marys, Upper
   Maumee, Tiffin) extend into Indiana and/or Michigan. ECHO's `p_huc` *did*
   return IN/MI facilities (e.g. Auburn IN, Amboy Twp MI), but for a complete
   inventory this pull should still be cross-checked against **Ohio EPA**,
   **Indiana IDEM**, and **Michigan EGLE** NPDES permit lists; any facility in a
   state list but absent from ECHO should be flagged. *(Not yet performed — those
   state datasets are a follow-up; this is an ECHO-only inventory.)*

4. **"All" is the active CWA universe, not just process wastewater.** `p_act=Y`
   includes some non-NPDES Industrial-User/pretreatment permits and stormwater
   general permits alongside true wastewater dischargers. The `permit_type`
   (`CWPPermitTypeDesc`) and `facility_type` fields make the distinction visible
   — filter on them rather than assuming every record is a wastewater outfall.

5. **`ottawa_discharge` undercounts.** This optional flag is keyed on ECHO's
   `CWPStateWaterBodyName` string, which is null for most of the Ohio rows. **Lima WWTP
   (OH0026069, 18.5 MGD)**, the largest Lima-area POTW, is flagged only because its
   permit-cited receiving water is supplied by the curated overlay; every other
   Ottawa-River discharger ECHO leaves blank is still missing from the flag, and per the
   "no inference" rule none of them is guessed at. Use `in_lima_subbasin` (every
   Auglaize + Blanchard record) plus `county` for the broad Lima/Allen screen, and
   treat `ottawa_discharge: true` as a floor, not a complete list.

## Field reference

Each entry under `facilities:` carries these keys (`null` = ECHO returned nothing):

| field | ECHO ObjectName | note |
|-------|-----------------|------|
| frs_registry_id | RegistryID | dedup key |
| name | CWPName | |
| npdes_id | SourceID | primary permit |
| npdes_ids_secondary | (from NPDESIDs) | list of other permits at the facility |
| ownership | derived | Federal / POTW / NON-POTW |
| facility_type | CWPFacilityTypeIndicator | POTW vs NON-POTW |
| permit_type | CWPPermitTypeDesc | NPDES vs non-NPDES, individual vs general |
| design_flow_mgd | CWPTotalDesignFlowNmbr | `null` = ECHO returned no value |
| design_flow_missing | derived | `true` when design_flow_mgd is null |
| receiving_water | CWPStateWaterBodyName | sparse for OH; a curated `mode: field` row carries the document-cited value instead |
| receiving_water_source | curation | present (`curated`) only on a `mode: field` row |
| receiving_water_echo | CWPStateWaterBodyName | the verbatim ECHO value a curated row replaced |
| receiving_water_documented | curation | a `mode: caveat` correction, recorded beside the untouched field |
| receiving_water_citation | curation | the document naming the curated receiving water |
| huc8 / huc8_name | FacDerivedHuc | |
| huc12 | RadWBDHuc12 | |
| county | FacCountyName | |
| latitude / longitude | FacLat / FacLong | |
| compliance_status | CWPSNCStatus | current CWA status |
| informal_enf_count / formal_enf_count | CWPInformalEnfActCount / CWPFormalEaCnt | |
| in_lima_subbasin | derived | `true` for Auglaize or Blanchard |
| ottawa_discharge | derived | boolean; see caveat 5 |
| queried_huc8 | — | the `p_huc` this record was returned under |

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `echo-great-miami-wwtp` — Great Miami-basin NPDES discharger inventory (EPA ECHO)

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:great-miami · Refresh: quarterly (ttl 180d)

Regenerate: `watermark npdes --basin great-miami`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/great-miami-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/great-miami-wwtp.huc-counts.yaml` | application/x-yaml | no |
| `reference/echo/great-miami-wwtp.potw.yaml` | application/x-yaml | no |

### `echo-little-miami-wwtp` — Little Miami-basin NPDES discharger inventory (EPA ECHO)

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:little-miami · Refresh: quarterly (ttl 180d)

Regenerate: `watermark npdes --basin little-miami`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/little-miami-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/little-miami-wwtp.huc-counts.yaml` | application/x-yaml | no |
| `reference/echo/little-miami-wwtp.potw.yaml` | application/x-yaml | no |

### `echo-maumee-npdes` — Maumee-basin NPDES discharger inventory (EPA ECHO)

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:maumee · Refresh: quarterly (ttl 180d), last 2026-07-28

Regenerate: `watermark npdes --basin maumee`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/maumee-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/maumee-wwtp.potw.yaml` | application/x-yaml | no |
| `reference/echo/maumee-wwtp.huc-counts.yaml` | application/x-yaml | no |

### `echo-maumee-receiving-water` — Curated receiving-water overlay for the Maumee ECHO NPDES inventory

Source: Hand-authored, document-cited corrections to ECHO's CWPStateWaterBodyName — Ohio EPA NPDES permit 2PE00000*OD (Lima WWTP), Ohio EPA NPDES fact sheet 2PD00006 Table 12 (Van Wert WWTP), and the EPA ECHO detailed facility report for OH0135569 · License: U.S. Government work (public domain) — the cited permits and fact sheets are Ohio EPA records · Access: public · Site scope: basin:maumee · Refresh: on-demand

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/curation/maumee-wwtp.receiving-water.yaml` | application/x-yaml | no |

### `echo-ohio-brush-creek-wwtp` — Ohio Brush Creek-basin NPDES discharger inventory (EPA ECHO)

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:ohio-brush-creek · Refresh: quarterly (ttl 180d)

Regenerate: `watermark npdes --basin ohio-brush-creek`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/ohio-brush-creek-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/ohio-brush-creek-wwtp.huc-counts.yaml` | application/x-yaml | no |
| `reference/echo/ohio-brush-creek-wwtp.potw.yaml` | application/x-yaml | no |

### `echo-portage-wwtp` — Portage-basin NPDES discharger inventory (EPA ECHO)

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:portage · Refresh: quarterly (ttl 180d)

Regenerate: `watermark npdes --basin portage`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/portage-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/portage-wwtp.huc-counts.yaml` | application/x-yaml | no |
| `reference/echo/portage-wwtp.potw.yaml` | application/x-yaml | no |

<!-- catalog:end -->
