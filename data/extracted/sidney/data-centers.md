# Sidney / Shelby County, OH — Data-Center Activity Register

Discover-and-pin register for the Sidney onboarding — the **I-75 corridor** sweep required by
#511. Status **as of 2026-07-02**. Tags are BOSC evidentiary discipline: `[verified]` = cited
public source, `[inference]`, `[open]`, `[reference]`. **Nothing here is in the BOSC corpus yet**
— this records the *verified public record* and the specific primary instruments to *pull*. Every
figure is cited; none is fabricated. Do not bridge the Lima/Allen Bistrozzi graph onto Shelby
County — there is no evidentiary link.

## Disambiguation guardrail

Every entry confirmed as genuinely Shelby County, OH / City of Sidney. Sidneyoh.com and the
council resolution references are primary-source verified. `[verified]`

## 1 — Amazon Data Services / AWS "Project Galaxy"

- **Operator:** Amazon Web Services, Inc. (Delaware corp, operator). `[verified]`
- **Developer entity:** Amazon Data Services, Inc. (Delaware corp). `[verified]`
  Source: Resolution 27-26 text / city FAQ (sidneyoh.com/526).
- **Project name:** Project Galaxy (AWS internal codename). `[verified]`
- **Location:** 2388 W. Millcreek Road, Sidney, OH — northwest corner of Vandemark and Millcreek
  Roads, north side of Millcreek Road, pre-existing industrial corridor. `[verified]`
  Source: Obedio / Sidney City Council resolution references.
  *Note (#1379): that street address is a **retired pre-consolidation situs**. The parcel of
  record is now `26-03-201-002`, situs **1151 S Vandemark Rd** — see "Land / parcel acreage".*
- **Investment:** $3 billion campus. `[verified]`
  Source: Data Center Dynamics (DCD), Oct 2025; baxtel.com.
- **Land / parcel acreage:** **243.092 ac deeded / 235.468 ac planar** (UTM 16N) — Shelby County
  parcel **`26-03-201-002`** (auditor number `01-2603201.002`), owner of record **Amazon Data
  Services, Inc.** (mailing PO Box 80416, Seattle WA), conveyed **2025-11-24 for $5,621,490**,
  deed **OR2329/454**, land use 110 "Agricultural vacant land (CAUV)", tax district 01 (Clinton
  Twp / Sidney Corp / Sidney CSD). `[verified]`
  Source: Shelby County Auditor CAMA via the Shelby County Engineer's Office ArcGIS `Parcels`
  layer, tax year 2025 (read 2026-07-31) — committed as
  `data/reference/sidney/parcel-assemblage.geojson` (#1379).
  *Why this was `[open]`: the search was keyed on a street address the consolidation plat had
  already retired. `26-03-201-002` is **Lot 7658, Consolidation & Roadway Dedication Plat, Plat
  V37 P50**, which absorbed five predecessor tracts — including `26-03-226-001` (77.6 ac), the
  parcel that carried situs "2388 Millcreek Rd" — plus `26-03-126-001` (78.26 ac),
  `26-03-201-001` (56.14 ac), `26-03-251-001` (21.24 ac) and `26-03-251-002` (2 ac). All five
  stand in the 2023-05-23 OGRIP statewide extract, lie 85–99% inside the current polygon, and are
  gone from the current CAMA. `[verified]` as a geometric containment test of the two layers.*
  *Scope caveat: Amazon Data Services owns **exactly one** parcel in Shelby County (countywide
  owner scan) — but no **campus** acreage is disclosed by AWS or the City, so this parcel acreage
  is the campus's **outer bound**, not a measurement of it.*
- **Zoning district:** `[open]` — the City of Sidney publishes a zoning REST layer
  (`SidneyGIS_AllLayers/MapServer/270`, 9 districts, "officially adopted October 24, 2016") but
  the campus parcel falls in a **hole** in it: zoning, corp-limits and annexation layers all miss
  the parcel's interior point while its two district-01 neighbours hit all three (SEMCORP
  `26-03-301-001` → IIM; DP&L `26-03-429-009` → CC), and the annexation layer stops at ordinance
  A-3145 (2023-08-28). Since the auditor's TY2025 tax district already places the parcel inside
  the corporate limits, this is a **currency gap**, not an unzoned site. Instrument to pull: the
  City of Sidney annexation / rezoning ordinance for the campus.
- **Dominant hydrologic soil group:** **D** — SSURGO/SDA 64-point grid over the committed parcel
  geometry (2026-07-31): D 62 pts (96.9%) + C/D 2 pts (3.1%); dominant map units Blount and
  Glynwood silt loams, *end moraine*. `[verified]`
  *This corrects the prior `[inference]` of HSG "B" and its reasoning: the campus is not in the
  Great Miami buried valley at all — it sits ~2 mi west of it on the Wisconsinan end moraine.
  The sole-source-aquifer claim below remains true of the Sidney **well field**; it was never
  true of this footprint. Consequence: post-development runoff off this site screens materially
  higher than a buried-valley outwash assumption would have given.*
- **Construction:** grading permit issued 2026-05-14; ground breaking ~January 2026. `[verified]`
  Source: sidneyoh.com/526.
- **Operations target:** December 31, 2028. `[verified]`
  Source: sidneyoh.com/526 (CRA Agreement 80-25 deadline).
- **Jobs required:** ~75 long-term skilled operational positions by December 31, 2030; annual
  payroll $6.75 million. `[verified]`
  Source: sidneyoh.com/526; DCD Oct 2025.
- **Power utility:** AES Ohio (Dayton Power & Light / DP&L). `[verified]`
  Source: sidneyoh.com/526.
- **Power draw (MW):** `[open]` — not disclosed in public records reviewed. The `_SIDNEY`
  `SiteFacility` (#1378, 2026-07-13) carries an **investment-scaled `[inference]` screening
  bracket** for the IT load (~150 / 250 / 350 MW low/central/high = the disclosed $3B campus ÷ a
  ~$8.5–20M per MW-IT hyperscale construction-cost band) so the profile's power stack has an
  input — it is **not** a disclosure and does **not** close this `[open]`; the disclosed
  interconnection/air-permit MW remains the target to pull. No floor area is disclosed, so the
  network's usual floor-area screen (Urbana #1327 / Troy-Piqua / Bowling Green) does not apply.

### Financial / tax instruments

- **CRA tax abatement:** 30-year, 100% real-property abatement per building; no exemption
  extending beyond tax year 2065. Resolution 18-25 (Sidney City Council), October 2025. `[verified]`
- **PILOT:** $50 million total over 15 years — $25 million to City of Sidney, $25 million to
  Sidney City Schools. `[verified]` Source: sidneyoh.com/526; DCD Oct 2025.
- **Abatement estimated value:** $180–$350 million over 30-year term (~$2.4M–$4.6M per job). `[reference]`
  Source: stopohiodatacenters.org/shelby-county (advocacy group; figures not independently
  verified against appraisal records).
- **Infrastructure contribution:** up to $8.0 million for Millcreek Road reconstruction (AWS
  commitment); city engineer's estimate $7,927,151.50. Resolution 27-26, adopted April 27, 2026. `[verified]`
- **NDA:** non-disclosure agreement executed mid-2025 between Sidney City Council and AWS prior
  to public announcement. `[verified]` Source: stopohiodatacenters.org/shelby-county.

### Water / hydrology hook

- **Max withdrawal:** 1.0 million gallons per day (694 gpm). 10-year water and sewer service
  agreement with Amazon Web Services, Inc. — Resolution 26-26, adopted April 27, 2026. `[verified]`
  Source: sidneyoh.com/526; obedio.com.
- **Projected cooling-water consumption:** 4.6 million gallons per year (~12,600 GPD average).
  `[verified]` Source: sidneyoh.com/526.
  *Note: the 1.0 MGD max is peak withdrawal; the 4.6M gal/yr figure is projected evaporative
  consumption. Net consumptive loss ≈ 0.0195 cfs average against the Great Miami 7Q10 = 30.95 cfs —
  <0.1% of 7Q10.* `[inference]` (arithmetic from cited inputs; see hydrology hook below.)
- **Water source:** City of Sidney municipal system — multiple sources: groundwater wells, Great
  Miami River intake, Tawawa Creek. `[verified]` Source: sidneyoh.com/526.
- **Wastewater:** all facility wastewater to Sidney municipal sanitary sewer → OH0027421 → Great
  Miami River. `[verified]` Source: sidneyoh.com/526.
- **Stormwater:** retention/detention basins per Ohio EPA regulations; no on-site waste ponds.
  `[verified]` Source: sidneyoh.com/526.

### Hydrology screen

- **Receiving water (indirect):** Great Miami River at Sidney — 7Q10 30.95 cfs (derived LP3, gage
  03261500, 44 yr 1980–2024; `low-flow-7q10.derived.yaml`). `[verified]`
- **Abstraction vs. 7Q10:** 1.0 MGD peak = 1.55 cfs; consuming 4.6M gal/yr = 0.0195 cfs average.
  Net consumptive draw is <0.1% of the 7Q10 denominator — **no assimilative violation flag on
  water-quantity grounds.** `[inference]` (confirmed arithmetic; regulatory passby threshold not
  yet set — see SiteProfile `passby_primary_cfs`.)
- **Effluent path:** all process water returns via OH0027421 (design 7.0 MGD, actual 4.01 MGD
  2023); the data-center wastewater volume is not reported separately in ECHO DMR and is presumed
  subsumed in the WWTP totals. `[open]` — confirm when NPDES fact sheet is ingested (#833).

### Regulatory record (status as of 2026-07-02)

- **Ohio EPA air PTI (emergency generators):** `[open]` — not found in public search. A campus of
  this scale would require PTI for diesel generators prior to operation. Instrument to pull: OEPA
  Air Pollution Control / NWDO eSuite, search "Amazon Data Services" or "Project Galaxy," Shelby
  County, 2025–2026.
- **Ohio EPA NPDES stormwater:** `[open]` — coverage expected under draft general permit OHD000001
  (data-center stormwater general permit) or an individual permit. Not confirmed from open sources.
- **Ohio SOS entity registrations:** Amazon Data Services, Inc. (Delaware — expect Ohio foreign-corp
  filing) and Amazon Web Services, Inc. `[open]` — not pulled.

## 2 — No other activity found

RSEI TRI inventory (Shelby County, RSEI v234, 39 facilities): no NAICS 518210 entry; no
data-center SIC code. All 39 facilities are legacy manufacturing, quarrying, or food processing.
`[verified]` Source: `data/reference/rsei/sidney/inventory.yaml` (EPA RSEI Public Data Set v234,
county FIPS 39149).

ECHO Great Miami all-NPDES (committed 2026-07-02, 286 facilities, 18 Shelby County): no NAICS
518210 or data-center-type facility. Shelby County entries are municipal WWTPs (Anna STP,
Botkins WWTP, Sidney WWTP OH0027421, Jackson Center, Russia) + quarries (Barrett Paving ×4) +
Honda Anna Engine Plant + miscellaneous non-POTW. `[verified]` Source:
`data/reference/echo/great-miami-wwtp.all-npdes.yaml` (committed 2026-07-02).

I-75 corridor web sweep (2026-07-02): no evidence of a second data-center operator or land
assembly beyond Project Galaxy. `[verified]` Source: stopohiodatacenters.org; CleanView; DCD; WHIO.

## Instruments to pull (priority order)

1. **City of Sidney council resolutions 18-25, 80-25, 81-25, 82-25, 26-26, 27-26** — CRA agreement,
   PILOT terms, water/sewer contract, infrastructure agreement. Primary instruments cited above.
2. **Shelby County Recorder** — the deed behind **OR2329/454** (parcel `26-03-201-002`, grantee
   Amazon Data Services, Inc., 2025-11-24, $5,621,490). Acreage, transfer date and price are now
   `[verified]` from the auditor CAMA (#1379); what the recorder still owes is the **sequential
   instrument number**, the **grantor**, and any recorded easements — plus the companion
   **OR2329/497** (Shelby County Commissioners → Dayton Power & Light Co., `26-03-429-009`,
   7.305 ac, same day, $547,875), the likely campus substation conveyance (`[inference]`).
   Also pull **Plat V37 P50** (Lot 7658 Consolidation & Roadway Dedication Plat), which is the
   instrument that retired the "2388 W. Millcreek Rd" parcel and would close the ~4-ac
   planar-acreage difference as a roadway dedication.
3. **Ohio SOS** — Ohio foreign-corp registration for Amazon Data Services, Inc. and Amazon Web
   Services, Inc.
4. **OEPA Air PTI** — emergency generator bank PTI(s) for Project Galaxy site (NWDO district,
   Shelby County, entity "Amazon Data Services").
5. **OEPA stormwater permit** — coverage letter or individual permit number.
6. ~~**Shelby County Auditor / GIS** — parcel record at 2388 W. Millcreek Rd~~ — **DONE** (#1379):
   wired as the `shelby_gis` connector and committed as
   `data/reference/sidney/parcel-assemblage.geojson`. Note the assessed value is genuinely 0 in
   the TY2025 extract (an unvalued new consolidation parcel), so the appraisal record is the
   remaining ask on that line.
7. **City of Sidney annexation / rezoning ordinance** for the campus parcel — the instrument that
   would close the zoning `[open]` the city's published GIS layers cannot (see "Zoning district").

## Sources

- City of Sidney FAQ (primary): [sidneyoh.com/526/Proposed-Data-Center-FAQ](https://www.sidneyoh.com/526/Proposed-Data-Center-FAQ)
- Data Center Dynamics (Oct 2025): [amazon-secures-tax-break-3bn-data-center-campus-sidney-ohio](https://www.datacenterdynamics.com/en/news/amazon-secures-tax-break-for-3bn-data-center-campus-in-sidney-ohio/)
- Obedio (Apr 2026 infrastructure approvals): [aws-data-center-campus-in-sidney-ohio-clears-final-infrastructure-approvals](https://hs.getobedio.com/blog/aws-data-center-campus-in-sidney-ohio-clears-final-infrastructure-approvals-locking-in-8m-of-private-road-funding)
- Stop Ohio Data Centers (advocacy, use for leads not primary facts): [stopohiodatacenters.org/shelby-county](https://stopohiodatacenters.org/shelby-county)
- WHIO TV (community meeting): [community-gathers-share-concerns-learn-about-data-center-plans-shelby-county](https://www.whio.com/news/local/community-gathers-share-concerns-learn-about-data-center-plans-shelby-county/OF4XYJ5YAVEXZGH55OYPRZLHIA/)
