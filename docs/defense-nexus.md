# The defense nexus — what the corridor shows, and what it can't

> A `#233` extension narrative, and the sharpest open question in the file. Like
> [end-use-and-workloads.md](end-use-and-workloads.md) it is hand-assembled analysis
> over cited records, and it ends at the question rather than closing it. Every
> statement carries its register: `[verified]` (read from a cited record),
> `[inference]` (a labeled reading of it), `[open]` (a question the record does not
> answer), `[reference]` (an outside-published spec). This page is built to a single
> rule from the project's method: **geographic adjacency, a capability, and a named
> market segment are an _inferred_ connection — legitimate to raise as a question,
> never to assert as a finding.** The reader is owed the discipline more here than
> anywhere else, because the subject is the one most easily turned into innuendo.

The plainest way to say what this report is: there is a defense installation near
the campus, the developer has the credentials to do defense work, and an industry
witness told a state committee that hosting the government is a normal line of
business. Each of those is true. None of them, alone or together, shows that the
Lima campus does defense work. Holding those two sentences at once — the facts are
real, the conclusion is not earned — is the whole exercise.

It is worth saying who raised this first. The person who put the defense question to
Ohio's data-center committee is the relator behind this record, a cloud engineer who
builds for regulated industries — and he framed it, on the record, as a question he
could not answer: _"I can speculate there. I think you probably understand that most
of that is classified."_ He called the broader pattern _"likely speculative."_
`[verified: relator testimony, 2026-06-04]` If the witness who introduced the thread
labels it speculation, a page assembled from the public record has no business doing
less.

———

## the geography is real

About **five and a half miles south** of the campus sits the **Joint Systems
Manufacturing Center** — the Lima Army Tank Plant — operated by **General Dynamics
Land Systems**. It is not a rumor; it is on the parcel map. The corpus carries it as
five contiguous parcels totaling **~384 acres**, every one of them owned, in the
auditor's own field, by **"UNITED STATES."**
`[verified: data/site/bundle/feeds/geo/jsmc.geojson]` Measured against the campus
parcels, the nearest edges are **~5.5 miles apart** (centers ~6.6 mi)
`[verified: computed from geo/campus + geo/jsmc]` — the two share a city and a
corridor study area, not adjoining land. GDLS's operation of the plant is a matter
of public record `[reference]`.

So the corridor contains, within a few miles of each other, the largest data-center
build in the county's history and one of the country's two heavy-armor manufacturing
plants. That is a striking coincidence of geography. It is also _only_ that — two
facts that share a map and five and a half miles of city, which is precisely the kind
of connection the method says to raise as a question and stop.

———

## the capability is real

The developer is Google `[verified, #234]`, and Google can, as a technical and
contractual matter, do high-authorization government work. The relator testified —
with sources in his written submission — that **Google has achieved IL-6**, the DoD
impact level for data classified up to SECRET `[verified: relator testimony;
reference: DoD CC SRG]`. Google's air-gapped Distributed Cloud appliance holds DoD
IL5 `[reference]`. The federal market is not hypothetical for the industry, either:
before the same committee, **AWS named the Department of War and the CIA** among
"11,000 government agencies of all classification levels" `[verified: hearing
record, 2026-06-04 morning panel]`, and the relator tied the timing to **Executive
Order 14265** (signed 2025-04-09), which pressed defense primes to modernize cloud
procurement `[verified]`.

The capability has an economic edge the rest of the record sharpens. Government cloud
runs **20–30% above commercial** rates, and — the relator's point — an authorized
facility is closed to the community that subsidized it: _"I cannot use that data
center if it is a FedRAMP-compliant facility."_ `[verified: relator testimony]` That
is why the question is not idle. _If_ the campus were a high-authorization enclave,
the public-benefit math the abatement was scored on would not hold — a sealed federal
supply chain seeds no local cluster (see [end-use-and-workloads.md](end-use-and-workloads.md)).
But that is an _if_, and the record does not resolve it.

———

## proximity is not connection

Set the three confirmed facts down together: a defense plant nearby, a developer with
the clearances, an industry that markets to the government. The temptation is to let
them lean on each other until they look like a finding. The method forbids it,
explicitly: name-proximity, temporal coincidence, and geographic adjacency are the
signatures of an _inferred_ connection, and an inferred connection is never a fact.

Nothing in the corpus ties the campus to the plant, to GDLS, or to a defense
workload. There is no contract, no filing, no dated communication naming both. The
proximity to the JSMC is geography; the IL-6 credential is a capability Google holds
everywhere it operates, not a fact about Lima; the AWS testimony is about AWS. Each
thread, followed honestly, ends without reaching the campus.

The committee record is consistent with that limit rather than against it. Google's
own witness testified to Ohio's data centers and **did not name Lima at all**
`[verified, #234]` — the silence is documented; what it means is `[inference]`, not a
finding.

———

## the wall of "no records"

There is one place the record could have spoken, and the answer it gave is its own
kind of fact. The public-records request asked the County for any communications
between it and **the DoD or its contractors — GDIT, GDLS** — concerning the facility
or the corridor. The County's response: **"No records."** It asserts that none exist
on its side. `[verified: bosc-prr-production-2026-06-05.response-index.yaml, item 2]`

A clean negative is a result, and it should be stated cleanly: on the County's
account, there is no documented defense channel. But "no records" is not quite a
no-link finding, because elsewhere in the same production the phrase did heavier
lifting than it should have — conflating _"we do not hold it"_ with _"it does not
exist"_ `[verified: same index]`. So the honest reading is narrow: the County holds
no such records, or produced none. That forecloses one avenue. It does not establish
that the connection is absent, and it does not establish that it is present. It
leaves the question exactly where it was — open, and now with one door confirmed shut.

