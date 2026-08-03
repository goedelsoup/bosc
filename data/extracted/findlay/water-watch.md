# Findlay's standing water watch — the phosphorus number moved, and the deadlines did not

**Issue 1461** · sub-issue of **1265** (`readiness(findlay)`) · ingested 2026-08-02 ·
strengthens `record` · no readiness movement, no contract bump

This is the record-domain companion to the discharge record — the thread that keeps the site
honest as its instruments move. Where
[`discharge-record.md`](discharge-record.md) read the permit as issued, this reads what the plant
has actually reported since, and sets the dates on which each open question next becomes
answerable.

The issue that commissioned it was named for a finding: *over-WLA phosphorus, shielded by the
general-permit bubble*. That framing was correct on the evidence available when it was written,
and the first thing this ingest has to say is that the evidence has changed.

## The headline: the plant went under its allocation the first season the general permit governed

The Maumee TMDL assigns Findlay WPCF a spring wasteload allocation of **3.2 metric tons** of total
phosphorus, restated as a **3,200 kg** Individual Load Limit by general permit `OHP000001`. The
TMDL's own record of what the plant discharged runs 2017 to 2021 and shows 4.8, 5.5, 5.3, 5.5 and
5.4 metric tons — over the allocation, by 50 to 72 percent, in every reported year. After 2021 the
record stopped: the 2024 Biennial Report publishes only the 39-facility group total, so the corpus
could not say whether Findlay was still over. Issue 1460 left that open as `TP-SEASON-REPORTS`.

It is answerable, because the general permit publishes its own load equation and every input to it
is in the reported effluent record:

> Load = C_M \* Q_S \* F — where C_M = median of total phosphorus effluent concentration data for
> the season in mg/L, Q_S = sum of all effluent daily flow rate data for the season in million
> gallons, F = conversion factor = 3.7854
>
> — `OHP000001` Part III, item 1.b, p. 7

Reconstructing it from the DMRs gives this:

| Spring season | Median mg/L | Season volume MG | Derived load kg | Against 3,200 kg |
|---|---|---|---|---|
| 2023 | 0.730 | 1,610 | **4,450** | 139% — over |
| 2024 | 0.400 | 1,820 | **2,756** | 86% — under |
| 2025 | 0.420 | 1,951 | **3,101** | 97% — too close to call |
| 2026 (Mar–Jun) | 0.395 | 1,510 | 2,258 | season incomplete |

The 2023 season — the last spring before the general permit took effect on 2023-11-01 — is
consistent with the TMDL's 2017–2021 record and comfortably over. The 2024 season, the first the
general permit governed, is **1.7 metric tons lower**. Whatever else is true, the plant is not
running at 5.4 MT any more.

What changed is visible in the monthly data, and it is seasonal:

| Year | Spring mean mg/L | Non-spring mean mg/L | Ratio |
|---|---|---|---|
| 2023 | 0.708 | 0.761 | 0.93 |
| 2024 | 0.424 | 0.752 | 0.56 |
| 2025 | 0.402 | 0.761 | 0.53 |

Before the general permit, the two halves of the year are indistinguishable. From the 2024 season
onward the plant runs at roughly 0.40 mg/L inside March–July and roughly 0.75 mg/L outside it,
against an individual-permit concentration limit of 1.0 mg/L that never changes. That is what a
seasonal mass limit is built to produce, and the record shows it producing it. The non-spring
concentration did not rise, so this reads as extra treatment during the season rather than load
pushed out of it — though the corpus holds no operating record, so the *cause* is inference. The
pattern and its timing are not.

Two cautions, both load-bearing.

**This is `[inference]`, not `[verified]`.** The number the permit actually binds is a *reported*
value — parameter 51451, "Phosphorus, Total – Kg", calculated by the permittee and entered on the
July eDMR. What is above is a reconstruction of it. The season volume Q_S is exact, because a
month's mean daily flow times its day count *is* the sum of that month's daily flows. The median
C_M is not: the permit takes the median of every sample in the season, and the eDMR publishes only
each month's average, so this is a median of five monthly means.

**And that approximation swallows the 2025 season.** For 2025 the median that would put the load
exactly at 3,200 kg is 0.4334 mg/L, which falls between the season's 0.42 cluster and its 0.48
March mean. A within-month distribution modestly different from the monthly averages could put the
true median either side of it. 2024 is robust — the break-even median of 0.4644 is above four of
that season's five monthly means — but **2025 cannot be called from this data and is not called
here.** The trend 4,450 → 2,756 → 3,101 kg is not a trend toward safety, and the right question
for the watch is no longer whether the bubble is holding but whether the margin is closing.

