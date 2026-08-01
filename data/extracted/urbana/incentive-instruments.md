# Urbana Technology Hub — the incentive instruments

**Issue**: #1354 · sub-issue of #1263 · strengthens `record` + `story`. **As of**: 2026-08-01.
**Sources**: [`data/documents/urbana/council/`](../../documents/urbana/council/) — seven City of
Urbana instruments. **Structured record**:
[`incentive-instruments.yaml`](incentive-instruments.yaml).

> **The City of Urbana's legislative record is reachable now.** At the 2026-06-28 corpus freeze it
> was recorded as unavailable to this build environment ([`datacenter-facility.md`](datacenter-facility.md)
> §7). It is not: `www.urbanaohio.com` serves every council packet and approved minute as a static
> PDF. That reverses the #1353 posture for this thread — the incentive instruments did not need a
> records request, only a look.

## What the City actually signed

There is **no tax-abatement agreement**. That is the finding, and it inverts what the corpus and
the issue text both assumed.

The City did two separate things, fourteen months apart:

1. **December 2024 — it signed a contract with the developer.** Ordinance **4612-24** authorised a
   **Pre-Annexation Agreement** with **`Urbana0624C, LLC`**, passed **5-0** on 2024-12-17. This is
   the City's *only* contract with the developer, and it was not in corpus at all.
2. **November 2025 — it designated an area.** Ordinance **4631-25** established **Community
   Reinvestment Area #2**, passed **5-2** on 2025-11-04. A CRA is a geographic envelope with
   ceilings. It grants nothing to anybody.

Under R.C. 3735.67/.671 an actual abatement requires a *separate* written **CRA Agreement**, and
Ord. 4631-25 §Five makes **Council approval a precondition to executing one**. No such agreement
has ever come before Council — through the 2026-08-04 agenda, the current one. So the abatement
percentage and term this issue asked for **do not exist as an instrument**; only the ceilings do.

The City says so itself. Its public notice — "CITY OF URBANA'S RESPONSE TO ALLEGATIONS OF LACK OF
TRANSPARENCY TO COUNCIL" — states in its own overview: *"Other than the Pre-Annexation Agreement,
there are no contracts between the developer and the City,"* *"There are no Community Reinvestment
Agreements with the developer,"* *"No 'deals' have been made,"* and *"No Non-Disclosure Agreements
have been signed."*

> ⚠️ **Conflation guard.** Secondary summaries assert that in November 2025 Council "approved a
> Community Reinvestment Area agreement it negotiated with Thor, creating a tax abatement." The
> primary record refutes this. On the night of the vote, Director of Law **Mark Feinstein** told
> Council that *"the legislation is to create an area, not an agreement"* and that *"there are no
> current agreements on the table."* Never cite a Nov-2025 Urbana CRA *agreement*, and never quote
> an abatement percentage for this project.

## 1. The pre-annexation agreement — the instrument nobody had

`Urbana0624C, LLC` does not appear anywhere in the corpus before this ingest. It is the counterparty
the City contracted with in 2024, a year before the first Thor deed recorded.

Two things pin it to the project graph:

- **The City names it.** Its public notice writes: *"a pre-annexation agreement with Urbana0624C,
  LLC **(which is Highland)**."* `[verified]` as the City's own identification.
- **The address matches.** Exhibit A gives the Company's mailing address as **720 E. Broad Street,
  Columbus, OH 43215** — the same street address the OEPA §401 WQC preliminary-JD cover (eDoc
  3938251) carries for *"Highland Realty Development LLC / Urbana Owner I LLC, 720 E Broad St Suite
  200."* [`land-assembly.yaml`](land-assembly.yaml) had flagged that address `[open]`. Two
  independent primary instruments — a City ordinance exhibit and an OEPA permit filing — now put
  the development vehicle there.