———

## the money is a separate question

Everything above reads the nexus as _geography_ — how close the plant is, what the
developer is cleared for. There is a second reading the lens could not previously even
state: whether the defense base **distorts the local economy** the campus lands in.
It is worth running, because it comes back as a limit rather than a confirmation.

On the payroll record it does not. BLS QCEW 2024 annual averages for Allen County put
federal-government employment at **321 jobs** across **15 establishments**, averaging
**$83,773** a year against the county-wide **$58,790** — a real wage premium on a very
small base `[verified: data/reference/economics/baseline.yaml]`. The location quotient
is **0.33**: the county's share of federal employment is a third of the national one.
An enclave economy would show the opposite.

The reason is structural, and it is why the number is a limit rather than a finding.
The JSMC is government-owned and **contractor-operated** — the plant belongs to the
Army, the workforce belongs to General Dynamics Land Systems. Those jobs book as
private manufacturing, not federal employment, so the federal ownership row does not
count the arsenal at all `[inference]`. QCEW also excludes uniformed active-duty
entirely `[reference: the model's standing coverage caveat]`. The payroll series is
simply not the instrument that would measure this.

Two threads stay open, and they are the ones worth pulling. The **land** is off the
tax rolls: the five federally-held parcels carry **$14,688,900** of assessed market
value across **384.15 acres**, and the United States owes no local property tax on any
of it `[verified: data/reference/allen-gis/parcels.defense.yaml]`. And no **abatement,
PILOT, or public-benefit agreement** tied to the JSMC footprint has been searched for
or found `[open]` — unlike the campus's own CRA, which is on record. The prime's
federal dollars are real but are the wrong scale to attribute here: General Dynamics
Corp's **$301B** in all-time prime-award obligations (88% defense-agency) is a
_national_ total resolved by UEI, not a Lima figure `[verified: data/reference/usaspending/awards.yaml]`,
and the same graph overlay that surfaces it appears on every site in the network. It
is a cross-reference to follow, not a local finding.

## where this stops

What would actually close it is small and specific: the facility's **authorization
posture** — whether it carries any FedRAMP or DoD impact-level authorization — is a
single disclosable fact that would answer the end-use question and this one at once.
It is not in the record. The relator's sixth recommendation to the committee was that
it should be `[verified: relator testimony]`. Until it is disclosed, the question is
held open by two things at once: the classification that would keep a real defense
use quiet, and the "no records" wall that keeps even the absence of one unproven.

The public instrument surfaces have now been searched for it, and they come back
empty on every path `[verified: federal-authorization-instrument-search.md, #1480]`.
USASpending and SAM.gov hold no award or recipient for the campus's owner-of-record
shell (Bistrozzi LLC / Bistrozzi Addition LLC); the FedRAMP Marketplace lists Google
Cloud service-wide, at High, and names **no** Lima facility. That last point is the
one worth holding onto, because it is structural, not circumstantial: Google's
public-sector compliance runs on **Assured Workloads**, which by Google's own account
"does not rely on physical infrastructure distinct from Google's public cloud data
centers" `[reference: Google Cloud, FedRAMP High blog]`. A FedRAMP or DoD-IL
authorization in that model binds to the _service_, not to a building — so a
facility-scoped instrument for Lima **cannot exist by construction**, and its absence
proves nothing in either direction. The negative maps where the ceiling is; it does
not lower it. The nexus stays `[inference]` and the search declines to force a link —
the same discipline Urbana's analogous search held to `[reference: #1353]`.

That is an uncomfortable place to end, and it is the correct one. A defense nexus is
not a finding of this record. It is a question the record raises by what it contains —
a federal plant a few miles down the corridor, a developer cleared to SECRET, a procurement
order, an industry that hosts the CIA — and cannot answer by what it withholds. The
walk's discipline was built for exactly this thread: to let the reader see the
question clearly without being handed a conclusion the evidence has not earned. The
honest end is the open one.

———

## sources

- The JSMC parcels (owner "UNITED STATES", ~384 acres) — `data/site/bundle/feeds/geo/jsmc.geojson`
- Relator testimony, 2026-06-04 (the IL-6 statement, the "speculation" framing, the FedRAMP-access point) —
  `data/extracted/legal/select-committee-2026/hearings-audio/bosc-committee-testimony-2026-06-04.transcript.md`
- Relator written testimony (impact levels, EO 14265, the Ohio defense footprint, the six recommendations) —
  `data/extracted/legal/select-committee-2026/relator-testimony/bosc-written-testimony-2026-06-01.md`
- AWS / DoW + CIA + "all classification levels"; hearing cross-read —
  `data/extracted/legal/select-committee-2026/select-committee-2026.hearing-index.yaml`
- The "no records" defense-channel response — `data/extracted/legal/prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml` (item 2)
- The #1480 documented negative search for a facility-naming federal-authorization instrument (FedRAMP / DoD IL / GSA-DoD award / cloud-region) — `data/extracted/lima/federal-authorization-instrument-search.md`
- The county employment / wage baseline behind the capture reading (QCEW 2024, federal ownership row) — `data/reference/economics/baseline.yaml`
- The federally-held parcels' assessed value + acreage, and the typed scan registers — `data/reference/allen-gis/parcels.defense.yaml`
- The prime's federal obligations (national totals, resolved by verified UEI) — `data/reference/usaspending/awards.yaml`
- The end-use frame this sits inside — [end-use-and-workloads.md](end-use-and-workloads.md), [DOSSIER.md](DOSSIER.md)