### Why the authoritative number is not in the corpus

It is not withheld; it is not published anywhere reachable.

Parameter **51451 does not appear in `OH0025135`'s effluent chart at all** — the individual
permit's DMR carries the concentration and flow inputs but not the calculated load. Pulling the
general permit itself (`p_id=OHP000001`) returns a chart with **zero** DMR rows. The number lives
in Ohio EPA's own eDMR system under the general-permit coverage, which ECHO does not mirror.

The two documents that would settle it are both out of reach for different reasons. The **Season
Report** (Part IV.D, due each September 1) is an electronic submission through the Ohio EPA
eBusiness Center, not a published document — a records request. And Ohio EPA's **General Permit
Annual Report**, which the fact sheet commits the agency to release each November 1 with a
determination of compliance against the Cumulative Limit and a list of any facilities in
violation, **could not be found for either 2024 or 2025**: eight candidate filenames in the portal
folder that serves `OHP000001.pdf` all returned 404, and targeted searches surface nothing. Worth
noting precisely — Attachment 3 lists that row's Permit Condition as `--`. It is an administrative
commitment in a fact sheet, not an enforceable permit term. Recorded as an access gap, not as a
negative.

The permit's own citation for the Season Report form is also dead: the technical-assistance URL
printed in Part IV.D returns HTTP 404, as does its hyphenated variant.

## The calendar the watch runs on

The general permit's fact sheet prints its own annual schedule, and it carries a milestone the
issue body did not have — **August 20**, two and a half weeks after this ingest.

| Date | Item | Who acts |
|---|---|---|
| March 1 – July 31 | Critical season | Permittee collects TP and flow data |
| **August 20** | Individual Seasonal Load | Permittee submits the load (kg) to the July eDMR |
| **September 1** | Season Report | Permittee submits it to Ohio EPA |
| **November 1** | GP Annual Report | Ohio EPA releases the cumulative determination |
| **November 1** | Termination notices | Ohio EPA sends them, if any |

The August 20 date is the cheapest check on this page: re-pull the effluent chart after it and
look for parameter 51451. If it appears, it supersedes every derived figure above — and it may
carry prior seasons, which would close the 2025 question outright. A **termination** would matter
more than any single season's number, because it would move the 3,200 kg limit into the individual
permit as an effluent limit and end the bubble for this plant.

## The ECHO mismatch, reconciled — and it splits

The issue recorded two unresolved schedule violations on the federal record and one hypothesis for
both: `[inference: federal ICIS not reflecting the state modification]`. The hypothesis is right
about one of them and wrong about the other, and the difference is the whole point of running the
check.

The permit in force carries **exactly two** milestones (2PD00008\*VD, p. 14):

| Section | Event | Code | Due |
|---|---|---|---|
| Municipal Pretreatment Schedule | Eff Limits For Pollutants | 52599 | 2026-05-01 |
| Municipal CSO Schedule | Submit Study Plan | 34099 | 2026-11-01 |

**The "Study Plan" violation dated 2025-12-01 is a stale federal record.** The permit carries no
milestone due that date; it carries one Study Plan event, 34099, due 2026-11-01. The `*VD`
modification's entire substance was to move that event's date, and a modification that pushes a
deadline forward implies an earlier one it replaced. So ICIS is still carrying the pre-modification
instance of 34099, superseded by a state action effective 2026-02-01. This stays `[inference]`
only because the `*UD` permit as issued is not in the corpus — the DAM's document slot serves the
`*VD` package instead — so the original due date is inferred from ICIS rather than read from the
instrument. Obtaining those bytes (lead `UD-ISSUANCE-BYTES`) would settle it in one step. **Do not
write that Findlay missed a CSO study-plan deadline.** On the state record that deadline is
2026-11-01 and has not arrived.

**The second violation is live.** ICIS records event 52599 — due 2026-05-01 under the permit as it
stands today — as "Schedule Event unachieved and not reported" as of the 2026-07-31 extract, three
months past due. The modification did not touch 52599; its two revisions are confined to event
34099 and the LTCP addendum language. So no state action explains this one.

