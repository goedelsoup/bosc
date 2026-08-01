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
  **Mercer Rd substation**; **~280-ac initial site** inside a **~750-ac Liames land assembly**
  (codename framing). `[verified]` township/company for the location · `[reference]` for the
  acreage split. Deeds recorded from **2023-09-05**.
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
- **Building:** **61,554 sq ft / ~12 ac**. `[reference]`
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
  claim. `[open]` → **#1439**.
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
