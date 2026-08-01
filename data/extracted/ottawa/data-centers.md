# Ottawa / Putnam Co., OH — Data-Center Activity Register

Discover-and-pin register for the Ottawa watershed point (Blanchard River → Auglaize → **Maumee**).
Status **as of 2026-07-31** (#1423). Tags are BOSC evidentiary discipline: `[verified]` = cited
primary/government source, `[reported]` = credible secondary, `[reference]` = secondary/advocacy
(leads only, never a finding), `[inference]` = arithmetic or pattern from cited inputs, `[open]` =
not found in any public source yet. **Nothing here is fabricated**; every figure is cited or marked
`[open]`.

**The finding is a negative, and the negative is the point.** No data-center, AI-campus, hyperscale
or large-load project is announced, rumored, rezoned, land-optioned, permitted, or queued in Putnam
County or the Village of Ottawa, 2024–2026. Ottawa's `SiteProfile` carries `facilities=()` and the
`facility` readiness domain stays **locked** — not because the sweep was not run, but because it was
run and came back empty. Six independent record systems were queried record-by-record for this
register (§1); five return a clean negative and the sixth returns a closure, not an arrival.

This register **supersedes** the 2026-06-21 self-research pass, whose negative rested on corpus
absence alone ("no Putnam/Ottawa data-center permit, deed, SOS filing, or meeting record in the
corpus"). The negative now rests on federal and state record systems that would carry a project
whether or not BOSC had ever heard of it.

## Disambiguation guardrail — run first, always

Four traps, all of which return live 2026 data-center hits on this site's own search terms:

- **Putnam County, WEST VIRGINIA** — the load-bearing trap. Google has bought ~1,700 acres at the
  north end of Buffalo, WV for a multibillion-dollar "High Impact Data Center Project"; the
  Governor's office announced it, WSAZ/WCHS covered the land purchase 2026-03-27, and a town hall
  was set for July 2026 `[reported — WV MetroNews 2026-07-14; wvgazettemail; wsaz 2026-03-27]`.
  A bare `"Putnam County" data center` query returns **this** project, not an Ohio one. It has no
  connection to Putnam County, Ohio (FIPS 39137). **Never let it into this register.**
- **Ottawa County, Ohio / Port Clinton** — a different Ohio county on Lake Erie.
- **The Ottawa River** — there are two, one at Lima/Allen County and one at Toledo. Neither is this
  site's water. Ottawa the *village* is on the **Blanchard**.
- **Ottawa, Illinois / Ottawa, Kansas / Ottawa, Ontario** — all carry unrelated data-center news.

And the standing network guardrail: do **not** bridge the Lima/Allen County Bistrozzi
land-assembly graph, or the Van Wert QTS / Urbana Highland55 / Sidney "Project Galaxy" records,
onto Putnam. There is no evidentiary link, and a shared corridor is not a link.

## 1 — The negative, check by check

Each subsection is one record system queried at the stated date, with the query and the result. A
negative is only as good as the system that produced it, so each names what it **cannot** see.

### 1.1 — PJM interconnection queue `[verified]` — closes an open check

Queried **2026-07-31** against PJM's public planning-queue export
`https://www.pjm.com/pjmfiles/media/planning/queues-data/PlanningQueues.xml` (23.2 MB, the file
that backs the Serial Service Request Status page). **9,263 projects; 966 in Ohio; 9 in Putnam
County, Ohio.** All nine are `Generation Interconnection`, all on AEP, all wind or solar:

| Queue # | Point of interconnection | Commercial name | Fuel | MW | Status | Submitted |
|---|---|---|---|---|---|---|
| V2-006 | East Leipsic 138 kV | Leipsic Wind Project | Wind | 150 | Withdrawn | 2009-05-28 |
| W2-007 | East Leipsic 138 kV | — | Wind | 100 | Withdrawn | 2010-05-14 |
| W3-170 | Buckskin 69 kV | — | Solar | 12 | Withdrawn | 2010-10-29 |
| AD1-101 | Continental 69 kV | Blue Harvest Solar Park | Solar | 49.9 | **In Service** 2023-11-22 | 2017-09-21 |
| AE2-072 | East Leipsic–Richland 138 kV | Powell Creek Solar | Solar | 150 | **In Service** 2025-04-30 | 2019-02-15 |
| AG2-405 (moved to TC2) | Continental 69 kV | — | Solar | 49.9 | **Active** (feasibility in progress) | 2021-03-30 |
| AI2-035 | East Leipsic–Richland 138 kV | — | Solar | 150 | Withdrawn | 2023-01-25 |
| AI2-118 | Continental 69 kV | — | Solar | 49.9 | Withdrawn | 2023-02-28 |
| AI2-246 | East Leipsic–Richland 138 kV | — | Solar | 150 | Withdrawn | 2023-03-02 |

Three findings:

- **The queue independently corroborates the county's grid posture** (§3): the two projects the
  SB 52 blanket restriction grandfathered are the two that reached service — Blue Harvest (49.9 MW,
  Continental 69 kV) and Powell Creek (150 MW, East Leipsic–Richland 138 kV). Six of the other
  seven are withdrawn.
- **One entry the 2026-07-10 sweep did not have:** `AG2-405`, a 49.9 MW solar request at Continental
  69 kV, submitted 2021-03-30, still **Active** and moved into Transition Cycle 2, with its
  feasibility study "In Progress" and 10.98 MW of capacity interconnection rights. Whether it is a
  re-file of, or successor to, the withdrawn `AI2-118` (same POI, same 49.9 MW) is `[open]` — the
  XML does not carry a developer name for it.
- **Zero requests of any type at 345 kV, and no bulk-transmission build.** Putnam's highest-voltage
  queue point is 138 kV.

**What this check cannot see, and it matters.** PJM's queue has exactly four project types —
`Generation Interconnection`, `Long-Term Firm Transmission`, `Merchant Transmission`,
`Upgrade Request`. **A data center's load is in none of them.** Large end-use load interconnects
through the transmission owner (AEP Ohio) and, in Ohio, surfaces publicly through a PUCO large-load
tariff filing or an OPSB certificate for on-site generation — not through this queue. So this check
proves *no generation is being built to serve a Putnam load*, which is corroborating but **not
dispositive**. It is also **vintage-bounded**: the newest `SubmittedDate` anywhere in the file is
**2025-06-03**, so it closes the generation negative through mid-2025 and no further.

### 1.2 — ODJFS WARN notices `[verified]` — closes an open check, and does **not** come back clean

Read record-by-record from the Ohio Department of Job & Family Services public WARN lists for
**2024, 2025 and 2026** (the CSVs the jfs.ohio.gov notice pages render from, served off the Ohio
DAM), fetched **2026-07-31**. **241 notices read: 93 (2024) + 89 (2025) + 59 (2026, through
2026-07-30).** One is in Putnam County, and it is in the village itself:

This notice is **committed to the corpus**: source at
[`../../documents/ottawa/warn/RKIndustries.pdf`](../../documents/ottawa/warn/RKIndustries.pdf),
structured read at [`warn/rk-industries-ottawa-2024.warn.yaml`](warn/rk-industries-ottawa-2024.warn.yaml).

> **RK Industries, Inc.** — 725 N Locust St, Ottawa, OH 45875. Notice received **2024-05-16**
> @ 1:18 pm, ODJFS notice ID **007-24-042**. "Expected Closure of Operations" of the company's
> "automotive production stamping, robotic mig welding and spot welding business … due to ongoing
> economic difficulties." Operations expected to **permanently cease 2024-07-14**, affecting
> **80 employees**, **none represented by a union**. Signed Anne Woodyard, President. Filed under
> the federal WARN Act (29 U.S.C. § 2101 et seq.) **and Ohio Rev. Code § 4141.28(C)**. The
> attached position schedule totals 80: General Labor 68, Customer Service Representative 2, and
> one each of Plant Manager, Production Supervisor, Shipping Supervisor, Maintenance Supervisor,
> Production Scheduler, Quality Inspector, Accounts Payable Clerk, Inventory Clerk, Shipping &
> Receiving Clerk, Payroll Clerk. `[verified — ODJFS WARN notice, read from the filed PDF]`

The letter also states the company was "considering a number of options, including a potential
sale, merger, or other strategic transaction, although no definite plans in that regard have
emerged," and it conditions the cease date on no such transaction intervening. So the closure is
**expected, not confirmed**: whether the operation was sold, restarted, or the building
re-tenanted is **`[open]`** — no follow-on instrument was found, and this register does not state
the plant closed as a completed fact.

⚠️ **All three headcount figures in the instrument are handwritten** into blanks the printed
document left empty — the body's "approximately \_\_ employees" (80), the schedule's General Labor
row (68) and its TOTAL (80). The printed positions sum to 12 and 68 + 12 = 80, and the ODJFS index
row reads 80, so four readings corroborate; but it is the employer's stated approximation, carried
as `~80`, never a precise payroll count.

Two things this closes and one it opens:

- The closure/layoff negative **does not close clean**. The village noticed the loss of an 80-job
  stamping plant in July 2024. That is the second industrial closure in the record here,
  twenty-two years after the Philips/Sylvania CRT works (§2.3).
- **It is not a data-center datum.** No arrival, no siting, no assembly. It belongs in this register
  because a vacated industrial building is watch surface (§2.4), not because it is activity.
- Nothing in the adjacent counties changes the picture either: the only Allen/Hancock/Paulding/
  Van Wert notices in the window are ordinary manufacturing and services closures (Dana and FedEx
  Supply Chain at Lima, ZF Active Safety and Michigan Sugar and Goodyear at Findlay, Spartech at
  Paulding, Ohio Recovery Center at Van Wert) — none data-center-adjacent.

**Vintage caveat on the instrument itself:** Ohio's mini-WARN statute (R.C. § 4113.31) took effect
**2025-09-30**, after this notice. The RK filing cites the older R.C. § 4141.28(C) notice
provision, which is what the 2024 record would say.

### 1.3 — Ohio EPA / EPA ECHO air universe `[verified]`

EPA ECHO ICIS-Air, county FIPS 39137, queried **2026-07-31**. **33 facilities**, 26 Operating and
7 Permanently Closed. Emissions classification: 3 Major, 1 Synthetic Minor, 3 at 80% Synthetic
Minor, 25 Minor, 1 unknown.

The three majors are exactly the set the county's industrial history predicts:

- **POET Biorefining – Leipsic** (NAICS 325193, ethanol) — Operating.
- **PRO-TEC Coating Company**, Leipsic (NAICS 332811/332812, steel coating) — Operating.
- **L.G. Phillips Displays USA, Inc.**, Ottawa (NAICS 334411, CRT manufacture) — **Permanently
  Closed.** This is the site's own anchor place (§2.3) appearing in a federal air dataset as a
  dead major source, independently of the county record.

**No NAICS 518210 (data processing, hosting and related services) facility exists anywhere in the
county's air universe, operating or closed** — and no emergency-generator bank, the air-permit
trigger a data center pulls first. The village's operating minor sources are the ordinary ones:
Whirlpool Corporation Ottawa Division (335222), Endera Automotive (336211), Nelson Manufacturing
(336212), Hirzel Canning, Gerken Material Plant #5, two National Lime & Stone operations, K&L Ready
Mix, Gerald Grain, Verhoff Alfalfa.

**Limit of the check:** ICIS-Air carries permitted sources. A campus in land-assembly or zoning —
before any PTI/PTIO application — is invisible here by construction. This check answers "is one
built or being permitted," not "is one coming."

### 1.4 — NPDES + construction-stormwater coverage `[verified]`

EPA ECHO CWA, FIPS 39137, queried **2026-07-31**: **48 permits.** The individual permits are the
county's municipal WWTPs (Ottawa OH0026921, Leipsic, Pandora, Ottoville, Continental, Columbus
Grove, Kalida, Fort Jennings, Belmore, Gilboa, Cloverdale-Dupont), the landfill, two National Lime
& Stone plants, POET, and a handful of small institutional and bulk-plant permits.

The interesting half is the **14 active `OHGC*` construction-stormwater general-permit NOIs** — the
earliest public signal any large build emits, months before an air permit. Every one is a road,
utility, municipal or small-commercial project:

| NOI | Project | Place |
|---|---|---|
| OHGC10438 | Nelson Manufacturing Expansion | Ottawa |
| OHGC11391 | Trilogy Ottawa Health Services | Ottawa |
| OHGC11848 | ODOT Putnam County FSM Facility | Ottawa |
| OHGC15062 | Gemstone Addition Phase 1 | Ottawa |
| OHGC11587 | Leipsic Northside Pump Station | Leipsic |
| OHGC15330 | Leipsic Bennett Park | Leipsic |
| OHGC11823 | Kalida–Ottoville 69 kV line rebuild | Fort Jennings |
| OHGC18510 | North Delphos–Ottoville 69 kV line rebuild | Fort Jennings |
| OHGC18393 | Ottoville Station Expansion | Fort Jennings |
| OHGC17877 | PUT-SR 190-5.71, PID 119866 | Fort Jennings |
| OHGC18054 | PUT Kalida Pedestrian Loop | Kalida |
| OHGC18222 | PUT-634-16.44 (PUT-634 & Road E) | Continental |
| OHGC18241 | PUT-115-(5.23)(6.96) | Columbus Grove |
| OHGC01836 | Blueprint Kent-Fairwood Area | (city field reads Columbus — likely an ECHO attribution artifact, not a Putnam project) `[open]` |

**No large-site industrial NOI. No campus grading.** The three grid-side entries are worth naming
precisely so they are not over-read: two **69 kV** line rebuilds and one substation expansion, all
in the Ottoville/Fort Jennings corner. 69 kV is sub-transmission — an order of magnitude below the
345 kV a hyperscale campus interconnects at — and their scale is consistent with routine
cooperative asset renewal `[inference — from the voltage and the "rebuild" designation; no
engineering record pulled]`. They are logged as watch items, not as signal.

### 1.5 — RSEI / TRI `[verified]`

`data/reference/rsei/ottawa/inventory.yaml` (EPA RSEI v234, FIPS 39137): **14 TRI-reporting
facilities, 12 scored.** No NAICS 518210 entry. The highest-scoring facility in the county is
**LG.Philips Displays USA Inc., 700 N. Pratt St., Ottawa** (NAICS 334411) — the closed CRT works
again, in a third independent dataset.

### 1.6 — Employment baseline `[verified]` — the prior argues against a cluster

BLS QCEW 2023 annual averages, area 39137 (`data/reference/economics/ottawa/baseline.yaml`):
12,320 covered jobs across 857 establishments.

- **Information (NAICS 51): 50 jobs, location quotient 0.21** — roughly a fifth of the national
  share. There is no existing IT-hosting or data-center employment concentration to build on.
- **Manufacturing (NAICS 31-33): 3,853 jobs, LQ 3.72** — this is a manufacturing county at nearly
  four times the national share, and that is the whole economic story.
- Professional/Scientific/Technical (54) LQ 0.28; Utilities (22) and Transportation & Warehousing
  (48-49) both report 0 covered jobs.

So a sited campus here would be a genuine discovery against the prior, not an expected find.
`[inference — LQ is an export-orientation proxy, not a siting model]`

### 1.7 — Trackers, registers and marketed-site listings

- `[reference]` **stopohiodatacenters.org** publishes a **dedicated Putnam County, Ohio page**
  (`/counties/putnam`, last updated **2026-04-27**) reading "**No active data center in Putnam
  County — yet**" and "No documented activity in or near the county," with a risk classification of
  **Low, 24/100**, utility "AEP Ohio + Paulding-Putnam Electric," and the note "Below-average
  transmission capacity. Hyperscale loads would require significant infrastructure investment."
  This is a per-county negative, which is stronger than the "no entry in the tracker" the
  2026-07-10 sweep recorded — but it remains an **advocacy source**: it contributes a lead and a
  corroboration, never a finding, and it is three months stale as read.
- `[verified]` **Putnam County CIC project register** (`putnamcountyohio.com/projects/`), read
  **2026-07-31**: the named projects are Weigand Construction's Ohio headquarters (groundbreaking
  2026-06-02), Endera electric-bus manufacturing at Ottawa (O.H.I.O. Fund investment announced
  2026-01-05), American Trenchless at Kalida (2025-08-04), the Nelson Manufacturing expansion
  (announced 2024-12-18), and Meadows of Ottawa senior living. **No data-center, hyperscale, AI or
  large-load project appears.** Note: the "four priority sites for 2026" the 2026-07-10 sweep
  recorded from this source **are not on the page as read today** `[open]` — the page may have been
  re-cut, so the four-site framing is carried below at `[reference]` to that sweep, not `[verified]`.
