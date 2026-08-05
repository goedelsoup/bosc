# Bowling Green / Wood County, OH — Data-Center Activity Register

Discover-and-pin register for the Bowling Green watershed point — the **Portage River · Maumee
divide** (drinks the Maumee at the Waterville intake, discharges to the North Branch Portage).
Status **as of 2026-07-10 (#1435)**. Tags are BOSC evidentiary discipline: `[verified]` =
on-record in a government/primary source (often two+), `[reported]` = credible secondary /
investigative journalism, not officially confirmed, `[reference]` = authoritative-but-secondary
dataset/claim, `[inference]` = grounded reasoning, `[open]` = genuinely unsourced. Most of the
company/PR material here is a **lead** — the facility pins on the site plan + the OPSB/permit
instruments; MW figures stay tagged until an instrument names them. Every figure is cited; none
is fabricated.

## Disambiguation guardrail

Most "**Bowling Green data center moratorium**" headlines online are **Bowling Green, KENTUCKY**
(Warren County, KY). The **Ohio** city (Wood County) has enacted **no** data-center moratorium —
though **7 Wood County townships** have, with 8 more discussing (`[reference]`, county governance
wave, #1440). Keep clearing this trap on every search. The two confirmed Ohio facilities below —
Meta (Middleton Twp) and Oppidan (city proper) — are **distinct projects**; do not conflate them.

## 1 — Meta "Bowling Green Data Center" / "Project Accordion" (Middleton Twp)

- **Operator:** **Meta Platforms** — announced as the "Bowling Green Data Center", Meta's 24th US /
  28th global data center and its **2nd in Ohio**. `[verified]` Source: Meta, "Hello, Bowling
  Green" (2025-04-09); Middleton Township ("Meta introduced as company behind township data
  center").
- **Land / nominee entity:** **Liames, LLC** — the entity on all deeds and rezoning applications,
  and the **customer of record on OPSB 25-0973-EL-BLN**. `[verified]` (docket) · the corporate
  parentage tying Liames to Meta pre-reveal was `[reported]` press before the 2025-04-09
  confirmation.
- **Codename:** **"Project Accordion"** — the NDA-era name (2023→2025). `[reference]` Source: BG
  Independent, Wood County Economic Development Corp (WCEDC) coverage. **Do not merge the Liames,
  LLC entity record with a Meta entity in the graph on the codename alone** — the pre-reveal link
  was press; the post-reveal Meta operator attribution is what carries `[verified]`.
- **Site:** Middleton Township, **SR-582 between SR-25 and I-75**, adjacent the FirstEnergy
  **Mercer Rd substation**; **~280-ac initial site** inside the Liames land assembly.
  `[verified]` township/company for the location · `[reference]` for the ~280-ac initial-site
  split (a site-plan figure, not derivable from the parcels). Deeds recorded from **2023-09-05**.
- **Land of record (#1436, the places domain):** **twelve contiguous Wood County parcels deeded
  to LIAMES, LLC — 775.020 ac deeded / 774.878 ac planar**, whose union is a **single polygon**
  over a 1,821 m × 2,489 m extent. `[verified]` — the county auditor's Vision CAMA, committed as
  `data/reference/bowling-green/parcel-assemblage.geojson`. This **replaces the "~750-ac"
  `[reference]` press figure with a measurement**, and the contiguity is measured, not summed.
  Four tracts over 50 ac carry 753.65 ac; the other 21.37 ac are eight small parcels along SR-25,
  Mercer Rd and Middleton Pike. **Eight of the twelve parcels are billed to `1 META WAY, MENLO
  PARK, CA 94025`** — Meta's own headquarters, in the tax record, independent of the
  announcement; the other four go to `52 E GAY ST, COLUMBUS, OH 43215`. A billing address is not
  ownership of the LLC, and the Ohio SOS registration for Liames stays `[open]`. **Do not sum
  the transfer prices**: the CAMA keeps only the last conveyance per parcel, and the 2025-04-09
  consolidation quitclaims ($0) erased eleven predecessor tracts' purchase prices, so the
  $6,921,460 that survives is a floor on a fraction of the assembly. The **FirstEnergy/ATSI
  transmission tract** (72.43 ac, 22105 Mercer Rd) and the **Northwestern Water & Sewer
  District's** 20-ac tract at 12560 Dixie Hwy both **share a boundary with the assembly at
  0.0 m** — the profile's "adjacent the Mercer Rd substation" is now a measurement too.
- **Zoning:** the campus core reads **99.8–100% `M-1: Light Industrial`** in Middleton Township's
  own parcel-joined layer. `[verified]` The eight small parcels still read `A-1` / `R-4` there:
  they are part of the **thirteen parcels / 31.82 ac the trustees rezoned to M-1 by 2–1 on
  2026-07-07**, and **no published Wood County layer carries that change** — see §4.
- **Building program:** **715,000 sq ft** initial phase + **~1,700 parking spaces**. `[verified]`
  Source: Meta. **Phase 2 signaled** in Meta's **2026-01-07** letter to the township trustees.
- **Investment:** **>$800M**. `[verified]` (Meta) · an earlier Liames pro-forma put it at **$240M
  land + $510M buildings (~$750M)**. `[reference]` (pro-forma / DCD "$750M campus" framing).
- **Jobs:** **~100 permanent** (avg ~mid-$80k) / **>1,000 peak construction**. `[verified]` (Meta).
- **Power draw (MW):** **up to ~180 MW at peak**. `[reference]` — OPSB filings reported via press
  (BG Independent, DCD); not an air-permit or interconnection instrument disclosure of the data
  center's own load, so the official/interconnection MW stays `[open]`. Grid interconnect =
  **Toledo Edison / ATSI** — Wood County is named in that company's own **filed tariff**
  (§3a); but the campus is designed **self-powered behind the meter** by the
  **Apollo** plant (**350 MW gas + ~120 MW BESS**, see §3). The **350-vs-180 MW oversizing** (~2x)
  is a **Phase-2 signal**, consistent with the 2026-01-07 Phase-2 letter. What Toledo Edison
  actually **sells** this customer — full-requirements backup, standby, or nothing — is `[open]`
  and is the largest single unknown on the power side.
- **Cooling / water:** the company describes **closed-loop, liquid-cooled with dry coolers —
  "no operational water"**, with domestic / cleaning / fire use only. `[reference]` — a **company
  claim**, not yet confirmed by an instrument (NPDES / the negotiated water agreement). This is in
  tension with the NWWSD wholesaling BG water to Meta (contract ceiling raised to 1.5 MGD, Aug
  2024; conflicting ~50k vs ~600k GPD figures; a Meta-funded 2 MG tank + 16-in main) — **that
  reconciliation is the water sub-issue's job (#1439), not this register's.** Do not assert the
  cooling design as verified.
- **Cooling reconciliation (B5, #1685):** the dry-cooler claim was run through the A3 harness
  (`data/reference/oepa/cooling-reconciliation.yaml`) and comes back **`reservation_conflict`** —
  the pin is **kept** at `closed_loop_dry` `[reference]`, but the district-linked **~600,000 gpd**
  design commitment is a demand signal *independent of Meta's own account of its cooling* and is
  disproportionate to "no operational water" (it is also **12x** Meta's own announced ~50,000 gpd —
  a conflict #1439 recorded and B5 does not settle). A negotiated ceiling is **not** a withdrawal
  or discharge instrument, so it cannot license a re-archetype. **And there is no instrument to be
  had:** the campus *buys* finished water, so the Ohio DNR withdrawal registry — which records
  withdrawals *from waters of the state* — carries **no Meta / Liames / Project Accordion / NWWSD
  registration in Wood County at all** (`data/reference/ohio-water-withdrawal/wood.yaml`), while
  **Apollo Power Generation Facility - TEMP** registered a 0.27 MGD surface intake in the campus's
  own HUC-12 on **2026-03-26** — so the register is live here and Meta's absence is a *route*, not
  a coverage gap. A full ECHO CWA sweep of Wood County (FIPS 39173, 2026-08-01; 241 records, 50
  effective individual NPDES permits) finds **every** campus-linked record — PROJECT ACCORDION
  `OHGC15219`, APOLLO POWER GENERATION FACILITY `OHGC17963`, APOLLO LAYDOWN YARD `OHGC18721`,
  APOLLO NORTH PIPELINE `OHGC19094`, ACCORDION-DOWLING 138KV `OHGC15929` — under the **construction
  stormwater** general permit (master `OHC000000`), with no process outfall and no DMR. With
  **OHD000001 withdrawn 2026-07-21**, an **individual NPDES permit** is the only remaining
  instrument on the *direct-discharge* path — but that path may not be this campus's: the
  discharge route is **not established**, and a facility blowing down to a sanitary sewer files no
  DMR at all and is disclosed instead by the **industrial-pretreatment (IU) permit and sewer-use
  agreement**, which is what the records ask actually seeks. `[verified]` on the records; the
  cooling architecture stays `[reference]`.
  **KY/OH:** every identifier in that reconciliation is an Ohio key (Wood County FIPS **39173**,
  Ohio DNR registrations, Ohio EPA NPDES, EIA-861 utility **#2054** — the Bowling Green, KY muni is
  #2056), and both instruments are Ohio-statutory, so **neither can return a Kentucky record**. The
  KY collision reaches only the press-sourced ~50k / ~600k figures — which is exactly where it has
  to be watched.
- **Timeline:** deeds **2023-09-05** → reveal **2025-04-09** → **ground 2025** → **target ops
  2027**; **Phase 2 signaled** in Meta's **2026-01-07** letter (PDF on the township site).
  `[verified]` (letter PDF).

This is what the `SiteFacility` on `_BOWLING_GREEN` is pinned from (site-plan-grounded, #1327
Urbana precedent): the disclosed type / 715,000 sq ft / >$800M are populated `[verified]`; the IT
load is carried as the disclosed **~180 MW peak** `[reference]` (a design ceiling, not a firm
average); `cooling_model` records the company's **closed-loop dry** claim as `[reference]`.

## 2 — Oppidan colo (Woodbridge Business Park, city proper) — DO NOT conflate with Meta

- **Developer:** **Oppidan Investment Company**. Site: **2501 Woodstream Dr**, Woodbridge Business
  Park, **City of Bowling Green** (city proper — *not* the Middleton Twp Meta campus). `[reference]`
- **Land of record (#1436):** parcel **`511210000002003`**, **11.80 ac deeded**, conveyed to
  **CLOP BOWLING GREEN OH LLC** on **2025-02-03 for $1,105,000** by warranty deed. `[verified]`
  — Wood County Auditor Vision CAMA. The owner's mailing address, **400 Water St Suite 200,
  Excelsior MN 55331**, is Oppidan's own headquarters, which is what identifies the SPE. This
  upgrades the "~12 ac" `[reference]` above to a deeded figure. The site is **7,771 m
  (4.83 mi)** from the nearest Meta campus boundary, measured in UTM 17N. Its situs reads
  **2371 Woodstream** in the ~2025-07 CAMA snapshot; the building address is 2501 Woodstream Dr.
  Zoning here is the **City's** layer, not Middleton Township's.
- **Building:** **61,554 sq ft / ~12 ac**. `[reference]` — note a competing figure of **98,695
  sq ft** appears in the vendor/engineering trade record. `[reference]` The two are not
  reconciled and neither is an instrument; the city building permit is the pull. `[open]`
- **Power:** **6 MW avg / 8 MW peak**, on **city power**. `[reference]` for the MW (BG Utilities
  and Infrastructure Director Brian O'Connell, 2026-02-10). The muni serving assumption is
  **no longer `[open]`** — #1440 upgraded it to a high-confidence `[inference]`: the **City's own
  electric-distribution GIS** carries **five overhead electric features crossing the parcel**
  (`gis.bgohio.org` `PublicData/UtilitiesWithZoning`, layer *Electric Overhead*, queried
  2026-08-05 against the CAMA polygon), the parcel is **city-zoned `IE - Innovation and
  Employment Zone`** under annexation ordinances **8597** and **8824**, and O'Connell described
  it on the record as "a steady electric customer for the city," sized against two existing
  **city** customers (Magna, Southwestern Container). A commercial tracker
  (interconnection.fyi) attributes it instead to **Hancock-Wood Electric Cooperative** with no
  stated source — recorded and **not adopted**, and not dismissed either, since a co-op's
  certified territory does not vanish on annexation. The instrument remains the **BPU minutes**.
  See `data/extracted/grid/bowling-green/serving-utility.yaml`.
- **End user:** **undisclosed**; an "Amazon blue" exterior stripe is **unconfirmed** and must not
  be reported as an Amazon attribution. `[open]`
- **Completion:** **~April 2026**. Water use characterized as **"negligible"**. `[reference]`
- **Disposition:** **register-only.** The `SiteProfile.facility` model holds **one** facility per
  site (the #1327 seam did not add multi-facility support), so Oppidan is **not** pinned as a
  second `SiteFacility` — it is recorded here and belongs in the record-domain register (#1438).
  Source: BG Independent, "BG has its own, much smaller, less energy-guzzling data center being
  built in Woodbridge Business Park" (2026-02-10).

## 3 — Apollo Power Generation Facility (the behind-the-meter power instrument, #1437)

**Worked in #1437.** Both instruments are now captured and transcribed — the siting case at
[`grid/bowling-green/apollo-power-generation-facility.yaml`](../grid/bowling-green/apollo-power-generation-facility.yaml)
and the air chain at [`oepa/bowling-green/`](../oepa/bowling-green/). Standing watches and the
blocked-route negatives live in [`power-watch.yaml`](power-watch.yaml). The summary below is a
pointer; the transcriptions are canonical.

- **What:** **350 MW net behind-the-meter natural-gas generation + 119.5 MW / 239 MWh BESS**
  (Will-Power OH, LLC) to power the Meta campus. 21 turbines + 6 reciprocating engines, capable of
  **491 MW gross** at design conditions and derated to a certified 350 MW net. `[verified]` (staff
  report). Beware the ten **"Solar" PGM 130 turbines** — Solar Turbines is a Caterpillar brand and
  they burn gas; the staff report's own footnote says so.
- **Instrument:** **OPSB 25-0973-EL-BLN** — *not* `-EL-BGN`, which is what OPSB's own press release
  says and what this file previously carried. Filed **2025-11-05**, **approved 2026-02-03** by
  automatic approval under **accelerated Letter-of-Notification review with no public hearings**
  (34 staff-recommended conditions). `BLN` *is* the letter-of-notification track — the wrong suffix
  names a proceeding that did not happen. `[verified]` (staff report caption + DIS filing stamp).
  The "14 resident opposition comments" figure is `[reference]` press reporting; the staff report
  says only "Several public comments" and the docket that holds them is access-blocked.
- **Air:** **final PTI P0139272 issued 2026-06-02** (facility ID 0387022027) — the chain issue
  #1437 recorded as pending is closed, with a 42-comment Response to Comments bound in. The
  facility is **major for Title V, not major for PSD** (234.62 tpy CO against a 250 tpy threshold)
  and **not major for MACT** (24.40 tpy total HAP against 25). **Title V itself is still open** —
  due within twelve months of commencing operation, so roughly mid-2028. `[verified]`.
- **Grid posture:** Condition 15 **bars** any physical or electrical interconnection with the PJM
  Transmission System (OATT Part IV / Part VI); Condition 16 requires a PJM new service request
  *and* supplemental Board approval before any export. Condition 14 caps output at 350 MW.
  `[verified]`.
- **Scope note:** the Apollo gensets are a **separate OPSB-permitted power facility**, not the data
  center's own emergency gensets, so `SiteFacility.genset_count` / `genset_mw` stay `None` on
  `_BOWLING_GREEN`.
- **Not in the federal generator inventory.** Apollo appears **nowhere in EIA-860M** (June 2026
  edition) — not in Wood County, not in any state, on any sheet. Two readings, neither asserted:
  a plant its own certificate bars from the PJM Transmission System may be outside Form 860's
  scope, or it may be a reporting lag. If the first holds, the behind-the-meter pathway makes
  350 MW statistically invisible to the inventory every fleet-level count runs off. Testable
  against a later edition — `data/extracted/grid/bowling-green/wood-county-generation-census.yaml`.

## 3a — Grid posture and serving utility (#1440)

Full records at `data/extracted/grid/bowling-green/` (catalog `bowling-green-grid`). The load-bearing
points, so this file is not the place they get re-derived:

- **Two grids.** The Meta campus is in **Toledo Edison** territory and this is now **tariff-grounded**,
  not press-sourced: Toledo Edison's own filed **P.U.C.O. No. 8, Original Sheet 3, Definition of
  Territory** (effective 2026-03-01) names **Wood County** among the ten counties of "Company's
  Territory." `[verified]` — but a county is not a parcel, and the sheet itself points to PUCO's
  county maps for township detail, so the parcel-level read stays `[open]`.
- **There is no Schedule DCT at Toledo Edison.** A full-text scan of all 168 pages returns no "DCT"
  and no "data center." `[verified]` The FirstEnergy DCT is **filed and pending** — **PUCO
  26-0697-EL-ATA**, joint filing of Ohio Edison / Cleveland Electric Illuminating / Toledo Edison,
  June 2026. `[reference]` (EEI compilation; PUCO DIS refuses automated retrieval, re-probed
  2026-08-05).
- **What governs in the meantime** is **Rate GT**, whose Contract Demand is **"60% of the customer's
  expected, typical monthly peak load"** on a **two-year** term with **no exit fee** — put that
  beside Schedule DCT's **85% for twelve years** and the pending case has a number, not just a
  controversy. The sheet that reaches a *behind-the-meter* campus is **Electric Service Regulations
  §II.G**, already in force, which counts a 500 kW capacity change **"including the effects of the
  addition of onsite generation."** `[verified]`
- **The muni island, corrected against EIA-860M (June 2026).** Three separate solar facts here —
  do not merge them:
  - *The existing array* — the **Bowling Green Solar Facility, 20 MW nameplate, COD January 2017**
    (EIA plant 60622, `DG AMP Solar Bowling Green`). `[verified]` The **20-not-125 MW** correction
    applies to **this facility only**: the ~125 MW figure is a conflation with AMP's multi-site
    Solar Phase II programme, and EIA carries exactly one solar generator at Bowling Green.
    The correction is now `[verified]` federally, where it had been `[reference]`.
  - *The replacement build, a different and later thing* — **10–12 MW** across two sites, authorized
    by the **Board of Public Utilities on 2026-03-23** to run **"behind the meter for the city,"**
    Eitri Foundry as preferred partner, construction Q4 2026, in service **spring 2027**.
    `[reference]` — BG Independent reporting a public meeting whose **minutes were not read**.
  - *What it replaces* — the four **1.8 MW** wind turbines (7.2 MW plant total, Ohio's first
    commercial wind farm) **retired March 2025** `[verified]`, closing the repower watch as a
    **retirement**. The city's *entitlement* to that plant is `[open]` (3.6 / "4.1" / "~4" MW are
    all in circulation), so the replacement ratio is a range of **2.4–3.3×**, never one figure —
    and a nameplate range at that, not an energy comparison.
  - AMP's combustion turbines in the city are **81.5 MW** across two plants, and a **12 MW battery**
    has been operating since **May 2023** that no prior record here mentions.
- **Juliet Energy is 50 MW nameplate**, not "~62–65 MW AC," and was due in service **July 2026**.
  `[verified]` **Troy Energy** is **4 × 198.9 = 795.6 MW** of existing simple-cycle CTs with **no
  planned addition in the federal inventory**; the combined-cycle conversion is a **PJM queue
  position, not a planned generator**, and its queue id / POI / in-service year were **not**
  corroborated. `[open]` — note the route: PJM's **interconnection queue is not in Data Miner
  2** (queried with a valid key; none of its 119 feeds is a queue), so the pull is the
  planning-page PDFs, not the API.
- **The headroom number stays `[open]`**, as the issue instructed. No published Bowling Green peak
  load or firm-capacity figure exists. "The muni could never serve 180 MW" is an **inference** from
  portfolio size with its arithmetic shown — never a finding.

## 4 — The land-use track: three rezonings, one of them contested (#1436)

The assembly is still moving, and the township's own bodies do not agree with its trustees. Dates
and tallies here are `[verified]` from the Sentinel-Tribune and BG Independent News reports of the
meetings; the resolutions themselves are `[open]`.

- **The 13 parcels / 31.82 ac** (former homes and a strip of motel rooms, since razed), **R-4
  Residential and A-1 Agricultural → M-1 Industrial**, applicant Liames LLC, stated purpose
  "construction logistics" and consistent zoning across the holding. Their positions —
  north of SR-582, **eight on the east side of SR-25 and five on the west side of Mercer Rd** —
  are `[reference]` **press** (BG Independent News, 2026-06-03 and 2026-07-08), *not* a parcel
  schedule: the record names only eight of the thirteen, so that 8/5 split cannot be checked
  against the CAMA and the five unnamed parcels stay `[open]`. The application's own parcel
  schedule at the county planning commission is the instrument:
  - Wood County Planning Commission **recommended, 6–2, 2026-06-02**
  - Middleton Township Zoning Commission **REJECTED it, 2026-06-10**
  - Middleton Township Trustees **granted it anyway, 2–1, 2026-07-07** — Mike Moulton and Fred
    Vetter in favor, Melissa Petrea against
  - **R.C. 519.12 referendum window: 30 days, closing ~2026-08-06.** A petition drive needing
    **971 valid signatures** for the **November 2026** ballot was circulating as of **2026-07-18**
    (organizers targeting ~1,300 to absorb rejections; Leslie Harper coordinating). `[reference]`
    — The Blade via thecooldown.com. **As of 2026-08-01 the window is still open and the outcome
    is `[open]`.** Watch: whether a petition is filed with the Wood County Board of Elections by
    ~2026-08-06, and its certification.
  - The record shows **8 of the 13** parcels (21.37 ac) in Liames' name; the press reports all
    thirteen as already Meta-owned. The gap is the CAMA layer's ~2025-07 vintage, not a research
    gap. `[open]`
- **A. Schaller Limited Partnership, 39.265 ac** of parcel `611190000006000` (64.55 ac total),
  **A-1 → M-1**, for **Liames construction parking**, with Liames **in contract to purchase**:
  county planning commission **recommended 6–2 on 2026-07-07**; **township action pending**.
  The application describes moving construction parking "from the southwest corner to the
  northwest corner of the campus **once construction of building five starts**" — a
  **five-or-more-building** campus against a 715,000 sq ft "initial phase", and a Phase-2 signal
  independent of the 2026-01-07 trustees letter. `[verified]`
- **Devils Hole Rd, ~112 ac**, ag → light-industrial, township zoning commission voted against
  recommending. `[reference]` — **not resolved by #1436**: no such request appears in the
  2026-06 / 2026-07 meeting coverage and the parcel is unidentified. Beware the neighbouring
  **LIMES** family holdings there (Dale Limes LLC, Limes Real Estate Holdings LLC, Limes Galen
  E) — one letter from **LIAMES**, and several hundred acres of it. `[open]`

## Instruments to pull (record / water sub-issues #1438 / #1439)

- ~~**OPSB 25-0973-EL-BLN** docket (Apollo) — application, staff report, the 34 conditions,
  opposition comments.~~ **Partly done (#1437):** the staff report and its 34 conditions are
  captured and transcribed. The application, the ODNR review letter, the data-request responses,
  the comments and the Board's approval entry could **not** be pulled — `dis.puc.state.oh.us`
  serves an F5 JavaScript bot-challenge to automated retrieval. **Access-blocked, not empty**; see
  `power-watch.yaml` → `blocked_routes`.
- **Meta → Middleton Township trustees letter, 2026-01-07** (PDF on the township site) — the Phase-2
  signal. `[verified]`.
- **Liames, LLC** deed chain (Wood County Recorder/Auditor) from 2023-09-05 — the land assembly.
  `[open]` primary records.
- **NWWSD water agreement / BG–Meta wholesale water** (contract ceiling 1.5 MGD, Aug 2024; the
  conflicting ~50k vs ~600k GPD figures) — reconcile against the "no operational water" cooling
  claim. `[open]` → **#1439**, sharpened by **#1685**: the reconciliation established that no
  withdrawal or discharge instrument can reach this campus, so these two documents *are* the
  measurement, and the request has to go to **both** holders — the **service agreement + campus
  meter** are NWWSD's, the **wholesale contract** is the City's, and neither body holds both.
- **BG WPC NPDES** (**2PD00009 / OH0024139** → Poe Ditch → North Branch Portage) — the effluent
  chain; ECHO shows 9 of 12 recent quarters non-compliant. `[reference]` → **#1439**.
- **Title V air permit** for Apollo — genuinely still pending, but the **PTI is not**: final
  P0139272 issued **2026-06-02** and is committed under `data/documents/oepa/bowling-green/air/`.
  Title V is due within twelve months of commencing operation (~mid-2028). `[open]` → **#1437**
  watch `APOLLO-TITLE-V`.

## Sources (live, 2026-07-10)

- Meta, "Hello, Bowling Green" — <https://datacenters.atmeta.com/2025/04/hello-bowling-green/>
- Middleton Township, "Meta introduced as company behind township data center" —
  <https://www.middletontownship.com/meta-introduced-as-company-behind-township-data-center/>
- Meta → trustees letter (2026-01-07) —
  <https://www.middletontownship.com/wp-content/uploads/2026/01/Meta-Middleton-Township-Letter-010726.pdf>
- BG Independent, "Meta reveals plans for $800 million data center north of BG" —
  <https://bgindependentmedia.org/meta-reveals-plans-for-800-million-data-center-north-of-bg/>
- DCD, "Fortune 200 tech company looks to build $750m campus in northern Ohio" (Liames LLC) —
  <https://www.datacenterdynamics.com/en/news/fortune-200-tech-company-looks-to-build-750m-campus-in-northern-ohio/>
- BG Independent, Oppidan build (2026-02-10) —
  <https://bgindependentmedia.org/bg-has-its-own-much-smaller-less-energy-guzzling-data-center-being-built-in-woodbridge-business-park/>
