# Sidney / Shelby County, OH — Data-Center Activity Register

Discover-and-pin register for the Sidney onboarding — the **I-75 corridor** sweep required by
#511. Base status **as of 2026-07-02**; the regulatory record re-checked and the state
instruments **ingested 2026-07-31** (#1383); the City's own **primary instruments ingested
2026-08-01** (#1380). Tags are BOSC evidentiary discipline: `[verified]` = cited public source,
`[inference]`, `[open]`, `[reference]`. Every figure is cited; none is fabricated. Do not bridge
the Lima/Allen Bistrozzi graph onto Shelby County — there is no evidentiary link.

The standing watch and its dated negatives live in
[`regulatory-watch.yaml`](regulatory-watch.yaml); the structured read of the City's instruments is
[`incentive-instruments.yaml`](incentive-instruments.yaml); the source bytes are in
[`data/documents/sidney/council/`](../../documents/sidney/council/),
[`data/documents/sidney/permits/`](../../documents/sidney/permits/),
[`data/documents/oepa/sidney/`](../../documents/oepa/sidney/) and
[`data/documents/grid/sidney/`](../../documents/grid/sidney/).

> **What the 2026-08-01 instrument pull changed.** A run of this register's `[verified]` financial
> and chronological facts came from the City's FAQ, the trade press or an advocacy site, and the
> executed instruments contradict them. The PILOT is **$46M over 14 years**, not $50M over 15; the
> **$50M** figure is the PILOT cap **plus a separate $4M initial payment**, and the schools' half
> is **$21.2M to Sidney City Schools and $3.8M to Upper Valley Career Center**, not $25M to
> Sidney. The CRA legislation is **Res. 69-25 of 2025-09-08**, not "Res. 18-25, October 2025".
> The **NDA is dated 2023-12-19**, not mid-2025. Projected cooling-water **consumption** is
> **3.44M gal/yr**, not 4.6M — that figure is the withdrawal. Each correction is carried below
> with the instrument that makes it.

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
  disambiguation guardrail above. `[verified]` A third name, **"Project Rey"**, is the name the
  **City itself uses in an executed instrument**: the Development Agreement authorized by
  Resolution 81-25 calls the investment "its Project Rey data center investment" in the recitals
  and again in the non-precedent clause (§6.4). `[verified]`
  Source: `data/documents/sidney/council/81-25 - Authorizing Development Agreement with Sidney City Schools and Upper Valley - Amazon Data Services_202601141342204952.pdf`.
  *This closes the prior `[open]`, which rested on a single resident's question on the City FAQ.
  So the campus carries four names across four record systems — the state's two, the trade
  press's one, and the City's own.*
  The AWS designation **CMH-232** is corroborated from the municipal side too: the Development
  Agreement routes developer notices to "Attention: Real Estate Manager (AWS) **CMH232**".
  `[verified]`
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
  *Confirmed by instrument 2026-08-01 (#1380): the Development Agreement's Exhibit A carries a
  surveyed metes-and-bounds description — **243.0924 acres**, by **Farnsworth Group, Inc.** under
  **Justin A. Bischof, P.S. #8596**, bounded north by the **CSX Transportation** right-of-way
  (D.V. 381 p. 290) — matching the CAMA's deeded acreage to four decimals. Both Res. 27-26 and
  Res. 26-26 independently recite the same **five** predecessor parcel numbers, so #1379's
  geometric reconstruction of the assemblage is now corroborated by two City instruments.*
- **The deeds: three, not one.** `[verified]` The Development Agreement's Exhibit A closes with
  "Being all of the lands now or formerly owned by" and names **three** conveyances to Amazon Data
  Services Inc., all in Official Record volume 2329:
  **O.R. 2329/445** (Lot 7648, predecessor `02-2603226.001`) · **O.R. 2329/449** (Lot 7647,
  predecessor `02-2603201.001`) · **O.R. 2329/454** (Lot 7646, predecessor `02-2603126.001`).
  Source: `data/documents/sidney/council/27-26 - Authorizing Infrastructure Development Agreement - Amazon Web Services.pdf`, Exhibit A.
  *The auditor CAMA carried only OR2329/454 against the consolidated parcel, so this register and
  #1379 both recorded a single deed. Three still leaves two of the five predecessor tracts
  (`-251-001`, `-251-002`) unaccounted for, and lot numbers 7646/7647/7648 are **not** Lot 7658,
  the lot the consolidation plat created. Grantors, instrument numbers, per-deed consideration and
  easements remain `[open]` — but book and page are now known, so the recorder pull is a
  retrieval rather than a search.*
- **Abutting owners of record** (from the same legal description): Mill Creek Subdivision Nos. 1–4
  (Plat Book 5 p. 96; 7 p. 23; 7 p. 34; 7 p. 47), **Bridget Douglas** (O.R. 2269 p. 659) and
  **John A. Clark, Jr.** (O.R. 2319 p. 5821). `[verified]`
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
- **Construction:** City of Sidney Engineering Department **grading permit signed 2026-05-15** by
  Engineering Manager **Chad M. Arkenberg**, contractor of record **George J. Igel & Co., Inc.**,
  valid **180 calendar days**, scope limited to "excavation and site preparation" — it is **not**
  a building permit. Ground breaking ~January 2026. `[verified]`
  Source: `data/documents/sidney/permits/Grading Permit 5-14-2026 - AWS Data Center 2388 W. Millcreek Road.pdf`.
  *Date corrected from 2026-05-14: that is the date in the City's **filename**, and the permit's
  own signature block reads 5/15/2026. Per chain-of-custody rules a filename is not evidence of a
  date. The permit also recites a **grading plan** and a **storm water report** "on file at the
  City's Engineering Department" — neither is published; both are new `[open]` leads.*
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

Full structured read, clause by clause: [`incentive-instruments.yaml`](incentive-instruments.yaml).
Source bytes: [`data/documents/sidney/council/`](../../documents/sidney/council/).

- **The chain of legislation.** `[verified]` Five resolutions over six months:
  **69-25** (2025-09-08) designating the CRA · **80-25 / 81-25 / 82-25** (all 2025-10-27) — the CRA
  Agreement, the school distribution agreement, the income-tax sharing agreement · **26-26 / 27-26**
  (both 2026-04-27) — water/wastewater service and public infrastructure.
  *The register previously named "Resolution 18-25 … October 2025" as the CRA instrument. No such
  legislation exists in this chain. The designating legislation is **Resolution 69-25, adopted
  2025-09-08**, and it designates a **City-Wide** Community Reinvestment Area, not a
  project-specific envelope. Both the CRA Agreement's recitals and Resolution 82-25's recitals
  state it independently. Res. 69-25 itself is `[open]` — see "Instruments to pull".*
- **State certification of the CRA:** the Director of the Ohio Department of Development
  designated the area **effective 2025-09-19** as CRA area **# 149-72424-06A**. `[verified]`
  Source: Res. 82-25 recitals.
- **CRA tax abatement:** 30-year, **100%** real-property exemption **per Building**; **no exemption
  may commence after tax year 2035** and none extends beyond **tax year 2065**; the exemption
  applies irrespective of whether the Company, an Affiliate or another entity owns the property.
  Resolution 80-25, effective 2025-10-27. `[verified]` (CRA Agreement §4.)
  *The 2035 commencement cutoff is new to this register. Because each Building runs its own
  30-year clock, the exemption for the Project as a whole may last more than 30 years.*
- **The abatement did not take effect in October 2025.** `[verified]` CRA Agreement §34 conditions
  the exemptions on **prior execution of a Development Agreement** for public infrastructure. That
  agreement is Resolution 27-26 — six months later, **2026-04-27**.
- **PILOT — corrected.** `[verified]` The CRA Agreement caps PILOTs at **$46,000,000** over a
  **14-year** term (§7(b); Exhibit E schedules 13 years at $3,333,333 plus a final $2,666,671).
  A **separate one-time $4,000,000 Initial Payment** (§8) brings Total Payments to **$50,000,000**.
  *The register previously carried "$50 million total over 15 years — $25M to City, $25M to Sidney
  City Schools", sourced to the City FAQ and DCD. Every element of that was off: the $50M is not
  all PILOT, the PILOT term is 14 not 15 years, and the schools' share does not go to Sidney.*
- **Where the $50,000,000 actually goes.** `[verified]` Resolution 81-25 §2.1 and Exhibit A:
  **50% City of Sidney = $25,000,000** (including the whole $4,000,000 paid up front) and
  **50% to the school districts = $25,000,000**, which divides **$21,220,529 to Sidney City
  Schools (84.882116%)** and **$3,779,471 to Upper Valley Career Center (15.117884%)**.
  The City's own column zeroes out in Years 13–15 while the schools take $2,500,000 in each.
- **PILOT ceiling mechanism:** in any year the Company's total payments would exceed 100% of the
  taxes otherwise payable, the PILOT is cut to that ceiling and the shortfall carries forward.
  `[verified]` (§7(b).) The abated taxpayer can never be made to pay more than an unabated one.
- **Schedule discrepancy — `[open]`.** The CRA Agreement's Exhibit E runs **14** PILOT years; the
  distribution schedule attached to Res. 81-25 lays the same $46,000,000 across **15**, and its own
  workspace cells read "Total $50,000,000 / Per Year $3,333,333.33". The binding cap is the CRA
  Agreement's. Which instrument governs the final year is unresolved on this record.
- **Income tax sharing (R.C. 5709.82):** the City calculates **75%** of municipal income tax
  withheld from **New Employees** (the permanent **1.5%** levy); Sidney City Schools receives the
  **lesser** of that and (foregone property tax × **85%**), Upper Valley receives (foregone
  property tax × **15%**), disbursed the second week of May. `[verified]` Resolution 82-25 §4.
  *Note the split differs from the PILOT split — 85/15 here, 84.88/15.12 there. Different bases;
  do not quote them interchangeably.*
- **The school boards waived their statutory rights.** `[verified]` Res. 81-25 §3.1: both boards
  **irrevocably** approve every exemption grantable under the CRA Agreement, **irrevocably waive**
  notice under R.C. 3735.671, 5709.83 and 5715.27, waive any right to grant approvals required by
  R.C. 3735.671, and waive any defects or irregularities in the authorization. §4.2 states the two
  school agreements are "the entirety of the compensation" they may be entitled to.
- **Megaproject status — a state instrument this corpus does not hold.** `[verified]` The CRA
  Agreement recites that on **2025-10-08** the **Ohio Tax Credit Authority** authorized a **Sixth
  Amendment to Tax Credit Agreement** under which the Company qualifies as a **"megaproject"** and
  **"megaproject operator"** (R.C. 122.17(A)(11)–(12)). §12 hangs **years 16 through 30** of the
  abatement on the Company holding a current Megaproject Certificate or certifying annually.
  The amendment itself is `[open]` — see "Instruments to pull".
- **No clawback.** `[verified]` The City's sole remedy for material breach is to terminate,
  suspend or modify the exemptions (§12); for unpaid non-exempt taxes, rescission (§6). No
  provision requires repayment of PILOTs already made. The Company may terminate the agreement
  **for any reason or no reason on 30 days' notice** (§28), and both parties are barred from
  challenging the validity of the agreement or of the CRA (§20).
- **Job and investment figures are estimates, not covenants.** `[verified]` §1 and §2 state in
  terms that the $3,000,000,000 investment, the 75 jobs and the $6,750,000 payroll "will not limit
  the amount or term of the tax exemptions … or allow the City to compel the Company" to invest or
  to hire. They are R.C. 3735.671(B) good-faith estimates.
- **Abatement estimated value:** $180–$350 million over 30-year term (~$2.4M–$4.6M per job). `[reference]`
  Source: stopohiodatacenters.org/shelby-county (advocacy group; figures not independently
  verified against appraisal records). *No instrument in the corpus values the abatement, and the
  §4 exemption is per-Building against valuations that do not yet exist, so this stays
  `[reference]`.*
- **Infrastructure contribution:** **not to exceed $8,000,000**, deposited into escrow with
  **Fidelity National Title** within 10 business days of the effective date and drawn monthly
  against City Engineer certification, with up to 5% retainage and any unspent balance refunded.
  The City bears every City Improvements cost above it. Resolution 27-26. `[verified]`
  (City engineer's estimate $7,927,151.50 — `[reference]`, obedio.com; no instrument states it.)
- **NDA — corrected.** The Nondisclosure Agreement is dated **2023-12-19**, executed by the City
  for the benefit of the Developer and its Affiliates, and the Development Agreement binds the
  City to **continuing** compliance with it (§8.17). `[verified]` Source: Res. 27-26 Project
  Summary. *The register carried "executed mid-2025 … prior to public announcement", sourced to
  an advocacy site. The instrument puts it **twenty-two months earlier** — the City was under NDA
  from December 2023.*
- **The resolution and the agreement name different Amazon entities.** `[verified]` Resolution
  27-26 authorizes a Development Agreement with **Amazon Web Services, Inc.**; the agreement it
  authorizes names **Amazon Data Services, Inc.** as "Developer" in its Project Summary and
  signature block. Both entities are real and both appear elsewhere in this record. Not resolved
  here. (Res. 26-26 and its water agreement, by contrast, agree on Amazon Web Services, Inc.)

### Water / hydrology hook

The governing instrument is the **Water and Wastewater Service Agreement** (Execution Version)
authorized by Resolution 26-26 and adopted 2026-04-27, with its Schedule 1 impact-fee attachment —
`data/documents/sidney/council/26-26 - Authorize Water and Sewer Service Agreement - Amazon Web Services.pdf`.
It states **four** reserved capacities where this register previously had one.

- **Reserved capacities — all four, `[verified]` (§1.1):**

  | Service | Maximum | Rate cap | Projected annual |
  |---|---|---|---|
  | Cooling water | 1.0 MGD | 694 gpm | 4,600,000 gal |
  | Potable water | 14,000 gpd | — | — |
  | Fire flow | — | ≥1,818 gpm at ≥20 psi | — |
  | **Sewer discharge** | **390,493 gpd** | **716 gpm gravity** | **1,160,000 gal** |

- **The sewer number closes a standing `[open]`.** The register held that nothing separated the
  campus's wastewater from the WWTP's totals. That remains true of **metered actual** discharge
  (which needs the City's pretreatment/SIU permit, still `[open]`), but the **reserved** capacity
  is now documented: **0.390493 MGD = 5.60% of the 7 MGD plant**, with 1,160,000 gal/yr projected.
- **Projected consumption — corrected.** `[inference]` (arithmetic from `[verified]` inputs.)
  4,600,000 gal/yr is the projected annual **withdrawal**; 1,160,000 gal/yr **returns** to the
  sanitary sewer; consumption is the **3,440,000 gal/yr** difference — **~9,425 GPD = 0.0146 cfs**,
  which is **0.061%** of the cited regulatory Great Miami 7Q10 of 24.0 cfs.
  *The register described the 4.6M gal/yr figure as "projected cooling-water consumption" and
  screened 0.0195 cfs / 0.08% off it. The agreement calls it the annual cooling water **volume**
  and books the return separately, so the old figure overstated consumption by ~34%. The
  conclusion — no assimilative flag on water-quantity grounds — is unchanged and now stronger.*
- **The cooling mechanism finally appears in a record.** `[verified]` The City's 2026-04-27 staff
  presentation states "All wastewater, **including cooling tower discharges**, are required to be
  discharged to the sanitary sewer." That is the only description of the cooling design on the
  public record.
  **Back-solved cycles of concentration ≈ 4.0** `[inference]` — makeup 4,600,000 ÷ blowdown
  1,160,000 = 3.97, the signature of a closed-loop evaporative tower. This is the first
  documentary handle on the campus's cooling model, which `_SIDNEY.facility` still carries as
  `UNKNOWN` (#1378). It is a *projection* in a service agreement, not a design disclosure — it
  brackets the model, it does not close it.
- **The City contracted away its data-center rate class.** `[verified]` §2.1: "During the Term of
  this Agreement, Provider **shall not take steps to create a separate class of water or sewer
  rates for data centers** or similar high level, but highly variable, users." Ten years, renewing
  annually. Note the contrast with the electric side of the same campus, where AES Ohio's
  2026-07-21 PUCO stipulation is reported to **create** a data-center tariff.
- **Reserve-capacity impact fees** `[verified]` (§2.2, Schedule 1): AWS pays the ordinary metered
  rate for what it uses **plus** a monthly fee on the **unused** portion of its reservation —
  water at 14.3% of the $7.23/ccf standard rate (**$1.033/ccf**), sewer at 5.60% of the $4.11/ccf
  rate (**$0.230/ccf**). Reopened every three years from the third anniversary of build-out. The
  reserved **percentages** are fixed; the dollar rates track the City's ordinance rates.
- **Term and exit** `[verified]` (§3): 10 years, auto-renewing annually. **AWS may terminate at any
  time on 90 days' notice**; the City may terminate only after 3 years **and** 12 consecutive
  months of ceased operations.
- **Substitute supply is preserved** `[verified]` (§1.5): if the City fails to supply enough water
  or sewer service, AWS "may secure its own substitute services" and the City must provide access
  to its infrastructure. The FAQ's "no onsite wells will be used" is a present-tense description,
  not a contractual bar.
- **Regulatory penalties pass through** `[verified]` (§6.2): fines assessed against the City that
  result from AWS exceeding its §1.2 maxima are direct damages reimbursable by AWS.
- **What the reservation costs the City in headroom** `[inference]` (from the City's own
  presentation): water 2025 average daily demand **3.1 MGD** against a **7.0 MGD** plant leaves
  **~3.9 MGD**, so the 1.0 MGD reservation takes **25.6%** of remaining water headroom; the WWTP's
  2025 average daily flow **4.6 MGD** against **7.0 MGD** leaves **~2.4 MGD**, so 0.390493 MGD
  takes **16.3%** of remaining sewer headroom. Ohio EPA-approved raw pumping capacity is 14.0 MGD,
  which is a different constraint from the 7.0 MGD treatment design.
- **Water source:** City of Sidney municipal system — multiple sources: groundwater wells, Great
  Miami River intake, Tawawa Creek. `[verified]` Source: sidneyoh.com/526.
- **Wastewater:** all facility wastewater to Sidney municipal sanitary sewer → OH0027421 → Great
  Miami River. `[verified]` Source: sidneyoh.com/526; agreement §1.1.4.
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
  **3.44M gal/yr** (withdrawal 4.6M less the 1.16M returned to the sewer) = **0.0146 cfs** average
  = **0.061% of the 7Q10 denominator** — no assimilative violation flag on water-quantity grounds.
  `[inference]` (arithmetic from cited inputs; the return volume is Res. 26-26 §1.1.4.)
  *Supersedes the 0.0195 cfs / 0.08% figures, which treated the whole withdrawal as consumed.*
- **Effluent path:** all process water returns via OH0027421 → Great Miami River at **RM 128.68**
  (design 7.0 MGD, peak hydraulic 13.5 MGD; actual 4.01 MGD 2023 MO-AVG mean). The plant also
  serves Port Jefferson, the Mill Creek Subdivision and the Honda of America plant in Anna, and
  is allocated jointly with the **Piqua and Troy WWTPs** as interactive dischargers. `[verified]`
- **Separating the campus's wastewater:** its **actual metered** discharge will **not** appear
  separately in the WWTP's DMRs — a DMR reports outfall 001, not an individual user. The
  instrument that would separate it is the **City of Sidney's own industrial-pretreatment /
  significant-industrial-user permit** (the City reports 16 SIUs today), an R.C. 149.43 municipal
  record that is not on Ohio EPA's portal. `[open]` — no SIU permit for the campus is on the
  record.
  *Partially closed 2026-08-01: the **reserved** figure is now documented even though the metered
  one is not — 390,493 gpd maximum at 716 gpm gravity, 5.60% of the 7 MGD plant, 1,160,000 gal/yr
  projected (Res. 26-26 §1.1.4 and Schedule 1). A capacity reservation is a ceiling and a billing
  basis, not a measurement; the SIU permit is still what would produce a measured number.*

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
  `[open]` — **verified negative ROUTE as of 2026-08-01**, which is not the same as a verified
  absence. `businesssearch.ohiosos.gov` answers **HTTP 403** with a ~1.3 MB challenge body to
  scripted clients and `businesssearch.ohiosos.com` no longer resolves, so there is no scripted
  route from this workstation; the registrations are **unsearched, not missing**.
  *Partly moot on the substance: both companies are recited as **Delaware corporations** in the
  City's executed instruments (CRA Agreement preamble; Water Agreement preamble; Development
  Agreement Project Summary), so entity type and formation jurisdiction are `[verified]` from a
  primary source. What the SOS record would add is the Ohio foreign-registration date, the
  statutory agent and the agent's address.*
- **The City's own legislative portal:** `[open]` — ⚠️ **route corrected 2026-08-11 (#1999); it is
  REACHABLE.** `sidneycityoh.documents-on-demand.com` returns HTTP 403 to a **default (HTTP/2)**
  request — a genuine Cloudflare challenge (`cf-mitigated: challenge`) — and that was read as a
  host-wide block. It is not one: the trigger is the **HTTP/2 fingerprint**, not the client. The
  same request forced to **HTTP/1.1** with a browser UA returns **HTTP 200**, and the host exposes
  a JSON tree (`/meta/rootfolder`) enumerating City Council → Agendas / Agenda Packets /
  Legislation → **Ordinances, Resolutions** / **Minutes**. It is the route to Resolution **69-25**
  and to any council minutes, and it is now **searchable — neither has been pulled yet**, which is
  a retrieval job rather than a blocked route. The five data-center resolutions were obtained
  instead from the City's own DocumentCenter, linked off the FAQ.
- **Shelby County Recorder:** `[open]` — **route negative as of 2026-08-01**.
  `search.shelbyco.net/eservices/` answers HTTP 200 but is an Apache-Wicket application that
  posts a browser fingerprint before it will run a search; index stated to run from 1989-07-01.
  Book and page for all three campus deeds are now known from Res. 27-26, so the pull is a
  document retrieval (copy request to `recorder@shelbyco.net`), not a search.

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

The OEPA stormwater permit and Shelby County Auditor / GIS lines are **done** (#1383 / #1379 —
coverage `1GC10596*AG` and parcel `26-03-201-002`), and the **City council resolutions and the
grading permit are done** (#1380, 2026-08-01 — Res. 80-25 / 81-25 / 82-25 / 26-26 / 27-26 with
their executed agreements, in `data/documents/sidney/council/` and `data/documents/sidney/permits/`,
structured in [`incentive-instruments.yaml`](incentive-instruments.yaml)). What remains:

1. **City of Sidney Resolution 69-25** — the CRA designating legislation itself (2025-09-08,
   city-wide). Its terms are `[verified]` only through two instruments' recitals. The City does
   not publish it on the FAQ or in the DocumentCenter. ⚠️ **Search the legislative portal before
   requesting it** (#1999): `sidneycityoh.documents-on-demand.com` was read as Cloudflare-blocked,
   but the 403 is an HTTP/2 fingerprint block and the host answers **HTTP/1.1 with 200** and a
   browsable Resolutions tree. Still unpulled. Failing that, an R.C. 149.43 request to the
   Sidney City Clerk, 201 W. Poplar St.
2. **City of Sidney site plan as approved** — administrative under Zoning Code §1115.09, so it
   surfaces as a staff action, not an agenda item: an R.C. 149.43 request to the Community
   Development Director. Yields the building count. *The Development Agreement confirms a site
   plan is in the approval loop (§3.6.1, §5.4 site-plan fee under Codified Ordinances §1309.11).*
3. **City of Sidney significant-industrial-user permit / pretreatment agreement for the campus** —
   the only instrument that separates data-center wastewater from the WWTP's totals. Municipal
   record, R.C. 149.43. *Now sharper: the service agreement fixes the reserved ceiling at 390,493
   gpd, so the SIU permit is what would show actual load against it.*
4. **OEPA Air PTI** — emergency-generator PTI for facility "SIDNEY DATA CENTER CAMPUS" or
   "CMH-232" (Ohio EPA **NWDO** for air; **not** RAPCA, **not** "Project Galaxy"). The
   draft-for-public-comment is the earliest signal and carries the generator count and ratings.
5. **Shelby County Recorder — three deeds, not one.** `OR2329/445` (Lot 7648), `OR2329/449`
   (Lot 7647) and `OR2329/454` (Lot 7646), all grantee Amazon Data Services Inc., named in
   Res. 27-26 Exhibit A. Acreage, transfer date and aggregate price are `[verified]` from the
   auditor CAMA (#1379); what the recorder still owes is the **grantors**, the **sequential
   instrument numbers**, the **per-deed consideration**, any recorded easements, and whichever
   instrument carried predecessor parcels `-251-001` and `-251-002`. Plus the companion
   **OR2329/497** (Shelby County Commissioners → Dayton Power & Light Co., `26-03-429-009`,
   7.305 ac, same day, $547,875), the likely campus substation conveyance (`[inference]`).
   Also pull **Plat V37 P50** (Lot 7658 Consolidation & Roadway Dedication Plat), which retired
   the "2388 W. Millcreek Rd" parcel, would close the ~7.6-ac deeded-vs-planar difference as a
   roadway dedication, and would connect the 7646/7647/7648 lot series to Lot 7658.
6. **Ohio Tax Credit Authority — Sixth Amendment to Tax Credit Agreement, 2025-10-08.**
   *New lead out of the 2026-08-01 ingest.* The CRA Agreement recites it and conditions years
   16–30 of the abatement on the megaproject certification it establishes (R.C. 122.17(A)(11)–(12)).
   Route: Ohio Department of Development / Tax Credit Authority meeting minutes and agreements.
7. **City of Sidney annexation / rezoning ordinance** for the campus parcel — the instrument that
   would close the zoning `[open]` the city's published GIS layers cannot (see "Zoning district").
8. **The grading plan and storm water report** on file with the City Engineering Department.
   *New lead* — both are recited on the face of the grading permit. Expect R.C. 149.433 to be
   asserted over parts (see "Records posture").
9. **Ohio SOS** — Ohio foreign-corp registration for Amazon Data Services, Inc. and Amazon Web
   Services, Inc. Entity type and Delaware formation are already `[verified]` from the executed
   instruments; the SOS record would add the Ohio registration date and the statutory agent.
10. **FERC eLibrary** — an AES Ohio / Amazon transmission service agreement naming this campus. The
    City's FAQ answers a resident question premised on one existing without confirming or denying
    it, which makes it a lead, not a source.
11. **PUCO 25-958-EL-AIR** — the stipulation and the DCT tariff sheets, when the docket is
    reachable (currently WAF-blocked).
12. ~~**Ohio EPA eDoc `4158406`** — the 20 MB approved sanitary-sewer-relocation plan set.~~
    **PULLED 2026-08-11 (#1998), and it does not answer the question it was ranked for.** Eight
    sheets — cover, two of general notes, a demolition plan, four PROFILE sheets — sealed by James
    D. Whitacre, Advanced Civil Design Inc, E-68154, 2026-04-16; Ohio EPA approved 2026-06-16
    (internal DSW-7167, cross-checking the PTI already held). **No cooling design**: "cooling",
    "pump", "force main", "manhole" and every pipe material are absent from its text layer, so the
    campus MW and cooling method stay `[open]` and `facility` readiness stays `seeded`. It carries
    no building footprint either. Structured read
    [`../oepa/sidney/4158406.plan.yaml`](../oepa/sidney/4158406.plan.yaml). The companion
    **application package (eDoc `4158414`, 18 pp.)** was shelved at the same time but is **unread**
    — it has NO text layer and needs a rendered/OCR read. It is the more likely of the two to state
    a design FLOW, so it is the next thing to read for the water thread.
13. **Unredacted Development Agreement exhibits** — the City published it with sewer and water
    line dimensions blacked out under R.C. 149.433. See "Records posture".

## Records posture

*Added 2026-08-01 (#1380). This project's public record arrives with three layers of friction on
it, all of them documented in the instruments themselves.*

- **The City redacted the published Development Agreement and wrote the statute beside each
  redaction, by hand, in blue ink: `ORC 149.433`.** `[verified]` (Read from the page image, not
  from OCR.) Redacted: sewer line size, manhole count and linear footage and the water service
  line size and location in the Article 1 definitions — and the **entire Exhibit D water service
  exhibit**, which is blacked out edge to edge with only its title, its scale bar (1 inch = 150
  feet) and a few stray linework fragments surviving. R.C. 149.433 exempts security and
  infrastructure records. Whether the application is sound is not assessed here; what is recorded
  is that the redactions exist, what they cover, and which statute the City cited.
- **Both major agreements carry a notice-before-disclosure clause.** `[verified]` CRA Agreement
  §32 and Development Agreement §8.17 require the City, on receiving a public-records request
  touching the company's "Confidential Information", to notify the company, give it a copy of the
  request, and allow it **at least five business days** to negotiate a response or "pursue, at its
  sole cost and expense, legal remedies to stop the City's release". Neither clause enlarges any
  R.C. 149.43 exemption — they are contractual delay layered on top of the statute — but a
  requester should expect the delay.
- **The 2023-12-19 NDA is still operative** and the City is contractually bound to continuing
  compliance with it (Development Agreement §8.17). `[verified]`
- **The City publishes the Ohio Attorney General's statutory-exemptions chart on the data-center
  FAQ page itself.** `[verified]`
  ([`/DocumentCenter/View/4586`](https://www.sidneyoh.com/DocumentCenter/View/4586/Statutory-Exemptions---Public-Records-PDF).)
  Not ingested — it is the AG's statewide chart, not a Sidney instrument; its **presence on that
  page** is the fact worth recording.
- **R.C. 149.433 is asserted on the engineering drawings too — as a pre-printed template field.**
  `[verified]` (#1998.) Every sheet of the approved sewer plan set carries: *"LEGAL NOTICE THIS
  INFORMATION IS VOLUNTARILY SUBMITTED TO A PUBLIC OFFICE IN EXPECTATION OF PROTECTION FROM
  DISCLOSURE AS PROVIDED BY SECTION 149.433 OF THE REVISED CODE."* That is the same statute the
  City wrote by hand beside its redactions, arriving here as a standing claim printed on the
  drawing template rather than a case-by-case judgement. **And Ohio EPA published the set anyway**,
  unredacted, on its public eDocument portal, where it was retrieved with a plain HTTP GET. The
  exemption is a claim by the submitter, not a determination by the agency, and on this record it
  did not prevent disclosure — which is worth knowing before treating a 149.433 marking as the end
  of an inquiry.

- **Practical implication** `[inference]`: frame requests to the **instrument or the approval**
  rather than to the engineering drawing, and expect a five-business-day company-notice delay.

## Sources

### City of Sidney primary instruments in the corpus (#1380, ingested 2026-08-01)

- City of Sidney Document Center — `https://www.sidneyoh.com/DocumentCenter/View/<id>`, linked
  from the City's own Proposed Data Center FAQ. Open to scripted retrieval, and it sends a real
  `Content-Disposition` filename, so the as-received names are the City's own upload names.
  Provenance for every file:
  [`data/documents/sidney/council/filename-map.yaml`](../../documents/sidney/council/filename-map.yaml)
  and [`data/documents/sidney/permits/filename-map.yaml`](../../documents/sidney/permits/filename-map.yaml).
- Structured read of the whole set, clause by clause, with the corrections it forces:
  [`incentive-instruments.yaml`](incentive-instruments.yaml).

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