A shared address is not corporate identity, so common control remains `[inference]` pending the
Ohio SoS pull (still HTTP 403, the same block recorded in #1328). But it is a far stronger
inference than the coincidence the corpus previously carried.

### Terms that matter

| Term | Substance |
|---|---|
| Property | ~**191.589 ac** at "0 US Route 68 South"; Company **in contract to purchase**, not owner |
| Petition | **Expedited Type II**, R.C. 709.023; agent **Andrew Wecker**, Wright and Moore Law Company, LPA |
| Petitioners | Board of County Commissioners; **Organ Farms LLC**; Madison-Champaign ESC; Urbana Health Facilities LLC (+28.397 ac = **219.986 ac** total) |
| Company duty | File within 30 days; pay county fees; **cause the landowners not to withdraw** from the petition during annexation "or any subsequent administrative or legal action" |
| City duty | Enact the service and zoning-buffer resolutions **within 20 days**; provide water and sewer, "projected to come online at some point in the future" |
| Zoning sought | **PUD (Commercial Industrial)** — the property was U-1 Rural in the township |

The 191.589 + 28.397 = 219.986 arithmetic closes exactly against Ord. 4619-25's annexation acreage,
and the City met its 20-day covenant: the petition was filed 2024-12-03 and Ordinances **4613-24**
(statement of services) and **4614-24** (land use and zoning buffers) both passed **5-0** on
2024-12-17.

### The detachment clause

Section 3(c) is the term with teeth:

> …if the Property is annexed but then **not rezoned in a manner that is satisfactory to
> Developer**, or if Developer exhausts its appeals, or the rezoning is subject to referendum
> and/or rejected by the voters, and/or if water and sewer capacity is not made available to
> satisfy the Developer's schedule, **the City of Urbana agrees to execute a petition to detach the
> entire Property from its jurisdiction upon the request of Developer or Company.**

In December 2024 the City pre-committed to **de-annex the whole property on the developer's
demand** if the zoning did not come out to the developer's satisfaction. Every trigger has
arguably since fired — Ord. **4635-26**, repealing the M-1 data-center use, passed **6-0 on
2026-06-16**, three days before Thor filed suit.

Whether the clause has been invoked is `[open]`, and the federal complaint does not plead it
([`litigation-thor-v-urbana.yaml`](litigation-thor-v-urbana.yaml)). Note also the **zoning
divergence**: the agreement contemplated a **PUD**, which requires its own hearings; what was
actually done in April 2025 was a straight **M-1 map amendment plus a Ch. 1126 text amendment**
making data centers principally permitted — the route that does not.

> **What is ingested is the draft.** Exhibit A reads *"entered into on ____ 2024"*; Ord. 4612-24
> §One authorises execution "in general accordance with" it. The **signed counterpart and its
> Exhibits B & C legal descriptions are `[open]`** — a clean R.C. 149.43 target.

## 2. The CRA — ceilings, and a state gate nobody has cleared

Ord. 4631-25 §Four sets maxima only, all "negotiated on a case-by-case basis":

| Tier | Max term | Max % |
|---|---|---|
| Remodeling (materials ≥ $100,000) | 15 years | 100% |
| **New commercial/industrial construction** | **15 years** | **100%** |
| New construction on a **'megaproject'** site | **30 years** | *(no percentage stated)* |

The exemption reaches only **"the increase in assessed valuation resulting from improvements"** —
the land stays on the roll.

**The 30-year tier is a state gate, not a City one.** It requires a *megaproject operator* under
R.C. 122.17, and megaproject status is designated by the **Ohio Tax Credit Authority**. The
statutory test is a disjunction with a wage floor: ≥$1B fixed-asset investment **or** ≥$75M Ohio
payroll, **plus** an average hourly wage ≥300% of the federal minimum, **plus** a site/utility
condition. Asked at the hearing what a megaproject was, Community Development Manager **Doug
Crabill** said *"he believes it requires a billion-dollar investment"* — one prong, without the
wage floor. With 30–80 permanent jobs the payroll prong is plainly not met, the wage and site
conditions are unevidenced, and **no megaproject designation for this project was found**. On this
record the 30-year tier is unavailable to it.

Councilwoman **Amy Jumper** asked at the third reading whether the megaproject language could be
removed entirely; Feinstein answered that it would not prevent a megaproject from coming. She voted
no.

### The boundary finding — most of the assembly is outside the CRA

Exhibit B defines CRA #2 as parcels per the auditor's **tax-year-2024** records across five map
sheets. Only the **South Annexation Map** touches the project, and it lists exactly nine parcels:

| In CRA #2 | Acres | Owner |
|---|---|---|
| K48-25-11-01-30-005-00 | 7.09 | **Urbana Owner II LLC** |
| K48-25-11-01-30-006-00 | 90.00 | **Urbana Owner II LLC** |
| -36-001, -37-001 | 94.50 | Board of County Commissioners |
| -36-002, -37-002 | 10.71 | Madison-Champaign ESC |
| -36-003, -36-004, -37-003 | 17.78 | Urbana Health Facilities LLC |

That totals **220.08 ac** — i.e. CRA #2's south sheet *is* the 219.986-ac annexed territory, not
the developer's assembly.

Of the **230.346 recorded acres** in the Thor assembly, only **97.09 ac** — the Urbana Owner II
parcels, conveyed from Organ Farms on 2026-06-12 — fall inside CRA #2. The **133.256 ac bought
first** from Brand Investments (the "Vance Brands" parcel, 47.637 ac, and the 85.6-ac parcel south
of Rittal) appear on **none** of Exhibit B's five sheets.

**The exclusion is a choice, not a jurisdictional artefact.** A city CRA can only cover territory
in the city, so the obvious objection is that the Brand parcels were simply outside the corporation
limits. They were not: intersecting the committed parcel geometry against the county GIS
`Municipal_Boundaries` layer puts **all four assembly parcels 100% inside the Urbana city limits**
(and the layer carries the 2025 annexation, since the Organ Farms parcels fall inside it). The two
Brand parcels were eligible for CRA #2 and were left out of it.

They were, however, **not part of the Ord. 4619-25 annexation** — that petition's owners were the
County Commissioners, Organ Farms LLC, the Madison-Champaign ESC and Urbana Health Facilities LLC,
and the nine CRA-2 South parcels match those four owners exactly. Worth flagging because **both**
the City's public notice **and** the federal complaint describe the 47-acre and 80-acre purchases
as being *"in the newly zoned and annexed territory"* — loose on this point, and in near-identical
wording in both documents.

The Project Overview places the building *"on the NW side of the property adjacent to the Rittal
facility"*, which reads onto the Highland55 parcel — outside CRA #2. The site plan is not in
corpus, so the footprint cannot be fixed to a parcel `[verified]`, and Exhibit B's own "as the
parcels may be split, re-combined, or combined from time to time" language means a re-plat could
change coverage. What is `[verified]` is the enacted parcel list.

## 3. The noise limits are an offer, not a condition

The Project Overview says the project is *"offering to commit to decibel limits **via a formal CRA
agreement**: Daytime 65 dB … Nighttime 55 dB."*

Ord. 4631-25 contains **no acoustic condition of any kind**, and the agreement that would carry
them does not exist. The corpus previously listed "CRA agreement offered (noise limits 65 dB day /
55 dB night)" among the facility's disclosed terms; the correct reading is that **Urbana's
enforceable noise constraint on this project is currently zero**.

