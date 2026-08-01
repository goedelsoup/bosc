# Findlay governance watch — the rules arrive after the load

**Issue 1463** · sub-issue of **1265** (`readiness(findlay)`) · ingested 2026-07-31 ·
strengthens `record` + `story`

Hancock County has three governments with something to say about where a data center may be
built, and as of this ingest not one of them has an adopted rule that reaches the 150 MW
already contracted inside its borders.

The county's instrument bars large wind and solar and is silent on load. The City of Findlay's
moratorium reaches data centers and stops at the corporation line. Allen Township — where One
Power's Findlay Megawatt Hub and MARA Holdings' take-or-pay actually sit — had no zoning at all
until **2026-05-11**, and the resolution that took effect that day does not contain the phrase
"data center" once in seventy-seven pages.

Eleven weeks later the township's zoning commission moved language that would conditionally
permit data centers in its two industrial districts, capped at **10 MW**.

## What is held, and how good it is

The evidence here is lopsided in a way worth naming up front.

The **township** half is nearly all `[verified]`. Allen Township publishes to a `.gov` site:
its adopted zoning book with a text layer, its district map, its zoning commission's minutes
back to 2024, the two July-2026 amendment resolutions with their handwritten roll calls, and a
pending rezoning application with its exhibits. The **court** half is `[verified]` too — the
Third District's slip opinion in *One Energy Ents., Inc. v. Allen Twp. Bd. of Trustees*,
2026-Ohio-405. The **election** half is `[verified]` from the Board of Elections' own certified
canvass.

The **city** half is almost entirely `[reference]`. `findlayohio.gov` returns HTTP 403 to any
automated request; American Legal's code library does the same; the `findlay.legistar.com`
hostname resolves to an unprovisioned tenant that answers *"LegistarConnectionString setting is
not set up in InSite for client: findlay."* So Ordinance 2026-42 — the instrument the issue is
named for — is held only as two newspapers describe it, and one of those hedges its own roll
call mid-sentence (*"DeArment (or DeLong per some records)"*). That is an **access failure, not
a denial**, and the response is the ordinary one: a records request, drafted at
[`governance/records-requests/2026-07-31-findlay-clerk-of-council.md`](governance/records-requests/2026-07-31-findlay-clerk-of-council.md)
and **not sent** — sending is the requester's own act.

## The township: zoned by wind, amended for compute

The fight that made Allen Township zoned had nothing to do with data centers. The appellate
court's own background is explicit: in late 2023 One Energy "was making plans to construct
additional wind turbines in Allen Township to, inter alia, provide power to the Whirlpool
manufacturing facility." Residents asked about zoning. The trustees opposed renaming Township
Road 215 to "Electric Avenue" without meeting in public, stayed after an adjourned meeting to
talk about who should sit on a zoning commission, and got sued twice for it.

They lost, and so did One Energy. 2026-Ohio-405 affirms both violations and the prospective
injunction, and it also affirms the trial court's refusal to unwind the zoning commission — the
December 2023 resolutions had been rescinded, which "breaks any causal link," and the selection
criteria "were not unique": *"This Court declines to enjoin the use of common sense."*

That opinion also, incidentally, corroborates a correction this repo already made on the grid
side (issue 1464): the Wind-for-Industry turbines serve an industrial host's meter. Nothing
places generation at the Megawatt Hub, and now a court's findings say so too.

The resolution the trustees adopted on **2024-09-09** then sat for twenty months. A first
referendum passed in May 2025 and was undone over abbreviated ballot language — the township's
own minutes record that its "zoning status was revoked by Judge Jonathon Starn." The second
referendum, on **2026-05-05**, carried:

| | votes | share |
|---|---|---|
| **For the zoning resolution** | **503** | 69.48% |
| Against | 221 | 30.52% |
| | 724 of 732 ballots cast, 1,761 registered (41.57%) | |

