# Sidney / Shelby County, OH — Data-Center Activity Register

Discover-and-pin register for the Sidney onboarding — the **I-75 corridor** sweep required by
#511. Base status **as of 2026-07-02**; the regulatory record re-checked and the state
instruments **ingested 2026-07-31** (#1383). Tags are BOSC evidentiary discipline: `[verified]` =
cited public source, `[inference]`, `[open]`, `[reference]`. Every figure is cited; none is
fabricated. Do not bridge the Lima/Allen Bistrozzi graph onto Shelby County — there is no
evidentiary link.

The standing watch and its dated negatives live in
[`regulatory-watch.yaml`](regulatory-watch.yaml); the source bytes are in
[`data/documents/oepa/sidney/`](../../documents/oepa/sidney/) and
[`data/documents/grid/sidney/`](../../documents/grid/sidney/).

## Disambiguation guardrail

Every entry confirmed as genuinely Shelby County, OH / City of Sidney. Sidneyoh.com and the
council resolution references are primary-source verified. `[verified]`

⚠️ **"Project Galaxy" is not this campus's name in the regulatory record, and it names a
different Amazon campus.** Ohio EPA files this site as **"Sidney Data Center Campus"** (surface
water / NPDES) and **"CMH-232"** (401 / wetlands). Meanwhile ICIS-NPDES carries *"PROJECT
GALAXY"* — individual NPDES permit **OH0151745**, hydrostatic general permit **OHGH00907**, and
**OHGC17083** *"Project Galaxy force main for cooling water discharge"* — all permitted to
**Amazon Data Services, Inc.** at **1000 Innovation Way, Jeffersonville, OH 43128**, which is
**Fayette County**, ~90 miles away. A records search keyed on the codename returns a real,
Amazon-owned, **cooling-water-discharging** Ohio data center that is **not this one**. Search on
"Sidney Data Center Campus", "CMH-232", the address, or the permittee name. `[verified]`
(EPA ECHO `cwa_rest_services`, checked 2026-07-31.)

## 1 — Amazon Data Services / AWS "Sidney Data Center Campus" (CMH-232)

- **Operator:** Amazon Web Services, Inc. (Delaware corp, operator). `[verified]`
- **Developer entity:** Amazon Data Services, Inc. (Delaware corp). `[verified]`
  Source: Resolution 27-26 text / city FAQ (sidneyoh.com/526).
- **Names:** permitted as **"Sidney Data Center Campus"** (Ohio EPA surface water / NPDES) and
  **"CMH-232"** (Ohio EPA 401 / wetlands); **"Project Galaxy"** is the name in local and trade
  use, and on the agency's own record it belongs to a different Amazon campus — see the
  disambiguation guardrail above. `[verified]` A third name, **"Rey"**, appears once in a
  resident's question on the City FAQ ("the Project Galaxy/Rey development") and is corroborated
  by nothing else. `[open]`
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
- **Internal designation:** **CMH-232** (Amazon Data Services' own project name on its Ohio EPA
  401 filings). `[verified]` Source: `data/documents/oepa/sidney/3935117.pdf` §2.A.
- **Project extent as permitted:** **236.7 acres** "of agricultural and residential land"
  converted, in the applicant's own words on its §401 application; **230.7 acres** of total land
  disturbance declared on the stormwater NOI. `[verified]` Sources: `3935117.pdf` §2.C;
  `3931140.pdf` §III. These are the applicant's own *project* figures and they sit inside the
  243.092 ac parcel of record above — three different measures of the same site, none of them a
  disclosed campus footprint.
- **Coordinates:** 40.26920527 / -84.19566214 (stormwater NOI) and 40.266278 / -84.194246 (401
  application) — two filings' reference points ~350 m apart, neither a boundary. `[verified]`
- **Consultants of record:** Advanced Civil Design (civil/site); Smart Services, Inc. (wetlands);
  **George J. Igel & Co., Inc.** (earthwork, co-permittee on the stormwater permit). `[verified]`
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
  **Re-checked 2026-07-31 (#1383): still `[open]`.** Five state permits have now issued across
  this project and **not one of them states a load** — a construction-stormwater coverage, an
  isolated-wetland authorization, a sanitary-sewer PTI, the City's own road wetland permit and
  AES's adjacent transmission-reroute coverage have no megawatt field between them. The load will
  come from an air PTI or a utility filing, or not at all.

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
  consumption. Net consumptive loss ≈ 0.0195 cfs average against the cited regulatory Great Miami
  7Q10 of 24.0 cfs — 0.08% of 7Q10.* `[inference]` (arithmetic from cited inputs; see hydrology
  screen below.)
- **Water source:** City of Sidney municipal system — multiple sources: groundwater wells, Great
  Miami River intake, Tawawa Creek. `[verified]` Source: sidneyoh.com/526.
- **Wastewater:** all facility wastewater to Sidney municipal sanitary sewer → OH0027421 → Great
  Miami River. `[verified]` Source: sidneyoh.com/526.
- **Stormwater:** retention/detention basins per Ohio EPA regulations; no on-site waste ponds.
  `[verified]` Source: sidneyoh.com/526.

### Hydrology screen

**Two different denominators, and the register previously used one for both.** Wastewater leaves
at the Sidney WWTP outfall on the **Great Miami** mainstem; **stormwater** leaves the campus into
**Mill Creek → Loramie Creek**, which reaches the Great Miami below the Sidney gage.

- **Stormwater receiving waters:** "Mill Creek, Mill Branch" per the campus NOI; HUC-12
  **050800010604** (Mill Creek–Loramie Creek) and **050800010703** (Brush Creek–Great Miami
  River) per the 401 application and the adjacent AES filing. `[verified]`
  Sources: `3931140.pdf` §II; `3935117.pdf` §2.H/I; `grid/sidney/4184081.pdf`.
- **Regulatory stream design flows (cited, not derived):** Great Miami above Sidney annual
  **7Q10 = 24.0 cfs**, 1Q10 = 19.4 cfs, summer 30Q10 = 29.0 cfs, harmonic mean = 119.2 cfs (USGS
  03261500, 1927–2021); **Loramie Creek at mouth annual 7Q10 = 3.43 cfs** (USGS 03262000,
  1916–2020). `[verified]` Source: Fact Sheet for NPDES Permit Renewal, City of Sidney WWTP,
  2022, Table 14 — `data/documents/oepa/sidney/1PD00009.c43b66fd.pdf` p.32; structured read
  `data/extracted/oepa/sidney/1PD00009.npdes.yaml`.
  *This supersedes the 30.95 cfs figure this register carried: that was a BOSC-derived LP3 7Q10
  over 1980–2024 at the same gage, explicitly held as a placeholder pending this fact sheet. The
  regulator's long-record value is 22% lower, so the previous screen was the more permissive of
  the two.*
- **Abstraction vs. the regulatory 7Q10:** 1.0 MGD peak = 1.55 cfs (6.5% of 24.0 cfs); consuming
  4.6M gal/yr = 0.0195 cfs average = **0.08% of the 7Q10 denominator** — no assimilative
  violation flag on water-quantity grounds. `[inference]` (arithmetic from cited inputs.)
- **Effluent path:** all process water returns via OH0027421 → Great Miami River at **RM 128.68**
  (design 7.0 MGD, peak hydraulic 13.5 MGD; actual 4.01 MGD 2023 MO-AVG mean). The plant also
  serves Port Jefferson, the Mill Creek Subdivision and the Honda of America plant in Anna, and
  is allocated jointly with the **Piqua and Troy WWTPs** as interactive dischargers. `[verified]`
- **Separating the campus's wastewater:** it will **not** appear separately in the WWTP's DMRs —
  a DMR reports outfall 001, not an individual user. The instrument that would separate it is the
  **City of Sidney's own industrial-pretreatment / significant-industrial-user permit** (the City
  reports 16 SIUs today), an R.C. 149.43 municipal record that is not on Ohio EPA's portal.
  `[open]` — no SIU permit for the campus is on the record.

### Regulatory record (re-checked and ingested 2026-07-31 — #1383)

Full watch log, per-route negatives and next-check queries:
[`regulatory-watch.yaml`](regulatory-watch.yaml).

**Issued and in the corpus:**

| Instrument | Number | Permittee | Effective | Source |
|---|---|---|---|---|
| Construction Site Stormwater GP coverage | `1GC10596*AG` (ICIS `OHGC16923`), under GP `OHC000006` | Amazon Data Services, Inc. | 2025-12-05 → 2028-04-22 | `oepa/sidney/3931142.pdf` |
| — co-permittee (earthwork) | same number | George J. Igel & Co., Inc. | 2026-04-22 | `oepa/sidney/4091850.pdf` |
| Isolated Wetland GP authorization (Level One) | Ohio EPA ID `251911W` | Amazon Data Services, Inc. | 2025-12-16, modified 2026-01-15 | `oepa/sidney/3972773.pdf` |
| Surface Water Permit to Install (sanitary sewer relocation) | `DSWPTI-260517` | Amazon Data Services, Inc. | 2026-06-16 | `oepa/sidney/4160653.pdf` |
| Isolated Wetland Permit — West Millcreek Rd/Fair Rd | Ohio EPA ID `252256W` | **City of Sidney** | 2026-05-04 | `oepa/sidney/4109706.pdf` |
| Construction stormwater GP — "6694 Transmission Line Reroute" | `1GC11112*AG` | **The AES Corporation** | 2026-07-09 | `grid/sidney/4184081.pdf` |
| NPDES — receiving POTW (Sidney WWTP) | `1PD00009*SD` / OH0027421 | City of Sidney | 2023-01-01 → 2027-12-31 | `oepa/sidney/1PD00009.pdf` |

- **Wetland impacts:** 0.24 ac of one forested Category 2 wetland + 0.18 ac of two non-forested
  wetlands (re-classified Category 2 → **Category 1** by the 2026-01-15 modification); mitigation
  = **1.0 forested credit at the Norton Run Mitigation Bank**; fill must be complete by
  2027-12-16. `[verified]`
- **AES on the ground:** AES filed for and received stormwater coverage for a **1.55-acre
  transmission line reroute** at 2522 Mill Creek Road, ~500 ft west of the campus NOI point,
  construction **2026-09-01 → 2026-12-31**. `[verified]` It states **no voltage, no rating and no
  megawatts** — it is a stormwater permit for an earthmoving job and is **not** evidence of the
  campus load. `[open]` stays `[open]`.

**Still open, checked and dated:**

- **Ohio EPA air PTI (emergency generators):** `[open]` — **verified negative as of 2026-07-31**.
  Ohio EPA eDocument returns zero AIR PERMIT documents for Shelby County under "SIDNEY DATA",
  "CMH" or "AMAZON"; EPA FRS shows the site with **NPDES as its only program system**. Positive
  control: the same query shape returns 19 Amazon air-permit documents statewide, including the
  Licking County "AMAZON DATA SERVICES – CMH050" draft, public notice and permit. So the zero is
  a zero, not a broken search. Generator count and ratings stay `[open]`; the `SiteFacility`
  genset fields stay unset. Jurisdiction for the air program is Ohio EPA **NWDO** (not RAPCA,
  which covers Clark/Darke/Greene/Miami/Montgomery/Preble) — surface water for the same county is
  **SWDO**.
- **OHD000001 (draft data-center NPDES general permit):** **abandoned.** Ohio EPA Community Notice
  of **2026-07-21**: it "has decided not to move forward with finalizing the general permit. The
  individual NPDES permit issuance process is the most appropriate path forward." `[verified]`
  It never applied here anyway — this campus discharges no process water to surface water.
- **PUCO 25-958-EL-AIR (AES Ohio multi-year rate plan / data-center tariff):** AES Ohio announced
  on **2026-07-21** an **unopposed Stipulation** with PUCO Staff and 16 parties including "a new
  Data Center Tariff as recommended by the PUCO," rates planned through 2029. `[reference]` — the
  utility's account of its own filing. The docket itself is **WAF-blocked** from this workstation
  (HTTP 200, 244-byte "Request Rejected"), so it is **unsearched, not empty**. No AES service
  agreement or interconnection filing naming this campus is on the record. `[open]`
- **City site-plan approval:** still "under review by City staff"; the FAQ has not moved since
  **2026-06-24**. Review is **administrative** under Zoning Code §1115.09 by the Community
  Development Director — the Planning Commission does **not** review it — so there will be no
  agenda item to watch; the approved plan is an R.C. 149.43 request. `[verified]`
- **Ohio SOS entity registrations:** Amazon Data Services, Inc. and Amazon Web Services, Inc.
  `[open]` — not pulled.

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

The original list's OEPA stormwater permit and Shelby County Auditor / GIS lines are **done**
(#1383 / #1379 — coverage `1GC10596*AG` and parcel `26-03-201-002`). What remains:

1. **City of Sidney council resolutions 18-25, 80-25, 81-25, 82-25, 26-26, 27-26** — CRA agreement,
   PILOT terms, water/sewer contract, infrastructure agreement. Primary instruments cited above.
2. **City of Sidney site plan as approved** — administrative under Zoning Code §1115.09, so it
   surfaces as a staff action, not an agenda item: an R.C. 149.43 request to the Community
   Development Director. Yields the building count.
3. **City of Sidney significant-industrial-user permit / pretreatment agreement for the campus** —
   the only instrument that separates data-center wastewater from the WWTP's totals. Municipal
   record, R.C. 149.43.
4. **OEPA Air PTI** — emergency-generator PTI for facility "SIDNEY DATA CENTER CAMPUS" or
   "CMH-232" (Ohio EPA **NWDO** for air; **not** RAPCA, **not** "Project Galaxy"). The
   draft-for-public-comment is the earliest signal and carries the generator count and ratings.
5. **Shelby County Recorder** — the deed behind **OR2329/454** (parcel `26-03-201-002`, grantee
   Amazon Data Services, Inc., 2025-11-24, $5,621,490). Acreage, transfer date and price are now
   `[verified]` from the auditor CAMA (#1379); what the recorder still owes is the **sequential
   instrument number**, the **grantor**, and any recorded easements — plus the companion
   **OR2329/497** (Shelby County Commissioners → Dayton Power & Light Co., `26-03-429-009`,
   7.305 ac, same day, $547,875), the likely campus substation conveyance (`[inference]`).
   Also pull **Plat V37 P50** (Lot 7658 Consolidation & Roadway Dedication Plat), which is the
   instrument that retired the "2388 W. Millcreek Rd" parcel and would close the ~4-ac
   planar-acreage difference as a roadway dedication.
6. **City of Sidney annexation / rezoning ordinance** for the campus parcel — the instrument that
   would close the zoning `[open]` the city's published GIS layers cannot (see "Zoning district").
7. **Ohio SOS** — Ohio foreign-corp registration for Amazon Data Services, Inc. and Amazon Web
   Services, Inc.
8. **FERC eLibrary** — an AES Ohio / Amazon transmission service agreement naming this campus. The
   City's FAQ answers a resident question premised on one existing without confirming or denying
   it, which makes it a lead, not a source.
9. **PUCO 25-958-EL-AIR** — the stipulation and the DCT tariff sheets, when the docket is
   reachable (currently WAF-blocked).
10. **Ohio EPA eDoc `4158406`** — the 20 MB approved sanitary-sewer-relocation plan set, the
    closest thing on the public record to a campus layout. Known, deliberately not pulled.

## Sources

### Primary instruments in the corpus (#1383, ingested 2026-07-31)

- Ohio EPA eDocument public portal — [`edocpub.epa.ohio.gov`](https://edocpub.epa.ohio.gov/publicportal/edochome.aspx),
  searched by Facility Name × County × Program. Provenance for every file:
  [`data/documents/oepa/sidney/filename-map.yaml`](../../documents/oepa/sidney/filename-map.yaml)
  and [`data/documents/grid/sidney/filename-map.yaml`](../../documents/grid/sidney/filename-map.yaml).
- Ohio EPA DAM permit slots — `1PD00009` issued permit and draft-public-notice/fact-sheet package.
- EPA ECHO `cwa_rest_services` and Envirofacts `ICIS_PERMIT` / `FRS_PROGRAM_FACILITY` — the
  federal cross-check, and the source of the "Project Galaxy" collision finding.
- Ohio EPA NPDES General Permits page, captured 2026-07-31 — the 2026-07-21 Community Notice
  abandoning OHD000001.

### Secondary / self-published

- City of Sidney FAQ (primary): [sidneyoh.com/526/Proposed-Data-Center-FAQ](https://www.sidneyoh.com/526/Proposed-Data-Center-FAQ)
- AES Ohio press release, 2026-07-21 (`[reference]` — a party's account of its own PUCO filing):
  [aes-ohio.com/press-release/aes-ohio-files-unopposed-settlement-its-three-year-rate-plan](https://www.aes-ohio.com/press-release/aes-ohio-files-unopposed-settlement-its-three-year-rate-plan)
- Data Center Dynamics (Oct 2025): [amazon-secures-tax-break-3bn-data-center-campus-sidney-ohio](https://www.datacenterdynamics.com/en/news/amazon-secures-tax-break-for-3bn-data-center-campus-in-sidney-ohio/)
- Obedio (Apr 2026 infrastructure approvals): [aws-data-center-campus-in-sidney-ohio-clears-final-infrastructure-approvals](https://hs.getobedio.com/blog/aws-data-center-campus-in-sidney-ohio-clears-final-infrastructure-approvals-locking-in-8m-of-private-road-funding)
- Stop Ohio Data Centers (advocacy, use for leads not primary facts): [stopohiodatacenters.org/shelby-county](https://stopohiodatacenters.org/shelby-county)
- WHIO TV (community meeting): [community-gathers-share-concerns-learn-about-data-center-plans-shelby-county](https://www.whio.com/news/local/community-gathers-share-concerns-learn-about-data-center-plans-shelby-county/OF4XYJ5YAVEXZGH55OYPRZLHIA/)