What 52599 requires is the phosphorus milestone: a technical justification for revising or
retaining local industrial-user limits, including specifically whether local limits for total
phosphorus "will facilitate substantial progress toward achieving a monthly average effluent
concentration target of **0.5 mg/L**" — half the permit's own limit — or evidence that they would
not. The eight significant industrial users discharging 0.428 MGD (renewal fact sheet, p. 8) are
the load that reaches. It is
the one scheduled event in this permit that could change the plant's phosphorus trajectory, and it
is the one the federal record says has not been reported.

Whether the City submitted it and Ohio EPA has not entered it, or whether it was not submitted,
stays `[open]` — a state-to-federal lag is a real and common cause. What is established is that
the modification does not explain it.

### The rest of the federal picture, and one thing it will not explain

Current SNC: **No**, as of 2026-03-31. Five quarters in non-compliance, zero in significant
non-compliance, **zero formal enforcement actions, zero penalties**. Four inspections since
August 2021, the most recent a state pretreatment audit on 2024-08-28.

Exactly **one** numeric effluent violation appears in the whole reported record — 6,014 DMR rows,
one flagged: ammonia at outfall 001 for the period ending 2023-10-31, 1.41 mg/L against a 1.4
mg/L weekly maximum. A one percent exceedance, and the only one.

That leaves three quarters ECHO flags as **Reportable Noncompliance** that none of its own detail
blocks explains — Q1 2025, Q2 2025 and Q1 2026. The 2023 ammonia row accounts for Q4 2023; the two
schedule violations begin 2025-12-01 and 2026-05-01 and cannot reach the 2025 quarters. Every
other compliance block for this permit is empty. The driver is simply not in the Detailed Facility
Report, and no guess is recorded — candidate categories exist (DMR non-receipt, pretreatment
reporting, biosolids reporting, and the facility carries both report flags) but nothing in the
retrieved record selects among them. Lead `ICIS-RNC-QUARTERS-UNEXPLAINED`.

## The CSO clock, with a measurement under it

**2026-11-01** is 91 days out at ingest. Due then: the LTCP Addendum — a list of projects and an
implementation schedule that will meet the plan's goals — together with the milestone summary
report for event 34099. Both were moved there by the modification issued 2025-11-07.

Until now the corpus held the structure of Findlay's overflow system but no measurement of it.
The DMRs supply one:

| | 2023 | 2024 | 2025 | 2026 (Jan–Jun) |
|---|---|---|---|---|
| CSO events | 4 | 8 | 12 | **11** |
| CSO volume, MG | 1.27 | 5.87 | 6.46 | **7.50** |
| SSO events, located stations | 6 | 14 | 7 | 7 |
| SSO occurrences, station 300 | 1 | 3 | 8 | 1 |

The two sanitary rows are **separate counting bases and must not be added**. Station 300 is not a
located outfall: the permit makes it a system-wide reporting point counting overflows anywhere on
the collection system — "each location… where there is an overflow, spill, release, or diversion of
wastewater on a given day that enters waters of the state is counted as one occurrence" — and only
those reaching waters of the state. An overflow may appear in one row, both, or neither, so there
is no defined "sanitary total" and this record does not publish one.

Combined-sewer activity is rising, and through the first six months of 2026 the system has already
released **more volume than in any complete year on the record**. Four of the ten authorized CSOs
reported nothing at all across the whole 42 months. Outfall 004, East of Old WWTP, has gone
0 → 1 → 2 → 3 and is the steepest per-outfall trend in the set.

On the sanitary side the picture is narrower than it first looks. The located stations reported
more occurrences than the combined outfalls in **2023 (6 against 4) and 2024 (14 against 8)**, and
**fewer in 2025 (7 against 12) and through June 2026 (7 against 11)** — so sanitary activity does
not outrun combined activity across the record; it did in the first two years and does not in the
last two. What is concentrated is the source: 011 (First and Bank Street) and 018 (East End of
Tioga Avenue) account for nearly all of it, and six of the ten located stations reported none at
all. Station 300 is the one line that rises monotonically — 1 → 3 → 8 — and on its own basis that
is the sharpest trend in the record. No volume is reported for any sanitary station.

Two things this does **not** establish, both recorded in the artifact so nobody does the arithmetic
later. It does not say the four-overflows-per-typical-year level of control is or is not attained:
"typical year" is a defined design-rainfall year in the LTCP, the determination is Ohio EPA's, and
these are calendar-year occurrence counts. And it attributes the trend to nothing — wet-weather
activity tracks rainfall, and no precipitation normalization has been done, though the permit does
require rainfall reporting, which is the input one would need.