- `[open]` **JobsOhio** — no certified-site or project listing naming Putnam was found at web
  level. This is a negative *search*, not an auditable check against a JobsOhio record.

### 1.8 — Toledo Blade, 2025-12-13 — **still `[open]`**

"Where will the next northwest Ohio data centers be built?" (toledoblade.com,
`/business/development/2025/12/13/data-centers-northwest-ohio-sites-where-next-built/stories/20251213002`).
**Not closed.** The article is paywalled; the page returns only nav chrome, and the Internet
Archive snapshot of **2026-03-06** captured the same paywall shell rather than the body. No
syndicated or republished copy was found. **The register does not know whether Putnam is floated in
it**, and does not guess.

What can be said around it, without claiming to have read it: every northwest-Ohio location that
surfaced in the surrounding coverage universe is outside Putnam — Meta's ~715,000 sq ft / 280-acre
Bowling Green project in Middleton Township (Wood County), the Gibsonburg/Woodville/Madison
Township proposal (Sandusky County), Oregon's ~168-acre Corduroy-and-Wynn-roads site (Lucas), and
the western-Lucas/Waterville corridor, where Waterville Township trustees adopted a 12-month
data-center moratorium on 2025-12-17 `[reported — wtol, 13abc, DCD]`. **This is corroboration by
absence and nothing more.** Closing the check requires the article itself.

