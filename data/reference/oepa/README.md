# OEPA cooling-cycling reference (OHD000001 coverage + reconciliation)

Two derived references for the closed-loop cooling cycling epic (#1676): the A2
**OHD000001 coverage** resolution (#1678) and the A3 **cooling-cycling reconciliation**
(#1679), the latter now also carrying the A4 **independent corroborators** (#1680 —
air-permit cooling-tower PM + Tier II / EPCRA-312 chemistry). Both are computed over the
site registry's closed-loop cohort — data-center facilities disclosing a recirculating/
closed cooling archetype — and the cited OHD000001 permit lifecycle.

OHD000001's low-volume-wastewater coverage (cooling-tower blowdown, boiler blowdown,
air-compressor condensate) is the disclosure the cycling thesis predicts. The permit
documents themselves (draft body + public notice + fact sheet) are catalogued
separately under `oepa-ohd000001-gp` (`documents/oepa/OHD000001_Draft*.pdf`); this
folder holds the **coverage resolution** computed over them and the **reconciliation**
that reads it.

## Files

- [**`ohd000001-coverage.yaml`**](ohd000001-coverage.yaml) (A2) — `meta:` provenance, a
  `general_permit:` lifecycle block (OHD000001's own draft/effective state, the gate
  on whether coverage is even possible), and a `candidates:` list: for each registered
  facility disclosing a recirculating/closed cooling archetype, its resolved
  `ohd000001_status` (`covered` / `not_sought` / `no_record` / `not_available`), its
  `facility_own_discharge` status, and a one-line evidentiary `finding`. Regenerate with
  `watermark oepa coverage --write` (`watermark.hydrology.blowdown`).

- [**`cooling-reconciliation.yaml`**](cooling-reconciliation.yaml) (A3 + A4) — the
  per-facility **water account**: the pinned archetype's PREDICTED makeup/blowdown
  (from `watermark.hydrology.cooling_models`) vs the DOCUMENTED makeup (A1 withdrawal) /
  blowdown (A2 discharge), a back-solved cycles-of-concentration (an `[inference]`
  bracket) where both are on record, and an `outcome` per facility — `discrepancy` /
  `corroborated` / `reservation_conflict` / `route_blind` / `gap` — with a recommendation
  and, for every outcome whose move is a records request, a C2 `lead` payload. Each record
  also carries the A4 `corroborators` block (air-permit cooling-tower PM + Tier II chemistry
  — `watermark.hydrology.cooling_corroborators`), and its `meta` carries the per-IT-MW
  `reference_band`. Regenerate with `watermark cooling-reconcile --write`
  (`watermark.hydrology.cooling_reconcile`).

## Method & the gating fact

Coverage is gated on the general permit's **lifecycle**, and that lifecycle has ended.
OHD000001 was issued as a **draft** on 2025-10-31 (public notice No. 215991; hearing
2025-12-17; comment period closed 2026-01-16) — and on **2026-07-21** Ohio EPA published a
Community Notice saying that after reviewing the comments it "has decided not to move
forward with finalizing the general permit," and that "the individual NPDES permit issuance
process is the most appropriate path forward at this time." The permit is **WITHDRAWN**.

Every candidate still resolves to `not_available`, but read it correctly: the absence is
now **permanent, not pending**. No coverage list will ever exist, so this is no longer a
watch that closes by waiting — the only instrument that would ever disclose a data
center's cooling discharge is an **individual NPDES permit**, which is a substantially
better evidentiary object than a general-permit coverage row (public-noticed,
fact-sheeted, individually limited). The replacement watch is whether such an application
or draft permit appears for any cohort campus.

The lifecycle lives in one cited place — the `OHD000001` constant in
`watermark.hydrology.blowdown`; update it there and rerun the regenerate command. The
`covered` / `not_sought` authorization seam in `resolve_coverage` is now unreachable for
*this* permit and is kept for the next data-center general permit that does issue.

## The cohort (registry-derived)

The candidate list is derived from the site registry (`watermark.sites`): every
`SiteFacility` whose disclosed `cooling_model` is `closed_loop_dry` or
`hybrid_adiabatic` — the recirculating/closed claims the epic is testing. It is **not**
hand-maintained: a site enters the moment its profile pins such an archetype, and drops
if the archetype is revised.

Deliberately **out** of the current cohort, and why:

- **Facilities whose cooling archetype is still `unknown`** (e.g. Troy-Piqua's Project
  Klondike, pending #1486; Sidney's Project Galaxy) — there is no archetype claim to
  test yet; they are handled in per-site B-review.
- **Sites with no pinned `SiteFacility`** — they enter automatically once B-review pins a
  facility + cooling archetype on the profile. **New Albany / Intel** is the deliberate
  exception (B6, #1686): it still pins no facility — `SiteFacility.kind` admits `data_center`
  and `federal_installation`, and a semiconductor fab is neither, so pinning Intel would size a
  chip fab as a campus — but its record is reconciled explicitly as a live row anyway, because
  what it establishes is about the harness rather than about Intel (below).

## The reconciliation (A3)

For each cohort facility, `cooling-reconciliation.yaml` runs the pinned
`SiteFacility.cooling_model` archetype through `watermark.hydrology.cooling_models` to
get the **predicted** makeup/blowdown for the claim, reads the **documented** makeup (A1
withdrawal registry) and blowdown (A2 discharge coverage) where records exist, and
classifies the reconciliation:

Where a facility's water is outside the instruments' reach entirely, the classification is
`route_blind` and the predicted side may be refused outright — see the B6 section below.

- **discrepancy** — a low-water claim (`closed_loop_dry`) contradicted by documented
  flow ≫ its ~0 prediction (or over-cycling even vs a wet claim). Recommends
  re-archetyping up (`evaporative_tower` / `hybrid_adiabatic`, `source="document"`).
- **corroborated** — documented water is consistent with the claimed archetype (a dry
  claim with documented ≈ 0, or a wet claim whose documented water matches). Recommends
  the `reference → document` source upgrade.
- **gap** — no documented makeup or blowdown to test against. Emits a records-request
  `lead` payload for C2 (#1688). **B2 (#1682, Van Wert)** sharpens the gap when the
  operator has *disclosed* an ongoing draw (a self-report, not a metered instrument): the
  disclosed `[reference]` figure is recorded on `disclosed_makeup` — never `documented_*`,
  so it cannot corroborate the operator's own claim or upgrade the source — the pin stays
  `[reference]`, and the lead names the specific open quantity (Van Wert's initial
  closed-loop fill, whose fill-vs-annual framing is the #1409 discrepancy).
  **B3 (#1683, Springfield)** sharpens a gap the other way: the claim's own source (the City
  5C FAQ) self-discloses a permitted-withdrawal **ceiling** (300,000 gal/day at a >80 °F
  extreme-heat max, "near zero" most of the year), recorded on `disclosed_ceiling`. A permitted
  PEAK ceiling from the claim's own source is **not** a `reservation_conflict` — unlike B1's
  independently-negotiated reservation it is not a demand signal that contradicts the dry claim
  (a dry loop sits far below it) — so it too never feeds the classifier or upgrades the source;
  the lead names the actual-vs-ceiling denominator (pull the metered municipal withdrawal, #1415).

Where **both** documented makeup and blowdown are on record, cycles-of-concentration is
back-solved (makeup / blowdown) and emitted as an **`[inference]` bracket, never a
headline scalar** — the ratio of two self-reported figures is not a measurement.

**No live cohort facility has a documented cooling account**: with OHD000001 withdrawn and
no facility-own DMR on record, there is no metered makeup or blowdown to test against —
including Van Wert, whose operator-disclosed ~660k gal figure is a self-report, not an
instrument (B2 #1682), and Springfield, whose self-disclosed 300k gal/day is a permitted
ceiling, not metered use (B3 #1683). Most therefore read `gap`. Two do not, and the reason
is the same in both: they carry a figure that came from **somewhere other than the operator**.
Troy-Piqua's negotiated 2.0 MGD reservation (B1 #1681) and Bowling Green's district-linked
~600,000 gpd design commitment (B5 #1685) are `reservation_conflict` — disproportionate to a
low-water claim, but ceilings rather than instruments, so both keep their pin. Bowling Green
also shows why the reach guard is ordered the way it is: its makeup route is **blind**
(the campus buys finished water from a regional district), yet the reservation stands,
because a negotiated ceiling was never something the withdrawal registry could have metered.
The seams auto-activate when the records land.

**The harness recommends; it never mutates `cooling_model`.** Re-archetyping a facility
is a reviewed B1–B6 edit landed with the instrument cited — the reconciliation record is
the evidence packet for that edit.

**The Intel control row is constructed** (`is_control: true`; exemplar New Albany / Intel,
openly evaporative, ~125 cooling towers): an evaporative facility whose documented water
equals its evaporative-tower prediction, which the harness must classify `corroborated` —
**not** a false `discrepancy` for using a lot of water. It is a calibration vector built into
the harness, **not** documented Intel data.

### `route_blind` — when the instruments cannot reach the facility (B6, #1686)

B6 went looking for the real Intel record to replace that constructed vector and established
that it cannot: Ohio One is a **semiconductor fab** (so every IT-load-parameterized archetype
refuses to predict for it), it does **not operate until 2030–31**, and — the part that
generalizes — its makeup will be **purchased City of Columbus water** while its process
wastewater goes to the **Columbus sanitary sewer**.

That puts both sides of its account outside the instruments this harness reads. The withdrawal
registry meters withdrawals **from waters of the state**, so a purchased supply is the seller's
withdrawal and never appears; a discharge to a POTW has no NPDES outfall, so no DMR exists.
**Both return ~0 by construction** — and the classifier was reading that ~0 as "documented ≈ 0 →
*corroborated dry*". The same county proves it independently: the **operating** Amazon Data
Services campus at 2570 Beech Rd (WWFRP 03401) reports **0.02 MG for all of 2024**. Essentially
the entire closed-loop cohort is municipally supplied, so this would have silently upgraded
every one of their claims to document-grade.

So each record can carry a cited **`route`** (`supply`: self_supplied / municipal / unknown;
`discharge`: surface_npdes / sanitary_sewer / unknown) and a fifth outcome:

- **route_blind** — a ~0 from an instrument that cannot reach the facility is an *absence of
  jurisdiction*, not a measurement. The guard invalidates a **negative** read only: a documented
  flow is still a `discrepancy`, a reservation ceiling is still a `reservation_conflict`, and a
  wet claim corroborated by real documented water is still `corroborated`. The pin is **kept**,
  and the records request is re-aimed at the holder that actually meters the campus (the City's
  water-service consumption record + the industrial pretreatment / IU permit).

Two slots serve it. **`nonprocess_makeup`** carries a documented, metered withdrawal that *is*
on record but is **not** the cooling account — Intel's **0.0435 MGD** of construction-phase
groundwater (WWFRP 03498; ~89% returned, hydrostatic-test coverage held by Bechtel, peaking in
**May** while July–August are the year's lowest, the inverse of an evaporative signature).
**`prediction_refused`** carries the reason the archetype account could not be derived at all,
with `it_load` and the three `predicted_*` left null — a consumer must render the refusal and
**never substitute a zero**.

### The reference band (B6, #1686)

`meta.reference_band` records the per-IT-MW evaporative screening band (makeup / consumptive /
blowdown / CoC / WUE) the cohort's claims can be measured against. It is derived from the
**`evaporative_tower` archetype spec's own defaults**, tagged `[inference]`, and it says out
loud that it is **not** read off the disclosed positive control: Intel's ~5 MGD is *fab process
water* at a pre-operational campus whose ~100+ MW is an electrical, not an IT, load, so a
makeup-per-MW figure taken from it and applied to a hyperscale campus would be a category error.
**No documented evaporative-hyperscale band exists in the network yet** — that gap is itself the
finding, and the archetype figures stand in until an operating, metered evaporative campus lands.

## The independent corroborators (A4, #1680)

Two orthogonal tells corroborate over-cycling **independently of the makeup/blowdown
accounting** — and are hard for an operator to reconcile with a "dry, sealed" claim.
Each reconciliation record carries a `corroborators` block with both, plus a combined
`net_stance` (`corroborates` / `contradicts` / `silent`) relative to the claim:

- **Air permit** (`air_permit`) — an evaporative cooling tower emits PM (drift) and is a
  permitted air source fitted with drift eliminators; a sealed/dry system is not. A
  facility whose own air permit **lists cooling towers as PM emission units**
  (`pm_source_listed`) therefore **contradicts** a `closed_loop_dry` claim and
  **corroborates** an `evaporative_tower` / `hybrid_adiabatic` one. Read from the
  committed extraction at `SiteFacility.air_permit_relpath` (the same seam
  `watermark.air.emissions` grounds its rates on) — real today for any facility whose air
  PTI/PTIO is on file (Lima's `permits/4132514.epa.yaml` lists 36 cooling towers as
  ~4.0 tpy PM10 sources), `not_on_record` where none is wired.
- **Tier II chemistry** (`tier2_chemistry`) — cooling-water treatment (biocide, scale /
  corrosion inhibitor) scales with makeup and blowdown volume; a truly dry loop needs
  little. Source is the **Tier II / EPCRA-312** inventory + LEPC filings, held by the
  SERC/LEPC and **not on ECHO** — so for the live cohort this is a **forward seam**
  (`not_on_record` → a C2 records-request item) until a filing lands.

**Both are corroborators, never the sole basis for a re-archetype.** A re-archetype is
`[verified]` only with the discharge/withdrawal *instrument* cited (the A3 water
account), and an air permit is not such an instrument. So these signals sharpen a
finding and the gap's records-request but **never change the `outcome`**. Each carries
its own tag: an on-record listing/absence is `[verified]`; a not-on-record one is
`[open]`. **Every live cohort facility is `silent` on both today** (no air permit / Tier
II on file); the Intel positive control carries both `corroborates` (an openly-
evaporative facility's air permit lists its towers and its Tier II inventory carries
treatment chemistry — a constructed calibration vector, not documented Intel data).

## Evidentiary stance

- OHD000001 non-coverage is `[verified]` (the permit's own lifecycle) — and since the
  2026-07-21 withdrawal it is a permanent absence, not a pending one. Do not restate it as
  "the Director's action is still pending"; the Director acted, by declining.
- `facility_own_discharge: unknown` is an **`[open]` gap**, not "confirmed dry": a
  facility with no facility-own NPDES discharge permit is either genuinely dry, or
  blowing down to sewer under a City sewer-use agreement ECHO never sees → a C2
  records request (#1688). Absence is never silently read as corroboration.
- No per-site over-cycling conclusion is asserted here. Re-archetyping a facility is
  B-review work, landed only with a discharge/withdrawal instrument cited.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `oepa-cooling-reconciliation` — Cooling-cycling reconciliation — closed-loop cohort water account

Source: watermark.hydrology.cooling_reconcile — A2 closed-loop cohort × archetype-predicted water account × documented makeup (A1) / blowdown (A2) × A4 independent corroborators (air-permit PM + Tier II chemistry) · License: Public records (Ohio state government) · Access: public · Site scope: state:OH · Refresh: on-demand, last 2026-07-11

Regenerate: `watermark cooling-reconcile --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/oepa/cooling-reconciliation.yaml` | application/x-yaml | no |

### `oepa-ohd000001-coverage` — OHD000001 data-center general-permit coverage — closed-loop cohort

Source: watermark.hydrology.blowdown — site registry closed-loop cohort × the OHD000001 permit lifecycle · License: Public records (Ohio state government) · Access: public · Site scope: state:OH · Refresh: on-demand, last 2026-07-11

Regenerate: `watermark oepa coverage --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/oepa/ohd000001-coverage.yaml` | application/x-yaml | no |

### `oepa-ohd000001-gp` — Ohio EPA Draft General NPDES Permit for Data Center Facilities (OHD000001)

Source: Ohio EPA Division of Surface Water — public notice and permit package · License: Public records (Ohio state government) · Access: public · Site scope: state:OH · Refresh: on-demand, last 2026-06-29

| file | type | lfs |
| --- | --- | --- |
| `documents/oepa/OHD000001_Draft.pdf` | application/pdf | yes |
| `documents/oepa/OHD000001_Draft_PN.pdf` | application/pdf | yes |
| `documents/oepa/OHD000001_Draft.fs.pdf` | application/pdf | yes |

<!-- catalog:end -->
