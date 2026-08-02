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
  **Toledo Edison / ATSI**; but the campus is designed **self-powered behind the meter** by the
  **Apollo** plant (**350 MW gas + ~120 MW BESS**, see §3). The **350-vs-180 MW oversizing** (~2x)
  is a **Phase-2 signal**, consistent with the 2026-01-07 Phase-2 letter.
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
  **OHD000001 withdrawn 2026-07-21**, an **individual NPDES permit** is now the only instrument
  that would ever disclose this campus's cooling discharge. `[verified]` on the records; the
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
- **Power:** **6 MW avg / 8 MW peak**, on **city (BGMU-implied) power**. `[reference]` — the muni
  serving assumption is `[open]` (BGMU-implied, not instrument-confirmed).
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
  `_BOWLING_GREEN`. Grid posture vs the FirstEnergy data-center tariff remains **#1440**.

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