Certified 2026-05-11 — the same date Article XXIV of the zoning book gives as its effective
date. The instrument and the canvass agree, which is what makes the date safe to assert. Note
the correction: the widely reported unofficial figure was **502**–221.

### What the electorate actually approved

An enumerated-use scheme — *"no building or land shall be used and no building shall be erected
except for one or more of the following specified uses"* — across nine districts, with no
mention of data centers anywhere in it. Section 1518's prohibited-in-all-districts list is adult
entertainment, commercial marijuana and private landfills. Non-accessory solar and non-accessory
energy storage are conditional uses in I-2 only, and the storage rule is tethered to wind and
solar facilities.

Four weeks before the vote, on **2026-04-07**, the commission chairman asked the township's own
counsel whether the pending resolution would permit a data center. The minutes record the
answer in one sentence: **"Cindy stated that a data center would not be permitted."**

Three weeks after it took effect, the same counsel recommended drafting data-center and BESS
language.

## The amendment: a 10 MW cap on a 150 MW site

On **2026-07-28** the zoning commission adopted Resolution **24-04-124M** 5-0, proposing a new
Section 1521. The full read is in
[`governance/allen-twp-data-center-amendment-2026.zoning.yaml`](governance/allen-twp-data-center-amendment-2026.zoning.yaml).
The provisions that matter:

- **Conditional use in I-1 and I-2 only**, approved by the Board of Zoning Appeals.
- **Maximum Electrical Capacity: 10 MW Total Facility Load at any single site**, measured
  against interconnection agreements, engineering plans or nameplate capacity.
- **Anti-aggregation:** phases count as one site if on contiguous parcels *or* "Sharing
  electrical infrastructure, substations, or utility interconnections," and "The combined load
  of all phases shall not exceed the 10 MW limit."
- **Water:** no groundwater wells at all; municipal or approved public-utility supply only, with
  written capacity verification; **100,000 GPD** ceiling.
- **Cooling:** "All data centers shall be air cooled (dry cooling)," with evaporative,
  once-through *and* closed-loop liquid systems all expressly prohibited.
- Separation of one mile from another data center, 1,250 ft from residential use, 60% lot
  coverage, 40 dBA at the property line, generators tested weekdays 8–6 only.

The disclosed facility at this site is 150 MW contracted with 30 MW energized. The proposal is
an order of magnitude below the contract and three times below what is already running — and
its aggregation rule is written against precisely the architecture of a shared megawatt hub.

**This is not a finding that the amendment would close the Hub, and it must not be written that
way.** Three things are unresolved and none can be assumed: whether a bitcoin-mining operation
falls inside a definition keyed to "storing, processing, or distributing electronic data" (AEP's
Schedule DCT names cryptocurrency mining outright; this template, borrowed from Washington
Township, does not); what Section 1502 preserves for a use established during the twenty months
the township was unzoned; and whether the amendment is adopted at all. Under R.C. 519.12 it must
clear a commission hearing, a trustee hearing, and a possible referendum. As of this writing it
has cleared none.

Three drafting observations are recorded as `[inference]` in the YAML and are worth a hearing
comment rather than a headline: the permitted "dry cooling" and the prohibited "closed-loop
liquid" describe overlapping equipment; Section 1521 assigns approval to the Board of Zoning
Appeals, which does not hold that power until the *other* hearing that same evening moves it
there; and the anti-circumvention subsection assigns duties to a "Zoning Administrator," an
office the adopted book does not have.

## What else is on the calendar

On **2026-08-05**, two weeks before the data-center hearing, the commission hears **Interstate
Capital, LLC**'s application to rezone ~135.3 acres at SR 613 and TR 142 from Agriculture to
**I-1 Light Industrial** — one of the two districts Section 1521 would open. The application
states its proposed use as **"Warehousing / Manufacturing"** and its exhibit claims a $140
million investment.

