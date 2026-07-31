# Findlay's dislocation record — the WARN pair and Brownfield Round 11

**Site:** Findlay, OH (Hancock County) · **Issue:** 1460 · **Ingested:** 2026-07-31
**Instruments:** two ODJFS WARN notices (Goodyear 2026-01-30, Michigan Sugar 2025-12-11) · the Ohio
Brownfield Remediation Program Round 11 award descriptions (2026-05-13)

Four filed documents, all `[verified]` from their own text. They sit in the same eighteen months and
they point in opposite directions: two employers filing closure notices, and just under a million
dollars of state money going into contaminated Hancock County land.

## Goodyear — Tall Timbers Mold, 85 jobs, permanent

On **2026-01-30 at 2:33 p.m.** ODJFS received a letter from The Goodyear Tire & Rubber Company,
signed by Dusty Douglas, Director of Americas Manufacturing — Mixing, Racing and Non-Tires:

> We are writing to inform you that The Goodyear Tire & Rubber Company will close its Tall Timbers
> Mold facility located at 2025 Production Drive Findlay, OH 45840. As required by the Ohio WARN Act
> and the federal Worker Adjustment and Retraining Notification Act of 1988, this letter serves to
> give you notice of the closing. The entire facility will close and this action is expected to be
> permanent.

**85 positions.** Separations begin "on or around the 14-day period commencing on **March 31,
2026**." No bumping rights; severance and outplacement offered.

The enclosed schedule is the part worth reading twice, because it shows what kind of employment
leaves the county:

| Classification | Count |
|---|---|
| Manufacturing Technician | 39 |
| Technology Specialist | 7 |
| Area Manager | 4 |
| Quality Technician | 4 |
| Production Business Leader, Quality Specialist | 3 each |
| Engineer Senior, CAM Engineer, Electronic Tech, Manufacturing Clerk, Manufacturing Planner Schedule Leader, Technology Engineer, Technology Engineer Associate | 2 each |
| EHS Coordinator, HR Specialist, Mold Operations Apprenticeship, Procurement Coordinator, Quality Business Leader, Quality Engineer Associate, Quality Engineer Senior, Technician II Mold Operations, Technology Engineer Senior, Technology Engineer Staff | 1 each |
| **Grand Total** | **85** |

Roughly a fifth of the loss is engineering and technology grades. This is a mold-making operation,
not a line.

**What the letter does not say.** It names no destination for the work, no receiving plant, and no
labor organization — and it states outright that there are no bumping rights at this location. A
consolidation destination is widely reported; it is not in this instrument, so it is not carried as
a claim here. Lead `WARN-GOODYEAR-DESTINATION`.

## Michigan Sugar — four jobs, and a severed rail spur

The smaller filing is the more interesting one. On **2025-12-11 at 4:56 p.m.** ODJFS — and, jointly,
Mayor Christina Muryn — received a letter from Mario A. Spadafora, Director of Labor & Employee
Relations at Michigan Sugar Company in Bay City, closing the company's warehouse at 1343 Greenwood
Street. Four employees: a warehouse manager, an assistant, and two utility persons, two of them
represented by **BCTGM Local 19**.

The company is explicit that it did not have to file:

> Although we do not believe the closure required any notice, we are sending this as a courtesy to be
> considered notice of a facility closing under the Worker Adjustment and Retraining Notification Act
> (WARN Act).

Four employees is far below the federal threshold, so this is a courtesy filing, and reading it as a
statutory WARN trigger would misstate the company's own position. What makes it worth committing is
the stated rationale:

> Rail service was previously severed to the Findlay site and Ohio has stricter limits on truck
> weights than Michigan which means it is often difficult to transport sugar from our Michigan
> factories to the site. In addition, outdated and obsolete equipment would require a significant
> capital investment for a site that does not produce sugar and does not have rail service.

That is a **freight-access finding about a specific Findlay industrial parcel, from the tenant, in a
filed instrument** — not a press account. Which line was severed, when, and by whom, and whether the
same severance strands neighbouring parcels, is lead `FINDLAY-RAIL-SEVERANCE`. Findlay's rail
geometry is already load-bearing elsewhere in this site's record: the flood program's benching work
runs from Cory Street to the CSX tracks and around the Norfolk Southern bridge.