## 4. The tax figures — a double count, corrected

The corpus carried *"~$5.8M/yr combined city + school tax"*; #1354 states *"~$6M/yr"*. Both add two
numbers the source says not to add. The Project Overview reads:

> - Total Revenue: Over **$3,000,000** in new tax revenue for the City of Urbana annually
> - Local Schools: Over **$2,800,000** in new funding **(from the total revenue)** for Urbana
>   Schools annually

The schools' figure is a *component* of the total. **The disclosed aggregate is "over $3,000,000"
annually** — roughly half what the corpus asserted.

### Reconciling it `[inference]`

The auditor records the four assembly parcels at **$2,687,630 of land value and $0 of improvement
value** (three of four still on CAUV). Since the CRA exempts only the improvement increase, a ~$1B
build would be the entire exemptible increase.

Ohio assesses at 35% of true value, so $1B ≈ **$350M assessed**. For that to yield only
">$3,000,000" a year across *all* taxing bodies implies an effective rate of about **8.6 mills** —
far below any plausible Ohio commercial rate. The disclosed figure therefore cannot be unabated
property tax on the improvement. It is consistent only with a substantial abatement plus revenue a
CRA does not touch — municipal income tax on payroll, and any negotiated school compensation.

A City datum corroborates the mixed-source reading: Resolution 2721-25 (2025-10-21, **failed 2-5**)
would have cut *"the City of Urbana's share of the General Fund (Inside) property tax collection
from **1.8 mills** to 1.5 mills."* At 1.8 mills the City's own take on $350M assessed is
~$630,000/yr — nowhere near $3M.