Nothing in the corpus connects this applicant to a data center, and
[`governance/allen-twp-rezoning-interstate-capital-2026.yaml`](governance/allen-twp-rezoning-interstate-capital-2026.yaml)
says so plainly. It is recorded because a governance watch records what is filed. The one
detail worth holding onto is that the definition moved three weeks later contains an express
anti-relabeling clause — "Data centers shall not be considered warehouses, storage facilities,
or distribution centers for zoning purposes" — which came from the borrowed template and is
boilerplate in current data-center zoning. If that boundary is ever tested here, the dates
should already be in the record rather than reconstructed afterward.

## The county: a generation control, not a siting control

Hancock County adopted an SB 52 restricted area in 2022 covering the unincorporated county
except Biglick Township. What this repo actually holds is the **meeting-setting** Resolution
**167-22** of 2022-03-15 — Bateson moving, Pepple seconding, roll call 2-1 with Bechtol dissenting
— plus the published notice and the **proposed** map. The resolution adopted on 2022-04-19, its
number, its roll call and its final map are `[open]`: the county's online agenda archive begins
in 2024.

The scope point is the one that matters and it is `[verified]` from the notice's own title:
R.C. 303.57 restricted areas prohibit "ECONOMICALLY SIGNIFICANT WIND FARMS, LARGE WIND FARMS,
AND LARGE SOLAR FACILITIES." They do not reach data centers, load of any kind, or storage. The
county instrument that looks like a siting control restricts *supply* and leaves *demand*
untouched — which is the same asymmetry the grid record found in 2024, when a fresh 138 kV
station went up in Cass Township for a grandfathered solar interconnection and no load
instrument existed anywhere.

## Open, and what would close it

| Gap | Blocked by | Closes with |
|---|---|---|
| Ordinance 2026-42 certified text + the banned-use definition | `findlayohio.gov` 403, AmLegal 403, no Legistar tenant | the drafted R.C. 149.43 request, items 1–3 |
| Council journal 03-17 / 04-07 / 04-22 and the recorded roll call | same | same |
| Pre-annexation agreements, Allen Twp parcels | not published | request items 5–6 |
| SB 52 adopted resolution number, roll call, final map | county archive starts 2024 | a separate request to the commissioners' clerk |
| The 2025 ballot-language case number and final entry | Clerk of Courts eServices times out | docket pull or clerk request |
| May-2025 certified canvass | BOE publishes from Nov 2025 forward | BOE request |
| Which district covers the Hub parcels | the map is a PDF with no parcel labels | auditor parcel layer joined to district geometry — hand-off to places (1462) |

Every one of these is tracked as a lead in [`data/site/findlay/leads.yaml`](../../site/findlay/leads.yaml).

## Files

| Path | What it is |
|---|---|
| `governance/governance-timeline.yaml` | the four-jurisdiction chronology, every entry tagged and sourced |
| `governance/litigation-one-energy-v-allen-twp.yaml` | structured read of 2026-Ohio-405 (a `case:` record → `litigation`) |
| `governance/allen-twp-zoning-adoption-and-referendum.yaml` | the adopted resolution's chain + the certified canvass |
| `governance/allen-twp-data-center-amendment-2026.zoning.yaml` | proposed §1521 and §1520, verbatim, plus the analysis |
| `governance/allen-twp-rezoning-interstate-capital-2026.yaml` | the pending I-1 application |
| `governance/hancock-sb52-restricted-area.gap.yaml` | what is held of the county regime, and the hole at its centre |
| `governance/findlay-ordinance-2026-42.gap.yaml` | the city moratorium as `[reference]`, and why |
| `governance/records-requests/2026-07-31-findlay-clerk-of-council.md` | the drafted, unsent R.C. 149.43 request |

Source bytes and their custody manifests are under
[`data/documents/findlay/governance/`](../../documents/findlay/governance/) and
[`data/documents/legal/one-energy-v-allen-twp/`](../../documents/legal/one-energy-v-allen-twp/).