Whether any reported sanitary overflow was treated as an unauthorized discharge is `[open]`. A CSO
is an authorized wet-weather discharge under Part II.D; an SSO is not authorized by this permit.
The DMR records occurrences, not characterizations, and ECHO carries no enforcement action here.
The 2018 evaluation's finding that twelve outfalls no longer had combined sewer upstream and were
in substance sanitary overflows makes the classification itself the live question — and that
report is not in the corpus.

## The mercury variance: quiet, and not close

The variance sets 3.3 ng/L monthly average and 1,700 ng/L daily maximum against a water-quality
limit of 1.3 ng/L, with a standing condition that the **annual average stay at or below 12 ng/L** —
exceeding it starts a six-month clock to an individual-variance application, failing which the
1.3 ng/L limit applies.

Nothing is near it. The worst calendar year on the reported record averages **1.115 ng/L**, about
a factor of eleven below the trigger, and the highest single month ever reported — 1.49 ng/L in
September 2024 — is under half the monthly limit. The fact sheet's 2.2 ng/L for 2018–2023 has
fallen further since. The averaging here is over reported monthly averages rather than the
permit's own annual computation, and mercury is sampled in only four to eleven months a year, but
the conclusion is insensitive to method at an order of magnitude of headroom. This is an annual
check, not a quarterly one.

One incidental find worth keeping. The DMR record shows the mercury monthly limit changing from
3.9 to 3.3 ng/L at the 2024-11-30 monitoring period — **independent corroboration, from the
federal effluent record, of the `*UD` renewal's 2024-11-01 effective date**, which until now rested
only on the January 2026 statewide variance list because the `*UD` permit itself is not in the
corpus.

## Whole effluent toxicity, for anyone citing the dilution screen

The prior 1.0 TUa / 1.0 TUc limits were removed at the 2024 renewal: no toxicity detected,
reasonable potential not demonstrated, all four endpoints now monitoring only. No toxicity row in
the DMR record carries a violation.

Reasonable potential is the standard the rule prescribes and this is a normal outcome. It belongs
on the watch anyway, because the acute dilution ratio at this outfall is **1.0** — at design flow
the Blanchard below River Mile 56.42 *is* the effluent (issue 1458). Toxicity limits were removed
on a reach with no dilution. The two facts sit oddly together and any prose citing the dilution
screen should carry both, because a reader will ask.

## The drinking-water check, decomposed

Acceptance criterion 3 asked for the SDWA primary check "even if a clean negative." It is not
quite a clean negative, and the headline would mislead anyone who quoted it raw: ECHO shows
Findlay City PWS in **"Violation Identified" status for twelve consecutive quarters**.

First, the identification, because getting it wrong would attribute a dead record to the operating
utility. Thirteen Hancock County systems carry "Findlay" in the name. **`OH3200111` FINDLAY CITY
PWS** is the live one — active, community, surface water, local government, population served
**54,040**. `OH3200114` "FINDLAY WATER DEPARTMENT" has been **inactive since 1988-08-01** and its
enforcement history ends in the 1980s. Do not cite it. That the source is surface water is
consistent with the rest of the file: Findlay draws from the upground reservoirs it impounds off
the Blanchard — the same impoundment that regulates gage 04189000 downstream and disqualified it
as a low-flow denominator.

Now the decomposition. Those twelve quarters are **one** violation carried forward: a **Consumer
Confidence Rule** item, category "Other", open and Unaddressed since **2019-01-03**, which drew a
single informal State Violation/Reminder Notice the day it was recorded and nothing since. The CCR
governs the annual water-quality report a system delivers to its customers. It is a *reporting*
rule. There is **no maximum-contaminant-level violation, no treatment-technique violation, and no
monitoring violation of any other rule** anywhere in the record. Lead at the 90th percentile runs
0.0021–0.0025 mg/L against a 0.015 mg/L action level across the five periods carrying a published
result — a factor of six to seven below. ECHO lists eight periods and prints "0 mg/L" for three of
them; a 90th percentile of exactly zero is not a plausible analytical result, so those are read as
no published result rather than a measured zero — the same absence rule that applies to copper,
which has no published result at all. Reading them either way leaves the conclusion untouched: a
zero cannot raise a percentile.

Whether the 2019 item is a continuing failure or a record the state never closed stays `[open]`.
Seven and a half years unaddressed with one same-day informal notice and no escalation looks more
like an unclosed record than a live enforcement posture — but that is a pattern argument, not
evidence. **Do not write that Findlay's drinking water is in violation, or that the city has not
reported water quality to its customers since 2019.** Neither follows.

