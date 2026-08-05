# Van Wert / Van Wert County, OH — Data-Center Activity Register

Discover-and-pin register for the Van Wert watershed point — the upper Maumee basin (Town Creek
→ Little Auglaize → Auglaize → Maumee). Sweep status **as of 2026-07-02**; the committed-record
notes below are dated individually. Tags are BOSC evidentiary discipline: `[verified]` = cited
public source (two+ independent or a primary instrument), `[reference]` = single credible-media
source, `[inference]`, `[open]`. This began as a pure discover-and-pin register with **nothing**
in the corpus; the land (#1403), water (#1406) and City legislative (#1401) instruments are now
ingested, and the lines they ground cite them. Every figure is cited; none is fabricated.
The **incentive and water-service threads were searched to a dated negative on 2026-08-05
(#1407)** — where a line below says an instrument does not exist, it now names the route and the
date on which it did not.

> **City instruments committed (2026-08-03, #1401):** the legislative record is now in the corpus
> — the three emergency ordinances of **2026-05-11** (`26-05-028` annexation, `26-05-029` the
> code amendment that first defined "Data Center" in Van Wert, `26-05-030` the conditional I-2
> zoning), the certified **2026-05-04 public-hearing record**, and the 2026-04-27 and 2026-05-11
> council minutes — under `data/documents/van-wert/council/`, extracted to
> `data/extracted/van-wert/mega-site-instruments.yaml` (digest: `mega-site-instruments.md`).
> **Three things in this register were wrong and are corrected below**: the annexation is
> **901.698 ± ac, not ~962**; the minutes record **no numeric tally**, so "6-0" is a press
> reconstruction, not the instrument; and the county commissioners' approval is dated —
> **2026-03-10, one day after filing**. The finding that matters most is older than the project:
> the ordinances rest on **three Pre-Annexation Agreements dated 2014-11-14, 2014-12-22 and
> 2016-06-14** among the City, three township boards and the County Commissioners.
>
> **Land committed (2026-07-31, #1403):** the campus geometry is now in the corpus —
> `data/reference/van-wert/parcel-assemblage.geojson` + `data/extracted/van-wert/bosc-site-footprint.yaml`,
> the **five Van Wert County parcels deeded to `QTS VAN WERT LLC`** in June 2026, **900.59 ac
> deeded / 901.502 ac planar**, contiguous. This activates the **places** readiness domain and
> closes the "deed grantee" `[open]` below; it also corrects the school-taxing-body line (the
> campus straddles **two** districts) and the SSURGO HSG on the profile (flat `D` → dual `C/D`).
> The **grantor** and the recorder instrument numbers stay `[open]` — the county's parcel layer
> carries neither, so the Marsh Foundation → Thor → QTS chain is still #1401's pull.
>
> **Water record committed (2026-08-01, #1406):** the municipal water instruments are now in the
> corpus — NPDES **2PD00006\*WD**, the modification that put the CSO Long Term Control Plan on a
> dated construction schedule effective 2026-07-01, plus its draft public notice
> (`data/documents/oepa/van-wert/`, extractions under `data/extracted/oepa/van-wert/`). The
> standing register is `data/extracted/van-wert/water-watch.yaml`. Its finding: **Van Wert drinks
> Town Creek and discharges to Town Creek**, on one NHDPlus flowline, with the five CSO outfalls
> in between — see the water section below.
>
> **Construction-stormwater instrument committed (2026-08-03, #1402):** the campus's **own** first
> state permit is now in the corpus — Ohio EPA NPDES **Construction Site Stormwater General Permit
> OHC000006, coverage `2GC08872*AG`**: the applicant's Notice of Intent (certified under penalty of
> law **2026-07-21**), the site map it attaches, and Ohio EPA's approval letter (**2026-07-30**),
> under `data/documents/oepa/van-wert/stormwater/`, extracted to
> `data/extracted/oepa/van-wert/2GC08872.{noi,approval}.npdes.yaml`. **It is a construction-phase
> instrument and grounds nothing about operations** — no cooling, no process discharge, no operating
> water use, no load. What it does establish, on the applicant's own certification: the operator of
> record is **QTS Realty Trust Inc.** of Duluth GA (not the "QTS Realty Trust, LLC / Overland Park KS"
> press carried); the receiving stream is **Town Creek**; land disturbance is **792.0000 ac**
> (87.8% of the zoned area); the project runs **2026-08-03 → 2030-08-03**, not the press's "Q4 2026
> groundbreaking / ~2032 buildout"; and the **air permit-to-install is `YET_TO_APPLY`** — the first
> instrument-grade, dated statement of that negative. The attached site map is the **first site plan
> in the corpus**.
>
> **Incentive + water-service instruments searched to a dated negative (2026-08-05, #1407):** the
> five routes that would hold them were run and recorded — the City's legislation and minutes
> through Ord. `26-07-040` and 2026-07-13, the County Commissioners' whole published 2026 agenda,
> Lincolnview Local's twelve 2026 BoardDocs agendas, the Ohio Tax Credit Authority's 2026 minutes
> plus the committed ODD tax-incentive export, and a capture of the operator's own FAQ. **No
> executed incentive instrument and no water-service instrument exists in any of them.** What the
> pass did find is the City saying so itself: on **2026-07-13** Council's Economic Development
> committee reported that **VWAED's Executive Director "is concluding incentives and development
> agreements for the data center and hopes to have those done by the next council meeting"** —
> the first primary-source statement that an incentive package exists as a negotiation, who is
> running it, and when it was expected to close. Four City documents are now in the corpus (the
> approved minutes of 2026-05-27, 2026-06-08 and 2026-07-13, and the private-well ordinance
> `26-06-034`), plus two Ohio Tax Credit Authority minutes, the Governor's pause notice, the
> County's 2026 agenda index and the operator's FAQ. Register:
> `data/extracted/van-wert/incentive-water-instruments.yaml` (digest: `.md`). **Three lines below
> change**: the ~660,000-gallon fill is the **City's** figure and not the operator's — QTS's own
> page now declines to state a volume; the AEP **Haviland line is disclaimed by the City's
> Safety-Service Director as "not related to the Data Center"**; and the City's franchise with
> Ohio Power passed 2026-06-08 with its term **cut from 50 years to 10**.
>
> **Profile pin (2026-07-13, revised 2026-08-03, #1402):** the campus below is registered as a
> `SiteFacility` on the Van Wert `SiteProfile` (the #1327 Urbana precedent) — the 500 MW is carried
> as a `[reference]` bracket (never a disclosure; QTS declines to state capacity), with closed-loop-dry
> cooling and the ~$10B investment, and its citations now rest on the committed ordinances (#1401)
> and the stormwater NOI rather than on press. The **facility** readiness domain reads **`seeded`,
> not `live`** — and that is the correct reading, not a gap. Since #1630 the domain grades on
> documentary depth (`SiteFacility.is_instrument_grounded`): it needs an air permit or filed
> disclosure grounding the **load**, or a `[verified]` document grounding the **cooling**. Van Wert
> has neither, and both absences are now *documented* rather than merely unfound — QTS certifies the
> PTI is yet to be applied for, and AEP Ohio stated no megawatt figure for this campus on the record.
> The site's `tier` is **case**. Of the grounding *instruments*, the **ordinances, the hearing record**
> (#1401) and now the **stormwater coverage** are committed; the **deeds** and the **OPSB LON** are
> not, and both routes are recorded as per-source negatives in `mega-site-instruments.yaml`.

## Disambiguation guardrail

The confirmed project is the **Van Wert Mega Site**, City of Van Wert / Van Wert County, OH —
the ~1,500-acre Marsh Foundation industrial site north of U.S. Route 30. Van Wert County drains
to the Maumee (Lake Erie basin), distinct from the Great Miami / Scioto data-center clusters.
`[verified]`

## 1 — QTS "Van Wert Mega Site" campus

- **Operator / end user:** QTS Data Centers, Blackstone-owned since its 2021 take-private. Publicly
  named as the end user late May–June 2026. `[verified]` Source: q.com/data-centers/van-wert; DCD;
  VW Independent. **The legal entity on the instrument is `QTS Realty Trust Inc.`, 2470 Satellite
  Blvd NW, Duluth GA 30096** — the applicant of record on the campus's construction-stormwater NOI,
  certified under penalty of law 2026-07-21. `[verified]` (`edoc-4209395.pdf` p. 0) This register
  previously carried "QTS Realty Trust, **LLC**; Overland Park, KS" from press coverage; **both the
  entity form and the address were wrong** (#1402). Three QTS names are now live and none is a
  synonym for another: **QTS Data Centers** (the brand), **QTS Realty Trust Inc.** (the permit
  applicant), and **QTS VAN WERT LLC** (the deed grantee, below). How they relate is `[open]` —
  the SOS filings that would show it are unreachable (see the blocked-route note in
  `mega-site-instruments.yaml`).
- **Land developer:** Thor Equities Group, via its data-center division Form8tion ("Form8tion
  Van Wert"). `[verified]` Source: GlobeNewswire (Aug 19, 2025); citybiz; DCD.
- **Seller:** The Marsh Foundation (local non-profit; owner of the Mega Site). `[verified]`
- **Project codename:** none disclosed. `[open]`
- **Deed grantee / shell LLC:** **`QTS VAN WERT LLC`** — the operator holds title directly, on all
  five campus parcels. `[verified]` (#1403; Van Wert County Auditor CAMA, read 2026-07-31.) The
  intermediate Thor SPE **VAN WERT EAST OWNER LLC**, which held the 221.15-ac anchor as recently as
  a 2026-07-10 probe, is gone from the county roll; a countywide owner scan returns **zero** parcels
  for `THOR`, `FORM8TION`, `VAN WERT EAST` or `EQUITIES`, so no surviving nominee holding exists.
  The **grantor**, the recorder instrument numbers and the deed book/page stay `[open]` — the
  county's parcel layer carries none of them; pull the Van Wert County Recorder deeds. **#1401
  names the sellers from the City's own record**, which is the first primary-source appearance of
  the Thor entity in a Van Wert instrument: the annexation petition was "filed by **The Marsh
  Foundation and Van Wert East Owner LLC**", read into the record by the City Auditor on
  2026-04-27 and again 2026-05-11, with **Charles F. Koch** as agent for petitioners. `[verified]`
  (`4.27.26.pdf` p. 0; `5.11.26.pdf` p. 1) The recorded deeds themselves remain uningested —
  the county's GovOS CountyFusion portal serves a session login, not a document index.
- **QTS is named in none of the nine ingested City documents.** `[open]` The City legislated the
  campus without the end user appearing in the record; VWAED's letter to Council says only that
  Thor "successfully identified an end user." QTS was publicly named later, late May–June 2026.
- **Location:** Van Wert Mega Site — north of U.S. Route 30, between Stripe Road and Mendon Road
  (broader Mega Site bounded by Hwy 30, Gilliland Rd, Marsh Rd, US-224). `[verified]`
- **Acreage (evolving):** Thor's initial acquisition ~221 acres (Aug 2025); QTS campus footprint
  quoted at 902 acres, up to seven buildings. `[verified]` (221 ac = phase-1 land buy.)
- **Acreage, now instrument-grounded (#1403):** the committed holding is **900.59 ac deeded /
  901.502 ac planar** across five contiguous parcels — `17-034718.0000` (362.23 ac),
  `.0100` (221.15, the anchor), `.0200` (157.84), `12-034459.0000` (128.13),
  `33-047500.0000` (31.24). `[verified]` That meets the quoted **902 ac** to **0.16%** — the first
  independent confirmation of the operator's own figure.
- **Acreage, the annexation ordinance itself (#1401) — the "~962 ac" figure was wrong.** Ordinance
  26-05-028 annexes **901.698 ± acres**, and Ordinance 26-05-030 zones the same 901.698 ± acres
  I-2. Exhibit A's own components sum exactly to it: Parcel One **776.565 ac** (630.491 in
  Section 6 Ridge Twp + 114.861 elsewhere in Ridge Twp + 31.213 in Section 31 Hoaglin Twp) plus
  Parcel Two **125.133 ac** (Section 1, Pleasant Twp) = **901.698 ac**. `[verified]`
  (`26-05-028-draft-ordinance.pdf` p. 0; `26-05-028.pdf` pp. 0-9; survey by Michael L. Howbert,
  R.P.S., 2025.) The earlier **~962 ac** came from press coverage, has no support in any
  instrument, and **the 61.4-acre gap it created is retired**: annexed 901.698 ± vs deeded 900.59
  is a **1.1 ac** difference, inside deed-vs-survey rounding.
- **The parcel numbers do not reconcile, and the shortfall is one parcel.** `[open]` The
  2026-05-04 hearing notice — the notice mailed to adjoining landowners — names **four** petition
  parcels: `17-034718.0000`, `33-047500.0000`, `12-034459.0000`, `17-034718.0100`
  (`5.4.26-Public-Hearing-1.pdf` p. 0). `[verified]` Against the committed CAMA acreages those
  four total **742.75 ac** (362.23 + 31.24 + 128.13 + 221.15), or **82.4%** of the 901.698 ± ac
  the ordinance zones. The missing **157.84 ac** is `17-034718.0200`, the fifth deeded parcel,
  which the notice does not name. `[inference]` The likeliest explanation is timing, not scope:
  the petition was filed 2026-03-09 and the county survey records on these parcels
  (`VW-SD522-1/-2/-523`, `VW-SD524`) are the splits that carved the campus out of the Marsh
  tract, so `.0200` may not have existed as a separate number when the notice issued. That is
  **not established** — the metes-and-bounds in Exhibit A, not the parcel list, is what defines
  the zoned area, and reconciling the two is the cleanest remaining check on the campus boundary.
- **Consideration (#1403):** four parcels (679.44 ac) conveyed **2026-06-16** at a recorded
  **$39,117,825**, the anchor **2026-06-18** at **$110,575,000** — exactly **$500,000 × its 221.15
  CAMA acres**, and a **10.6×** step over the ~$47,000/ac Thor paid ten months earlier. All warranty
  deeds. `[verified]` The four same-day parcels share one date and one amount, the signature of a
  single multi-parcel deed, so that figure is **not summed** across them and the campus's total
  consideration stays `[open]`.
- **Zoning — now instrument-grounded (#1401):** annexed (Ord. **26-05-028**) and zoned I-2 General
  Industrial under a §150.12(C) conditional zoning petition (Ord. **26-05-030**), both passed as
  emergencies on first and final reading 2026-05-11. The use itself was created the same evening:
  Ord. **26-05-029** wrote "Data Center" into Van Wert Code §150.03 **for the first time** and
  added it to the I-2 permitted-use list — the City had no such category before that sitting.
  `[verified]` The same ordinance rewrote "Public Service Facility" to confine **power plants and
  substations to the I-2 district**. `[verified]` The conditional zoning's **entire** set of
  conditions (Exhibit C) is a 6-ft landscape mound at 75% opacity in 5 years, triggered only
  within 1,000 ft of a residential abutter — **no noise, height, water, discharge, lighting or
  hours limit**, recorded as an absence in the instrument. `[verified]`
  (`data/extracted/van-wert/mega-site-instruments.yaml`)
- **Investment:** ~$10 billion total capital investment (QTS). `[verified]` Source: q.com; all
  outlets. (An early Feb 2025 report cited "$2B" before the scope grew.)
- **Power draw (MW):** up to 500 MW (Thor/Form8tion figure at land acquisition). `[reference]` —
  QTS's own page declines to confirm MW ("we don't disclose specific power capacity"). **#1401
  does not upgrade this**: AEP Ohio testified at the 2026-05-04 hearing and stated **no megawatt
  figure for this campus**, so the profile's 500 MW bracket stays `[reference]`.
- **Power utility:** AEP Ohio (American Electric Power / Ohio Power Co). QTS states it will fund
  100% of the grid/energy infrastructure upgrades "at no cost to existing ratepayers." `[verified]`
- **AEP Ohio's own data-center pipeline, on a municipal record (#1401).** Zach Miller, Director of
  Economic Development and Data Center Integration, AEP Ohio, testifying 2026-05-04: AEP "paused
  new load studies" while developing a data-center tariff "approved by the Public Utilities
  Commission of Ohio last summer"; under it, "**early interest totaled more than 30,000 megawatts**
  of potential demand. Today, projects estimating **5,342 MW** have advanced to signed agreements."
  `[verified]` (`5.4.26-Public-Hearing-1.pdf` pp. 11-12) ~30 GW of inquiry against 5,342 MW under
  signed agreement — an 18% conversion, and the first primary-source AEP Ohio pipeline figure in
  this corpus. The tariff he describes matches PUCO **24-508-EL-ATA** (approved 2025-07-09); the
  case number is not printed and the identification is ours. `[inference]`
- **Transmission cost — two figures, unreconciled.** County Commissioner Thad Lichtensteiger's
  written comment puts Thor's upgrade cost at "**$72 million**" `[reference]`
  (`5.4.26-Public-Hearing-1.pdf` p. 15), unsourced; the register carries **$45M** for OPSB
  **25-0697-EL-BLN**, the AEP Ohio Transco Van Wert–Haviland 138 kV line. The two may cover
  different scopes; neither is established. `[open]`
- **…and the City says that line is not this campus's (#1407).** Safety-Service Director Jay C.
  Fleming to Council, 2026-05-27: AEP "has been planning a power line upgrade **for about 3
  years**" between the Haviland facility and the substation behind the street department, running a
  "135-kilovolt" line down Dutch John Road "to help Industrial Park along with the city's
  electrical backbone" — and "**Fleming reiterated this project was not related to the Data
  Center.**" `[verified]` (`5.27.26.pdf` p. 1, identical at 300 and 450 DPI.) One official's
  characterization is not a filing and does not settle what the LON covers, but it is the only
  primary-source statement in the corpus on the question and it cuts against attributing that line,
  or either cost figure, to this campus. (The minutes print "135"; every other source says 138 kV —
  a minutes typo is the likeliest reading, `[inference]`.)
- **The City's franchise with the campus's utility was cut from 50 years to 10 (#1407).**
  Ordinance **26-02-010** grants Ohio Power a franchise in the City's streets as "an extension of
  the agreement set out in Van Wert Ordinance Number **5270-75** passed October 15, 1975", and
  passed third and final reading **2026-06-08** ("all concurred"; no numeric tally). `[verified]`
  (`6.8.26.pdf` p. 3.) Twelve days earlier Fleming "supplied the updated AEP Lease Agreement to
  council which took the lease from **50 years down to 10 years**", and Council untabled the
  ordinance and amended the term to match. `[verified]` (`5.27.26.pdf` p. 3.) The ten-year figure
  was already announced at the 2026-05-11 Mega Site vote itself, so 2026-05-27 is the date Council
  conformed the ordinance to a term the administration had stated, not the date it was negotiated.
  The minutes give no reason for the change and none is inferred. The 1975 predecessor is not in
  the corpus.
- **Jobs:** >1,500 construction over the 5–6 year build (local building-trades unions);
  ~200 permanent full-time (q.com official; local coverage says 200–250). `[verified]`/`[reference]`.

### Financial / tax instruments

- **Projected local tax revenue:** ~$200 million — reported both as "over 20 years" (announcement)
  and "over 15 years" (March 2026 local piece); horizon ambiguous. `[reference]`
- **CRA / TIF / PILOT / enterprise-zone specifics:** not publicly disclosed with dollar figures or
  terms. Van Wert County is entirely within an Enterprise Zone (up to 100% real-property abatement
  for up to 15 years) and has CRA authority, but no executed abatement/PILOT ordinance with
  rates/years was found. `[open]` — pull the Van Wert City Council / County Commissioners
  economic-development agreements. **#1401 confirms the absence rather than closing it**: VWAED's
  Executive Director asked Council on 2026-05-04 to approve "the necessary **incentives**, zoning,
  and permitting," and no Mega Site incentive instrument appears in the ingested legislative
  record. `[verified]` Two Community Reinvestment Area ordinances passed as emergencies the same
  fortnight — `26-04-026` (True North Partners Holdings, LLC: 90% abatement over 10 years for a
  $14M building at 205 Bonnewitz Crossing, 15 jobs) and `26-04-027` (Cool Machines Holdings, Inc)
  — are **not** Mega Site instruments. Checked and excluded; do not re-chase them.
- **The agreements were under negotiation and unexecuted on 2026-07-13, on the City's own record
  (#1407).** Council's Economic Development committee, in the approved minutes of that meeting:
  "he reported the **Brent Stevens is concluding incentives and development agreements for the
  data center and hopes to have those done by the next council meeting**." `[verified]`
  (`7.13.26.pdf` p. 3.) Brent Stevens is VWAED's Executive Director — the same person who asked
  Council for "the necessary incentives" on 2026-05-04. This is the first primary-source statement
  that an incentive package **exists as a negotiation**, who is conducting it, and when it was
  expected to close; and it dates the negative, because one does not "conclude" what is already
  signed. Type, term, percentage, counterparty and any school revenue share stay `[open]`. Council
  next met **2026-07-27** — those minutes were not published as of 2026-08-05, and press coverage
  of that meeting reports public comment and no incentive action `[reference]`. Whether the
  agreements were signed on or after that date is the **highest-value re-check** on this register.
- **The rest of the City's legislation in the window carries nothing (#1407).** Every ordinance
  posted from `26-05-031` through `26-07-040` and every set of approved minutes from 2026-05-27
  through 2026-07-13 was read: no enterprise zone, no CRA, no PILOT, no TIF, no JEDD, no
  development agreement. `[verified]` The subjects actually legislated were a supplemental
  appropriation, the 2027 tax budget, a solar lease, private wells, a tree-commission repeal,
  door-to-door sales, a parking space, a smoking prohibition and an unrelated annexation. **The
  route has a blind spot**: an instrument signed administratively, or authorized in executive
  session, need never appear there — and Council did hold a property-transaction executive session
  on 2026-06-08 (7:44–8:12 p.m., no action after), whose subject is `[open]` and is **not**
  asserted to be the campus. One gap: the City's own media index lists the **2026-06-22** minutes
  and serves a 404 for the file, so that is the one meeting in the window that could not be read.
- **The state exemption: the pause held, and nothing in the state record names this project
  (#1407).** `[open]` as to whether the project will ever hold an R.C. 122.175 exemption. The
  Governor directed the chair of the Ohio Tax Credit Authority on **2026-05-27** to "pause
  consideration of any new data center tax exemption requests" pending the General Assembly's
  Joint Data Center Committee study — two days before this campus was announced (a sequence, not a
  cause). `[verified]` (notice captured in corpus.) Against the Authority's own minutes: the last
  data-center exemption went to **Cologix, Inc on 2026-06-01** — 50 percent for 10 years, Orange
  Township (Delaware Co.) and Johnstown (Licking Co.), 90 FTE / $10M new payroll, vote 3-0 with
  two abstentions — which is **five days after** the pause and consistent only if the pause is
  read as written, applying to *new* requests. `[verified]` The **2026-06-29** meeting, the first
  wholly under it, approved seven projects and **zero** data-center exemptions. `[verified]` **No
  application, award or agenda item naming Van Wert, QTS, QTS Realty Trust Inc. or QTS Van Wert
  LLC appears in any 2026 minute**, and the committed ODD tax-incentive export (pulled 2026-06-28)
  carries **zero QTS rows statewide** and eight Van Wert County rows whose newest approval is
  **2022-06-22**. `[verified]` One trap recorded so it is not re-sprung: a Van Wert item *does*
  appear on the 2026-06-29 agenda — **"Van Wert Forward II"**, a Transformational Mixed-Use
  Development item that the ODD export carries as a 2022 Historic Preservation credit for downtown
  redevelopment. It is not this campus.
- **The County's own agenda record is clean, and dates three things (#1407).** The Board of
  Commissioners' published 2026 agendas — all 63 meeting dates, 2026-01-01 to 2026-08-06 — contain
  **zero** enterprise-zone, abatement, CRA, TIF or QTS entries. `[verified]` They do record
  VWAED's Executive Director before the Board on **2026-02-12** "Re: Megasite End User Options"
  (three and a half months before the end user was publicly named, four weeks before the
  annexation petition was filed); the petitioners' agent **Chuck Koch** before the Board on
  **2026-03-10**, the date Ord. 26-05-028 recites for the county resolution granting the petition —
  the first corroboration of that date from the county's own record; and Ridge Township, the County
  Engineer and City representatives on **2026-07-28** on "Mendon Road and surrounding area
  expectations", Mendon Road being the campus's own address. `[verified]` **The Board publishes
  agendas and not journal entries**, so none of this evidences a county *action*.
- **The school boards: no data-center item at all (#1407).** Lincolnview Local's twelve 2026
  BoardDocs agendas — including every meeting after the campus was announced, through 2026-07-22 —
  carry no data-center, QTS, enterprise-zone, abatement or revenue-sharing item. `[verified]`
  Superintendent Jeff Snyder is reported to have told the board in June 2026 that negotiations are
  the *next* step `[reference]`. The negative is against the **agenda** record; the attached
  minutes documents were not retrieved. Van Wert City Schools and Vantage were not searched this
  pass — `[open]`.
- **School taxing bodies — the campus straddles TWO districts** (#1403, correcting the earlier
  single-district `[reference]`): **772.46 ac Lincolnview** Local School District (the four
  Ridge/Hoaglin parcels) and **128.13 ac Van Wert City** School District (`12-034459.0000`).
  `[verified]` — two independent lines for the Lincolnview four (the auditor's own district name
  carries the "(LV)" suffix, and the county SchoolDistrict layer returns Lincolnview at each
  parcel's interior point); for `33-047500.0000` only the spatial join is available. Vantage Career
  Center is also a taxing body. A CRA school-compensation agreement for a project of this payroll
  size would therefore have to reach **both** boards, not one. The auditor also has all five
  parcels in Van Wert **Corporation** tax districts (12, 17, 33), consistent with the annexation,
  while the county's district *polygon* layer still shows townships — a currency gap in the
  polygons, not a contradiction.
- **Developer-funded infrastructure (not a tax instrument):** ~$25 million for Bonnewitz Crossing
  (N. Washington St. to Mendon Rd.) and Mendon Road overpass improvements — developer-funded.
  `[reference]`
- **Legal counsel retained by City/County:** Vorys Sater Seymour and Pease LLP; Bricker Graydon
  LLP. `[reference]`

### Water / hydrology hook

- **Water source:** City of Van Wert municipal water — the City approved the initial closed-loop
  fill; QTS says it is still "in discussions to identify the best solutions." `[verified]`/`[open]`
  Source: vanwert.org/water-treatment; q.com.
- **The approval the operator claims is not in the City's record (#1407).** QTS's live page,
  captured 2026-08-05: "**The City of Van Wert has approved our water usage** and we're currently
  in discussions to identify the best solutions to support the initial fill. QTS has **no
  intentions of utilizing the aquifer** to support the initial fill." `[verified]` as to what the
  operator publishes. Against it: **no water-service approval, agreement, rate resolution or
  authorization to sell water to this campus appears in any City ordinance through `26-07-040` or
  in any approved minutes from 2026-04-27 through 2026-07-13.** `[verified]` as to that record;
  `[open]` as to what the approval actually is — a utility-director act, an administrative
  agreement, or something else. The same page names, for the first time, the document that would
  settle the capacity question: "**the analysis completed by QTS and City engineering** indicates
  that there is adequate capacity in the existing system." That is now a records request with a
  subject line, not a search.
- **The ~660,000-gallon figure is the City's number, not the operator's (#1407).** QTS declines to
  state a fill volume at all: "The total initial charging volume can vary widely based on a variety
  of factors including power capacity and facility design. Since we're still early in the planning
  stage for this development, it's hard to predict the exact amount of water needed."
  `[verified]` Every figure in the fill-vs-annual dispute below traces to a City official or to a
  citizen quoting the now-dead city microsite. That materially weakens reading "660,000 gallons" as
  a disclosure **by QTS**, and it is a further reason the `closed_loop_dry` pin stays `[reference]`.
  The operator also says the loop "uses **only water**", against the Safety-Service Director's
  sealed "**water and glycol**" description of 2026-04-21 — both are in the corpus and neither is
  withdrawn. `[verified]`
- **The fill volume, on the City's own record — and it does not agree with itself (#1401).**
  Three figures for one initial fill reach the 2026-05-04 hearing record. `[verified]` as to what
  was said:
  (a) Safety-Service Director **Jay C. Fleming**, City press release 2026-04-21: "there will be a
  one-time initial fill … The city will sell the developers approximately **660,000 gallons** …
  This is a **one-time transaction** required only at startup" — a sealed water-and-glycol loop,
  reservoir ">85% full", ~**2 MGD** excess treatment/distribution capacity
  (`5.4.26-Public-Hearing-1.pdf` p. 14);
  (b) County Commissioner **Thad Lichtensteiger**, written comment: "**700,000 gallons** of the
  city's 1.6 million daily consumption … and that **will last for 6 to 8 years**" (p. 15) — a
  service life, not a one-time purchase;
  (c) a written comment attributing **5,500 gallons** to the city-launched project website
  (p. 104). And six days after his own press release, Fleming told Council the City **could not**
  supply fill water at all — "no, even if the question presented itself, the city would be
  incapable of fulfilling the requires" (`4.27.26.pdf` p. 4). All four statements are in the
  record; none is reconciled.
- **Cooling:** closed-loop (Danfoss-patented equipment); ongoing consumption small. Operational
  draw ≈ 660,000 gallons/yr (single local timeline source); QTS characterizes ongoing use as
  "about what 4 households use per month." `[reference]`
- **Where facility water goes, per the City (#1401):** Fleming, 2026-04-27 — water the facility
  "must clean or dispose … goes directly to the wastewater treatment plant to be dealt with. It
  will not be put in the ground, aquifers or town creek." `[verified]`
  (`4.27.26.pdf` p. 4) **Van Wert's WWTP discharges to Town Creek** (outfall 001, RM 13.87, COMID
  15653063 — see below), so the statement holds for *direct* discharge and for groundwater but not
  as stated for Town Creek. `[inference]` If the campus routes blowdown to the WWTP, the
  receiving-water question becomes what it adds to a plant already under a dated CSO construction
  schedule — a narrower and more tractable question than the one the public debate was having.
- **Cooling-cycling reconciliation (B2, #1682):** the A3 harness
  (`watermark cooling-reconcile`) tested the closed-loop-dry claim against the record. With no
  metered makeup (the Ohio DNR withdrawal registry has no Van Wert County pull built) and no
  facility-own blowdown (OHD000001 was withdrawn 2026-07-21 and was never linked to the facility
  by name, so no coverage record can ever exist under it — a permanent absence, not a pending one),
  the outcome is a **`gap`** — the pin stays `closed_loop_dry` / `[reference]`, **not** upgraded to
  `document`-grade. The disclosed ~660,000 gal figure is a single-source self-report (not a
  metered instrument, so it cannot corroborate the operator's own claim), and the same number is
  framed both as an *annual* operational draw and a *one-time* initial fill — that fill-vs-annual
  ambiguity is the unresolved **#1409** discrepancy, quantified here, not settled. The initial-fill
  volume + a metered water-service use are sharpened into a C2 records request (#1688 / #1409). See
  `data/reference/oepa/cooling-reconciliation.yaml`. `[open]` **#1401 deepens this gap rather than
  closing it** — the fill-vs-annual ambiguity is not between the corpus and the City, it is inside
  the City's own record (the three figures above). Per the B2 rule a self-report never upgrades the
  source, so the pin stays `closed_loop_dry` / `[reference]`.
- **Wastewater path / NPDES:** not disclosed for the facility; no facility-specific NPDES number
  found. `[open]`
- **Receiving water:** Van Wert's stream is Town Creek → Middle Creek → Little Auglaize River →
  Auglaize River → Maumee River (Lake Erie basin). HUC-12: Lower Town Creek (04100007 08 04);
  Ohio EPA river code 04-143. `[verified]` Source: Ohio EPA permit 2PD00006*WD fact sheet,
  composite sheets 49 and 52 (`data/documents/oepa/van-wert/2PD00006.f8aaad0a.pdf`).
  (The stream network above corrects an earlier line that omitted Middle Creek.)
- **The City drinks the creek it discharges to — one reach, three claims on it** (#1406). Van Wert
  City is the **only surface-water public water system in Van Wert County** (PWS **OH8100611**,
  community system, primary source `SW`, 10,846 served, active — EPA SDWIS via ECHO, extract
  2026-07-09) `[verified]`, and the City's own utilities page says outright that "the water that
  the people of Van Wert use and drink comes from Town Creek" `[reference]`. Snapped to NHDPlus v2
  through USGS NLDI on 2026-08-01, the **water plant, the city's second NPDES point and the WWTP
  outfall all fall on one 17.05 km flowline (COMID 15653063)** running south → north, with the
  **five CSO outfalls in between** (Wall St., First & Monroe, Main St., Central, Keplar — all
  discharging to Town Creek, coordinates in Part II.C of the permit). `[verified]` The intake side
  is therefore **upstream** of the CSOs and the outfall — nobody drinks this plant's effluent —
  but every claim on the creek's flow is a claim on the same water in sequence. `[inference]`
  And the buffer is thin: the City's reservoirs hold **1.01 billion gallons**, while the creek's
  recorded annual yield since 1951 runs from **180 million gallons to 1.26 billion** — a 7× spread,
  with the worst year delivering under a fifth of storage. `[reference]` Standing watch, with the
  compliance record and every open thread: `data/extracted/van-wert/water-watch.yaml`.
- **The municipal wastewater permit is under a CSO construction schedule as of 2026-07-01**
  (#1406). NPDES **2PD00006\*WD** (modification of the \*VD renewal; action 2026-05-18, Public
  Notice 221593, comment closed 2026-06-24, entered the Director's Journal 2026-06-30, effective
  2026-07-01, expires 2030-05-31) rewrote Part I.C around the CSO **Long Term Control Plan
  Compliance Assistance Plan** — the 2022 Completion Evaluation Report having found the 1999
  plan's ≤4-events-per-typical-year goal **not attained**. Four control projects (Blaine St.
  interceptor, **Town Creek siphon**, Bonnewitz pump-station weir, raising the CSO 010 weir six
  inches) are now dated obligations: **begin construction by 2026-08-01**, operational by
  2027-01-01, 24-month post-construction monitoring 2027-03 → 2029-03, completion evaluation
  2029-06-01. `[verified]` Whether construction actually began by that first date is `[open]` —
  and the same permittee's CSO Event Report, O&M Report and Combined Sewer Report schedule events
  have been recorded by ECHO as "unachieved and not reported" **continuously since early 2024**,
  with **zero formal enforcement actions and $0 in penalties**. `[verified]` (ECHO DFR OH0027910,
  read 2026-08-01, ICIS-NPDES extract 2026-07-24; **12 of the 13 quarters ECHO displays** carry a
  violation, the exception being 2023-Q4 — *not* "12 of 12", which is what the pre-ingest research
  had.)
- **Maumee TMDL phosphorus:** the plant carries an individual wasteload allocation of **1,000 kg
  total phosphorus for the critical season (March–July)** under the September 2023 Maumee
  Watershed Nutrient TMDL, and Part II.AE routes compliance to "the Maumee Watershed Total
  Phosphorus NPDES General Permit" — **the permit prints no general-permit number**, so binding
  that to the corpus's `OHP000001` is our identification, not the instrument's. `[verified]` Held
  at its own 15 kg/day monthly-average loading limit across the 153-day season the individual
  permit would allow 2,295 kg — **2.30× the allocation** — which is why the condition defers to
  the general permit and carries a reopener. `[inference]` The same permit's Part II.AE names the
  covered facility "**Defiance** Van Wert WWTP", boilerplate carried over from another permittee
  and printed verbatim in an issued instrument. `[verified]`

### Hydrology screen

- **Receiving water:** Town Creek / Little Auglaize (the Van Wert WWTP receiving reach is
  OH0027910 → Town Creek RM 13.87; design flow 4.0 MGD, peak hydraulic capacity 8.0 MGD;
  **outfall 001 at 40.8882410 N, -84.58437518 W** — permit 2PD00006\*WD and its draft public
  notice, #1406; see the Van Wert `SiteProfile`). `[verified]`
- **Nearest mainstem gage:** USGS 04186500 (Auglaize River near Fort Jennings) — on the Auglaize
  mainstem, **not** Town Creek/Little Auglaize; a Town Creek 7Q10 needs separate derivation.
  `[reference]`/`[open]`
- **Abstraction vs. flow:** the facility's specific discharge point / receiving water and a Town
  Creek 7Q10 are not disclosed (closed-loop + still-negotiated water/sewer). `[open]` — no
  assimilative screen possible until the outfall and a low-flow denominator are pinned.
- **Site drainage — Town Creek is NOT where most of this campus drains** (#1403). Intersecting the
  committed boundary with the Van Wert County GIS `Watersheds` layer splits the 901.5 planar acres
  **North Spice Run 371.54 ac (41.2%), Marsh Ditch 347.43 ac (38.5%), Van Wert Corp Ditch 1024
  102.81 ac (11.4%), Town Creek 61.88 ac (6.9%)**; 17.8 ac (2.0%) fall outside the layer.
  `[verified]` as the county's own mapping. All four are **petitioned county ditches** with their
  own numbers (North Spice Run #1966, Marsh Ditch #1592, Town Creek #1391, Ditch 1024), which makes
  the **Van Wert County Engineer / ditch-maintenance record** the instrument for the campus
  stormwater path. The site profile's `corridor_name` and `abstraction_gage` model Town Creek as
  the receiving reach, and Town Creek takes under 7% of the campus — the downstream routing of the
  other three into the Little Auglaize → Auglaize → Maumee is `[inference]` pending an NHD/NLDI
  trace and is a live lead, not a settled path.

### Regulatory record (status as of 2026-07-02; #1401 lines dated 2026-08-03)

- **Annexation + zoning — the instrument, replacing the press summary (#1401):** **901.698 ± ac**
  annexed from Hoaglin, Pleasant and Ridge Townships (Ord. 26-05-028), plus the I-2 code amendment
  (26-05-029) and the conditional I-2 designation (26-05-030). All three introduced, **statutory
  rules suspended**, and passed **on first and final reading as emergencies** on 2026-05-11 — no
  second reading, effective on passage. `[verified]`
  **The "6–0" is a press reconstruction, not the record:** the minutes give **no numeric tally**
  for any of the three, only "all concurred. Ordinance passed." Seven members answered roll call;
  **Councilman Roberts was excused during public comment and abstained as an employee of the Marsh
  Foundation**, leaving six. `[verified]` The one roll-called Mega Site vote in the ingested set is
  the 2026-04-27 preparation motion: "Hurless, Agler, Ringwald, Johnson, Block, and Moore voted
  yes. Roberts abstained." `[verified]` (`5.11.26.pdf` pp. 0-4; `4.27.26.pdf` p. 2)
- **The 2026 ordinance reaches back to 2014 to justify itself (#1401).** Ord. 26-05-028 declares
  itself "in furtherance of" **three Pre-Annexation Agreements** — **2014-11-14** (Ridge Twp),
  **2014-12-22** (Hoaglin Twp), **2016-06-14** (Pleasant Twp) — each recited as being among City
  Council, a township board of trustees and the Board of County Commissioners. **That recital is
  the whole of what is `[verified]`**: the dates, the parties, and what the ordinance says it
  furthers. None of the three is in the corpus, so their terms, the territory they cover, whether
  they bind anyone, and whether they bear on this annexation beyond being cited by it are all
  `[open]` — and reading them as a decade-early runway for the campus is an `[inference]` from a
  recital, not a finding. All three are now the top of the pull list. The recurring public-comment
  claim that the site was "designated and pre-annexed for industrial use **since 2007**" is
  supported by **nothing** in the instrument set. `[open]`
- **County approval, now dated (#1401):** the annexation petition was filed with the Board of
  Commissioners by **Charles F. Koch, agent for petitioners**, on **2026-03-09**, and the BOC
  "approved and granted the petition by the passage and approval of a resolution on **2026-03-10**"
  — one day later. `[verified]` (ordinance recital) The BOC's own journal entry is still not in the
  corpus. The City Auditor recorded receiving the transcript **2026-03-11** for the petition "filed
  by **The Marsh Foundation and Van Wert East Owner LLC**", with the R.C. 709 sixty-day hold
  expiring 2026-05-10. `[verified]`
- **The instrument set contradicts itself on its own statutory route.** `[open]` The 2026-04-27
  committee motion, the ordinance the City posted on 2026-05-07, and the 2026-05-11 agenda all say
  **Expedited Type 2**; the title as read at passage says **Expedited Type 1**, which the Law
  Director explained as "a typographical error in the agenda only." The minutes go further —
  "consistent with the heading of Ordinance 26-05-028 itself" — and **that heading reads Type 2**
  (both readings confirmed visually at 400 DPI, so this is the record, not an OCR artifact). It
  cannot be settled from this
  corpus, because **no signed or certified copy of any of the three ordinances is public** — all
  six ordinance PDFs were uploaded four days *before* the vote and print an unfilled
  `Passed this ___ day of ___, 2026`. `[verified]` R.C. 709.022 and 709.023 are different
  procedures with different township-taxation consequences. A certified copy from the Clerk of
  Council resolves it.
- **Timeline — the applicant's filed dates now supersede the press ones (#1402).** The
  construction-stormwater NOI gives **project start 2026-08-03** and **estimated completion
  2030-08-03**. `[verified]` (`edoc-4209395.pdf` p. 0) The press schedule the register previously
  carried — groundbreaking Q4 2026, full buildout ~2032 — is `[reference]` and is **two years long
  at the far end**; first building operational Q1 2029 is unaffected and remains `[reference]`.
  Council, answering from the floor 2026-04-27: "It will take 5-6 years to complete"; "the end user
  will create at least 250 jobs." `[reference]` (`4.27.26.pdf` p. 4)
- **Ohio EPA air PTI (emergency generators):** still **not applied for**, and that is now
  `[verified]` rather than an unsuccessful search (#1402). The campus's own NOI answers the permit
  status field **`PTI: YET_TO_APPLY`**, certified under penalty of law 2026-07-21.
  (`edoc-4209395.pdf` p. 0) A full eDoc sweep on entity "QTS" the same day returned **35 documents
  and no Van Wert air permit of any kind** — QTS's entire Ohio air-permit fleet is Licking County
  (New Albany, facility IDs 0145000602/0145000603). QTS says generators are emergency backup only,
  tested monthly; emergency generators <500 hr/yr may fall under permit-by-rule, otherwise a
  PTI/PTIO is required — whether one is required here is `[open]`, and the certification promises
  no filing. **This is the single instrument that would lift the facility domain to `live`**, so
  re-run the eDoc sweep on cadence.
- **NPDES / construction stormwater — the campus's first state permit (#1402).** Coverage
  **`2GC08872*AG`** under general permit **OHC000006** was approved **2026-07-30**, effective the
  same day, expiring 2028-04-22 (the general permit's own cycle date, not a project milestone).
  Applicant **QTS Realty Trust Inc.**; facility "QTS Data Center", **8002 Mendon Road**; point
  **40.893356 / -84.5528**; receiving stream **Town Creek**; **792.0000 ac** of land disturbance.
  `[verified]` (`edoc-4209395.pdf`, `edoc-4209398.pdf`) Ohio EPA's letter names township
  **Pleasant** only where the NOI names **Pleasant and Ridge** — recorded, not resolved. No
  **co-permittee** NOI is on file, so the general contractor is `[open]`; Sidney's identical
  coverage produced one, so this is a live watch. The NOI answers "NO" to both an individual 401
  WQC and an isolated-wetlands permit while answering **`YET_TO_APPLY`** on the USACE nationwide
  permit — applicant assertions on a form, not agency determinations.
- **A private-well ordinance is moving, and the drafted text does not match the motion (#1407).**
  On 2026-06-08 Councilman Block moved for an ordinance "prohibiting any new wells be drilled
  within city limits; existing wells within the city limits will be grandfathered in", and
  "Council agreed this may be necessary to more clearly define an existing ordinance in which it is
  not clear if **industrial areas are covered**." `[verified]` (`6.8.26.pdf` p. 1.) The drafted
  Exhibit A of Ordinance **26-06-034** reads in its entirety: "No new private wells shall be a
  permitted use within the City of Van Wert through all zoning classifications. All new private
  wells shall be a **conditional use** in all zoning classifications." `[verified]`
  (`26-06-034-DRAFT.pdf` p. 1, 450 DPI.) **It prohibits nothing** — it makes new wells a
  discretionary approval — and its own text carries neither the grandfather clause nor the
  closed-loop-geothermal exception the Council discussion turned on. Introduced and given first
  reading advisory 2026-07-13; not passed; unsigned, like every Van Wert ordinance PDF here. If
  enacted in this form the municipal system becomes the campus's only unconditional supply, which
  is consistent with QTS's "no intentions of utilizing the aquifer" — but the record nowhere ties
  the ordinance to this campus, and reading it that way is `[inference]`.
- **The citizen initiative to repeal the data-center use failed (#1407).** A petition filed by city
  resident Joe Jared in mid-July 2026 would have put the repeal of the I-2 data-center use to the
  2026-11-03 ballot; the Board of Elections found **255 valid signatures against 323 required**, and
  signatures cannot be added because the part-petitions were already filed. `[reference]` (VW
  Independent, 2026-07-20 and 2026-07-27, quoting Elections Director Pam Henderson.) The Board's own
  certificate is not in the corpus. `[open]`
- **NPDES / operating discharge:** Ohio EPA's draft general NPDES permit for data centers, **OHD000001**
  (public hearing 2025-12-17, comment period closed **2026-01-16** — non-contact cooling water,
  cooling-tower/boiler blowdown, low-volume wastewater, industrial stormwater), was **WITHDRAWN
  2026-07-21** and never took effect. `[verified]` (`data/reference/oepa/ohd000001-coverage.yaml`)
  It was never linked to the Van Wert facility by name, and with the general permit gone an
  **individual** NPDES permit is the only remaining instrument on a *direct-discharge* path — but
  that path is not established here: a campus routing blowdown to the City WWTP holds no NPDES
  permit at all and is disclosed instead by the City's **industrial-user / pretreatment permit and
  sewer-use agreement** (the C2 ask, #1688). Neither has been searched `[open]`. The 2026-05-04
  hearing record still cites OHD000001 as a live draft — a regulatory premise the record preserves
  and that has since lapsed.

### Opposition / litigation

- **Local opposition — corrected to the record (#1401).** The large public meeting was the
  **statutory hearing of 2026-05-04**, not the May 11 vote: **~200 attending, ~40 speakers**, two
  minutes each, comment-only by rule, 6:30-8:03 pm at the Niswonger PAC. `[verified]`
  (`5.4.26-Public-Hearing-1.pdf` pp. 0-1) On May 11, **18** members of the public spoke on the
  annexation and Council passed all three ordinances as emergencies on first and final reading.
  `[verified]` A moratorium was requested twice and moved neither time — from the floor on
  2026-04-27 ("Block does not feel the need to move this request forward at this point in time")
  and in writing at the hearing. `[verified]`
- **21 of 88 written-comment pages share an identical opening (#1401).** `[verified]` Of the 88
  written-comment pages in the 2026-05-04 record, **21 share an identical normalised 900-character
  opening with an earlier page** — 67 distinct openings across 88 pages, 15 clusters holding more
  than one page, the largest holding **five**. **Near-identical, not verbatim:** over the *whole*
  normalised body only **one** pair is byte-identical (pp. 17/64, the same letter scanned twice),
  while the other 20 run **0.974–1.000 similarity, median 0.987**, diverging only in the tail
  (signature blocks and addresses, handwritten and OCR-noisy). Reproducible: OCR at 300 DPI,
  normalise, cluster on the leading 900 characters, then score full bodies with difflib. The count
  is of pages, not people. `[inference]` That pattern is very hard to produce by independent
  authorship, so a coordinated letter campaign is the natural reading — but who organised it and
  how many distinct people are behind the 21 pages are `[open]`. Independent of that inference:
  the recurring claim set — $10B invested, **$200M in community revenue over 20 years**,
  **200-250 permanent jobs at ~$80,000**, **1,000-1,500 construction jobs** — **appears in no
  instrument**, so it is `[reference]` at best wherever repeated.
- **One cited opposition comment (#1401).** A written comment (pp. 104-106) argues the water case
  with a full reference list; two of its figures — the **1.01 BG** reservoir and the **180 MG–1.26
  BG** annual creek yield — are the same figures independently committed in `water-watch.yaml`
  from the City's own utilities publications. Its arithmetic elsewhere does not survive checking
  (it conflates MW with MWh). `[verified]` as to what was submitted.
- **Statewide:** a citizen effort is gathering signatures for a constitutional amendment to prohibit
  data centers consuming >25 MW; lawmakers heard data-center opposition (June 3, 2026) but
  enacted no moratorium. `[reference]` (advocacy).
- **Litigation:** none specific to the Van Wert project found. `[open]`

## 2 — No other confirmed Van Wert County activity pinned yet

No second data-center operator or land assembly in Van Wert County is confirmed to the pinning
standard as of 2026-07-02. `[open]` — re-sweep on the next pass.

## Instruments to pull (priority order)

0. **Certified copies of Ordinances 26-05-028 / 029 / 030, and the three Pre-Annexation
   Agreements.** New from #1401 and ahead of everything else. No signed copy of any of the three
   ordinances is public — only pre-passage uploads — and a certified copy is the only thing that
   settles whether the annexation ran as Expedited Type 1 or Type 2. The three agreements
   (**2014-11-14** Ridge, **2014-12-22** Hoaglin, **2016-06-14** Pleasant) are the **earliest
   datable instruments in the Mega Site's chain**, a decade older than the project, and nothing
   about their terms is known. Both are records requests to the Clerk of Council; the agreements
   may also sit with the Board of County Commissioners or the County Recorder. Add the BOC's
   **2026-03-10 resolution and annexation transcript** (recited, not held) and the 2026-05-04
   hearing's **audio/video recording plus the Clerk's written-comment file** — the certified
   minutes name both as part of the official record and summarise ~40 speakers in one paragraph,
   so the spoken opposition exists nowhere in this corpus.
1. **Van Wert County Recorder** — the **grantor** side and the instrument numbers. The Auditor half
   of this item is **done** (#1403): grantee, parcel IDs, acreage, prices and transfer dates are
   committed from the CAMA. What the auditor layer cannot give is the grantor, the deed book/page
   and the legal description, so the Marsh Foundation → Thor/Form8tion (Aug 2025) → QTS (Jun 2026)
   chain still needs the recorded instruments. Add the county Engineer's **survey records** named on
   the parcels — `VW-SD522-1`, `VW-SD522-2`, `VW-SD522-523`, `VW-SD524` — which are the splits that
   carved the campus out of the Marsh tract.
2. **Van Wert City Council / County Commissioners** — executed CRA / PILOT / TIF ordinance(s) with
   %/term, plus the Lincolnview + Vantage school-compensation agreements. **Re-aimed by #1407**:
   this is no longer a search but a **watch on a named negotiation** — VWAED's Executive Director
   was "concluding incentives and development agreements" on 2026-07-13 and expected them by the
   next meeting, so the pull is the **2026-07-27 and 2026-08-10 minutes and any `26-08-0xx`
   ordinance**, plus the County Auditor's abatement roll. Add the **joint QTS / City engineering
   water-capacity analysis** the operator's FAQ names, the **2026-06-22 council minutes** (indexed
   by the City, 404 on the file), and the **BOC journal entries** for 2026-02-12, 2026-03-10 and
   2026-07-28 — the Board publishes agendas only, so every county action remains unreachable.
3. **OEPA air PTI** — emergency generator bank PTI(s) for the Mega Site (NWDO, Van Wert County).
   **Now known not to exist yet** (#1402): the campus's own NOI certifies `PTI: YET_TO_APPLY` as of
   2026-07-21, and an eDoc sweep on "QTS" returns no Van Wert air document. So this is no longer a
   pull but a **watch** — and the highest-value one on this list, because it is the instrument that
   would ground the campus load and lift the facility domain from `seeded` to `live`. Re-run the
   eDoc entity search on cadence.
3a. **Co-permittee NOI + City grading/building permit** — new from #1402. Ohio EPA's approval
   requires each additional operator at the site to file its own co-permittee NOI (Sidney's
   identical coverage produced one), so the general contractor is `[open]`. The City grading permit
   is the network's trigger for moving the facility from `confirmed` to `construction`, and the
   applicant's filed start date is 2026-08-03.
4. **Ohio EPA / EPA ECHO** — the facility-discharge half, **re-aimed** (#1883): there is no
   notice-of-intent to look for, because OHD000001 was withdrawn 2026-07-21 and will never issue.
   Ask instead for an **individual** NPDES permit or application naming the QTS campus, and — since
   a campus on the City sanitary sewer holds no NPDES permit at all — the City of Van Wert's
   **industrial-user / pretreatment permit and sewer-use agreement** for it (#1688). Plus
   a Town Creek / Little Auglaize 7Q10. The **municipal** half of this item is **done** (#1406):
   permit 2PD00006\*WD is committed, the outfall is coordinate-pinned, and the compliance record
   is dated and regenerable in `data/extracted/van-wert/water-watch.yaml`. What that register
   leaves open — the raw-water intake's own location, the CSO volumes, a measured critical-season
   phosphorus load, and the two uncommitted water-plant permits (OHG8P0006, OH0135569) — is
   itemized there under `instruments_to_pull`.
5. **City of Van Wert water/sewer** — the closed-loop fill volume and any water/sewer service
   agreement (the peak-withdrawal figure to screen against Town Creek). Sharpened by #1406: the
   creek's own recorded annual yield ranges 180 MG–1.26 BG since 1951, so the screen a service
   agreement needs is against a **dry year**, not an average one.

## Sources

### Ingested primary instruments (cite these, not the press)

- **City of Van Wert legislative record (#1401)** — `data/documents/van-wert/council/`
  (manifest: `filename-map.yaml`; nine PDFs pulled 2026-08-03 from `vanwert.org`). Extraction:
  `data/extracted/van-wert/mega-site-instruments.yaml`, digest `mega-site-instruments.md`.
  Ordinances `26-05-028` (annexation), `26-05-029` (the "Data Center" code amendment),
  `26-05-030` (conditional I-2 zoning + Exhibit C conditions); the certified **2026-05-04**
  public-hearing record; council minutes **2026-04-27** and **2026-05-11**.
- **Ohio EPA NPDES 2PD00006\*WD + draft public notice (#1406)** — `data/documents/oepa/van-wert/`,
  extractions `data/extracted/oepa/van-wert/`, standing register
  `data/extracted/van-wert/water-watch.yaml`. **The CITY's plant**, not the campus.
- **Ohio EPA construction-stormwater coverage `2GC08872*AG` (#1402)** —
  `data/documents/oepa/van-wert/stormwater/` (manifest: `filename-map.yaml`; three PDFs pulled
  2026-08-03 from the eDocument portal). Extractions
  `data/extracted/oepa/van-wert/2GC08872.noi.npdes.yaml` and `2GC08872.approval.npdes.yaml`.
  **The CAMPUS's own permit** — construction-phase only. Includes the corpus's first site plan.
- **Campus parcel geometry (#1403)** — `data/reference/van-wert/parcel-assemblage.geojson`,
  `data/extracted/van-wert/bosc-site-footprint.yaml`.
- **The incentive / water-service search set (#1407)** — four more City documents in
  `data/documents/van-wert/council/` (the approved minutes of **2026-05-27**, **2026-06-08** and
  **2026-07-13**, and Ordinance **26-06-034** on private wells); the County's 2026 agenda index in
  `data/documents/van-wert/county/`; the operator's own FAQ in
  `data/documents/van-wert/operator/`; the Ohio Tax Credit Authority minutes of **2026-06-01** and
  **2026-06-29** in `data/documents/odd/tca/`; and the Governor's 2026-05-27 pause notice in
  `data/documents/odd/`. Extraction:
  `data/extracted/van-wert/incentive-water-instruments.yaml`, digest
  `incentive-water-instruments.md` — which carries the per-route negatives, their blind spots, and
  the priority pull list.

**Route note for future Van Wert legislation:** `vanwert.org/ordinances/` is a rolling window of
pending items only — the May 2026 ordinances had already dropped off it by 2026-08-03. The site's
open WordPress REST media index (`/wp-json/wp/v2/media?search=26-05&per_page=100`) enumerates the
whole upload archive with dates, titles and URLs, needs no auth, and is how these were found.
**One caveat from #1407:** the index can outlive the file. Its row for the **2026-06-22** council
minutes points at `/wp-content/uploads/2026/07/6.22.26.pdf`, which 404s along with three path
variants — the attachment record survived the upload. Treat an index row as a claim about the
archive, not a guarantee of it, and drop the paging filter (`per_page=100&orderby=date&order=desc`
across all pages) rather than searching one prefix.

**Route note for state incentives (#1407):** the **Ohio Tax Credit Authority publishes its meeting
minutes on the Ohio DAM** — the same open, unauthenticated, scriptable host as the Ohio EPA permit
DAM — under **two alternating filename patterns**, and which one a given meeting uses is not
predictable, so probe both:
`…/development.ohio.gov/business/stateincentives/TCA_Meeting_Minutes_<M.D.YYYY>.pdf` and
`…/development.ohio.gov/about/taxcreditminutes/Meeting_Minutes_TCA_<M.D.YYYY>.pdf`. Minutes appear
only after the *following* meeting approves them, so the record runs about a month in arrears. The
`development.ohio.gov` tax-credit-authority page itself is JS-rendered and its HTML carries no DAM
links. **BoardDocs** (any Ohio district: `go.boarddocs.com/oh/<code>/Board.nsf`) is likewise
scriptable without auth — POST `BD-GetMeetingsList` and `BD-GetAgenda` with the `committeeid` read
out of the public page's HTML — but it rate-limits into a CloudFront 403 under a burst.

**Route note for Ohio EPA permits:** the eDocument public portal
(`edocpub.epa.ohio.gov/publicportal/edochome.aspx`) is open to scripted search with no auth and no
challenge, and searching one operator name returns its **whole Ohio fleet** — which is how the
2026-07-30 Van Wert coverage was found four days after issuance, and how the absence of any Van
Wert air permit was established rather than assumed. Search by Entity Name ("QTS"); the portal
serves documents with **no `Content-Disposition`**, so the numeric docid is the as-served identity
and the committed files are named `edoc-<docid>.pdf`. Re-run it on cadence: the air PTI is the
instrument that would move this site's facility domain.

### Secondary / press

- QTS (official): [q.com/data-centers/van-wert](https://q.com/data-centers/van-wert/)
- Hometown Stations ($10B announcement): [van-wert-announces-10-billion-qts-data-center-campus-investment](https://www.hometownstations.com/news/van_wert_county/van-wert-announces-10-billion-qts-data-center-campus-investment/article_18b9e9fc-010b-4353-95c0-4ed96293c1ed.html)
- Data Center Dynamics (QTS end user): [qts-behind-van-wert-ohio-mega-site-acquisition-announces-10-billion-data-center-campus](https://www.datacenterdynamics.com/en/news/qts-behind-van-wert-ohio-mega-site-acquisition-announces-10-billion-data-center-campus/)
- VW Independent (end user): [2026/05/29/qts-data-centers-is-the-end-user-for-vw-data-center](https://thevwindependent.com/news/2026/05/29/qts-data-centers-is-the-end-user-for-vw-data-center/)
- VW Independent (council approval): [2026/05/11/council-unanimously-approves-data-center-legislation](https://thevwindependent.com/news/2026/05/11/council-unanimously-approves-data-center-legislation/)
- VW Independent (timeline): [2026/05/29/data-center-construction-operations-timeline-shared](https://thevwindependent.com/news/2026/05/29/data-center-construction-operations-timeline-shared/)
- VW Independent (opposition): [2026/06/03/lawmakers-hear-data-center-opposition](https://thevwindependent.com/news/2026/06/03/lawmakers-hear-data-center-opposition/)
- Thor Equities (GlobeNewswire, land buy): [thor-equities-group-expands-portfolio](https://www.globenewswire.com/news-release/2025/08/19/3135865/0/en/Thor-Equities-Group-Expands-Portfolio-with-Key-Acquisition-in-North-America-s-Leading-Data-Center-Corridor.html)
- Ohio EPA (data-center general permit — the superseded draft record, preserved): [wastewater-discharges-from-data-centers--general-permit](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit)
- Ohio EPA Community Notice **withdrawing** OHD000001, 2026-07-21 (in corpus as `data/documents/oepa/2026-07-21-ohio-epa-will-not-finalize-data-center-general-permit.npdes-general-permits.html`): [npdes-general-permits](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/npdes-general-permits)
- Bricker (draft NPDES OHD000001, at issuance): [ohio-epa-issues-draft-general-npdes-permit-for-data-centers](https://www.bricker.com/insights/publications/ohio-epa-issues-draft-general-npdes-permit-for-data-centers)
- City of Van Wert water: [vanwert.org/water-treatment](https://vanwert.org/water-treatment/)
- Ohio EPA HUC-12 (Lower Town Creek–Lower Little Auglaize): [nps report PDF](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/nps/Lower%20Town%20Creek-Lower%20Little%20Auglaize%20River_Ver1.0_10-31-2023.pdf)
- Ohio EPA NPDES 2PD00006 (the DAM slot; now serves the \*WD modification): [2PD00006.pdf](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/2PD00006.pdf)
- EPA ECHO Detailed Facility Report, Van Wert WWTP: [OH0027910](https://echodata.epa.gov/echo/dfr_rest_services.get_dfr?p_id=OH0027910&output=JSON)
- EPA "How's My Waterway", Lower Town Creek: [OH041000070804](https://mywaterway.epa.gov/waterbody-report/21OHIO/OH041000070804)
- Stop Ohio Data Centers (advocacy, leads only): [stopohiodatacenters.org/data-center-water-usage-ohio](https://stopohiodatacenters.org/data-center-water-usage-ohio)
