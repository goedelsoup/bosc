# Xenia / Beavercreek (Greene Co.), OH — Data-Center Activity Register

Discover-and-pin register for the Xenia watershed point — the **Little Miami** headwaters and the
Greene-County side of the WPAFB defense-supplier corridor. Status **as of 2026-07-02**. Tags are
BOSC evidentiary discipline: `[verified]` = on-record in a government/primary source, `[reported]`
= credible secondary, not officially confirmed, `[reference]`, `[inference]`, `[open]`.

**This is a scaffold, not a completed sweep (#460).** This is a **discover-and-pin task with a
real possibility of a flat no-activity outcome** — the web pass (parcel / SOS / EPA permit) is
**to-run**. Every open item names the primary instrument to pull. **Nothing here is fabricated.**

## Discipline guardrail

Do **not** bridge the **Lima/Allen Bistrozzi land-assembly graph** onto Xenia — any Xenia assembly
is a **separate register**. The Greene-County defense-supplier ecosystem (GDIT / RSO) belongs to
the WPAFB corridor register (`data/extracted/wpafb/data-centers.md`, #467), not to a sited Xenia
facility.

## 1 — Baseline: the employment mix argues *against* an existing cluster `[verified]`

`[verified]` **Zero Xenia / Greene / Little-Miami / Beavercreek data-center primary documents are
in the BOSC corpus** (the corpus is entirely Lima/Allen County). The Greene County employment mix
(BLS QCEW 2023, `reference/economics/xenia/baseline.yaml`) is a two-sided signal:

- **Information (NAICS 51) LQ 0.29** — *well below* national share: **no existing IT-hosting /
  data-center concentration by employment.** `[verified]`
- **Professional/Scientific/Technical (NAICS 54) LQ 2.11** — the **WPAFB defense-contractor**
  signature (the bedroom-community engineering/sustainment cluster), **not** a data-center signal.
  `[verified]` This is why the WPAFB econ caveat (#465) points here: the defense concentration is
  Greene's, the well-field/plume/metro-toxics context is Montgomery's.

So the prior is **flat no-activity**; a sited campus would be a genuine discovery, not an expected
find. Commit a **dated, sourced flat no-activity finding** if the web pass confirms nothing.

## 2 — Sited-facility scan (to-run) `[open]`

### Instruments to pull (priority order)

1. **Greene County Auditor / GIS** — parcel sweep for large contiguous industrial assembly near
   Xenia / Beavercreek / I-675; owner of record, transfer dates. (Profile GIS endpoints are
   `[open]` — `parcels_url="TODO"`, pending Greene County REST discovery.)
2. **Ohio SOS business search** — new LLC/shell formations tied to any assembly (keep any find a
   **separate register**, not bridged to Lima).
3. **City of Xenia / Beavercreek / Greene County zoning & rezoning dockets** — heavy-industrial
   rezonings 2023–2026. `[open]`
4. **Ohio EPA / EPA ECHO** — data-center stormwater coverage under draft general permit
   **OHD000001**; new industrial NPDES on the Little Miami / Massies Creek. (Little-Miami ECHO
   inventory committed: `data/reference/echo/little-miami-wwtp.potw.yaml`.)
5. **AES Ohio (DP&L) large-load / PJM DAY-zone interconnection queue** — a >100 MW tap is the
   earliest hard signal. `[open]`

## 3 — Contamination overlay: the WPAFB groundwater plume `[open]`

Track the **WPAFB TCE/PFAS groundwater plume** as the `[open]` contamination overlay intersecting
the **Mad River / Little Miami buried-valley sole-source aquifer** that the Xenia/Beavercreek well
fields draw on (profile `hsg_citation`, sourced to ODNR/USGS, `[reference]`). Any Beavercreek assembly near
the base sits over the same drinking-water aquifer — the receiving-water screen is **groundwater**,
not surface 7Q10. Verify the aquifer designation + plume against primary sources — see the WPAFB
groundwater screen (`data/extracted/wpafb/groundwater-screen.md`, #463). Until cited, the plume
overlay stays **to-verify**, not a finding.

## Sources

- Greene County economics baseline (in-corpus): `data/reference/economics/xenia/baseline.yaml`
- Little-Miami NPDES inventory (in-corpus, ECHO): `data/reference/echo/little-miami-wwtp.potw.yaml`
- WPAFB corridor register (the GDIT/RSO defense-cloud thread): `data/extracted/wpafb/data-centers.md`
- WPAFB groundwater screen (aquifer + plume, #463): `data/extracted/wpafb/groundwater-screen.md`
- Xenia onboarding self-research pass: `data/research/onboard-xenia-*/` (see the site's ONBOARDING.md)
- Ohio EPA (data-center general permit OHD000001): [wastewater-discharges-from-data-centers--general-permit](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit)