No final day of operations is stated — the letter says it "has yet to be determined." The only fixed
date is that the two represented employees remain on the active roll until 2026-01-31. Three
notification dates are distinct and are recorded separately: BCTGM notified in writing 2025-12-03,
employees verbally 2025-12-04, the represented employees in writing 2025-12-11.

## Brownfield Round 11 — $999,998 into contaminated ground

Announced **2026-05-13**. Three Hancock County awards:

| Project | Recipient | Amount | Category |
|---|---|---|---|
| Former Lincoln Elementary School Remediation | City of Findlay | $663,998 | Cleanup/Remediation |
| Tiffin Ave Abandoned Gas Station Assessment | City of Findlay | $238,000 | Assessment |
| Bluffton Former Gas America Assessment | **Hancock County Commissioners Office** | $98,000 | Assessment |
| **Total** | | **$999,998** | |

Note the third recipient: the Bluffton award goes to the **county**, not the city.

**Lincoln Elementary** is asbestos in a school building vacant since 2021 — pre-renovation abatement
and selective demolition to reach impacted materials, ahead of a mixed-use conversion to 32
residential units plus office and collaborative space and "potential retail amenities, including a
beer garden." The packet expects 24 jobs created and 28 retained, and frames the housing against
"Findlay's highly constrained rental market."

The other two are **petroleum in the ground**. The Tiffin Avenue site is a long-abandoned gas station
where the award pays to pull the underground storage tanks and run Tier 1 and Tier 2 BUSTR
assessments, ahead of a planned Holistic Health & Resilience Center. The Bluffton site is a former
Gas America where four USTs have already been removed and **a petroleum release was discovered
beneath a dispenser island**; the award funds a Tier 1 assessment, potential interim response
actions, and a Tier 2 evaluation toward a No Further Action designation, with reuse as support space
for an adjoining motel.

Two of three Hancock awards are subsurface petroleum. The BUSTR Tier 1 and Tier 2 reports these
grants pay for are the documents that would say what is actually in the ground and how far it has
moved — none of them are in the corpus.

**What this total is not.** It is Round 11 only. Hancock County's presence in Rounds 4 through 10 is
unresearched, so $999,998 is not a program total and must not be presented as one. Lead
`BROWNFIELD-ROUNDS-4-10`.

The job figures throughout are the packet's own forward-looking expectations for each
redevelopment, not outcomes.

## Committed artifacts

| Record | Instrument |
|---|---|
| [`warn/goodyear-tall-timbers-mold-2026.warn.yaml`](warn/goodyear-tall-timbers-mold-2026.warn.yaml) | Goodyear WARN notice + the 23-row position schedule |
| [`warn/michigan-sugar-findlay-2025.warn.yaml`](warn/michigan-sugar-findlay-2025.warn.yaml) | Michigan Sugar courtesy WARN notice + Exhibit 1 |
| [`brownfield/round-11-hancock-2026.award.yaml`](brownfield/round-11-hancock-2026.award.yaml) | The three Hancock Round 11 awards |

Source documents: [`data/documents/findlay/warn/`](../../documents/findlay/warn/) ·
[`data/documents/findlay/brownfield/`](../../documents/findlay/brownfield/)

Both WARN records publish under the `labor` record group, added to the bundle's `RecordGroup`
taxonomy for this ingest (contract 1.47.0). A statutorily required plant-closing notice filed with a
state workforce agency is not a permit, an enforcement order, an award, a deed, or a pleading, and
filing it under the nearest of those would present a workforce instrument as an environmental one.

## What this is not

These are labor and land instruments, not an economic finding. The county-level employment effect of
89 lost positions, and whether it is offset anywhere, is a question for the economics baseline and
the site's demand-pressure model — not a claim any of these four documents makes. What they
establish is narrower and firmer: two employers closed Findlay facilities in the same eighteen
months, one of them named a severed rail spur as the reason, and the state is paying to characterise
petroleum and asbestos on three parcels in the same county.
