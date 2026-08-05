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
the row. Four basins are committed today, each with its own
`<basin>-wwtp.*` fileset: the **Maumee** (`watermark npdes`, the default), the **Great
Miami** (`watermark npdes --basin great-miami`, the Miami-basin sites — Urbana, Springfield,
WPAFB, Troy-Piqua, Hamilton-Middletown), the **Little Miami** (`watermark npdes --basin
little-miami`, the Scenic-River sites Xenia and Wilmington / Todd Fork, a single HUC-8
`05090202`), and **Ohio Brush Creek** (`watermark npdes --basin ohio-brush-creek`, the
direct-to-Ohio-River branch at West Union / Adams County — a single HUC-8 `05090201`; #1120).
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
once its receiving water is document-cited. Files: `great-miami-wwtp.all-npdes.yaml`,
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
tree; 05090201 is a WBD **two-bank Ohio River corridor unit** — 67 HUC-12s and 5,439 km²
running roughly 150 river miles from Ninemile Creek at the Cincinnati metro edge east to
Kinniconick Creek, spanning both banks and therefore both states. Ohio Brush Creek proper is
16 of those 67 HUC-12s (including Beasley Fork, `050902010505`, West Union's own receiver);
Whiteoak Creek is 7 more; Eagle, Straight, Twelvemile, Tenmile, Fourmile, Bracken and Cabin
Creeks account for most of the rest. Every one of them reaches the Ohio on its own, so they
are **siblings** of Ohio Brush Creek, not its headwaters — a discharger on one is neither
upstream nor downstream of a discharger on another.

**Last pull (2026-08-05):** 273 active-permit rows in the one HUC-8 → **261 facilities**
after FRS dedup, **23 POTW** (17.87 MGD of design flow, present for 22 of 23). The
two-bank geography makes it **majority-Kentucky**: 168 of the 261 carry KY permits
(Campbell 111, Lewis 22, Mason 22, Bracken 11, Pendleton 2) against 93 Ohio ones (Clermont
20, Brown 15, Adams 11, Scioto 3, Highland 1, and 43 for which ECHO returned no county).
Completeness therefore needs a cross-check against **both** Ohio EPA and Kentucky DOW; only
what ECHO federalizes is reflected here.

### What screens, and what does not

`receiving_water` is null for **118 of the 261** rows, and for 13 of the 23 POTWs. The
assimilative screen (`watermark --site west-union basin-screen`) reports:

| outcome | POTWs | why |
|---|---|---|
| screened | 6 | name the Ohio River; dilution 1,799:1 (Maysville STP) to 95,570:1, all `ok` |
| no receiving water | 13 | ECHO carries no `CWPStateWaterBodyName` |
| no 7Q10 | 4 | named receiver, but an ungaged tributary (Bear Creek, Town Run, Grog Branch, Twelve Mile Creek) |

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

The screened six exist because #1120 added the **Ohio River** mainstem to
`data/reference/hydrology/mainstem-gages.yaml` — USGS 03216600 at Greenup Dam, chosen as the
*upstream-end* gage so its drainage area understates every facility's and the screen cannot
overstate dilution. That entry's note records what a reader is owed about it: the mainstem is
navigation-regulated in fact and unannotated on the record, and one gage across 150 river
miles makes a dilution ratio a magnitude check rather than a reach-specific finding.

Files: `ohio-brush-creek-wwtp.all-npdes.yaml`, `ohio-brush-creek-wwtp.potw.yaml`,
`ohio-brush-creek-wwtp.huc-counts.yaml`. There is no curated receiving-water overlay for this
basin yet.

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

<!-- catalog:end -->