## 2 — The watch surface: where a prospect would land

Nothing in this section is a project. It is the inventory of ground a prospect would have to touch,
recorded so that the *next* sweep has something to check against rather than starting over.

### 2.1 — Highland Industrial Park, Ottawa

`[verified — ottawaohio.us/2170/Highland-Industrial-Park, read 2026-07-31]` The Village markets two
sites: **Site #1, maximum available 70 acres** (minimum 5), and **Site #3, maximum available 18
acres** (minimum 5), both at **$10,000/acre, negotiable**, both **zoned industrial**, with
"Incentives: Possible for both State and Local." The page gives the location as **Road M**. It
publishes **no** utility, electric-service, water, sewer, gas, fiber or rail information, no CRA/TIF
or foreign-trade-zone designation, and no tenant list.

`[reference — #1423 sweep 2026-07-10]` That sweep recorded the park as 70 publicly-owned acres on
**Woodland Drive** inside a CRA + TIF district and a foreign-trade zone, and as one of the CIC's
four priority sites for 2026. None of that is on the Village page as read today, and the street
name differs. Treat the CRA/TIF/FTZ status as **unconfirmed** until the designating ordinance is
pulled.

`[inference]` Parcel-layer read of Putnam County GIS (`Parcels/Parcels/MapServer/0`, 2026-07-31):
the Village of Ottawa owns **182 parcels**. Two are on **Woodland Drive** — `321019000200` (1.383
ac, use class 300, industrial) and `321011310316` (1.808 ac, class 640) — and the largest
Village-owned parcel in the county is `321020000000` at **8649 Rd K-6, 70.004 acres**, carried at
use class **110 (agricultural)** with a 2004-09-20 sale date. The 70.004 acres matches the marketed
"70 acres" to three decimals, but the situs address does not match either street name the sources
give, so **the identification is `[open]`** — it needs the Village's own ordinance or plat, not a
coincidence of acreage.