One thing in the survey history is worth a second look. The complete sanitary survey of
**2021-06-15** found no deficiencies *and no recommendations* in any category. The one on
**2024-06-04** raised recommendations in five — source, treatment, finished water storage, pumps
and distribution — with deficiencies in none. Whether that is aging plant, a different surveyor or
a routine shift in emphasis is not determinable from the coded summary, and the survey report
itself is held by the district office. It is worth naming because the supply-side financing thread
is already live: the corpus carries a 2025-04-18 report of sewer repair bills adding up, and
Findlay is absent from the WPCLF PY2025 and PY2026 project lists. Lead
`SDWA-SANITARY-SURVEY-2024`.

## What this ingest closes, and what it leaves open

Closed, or as closed as the public record allows:

- **`TP-SEASON-REPORTS`, partially.** The 2024 season is under the allocation on a robust
  reconstruction; 2023 is over on an equally robust one. The reported figure remains a
  records-request target, and 2025 needs it.
- **The ECHO-vs-state schedule mismatch.** Two violations, one stale and one live, with the live
  one identified down to the event code and its substance.
- **The SDWA primary check.** Run, decomposed, and recorded — including which of the two city
  PWSIDs is the real one.
- **The mercury trigger.** Measured against the 12 ng/L condition with an order of magnitude of
  headroom.

Still open, with dates attached:

| Thread | Next check | Lead |
|---|---|---|
| The 2026 seasonal load hits the July eDMR | 2026-08-20 | `TP-SEASON-REPORTS` |
| The 2026 Season Report is filed | 2026-09-01 | `TP-SEASON-REPORTS` |
| The LTCP Addendum lands, or moves again | 2026-11-01 | `CSO-LTCP-2026-11-01` |
| Ohio EPA's GP Annual Report — if one appears at all | 2026-11-01 | `GP-ANNUAL-REPORT-NOT-PUBLISHED` |
| Termination notices under Part I, C.4.b | 2026-11-01 | `TP-SEASON-REPORTS` |
| Was the 52599 local-limits justification submitted? | on demand | `PRETREATMENT-52599-SUBMITTAL` |
| What drives the three RNC quarters? | on demand | `ICIS-RNC-QUARTERS-UNEXPLAINED` |
| The `*UD` permit as issued | on demand | `UD-ISSUANCE-BYTES` |
| The 2018 CSO evaluation report | on demand | `CSO-2018-EVALUATION-BYTES` |
| The 2024 sanitary survey report | on demand | `SDWA-SANITARY-SURVEY-2024` |
| The 2019 CCR violation — live or unclosed? | annual | `SDWA-CCR-2019-UNADDRESSED` |

## Committed artifacts

| Record | What it holds |
|---|---|
| [`watch/tp-seasonal-load.watch.yaml`](watch/tp-seasonal-load.watch.yaml) | The load equation, the four derived seasons with their break-even medians, the seasonal operating shift, and the GP calendar |
| [`watch/icis-compliance-reconciliation.watch.yaml`](watch/icis-compliance-reconciliation.watch.yaml) | The two schedule violations reconciled against the permit in force, the compliance posture, the mercury trigger, WET |
| [`watch/cso-sso-overflow-record.watch.yaml`](watch/cso-sso-overflow-record.watch.yaml) | Overflow events and volumes by outfall, 2023 to June 2026, with the double-counting trap recorded |
| [`watch/sdwa-findlay-city-pws.watch.yaml`](watch/sdwa-findlay-city-pws.watch.yaml) | The drinking-water check — system identification, the CCR item, lead results, sanitary surveys |

All four are corpus, not `RecordItem`s: they are readings of the federal compliance record, not
agency actions, and publishing an ECHO API read into the `permits-epa` group would misrepresent
what it is. The site's `record` domain is already `live`, so nothing here moves readiness and
nothing here bumps the contract — the same call issues 1463 and 1464 made.

Sources are live public services rather than documents: EPA ECHO `dfr_rest_services.get_dfr` and
`eff_rest_services.get_effluent_chart` for `OH0025135`, and `sdw_rest_services` for `OH3200111`,
all pulled 2026-08-02 against an ICIS-NPDES extract of 2026-07-31 and an SDWIS extract of
2026-07-09. The effluent pulls run through this repository's own connector
(`watermark.hydrology.connectors.echo_dmr`), which caches every response and passes values through
verbatim, so every figure above is regenerable rather than transcribed.
