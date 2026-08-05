# Van Wert Mega Site — the incentive and water-service instruments, searched to a dated negative

Digest of [`incentive-water-instruments.yaml`](incentive-water-instruments.yaml). Issue #1407
(epic #1267), mirror of Urbana's #1354. Every quotation below is cited to a committed file and
page; the structured record carries the rest.

**Provenance tags:** `[verified]` = read from a captured primary record or a named public system
on a named date · `[reference]` = secondary / self-published · `[inference]` = reasoned, labelled
· `[open]` = not established.

## The finding

**There is still no executed incentive instrument and no water-service instrument for the QTS Van
Wert campus — and as of this pass that is a dated, sourced negative against five named routes
rather than an unfound thing.**

The sentence that closes the first thread is the City's own. From the approved minutes of the
2026-07-13 Council meeting, Economic Development committee report:

> Johnson reported groundbreaking will occur on July 22[nd] for the new Hampton Inn.
> Additionally, he reported the **Brent Stevens is concluding incentives and development
> agreements for the data center and hopes to have those done by the next council meeting.**

`[verified]` (`7.13.26.pdf` p. 3, read at 300 and 450 DPI). Brent Stevens is the Executive
Director of Van Wert Area Economic Development — the same person who asked Council on 2026-05-04
to approve "the necessary incentives, zoning, and permitting" (#1401). This is the first
primary-source statement in the corpus that an incentive package for the campus exists as a
negotiation, who is conducting it, and when it was expected to close. It also fixes the negative:
on 2026-07-13 nothing was signed, because one does not "conclude" what is already executed. Type,
term, percentage, counterparty and any school revenue share are all `[open]`.

Council next met 2026-07-27. Those minutes were not published on 2026-08-05, and press coverage of
that meeting reports public comment and no incentive action `[reference]`. **Whether the
agreements were signed on or after that date is the single highest-value re-check on this file.**

## What was searched, and what each route can and cannot see

| Route | Covered through | Result |
|---|---|---|
| City of Van Wert legislation + minutes (WordPress REST media index, 298 items) | Ord. `26-07-040`; minutes 2026-07-13 | **No** enterprise zone, CRA, PILOT, TIF, JEDD or development agreement `[verified]` |
| Van Wert County Commissioners (published 2026 agenda index, 63 meeting dates) | 2026-08-06 | **Zero** enterprise-zone / abatement / CRA / TIF / QTS entries `[verified]` |
| Lincolnview Local BOE (BoardDocs, 12 meetings) | 2026-07-22 | **No** data-center agenda item at any 2026 meeting `[verified]` |
| Ohio Tax Credit Authority minutes (Ohio DAM) | 2026-06-29 | **No** Van Wert / QTS item in the four 2026 meetings read `[verified]` |
| ODD tax-incentive export (committed, `data/reference/odd/tax_incentives.csv`) | pulled 2026-06-28 | **Zero** QTS rows statewide; 8 Van Wert County rows, newest approved 2022-06-22 `[verified]` |

Each route's blind spot is written down in the YAML. The important ones: the City posts minutes
about two weeks in arrears and an instrument signed administratively need never appear there at
all; the County publishes **agendas but not journal entries**, so no county action is reachable;
BoardDocs agenda *titles* were read but the attached minutes documents were not retrieved; and the
ODD export lags — it does not yet carry the 2026-06-01 Cologix exemption its own minutes record,
which is exactly why the minutes were read as a second route.

## The state exemption

The Governor directed the chair of the Ohio Tax Credit Authority on **2026-05-27** to "pause
consideration of any new data center tax exemption requests while the Ohio General Assembly's
Joint Data Center Committee studies the growth of data centers in Ohio" `[verified]` (captured
notice in corpus). That is two days before the QTS Van Wert announcement — a sequence, not a cause,
and no causal reading is offered.

- **The last exemption granted** went to **Cologix, Inc** on **2026-06-01** — 50 percent for 10
  years, Orange Township (Delaware Co.) and the City of Johnstown (Licking Co.), 90 FTE / $10M new
  payroll, term 2026-01-01 → 2035-12-31, vote 3-0 with two abstentions. `[verified]`
  (`TCA_Meeting_Minutes_6.1.2026.pdf` p. 2.) Note the date: **five days after the pause was
  announced**, which is consistent only if the pause is read as it is written — applying to *new*
  requests.
- **2026-06-29, the first meeting wholly under the pause:** seven new projects, **zero** data-center
  exemptions. `[verified]`
- A **Van Wert item does appear** on that agenda and **it is not this campus**: "Van Wert Forward
  II", under Transformational Mixed-Use Development, for which the Authority engaged the University
  of Cincinnati Economics Center as third-party analyst. The committed ODD export carries the same
  name as an Ohio Historic Preservation Tax Credit approved **2022-06-22** — a downtown
  redevelopment four years older than this project. Recorded explicitly so a future keyword sweep
  for "Van Wert" in the state incentive record does not mistake it for a Mega Site award.

**The project's exemption status is `[open]`.** No application, award or agenda item naming Van
Wert, QTS, QTS Realty Trust Inc. or QTS Van Wert LLC exists in the 2026 state record read here.
Whether the project proceeds without the R.C. 122.175 exemption remains the live financial-structure
question the issue raised. The Authority's 2026-07-27 minutes are not yet published, so the "still
paused" reading stops at 2026-06-29.

## The water thread

The operator's live page still carries the claim, captured 2026-08-05:

> **The City of Van Wert has approved our water usage** and we're currently in discussions to
> identify the best solutions to support the initial fill. QTS has **no intentions of utilizing the
> aquifer** to support the initial fill.

`[verified]` as to what the operator publishes. **The City's own record contains no such act** —
no water-service approval, agreement, rate resolution or authorization to sell water to this campus
appears in any ordinance through `26-07-040` or in any approved minutes from 2026-04-27 through
2026-07-13. Whatever the approval was, it was not a published act of Council.

Three things this pass adds:

1. **The FAQ names the document that would settle it.** "The analysis completed by QTS and City
   engineering indicates that there is adequate capacity in the existing system to support the
   proposed development." That converts "no capacity study found" into a records request with a
   subject line — the joint QTS / City engineering capacity analysis, held by the City Engineer or
   the Safety-Service Director. **Priority-1 pull.**
2. **The ~660,000-gallon figure is the City's number, not the operator's.** QTS declines to state a
   fill volume at all: "The total initial charging volume can vary widely … it's hard to predict
   the exact amount of water needed." Every figure in the corpus's fill-vs-annual dispute traces to
   a City official or to a citizen quoting the dead city microsite. That materially weakens reading
   "~660,000 gallons" as a disclosure *by QTS*, and it is why the `closed_loop_dry` pin stays
   `[reference]` (B2, #1682). Four statements now, none reconciled — and the newest withdraws the
   number rather than settling it.
3. **The cooling medium is stated two ways.** QTS: "The closed-loop system that cools the data hall
   uses only water." The City's Safety-Service Director, 2026-04-21: a sealed **water-and-glycol**
   loop. Both are in the corpus; both stand.

### The private-well ordinance — and the gap between what Council moved and what was drafted

On **2026-06-08** Councilman Block moved for an ordinance "prohibiting any new wells be drilled
within city limits; existing wells within the city limits will be grandfathered in", and "Council
agreed this may be necessary to more clearly define an existing ordinance in which it is not clear
if **industrial areas are covered**." `[verified]` (`6.8.26.pdf` p. 1.)

The drafted Exhibit A of Ordinance **26-06-034** reads, in its entirety:

> Section 150.41 — Private Wells. No new private wells shall be a permitted use within the City of
> Van Wert through all zoning classifications. All new private wells shall be a conditional use in
> all zoning classifications.

`[verified]` (`26-06-034-DRAFT.pdf` p. 1, 450 DPI.) **It prohibits nothing.** It converts new
private wells from a permitted use to a *conditional* use — a discretionary approval — and its own
text contains neither the grandfather clause nor the closed-loop-geothermal exception the Council
discussion turned on. Introduced and given first reading advisory 2026-07-13; not passed; the
posted copy is unsigned and prints an unfilled `Passed: ____ 2026`, like every Van Wert ordinance
PDF in this corpus.

If enacted in this form, a campus inside city limits could not open a private well without a
discretionary City approval, leaving the municipal system as the only unconditional supply —
consistent with the operator's "no intentions of utilizing the aquifer". But the record nowhere
connects the ordinance to this campus; the closest it comes is Council's own "not clear if
industrial areas are covered". Reading it as aimed at the campus is `[inference]`.

## Three things the county's own agendas add

The Board of Commissioners publishes agendas (not journal entries) as a single page per year. All
63 dates from 2026-01-01 to 2026-08-06 were read.

- **2026-02-12 — "Brent Stevens, Executive Director, Van Wert Area Economic Development
  Corporation Re: Megasite End User Options".** Three and a half months before the end user was
  publicly named, and four weeks before the annexation petition was filed. The agenda line is
  `[verified]`; what was said is `[open]`.
- **2026-03-10 — "Chuck Koch, Attorney, Koch & White Law Re: Annexation".** Independent
  corroboration of the date Ordinance 26-05-028 recites for the County's resolution granting the
  petition. Until now that date rested on the City ordinance's recital alone.
- **2026-07-16 and 2026-07-28 — Ridge Township, the County Engineer and Van Wert City
  representatives on "Mendon Road and surrounding area expectations".** The campus's own address on
  its construction-stormwater NOI is 8002 Mendon Road (#1402). What was decided is `[open]` —
  these are agendas, not actions.

## Two corrections this pass makes to the register

**1. The City called the Van Wert–Haviland transmission line "not related to the Data Center."** On
2026-05-27 Safety-Service Director Jay C. Fleming told Council that AEP "has been planning a power
line upgrade **for about 3 years ago**" (the minutes' own phrasing) between the Haviland facility
and the substation behind the street department, running a "135-kilovolt" line down Dutch John
Road "to help Industrial Park along with the city's electrical backbone" — and **"Fleming
reiterated this project was not related to the Data Center."** `[verified]` (`5.27.26.pdf` p. 1,
identical at 300 and 450 DPI.) When this was written the corpus held OPSB **25-0697-EL-BLN** only
as a bare case number behind a bot-blocked docket, so this was the only primary-source evidence on
the question.

**#1408 committed the filing itself the same day, and it narrows this rather than confirming it.**
The two agree on the engineering: the LON's driver is a **PJM baseline thermal-criteria violation**
on a line of 1926 wooden monopoles, not a campus interconnection. They do not agree on absence —
AEP's Statement of Need **names the Van Wert Mega Site twice** and counts **30 requests for
transmission service** there in the past year. And the cost question this seemed to bear on is
settled by the instrument instead: **$45,877,232** for the whole project, so the $45M half is not a
subset and the commissioner's "$72 million" stays `[open]`. What survives is the narrow reading —
the City's own officer told Council this rebuild is not campus-built infrastructure. What does not
survive is reading it as the campus being absent from the project's justification. (The minutes'
"135 kV" matches neither figure in the LON — a 69 kV line rebuilt at 138 kV design — so it is a
minutes error on any reading, `[inference]`.)

**2. The City's franchise with the campus's utility was cut from 50 years to 10.** Ordinance
**26-02-010** grants Ohio Power a franchise in the City's streets as "an extension of the agreement
set out in Van Wert Ordinance Number 5270-75 passed October 15, 1975", and passed third and final
reading **2026-06-08** ("all concurred"; no numeric tally). Twelve days earlier, on 2026-05-27,
"Fleming supplied the updated AEP Lease Agreement to council which took the lease from 50 years
down to 10 years", and Council untabled the ordinance and amended the term accordingly.
`[verified]` (`6.8.26.pdf` p. 3; `5.27.26.pdf` p. 3.) It is the City's only executed instrument in
this window with the utility that will serve the campus. The minutes give no reason for the change
and none is inferred here.

## Two other dated facts from the window

- **The citizen initiative failed.** The petition to repeal the data-center use from the I-2
  district — filed by city resident Joe Jared to stop the campus — returned **255 valid signatures
  against 323 required**, so no city question reaches the 2026-11-03 ballot; signatures cannot be
  added because the part-petitions were already filed. `[reference]` (VW Independent 2026-07-27,
  quoting Board of Elections Director Pam Henderson.) The Board's own certificate is not in the
  corpus. **#1408 carries the fuller account** — the 2026-07-18 filing date, that the target was
  Ordinance **26-05-029** specifically, the statutes cited, and why the mechanism was an
  *initiative* rather than a referendum. Cite that one; this line is the same event seen from this
  pass's sweep.
- **The operator's page carries boilerplate from another market.** Its economy answer says the
  project will "support services and community programs throughout **Richmond County**" — Augusta,
  Georgia, not Van Wert County, Ohio. `[verified]` as to what the page says. Same species as the
  issued NPDES permit that names the "Defiance Van Wert WWTP" (#1406): recorded because a page
  carrying an unproofed paste is weaker evidence of Van-Wert-specific diligence than its tone
  implies, not because it moves a figure. The same page also prints no "$200 million over 20 years"
  — only "millions in local tax revenue annually".

## What is still missing (priority order)

1. The **incentive and development agreements** VWAED was concluding on 2026-07-13 — Clerk of
   Council (2026-07-27 / 2026-08-10 minutes, any `26-08-0xx` ordinance), VWAED, the County
   Auditor's abatement roll.
2. The **joint QTS / City engineering capacity analysis** named on the operator's FAQ.
3. The **water-service instrument** itself — whatever act the operator calls the City's approval.
4. The **2026-06-22 council minutes** — the City's media index lists the file and serves a 404, so
   this is the one meeting in the window that could not be read.
5. **BOC journal entries** for 2026-02-12, 2026-03-10 and 2026-07-28; **Lincolnview minutes** for
   2026-06-18 and 2026-07-22; **TCA minutes** for 2026-07-27 onward; the **Board of Elections**
   initiative certificate; **Ordinance 5270-75**.

## Route notes worth reusing

- **The Ohio Tax Credit Authority publishes its minutes on the Ohio DAM**, the same open,
  unauthenticated route as the Ohio EPA permit DAM — but under **two alternating filename
  patterns**, `.../business/stateincentives/TCA_Meeting_Minutes_<M.D.YYYY>.pdf` and
  `.../about/taxcreditminutes/Meeting_Minutes_TCA_<M.D.YYYY>.pdf`. Probe both. Minutes appear only
  after the *following* meeting approves them.
- **BoardDocs is scriptable without auth** for any district: `BD-GetMeetingsList` and
  `BD-GetAgenda` by POST, with the committee id read out of the public page's HTML
  (`committeeid="…"`). It rate-limits into a CloudFront 403 under a burst — pace it. The attachment
  endpoint was not resolved in this pass.
- **A county that publishes only agendas still yields a timeline.** Van Wert County's single
  `2026_agendas.php` page carried the whole year and produced three dated corroborations no other
  source in this corpus had.