`[open]` — the Urbana City School District effective millage and Urbana's municipal income-tax rate
would close this. Neither the county auditor (DNS failure on five hosts) nor tax.ohio.gov (404) is
reachable.

### The land spend closes exactly

The City's notice says the developer paid *"approximately $5,000,000"* to participating owners —
*"47 acres … for just over $2 million, and in November … just over 80 acres … for just over $3
million."* Against the deed register in [`land-assembly.yaml`](land-assembly.yaml):

| Deed | Recorded | Acres | Consideration |
|---|---|---|---|
| OR601/4948 | 2025-08-22 | 47.637 | $2,143,665 |
| OR603/1927 | 2025-11-18 | 85.619 | $3,210,712.50 |
| **Subtotal** | | **133.256** | **$5,354,377.50** |

A clean two-source corroboration — and confirmation that the City treats the Urbana Owner I /
Highland55 SPEs as "the developer." The Organ Farms conveyance ($3,398,150, 2026-06-12) postdates
the notice; all three total $8,752,527.50.

## 5. The state incentive record — documented negative

- **Zero** occurrences of *JobsOhio*, *Ohio Department of Development*, *Tax Credit Authority*,
  *122.17* or *122.175* across **all 37 approved council minutes for 2025–2026**. `[verified]`
- No JobsOhio award and no Tax Credit Authority approval naming Thor Equities, Highland,
  Urbana0624C or the Urbana Technology Hub surfaced on open-web search. `[reference]` — an
  open-web negative is weaker than a registry negative, and the registries are unreachable.
- **ODOD is unreachable** (`development.ohio.gov` → 404 on every path), so the CRA registry and the
  R.C. 3735.672 annual reports could not be pulled — including the **designation number** that
  Ord. 4631-25 §Eleven makes a precondition to *any* exemption under CRA #2. `[open]`
- **Ohio SoS** → 403; **Champaign County Auditor** → DNS failure. `[open]`

## 6. What Council was told, on the record

Worth preserving because the timeline turns on it:

- **2025-10-21**, asked directly about "a potential data center", Crabill answered that **"the City
  has not engaged in any agreements"** — and that each individual agreement would need Council
  approval.
- **2025-10-21**, Urbana City Schools treasurer **Mandy Hildebrand**: the statute allows up to a
  **75% abatement without going to the school board**; the board "has questions whenever a 100%
  abatement is asked for"; recent requests have been under 100%; revenue sharing becomes possible
  when total payroll exceeds $2 million; and abating commercial value "shifts the tax base more
  towards residential." She was explicit that she spoke neither for nor against.
- **2025-11-04**, Feinstein compared Urbana's action to **Sidney's**: *"what happened in Sidney is
  an agreement."* Sidney is a separate registered BOSC site (#1275) — recorded as the City's own
  comparison, **not** as an evidentiary bridge between the two projects.
- **2025-11-04**, Councilman **Pat Thackery** — the ordinance's own sponsor — said he felt *"by the
  time the agreement comes to Council, it would feel too late for Council to say no."*

## Open ingest targets

- The **executed** Pre-Annexation Agreement — signed, dated, with Exhibits B & C.
- Whether the **§3(c) detachment clause** has been invoked, and the City's response.
- The **CRA Application** form on file with the Clerk of Council, and whether one was ever filed.
- The **ODOD designation number** for CRA #2 and its R.C. 3735.672 annual reports.
- The **Ohio SoS** filing for `Urbana0624C, LLC`.
- The **Champaign County TIRC** annual report.
- County **effective millage** and Urbana's **municipal income-tax rate**.
- The **2026-02-17 council packet** — the meeting the Project Overview appears to accompany.
- The reported **September-2024 purchase agreement** between the Champaign Economic Partnership /
  Board of County Commissioners and `Urbana0624C, LLC` — reported, not sourced.