### 2.2 — The other CIC-marketed sites `[reference — #1423 sweep 2026-07-10]`

The 450-acre **U.S. Midwest Triple Rail Site** (Leipsic), **CSX South Side** (Columbus Grove), and
**Progressive Drive** (Ottoville). No tenant announcement at any of them, then or now. These are
carried at `[reference]` because they come from the sweep rather than from a source re-read for this
register; the CIC page as read 2026-07-31 does not list them (§1.7).

### 2.3 — The former Philips / Sylvania / GTE CRT campus — **not** a data-center site

700 and 804 North Pratt Street: two contiguous parcels, **38.234 ac deeded / 38.293 ac planar**,
committed as `data/reference/ottawa/parcel-assemblage.geojson` (#1420) with the footprint record in
`bosc-site-footprint.yaml`. This is the site's **anchor place** and the county's largest employer
until 2002-12-31 — a closed industrial works under a **$4,571,596** three-round Ohio Brownfield
Remediation Program remediation, with **Tawa Run crossing 325.8 m of the boundary** and discharging
to the Blanchard 525.9 m away.

It appears in this register only to be excluded. It is a brownfield with standing contamination
work, not a marketed campus, and no data-center interest in it is on any record. Its relevance to
facility posture is the opposite one: it is why `pre_cover == post_cover` in this site's runoff
model, and why Ottawa's industrial story is a **subtraction** story.

### 2.4 — 725 N Locust Street — newly vacant industrial building `[verified]`

The RK Industries plant (§1.2). Putnam County GIS parcel **320841200000**, situs 725 N Locust St,
Ottawa; owner of record **PATRICK HOLDINGS INC**, mailing 100 S Werner St, Leipsic OH 45856; sale
date **1994-08-05** (purchase code AFF); **2.31 acres**; use class **330** (industrial); land
$61,029 / building $478,057; auditor record at
`auditor.putnamcountyohio.gov/Parcel?Parcel=320841200000`. Read 2026-07-31.

At 2.31 acres this is **not** a data-center site under any siting model, and it is listed as watch
surface only in the narrow sense that an operating industrial building went dark in the village in
July 2024 and its post-closure disposition is unknown `[open]`. RK Industries does not appear in the
county's ICIS-Air universe (§1.3), so its closure leaves no trace in that dataset.

### 2.5 — Endera (804 N Pratt St) — a manufacturer, not a large load

`[verified]` **Endera Automotive** is an Operating **minor** air source in ICIS-Air, NAICS 336211
(motor-vehicle body manufacturing), at Ottawa (§1.3), and the Putnam County CIC records the
O.H.I.O. Fund's portfolio investment announced **2026-01-05** (§1.7). `[reference — #1423 sweep]`
~200 employees; $49M raise 2025-02-11.

An EV-bus OEM on the former CRT campus is a **record/story** fact for this site, and a genuinely
interesting one. It is **not** a `SiteFacility`: it is not a data center, not a large load, and
scaffolding it into `facilities=()` to make the facility domain light up would be exactly the
failure this register exists to prevent.

## 3 — Grid and energy posture — why the county exports rather than hosts

`[reference — #1423 sweep 2026-07-10]` Putnam County's **September 2023 SB 52 blanket restriction**
closed all unincorporated land to new utility-scale renewables, capping the pipeline at the
projects already grandfathered. The PJM queue (§1.1) shows what that produced: **two projects in
service and six withdrawn.**

- **Powell Creek Solar** — 150 MWac, Avangrid; PJM `AE2-072`, East Leipsic–Richland 138 kV,
  **in service 2025-04-30** `[verified — PJM queue]`. First panels installed 2024-07-10
  `[reference — Avangrid]`.
- **Blue Harvest Solar Park** — 49.9 MW, EDPR; PJM `AD1-101`, Continental 69 kV, **in service
  2023-11-22** `[verified — PJM queue]`. Output contracted to **Amazon/AWS** `[reference — EDPR]`.

The **Blue Harvest** contract is the register's sharpest point, and it should be stated carefully
because it is easy to overstate. **A Putnam County solar farm sells its output to the hyperscaler
whose data centers are somewhere else.** The county carries the land use and exports the electrons;
the load, the tax abatement, the jobs and the water draw all land in another county. That is a
finding about **this site's relationship to the data-center build-out**, and it is available here
precisely *because* there is no local campus to look at. It is not evidence of an Ottawa project,
and must never be cited as such.

Serving utility for the incorporated village is **AEP Ohio** (Ohio Power Co, EIA-861 #14006, PJM AEP
zone); rural Putnam is cooperative territory (Paulding-Putnam, Midwest, Hancock-Wood, Tricounty)
`[reference]`. Same zone as Lima, Findlay and Van Wert, so the grid variable is held constant across
the network's Maumee sites.

## 4 — What would flip this register

Named so the next sweep is a check, not a re-derivation. Any **one** of these turns the facility
domain from a documented negative into an investigation:

1. A **PUCO large-load tariff filing or OPSB certificate** naming a Putnam County point of delivery.
2. A **PJM queue entry** at 138 kV or above with a new developer name, or any Putnam entry that is
   not solar — checked against the `SubmittedDate` frontier, currently 2025-06-03.
3. An **OHGC construction-stormwater NOI** for a site over ~50 acres, or coverage under the
   data-center general permit **OHD000001**.
4. An **air PTI/PTIO application** for an emergency-generator bank at any Putnam address.
5. A **Village or County rezoning, annexation, CRA, TIF or PILOT** touching Highland Industrial Park
   or any of the three other marketed sites — note the Village's zoning code is under an active
   modernization RFP (issued 2026-06-23, proposals due 2026-08-04), so the ordinance baseline is
   about to move.
6. A **large contiguous assembly** in the Putnam parcel layer under a new or out-of-county grantee.

## Instruments to pull (priority order)

1. **The Toledo Blade article of 2025-12-13** — the one open check this register could not close
   (§1.8). Library or subscriber access; the Wayback copy is a paywall shell.
2. **What actually happened at 725 N Locust** — the closure is *noticed*, not confirmed (§1.2).
   Auditor transfer history after 2024-07-14, any successor entity, and whether Patrick Holdings
   Inc re-tenanted or sold. This is the one open question the committed notice raises and cannot
   answer. *(The notice itself is now in the corpus — source
   [`../../documents/ottawa/warn/RKIndustries.pdf`](../../documents/ottawa/warn/RKIndustries.pdf),
   read [`warn/rk-industries-ottawa-2024.warn.yaml`](warn/rk-industries-ottawa-2024.warn.yaml).)*
3. **The Highland Industrial Park designating instruments** — the Village ordinance or resolution
   creating the CRA and TIF, the FTZ designation, and the plat or deed that ties the marketed
   70 acres to a parcel number (§2.1).
4. **PJM `AG2-405`** — the still-active 49.9 MW Continental 69 kV solar request; developer name and
   relationship to the withdrawn `AI2-118`.
5. **The Putnam County SB 52 resolution** (September 2023) — cited throughout as `[reference]`; the
   adopted text is not in the corpus.

## Sweep log

| Date | Pass | Basis | Result |
|---|---|---|---|
| 2026-06-21 | Self-research (#247) | Corpus only | Affirmatively nothing documented |
| 2026-07-10 | External sweep (#1423 grooming) | Trackers + press + CIC | No project; watch surface identified |
| **2026-07-31** | **This register (#1423)** | **PJM queue · ODJFS WARN 2024-26 · ICIS-Air · ECHO CWA · RSEI · QCEW · county GIS** | **Negative holds on six record systems; one WARN closure found; Blade check stays open** |

Cadence: **on demand**, and on any of the six triggers in §4. The next scheduled touch is whichever
comes first of the Village zoning-RFP award (§4.5) and the next PJM queue publication.

## Sources

- PJM public planning queue — <https://www.pjm.com/pjmfiles/media/planning/queues-data/PlanningQueues.xml>
  (backs <https://www.pjm.com/planning/service-requests/serial-service-request-status>)
- ODJFS public notices of layoffs and closures (WARN) —
  <https://jfs.ohio.gov/job-workforce-services/job-programs-and-services/submit-a-warn-notice/current-public-notices-of-layoffs-and-closures>
  and the 2024/2025 archive pages; RK Industries notice PDF at
  <https://dam.assets.ohio.gov/image/upload/jfs.ohio.gov/warn/WARN%202024/RKIndustries.pdf>
- EPA ECHO ICIS-Air — `echodata.epa.gov/echo/air_rest_services.get_facilities?p_fips=39137`
- EPA ECHO CWA — `echodata.epa.gov/echo/cwa_rest_services.get_facilities?p_fips=39137`
- Putnam County GIS — <https://putnamcountygis.com/arcgis/rest/services/Parcels/Parcels/MapServer/0>
- Putnam County Auditor — <https://auditor.putnamcountyohio.gov/>
- Village of Ottawa, Highland Industrial Park — <https://www.ottawaohio.us/2170/Highland-Industrial-Park>
- Putnam County CIC project register — <https://putnamcountyohio.com/projects/>
- stopohiodatacenters.org, Putnam County profile — <https://stopohiodatacenters.org/counties/putnam>
- Avangrid, Powell Creek first panels (2024-07-10) —
  <https://www.avangrid.com/w/avangrid-installs-first-solar-panels-at-powell-creek-project-in-ohio>
- EDPR, Blue Harvest Solar Park — <https://edp.com/en/north-america/na/projects/blue-harvest-solar-park>
- The Blade, "Where will the next northwest Ohio data centers be built?" (2025-12-13, paywalled) —
  <https://www.toledoblade.com/business/development/2025/12/13/data-centers-northwest-ohio-sites-where-next-built/stories/20251213002>

## Cross-references

- [`README.md`](README.md) — the site's extraction index
- [`bosc-site-footprint.yaml`](bosc-site-footprint.yaml) — the anchor place (#1420)
- [`water-watch.yaml`](water-watch.yaml) — the standing regulatory watch (#1422)
- [`ONBOARDING.md`](ONBOARDING.md) — the onboarding record and review gate
- `data/extracted/findlay/data-centers.md` — the same-river sibling's register (a **confirmed**
  facility, for contrast)
