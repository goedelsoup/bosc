# Network NPDES inventories (EPA ECHO)

Verified inventories of CWA-permitted facilities per watershed basin, pulled from
EPA's **ECHO Clean Water Act REST services** (`cwa_rest_services`). Every facility,
NPDES ID, and value here was returned by the ECHO API — nothing is fabricated,
inferred, or filled in. Two basins are committed today, each with its own
`<basin>-wwtp.*` fileset: the **Maumee** (`watermark npdes`, the default) and the **Great
Miami** (`watermark npdes --basin great-miami`, the Miami-basin sites — Urbana, Springfield,
WPAFB, Troy-Piqua, Hamilton-Middletown). Two further basins are **registered in the
connector but not yet committed**: the **Scioto** (`--basin scioto`, the Columbus /
New Albany data-center cluster) — deferred on an ECHO 300/hr throttle (HTTP 429) — and
the **Little Miami** (`--basin little-miami`, the Scenic-River sites Xenia and
Wilmington / Todd Fork, a single HUC-8 `05090202`) — deferred when ECHO returned read
timeouts then a 500. Run `watermark npdes --basin scioto` / `--basin little-miami` to write
their `<basin>-wwtp.*` filesets when ECHO is healthy. Add a basin by registering it in
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

## Method

Per HUC-8: `get_facilities` (`p_huc=<HUC8>`, `p_act=Y`) returns a QID + summary
count; `get_qid` pages the rows as JSON, columns selected **by name** (mapped to
ECHO ColumnIDs). Deduplication keys on **FRS Registry ID**; a facility holding
multiple permits keeps its primary NPDES ID with the rest in
`npdes_ids_secondary`. Two distinct FRS IDs sharing a name are never collapsed.

Verified against `cwa_rest_services` metadata **CWA v2017-10-13 1325** (260 result
columns). Numbers come from the API's structured fields, not any text layer.

## Headline counts (last pull)

1,057 active-permit rows across the 7 HUC-8s → **1,006 facilities** after FRS
dedup: **129 POTW**, 875 non-POTW, 2 federal. POTW design flow present for
112/129 (the 17 blanks are mostly Michigan general-permit stabilization lagoons
that don't report a design-flow number).

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
it, so the basin-screen reports it unscreened rather than guess (same gap as Lima WWTP,
caveat 5). Files: `great-miami-wwtp.all-npdes.yaml`, `great-miami-wwtp.potw.yaml`,
`great-miami-wwtp.huc-counts.yaml`.

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
   `CWPStateWaterBodyName` string, which is null for ~70% of the Ohio rows —
   including **Lima WWTP (OH0026069, 18.5 MGD)**, the largest Lima-area POTW, which
   discharges to the Ottawa River but has no receiving-water value in ECHO. Per the
   "no inference" rule we do *not* backfill it. Use `in_lima_subbasin` (every
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
| receiving_water | CWPStateWaterBodyName | sparse for OH |
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

Source: EPA ECHO — cwa_rest_services (CWA v2017-10-13) · License: U.S. Government work (public domain) · Access: throttled · Site scope: basin:maumee · Refresh: quarterly (ttl 180d)

Regenerate: `watermark npdes --basin maumee`

| file | type | lfs |
| --- | --- | --- |
| `reference/echo/maumee-wwtp.all-npdes.yaml` | application/x-yaml | no |
| `reference/echo/maumee-wwtp.potw.yaml` | application/x-yaml | no |
| `reference/echo/maumee-wwtp.huc-counts.yaml` | application/x-yaml | no |

<!-- catalog:end -->
