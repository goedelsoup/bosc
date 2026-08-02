# Urbana cooling-water account — testing "comparable to a standard office building"

Resolves **#1684** (B4 of the closed-loop cooling-cycling epic **#1676**): run the A3
reconciliation harness on the campus where the closed-loop framing entered this network.

In February 2026 the developer of the **Urbana Technology Hub** told a City of Urbana meeting
that the campus would use closed-loop cooling, with water use **"comparable to a standard office
building."** That sentence is the reason the Mad River buried-valley abstraction thesis was set
aside for this site (#1327 / #1330), and the same framing then appeared at Van Wert, Springfield,
Troy-Piqua and Bowling Green. This file is what the record can and cannot say about it.

**The short answer: nothing on record tests the claim, and nothing on record can.** The outcome
is `route_blind`, not `gap` — the difference is that a gap is an unfinished lookup, and this one
cannot be finished by pulling harder on the sources the harness reads. What *is* new is a
denominator: the campus is invisible to the withdrawal registry, but its supplier is not.

Tags follow the project vocabulary (`[verified]` primary/government source; `[reference]`
authoritative outside data or public disclosure; `[inference]`; `[open]`).

## 1. The claim carries no number `[reference]`

Every other site in this epic disclosed a quantity to argue with — Troy-Piqua's 2.0 MGD
reservation (B1 #1681), Van Wert's ~660,000 gal (B2 #1682), Springfield's "up to 300,000 gal/day"
permitted ceiling (B3 #1683). Urbana disclosed a **comparison**.

That matters mechanically, not just rhetorically. A simile is not a self-report of a figure, so
nothing lands on `disclosed_makeup` or `disclosed_ceiling`; there is no operator number to record,
sharpen, or contradict. What the claim asserts is which *order of magnitude* the campus belongs
to — and its two candidate readings are three orders apart (§4).

## 2. Both instruments are out of reach — on the City's own record `[verified]`

The harness reads two record sources, and both are jurisdictional rather than universal. A1 (the
Ohio DNR Water Withdrawal Facilities Registration Program, R.C. 1521.16) registers withdrawals
**from waters of the state**. A2 (ECHO/ICIS NPDES) covers **discharges to them**.

The City legislated the campus onto both of its own systems:

- **Ord. 4612-24** (passed 5-0, 2024-12-17) authorized a **Pre-Annexation Agreement** with
  `Urbana0624C, LLC` — which the City's own public notice identifies as "Highland". Its City duty
  is to *"provide water and sewer"* to the property, and its § 3(c) makes the failure to make
  *"water and sewer capacity … available to satisfy the Developer's schedule"* a trigger for
  de-annexing the entire property on demand. `[verified]`
- **Ord. 4613-24** — the R.C. 709.023 **statement of services** for the annexation — passed 5-0
  the same night; the territory was annexed by **Ord. 4619-25**. `[verified]`

So the campus buys City water (it withdraws nothing itself) and discharges to the City sewer (it
has no outfall of its own). Both sides of its account sit precisely where A1 and A2 do not look.

Source: [`data/documents/urbana/council/2024-11-19_regular_meeting_packet.pdf`](../../documents/urbana/council/)
(Ord. 4612-24 Exhibit A) → [`incentive-instruments.md`](incentive-instruments.md) § 1.

### The consequence, confirmed as a searched absence

- **A1.** Champaign County has **31** WWFRP registrations, and **none of them is the campus** —
  no Thor Equities, no Highland55, no Urbana Owner, no Urbana Technology Hub. Pulled live
  2026-08-01 to [`data/reference/ohio-water-withdrawal/champaign.yaml`](../../reference/ohio-water-withdrawal/champaign.yaml).
  `[verified]`
- **A2.** ECHO's Champaign County CWA inventory (21 facilities) carries **no permit at the
  SR-55 / US-68 site**. The record that *would* carry a cooling discharge is a City **industrial
  user (IU) permit** under the City's OEPA-audited **industrial pretreatment program** — and ECHO
  never carries those. The program itself is documented in corpus: a **Pretreatment Compliance
  Inspection** (2025-09-09) and a pretreatment **significant-non-compliance Notice of Violation**
  (2025-10-07), both under permit **1PD00011**
  ([`data/documents/oepa/urbana/`](../../documents/oepa/urbana/)). `[verified]`

A ~0 from either instrument here is an **absence of jurisdiction, not a measurement** — it can
never corroborate the dry claim. That is the B6 (#1686) guard, and Urbana grounds it on a stronger
instrument than New Albany did: a City ordinance and contract rather than press reporting.

> **Also not built.** The February-2026 site plan was denied as "incomplete", a 12-month emergency
> moratorium (Res. 2727-26) is in force, and the zoning is in federal litigation
> ([`litigation-thor-v-urbana.md`](litigation-thor-v-urbana.md)) — so no meter reading exists
> anywhere yet. What the records request seeks is the **service and capacity** record that exists
> now — the will-serve letter, the supply-adequacy analysis, the IU pre-application — not a
> historical meter.

## 3. What the registry does reach: the supplier `[verified]`

The City of Urbana's public water system is fully in the registry, on two registrations drawing
the same high-yield buried-valley aquifer:

| reg# | facility | wells | registered | 2024 reported |
|---|---|---:|---:|---:|
| 00837 | Urbana City PWS **OTP** (Old Troy Pike) | 6 | 5.76 MGD | **644.99 MG = 1.76 MGD** |
| 03719 | Urbana City PWS **29 WTP** (2047 State Rte 29 W) | 3 | 3.00 MGD | *no annual report filed* |

Registered capacity totals **8.76 MGD** against **1.76 MGD** actually reported. The City PWS is
the county's **second-largest** reported withdrawer, behind an agricultural irrigator (Michael
Farms-East, 940 MG in 2024).

> ⚠️ **Do not read the 2026-03-26 registration date as capacity added for the data center.** The
> SR-29 plant is a long-standing City facility — the City's own water division page describes both
> plants, and the plant holds its own NPDES permit (**OH0137618**, effective, expiring
> 2027-12-31). The 2026 registration is a registry event whose occasion is `[open]`: a
> records-request item, not a finding. The tempting juxtaposition (a capacity registration one
> month after the February-2026 disclosure) is exactly the inference the record does not support.

This figure rides on the harness's `supplier_withdrawal` slot, kept distinct from every other
register. It is the **system's** account across every customer on it, so it can neither corroborate
nor contradict the campus's claim. It is carried because it is the denominator.

## 4. The measurement `[inference]`

The claim cannot be measured against the campus's own withdrawal — there is none, and there can be
none. It can be measured against **the only withdrawal record that exists**, which is the City's.

At the campus's own `[inference]` screening IT-load bracket — **34.5 / 74.8 / 115 MW**, from the
disclosed 460,000 sq ft (see [`datacenter-facility.md`](datacenter-facility.md) § 4; never a
disclosure) — run through the evaporative reference band carried in the reconciliation artifact's
meta (**0.0143 MGD makeup per IT-MW**, archetype-derived):

| reading | implied makeup | as a share of the City's entire 2024 withdrawal |
|---|---:|---:|
| Evaporative, low bracket (34.5 MW) | 0.49 MGD | **28 %** |
| Evaporative, central (74.8 MW) | 1.07 MGD | **61 %** |
| Evaporative, high bracket (115 MW) | 1.64 MGD | **93 %** |
| **"Comparable to a standard office building"** | below 0.01 MGD | *below the screen's own noise floor* |

The distance between the two readings of one sentence is the difference between a rounding error
on the City's system and a second City-sized demand on the same buried-valley aquifer — and **no
instrument on either side of the account can tell them apart.**

This is a screening comparison, not a prediction: the load bracket is an `[inference]` from floor
area, and the band is what an evaporative tower of a given IT load *would* draw under the
archetype, not what anyone has disclosed or metered. Its purpose is to show that the untested
question is material.

## 5. Outcome — and what it does not license

Recorded in [`data/reference/oepa/cooling-reconciliation.yaml`](../../reference/oepa/cooling-reconciliation.yaml)
(regenerate: `watermark cooling-reconcile --write`).

- Outcome **`route_blind`**; the `closed_loop_dry` pin is **KEPT** at `source=reference`.
- **No re-archetype is recommended, and no upgrade.** Nothing here is an instrument about the
  facility, in either direction. The absence of documented water is *not* evidence of a dry loop,
  and the size of the counterfactual is *not* evidence of a wet one.
- The `[verified]` tag on the row attaches to the **blindness**, which is an established fact
  about the record. The cooling account itself stays `[open]` — that is what the lead is for.

## 6. The records request (C2, #1688) `[open]`

Unlike New Albany — where the meter belongs to Columbus, two counties from the site's own
address — Urbana's holder **is the site's own city**, on both sides. It is also the defendant in
the developer's federal suit, which is context for the response, not a reason not to ask.

Holder: **City of Urbana** — Water Division (205 S Main St) for the makeup meter and any
will-serve / capacity analysis; the **Industrial Pretreatment Program** coordinator at the Water
Reclamation Facility for the IU permit and sewer-use agreement.

Sought:

- Metered municipal water-service consumption for the campus — the meter that records the makeup
  the withdrawal registry cannot see.
- The industrial pretreatment / indirect-discharge (IU) permit and its reported flow.
- The sewer-use agreement / capacity reservation for the campus.
- The water-service agreement or will-serve letter.
- **The water system's capacity / supply-adequacy analysis for the campus** — what draw the
  *supplier* planned for. This is the sharpest ask on the list: it is the figure the operator's
  claim never states, written down by someone who had to size a system around it.
- The facility air permit (PTI/PTIO) cooling-tower emission-unit list, and the Tier II /
  EPCRA-312 chemical inventory — both still `not_on_record` (A4, #1680), neither read as
  confirming anything.

Standing open items this does not resolve:

- `[open]` The executed Pre-Annexation Agreement (what is in corpus is the draft Exhibit A) —
  lead `URB-PREANNEX`.
- `[open]` The occasion of WWFRP registration 03719 (2026-03-26).
- `[open]` The disclosed MW load, which would replace the screening bracket the § 4 comparison
  rests on (#1353 searched negative).
