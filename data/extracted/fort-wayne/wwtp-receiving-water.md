# Fort Wayne WWTP (NPDES IN0032191) — receiving-water characterization

Reviewed synthesis of the basin's largest POTW against its low-flow receiving water. Resolves
issues **#358** (the 7Q10 denominator) and **#359** (the NPDES/DMR/enforcement extract), and — with
the **draft 2026 permit renewal now in hand (#1453)** — replaces the earlier *derived* low-flow proxy
with the permit's **cited regulatory Q7,10**, resolves the compliance-flag reconciliation, and records
the Maumee TMDL boundary-condition answer and the CSO consent-decree endgame. Tags follow the project
vocabulary (`[verified]` / `[inference]` / `[reference]` / `[open]`).

Sources, all regenerable / chain-of-custody:

- **Draft permit renewal + Fact Sheet** — `data/documents/idem/fort-wayne/notice_20260629_npdes_in0032191.pdf`
  (Public Notice 20260529-IN0032191-D+SMV, dated 2026-05-29; comments closed 2026-06-29). The
  authoritative source for the receiving water, the cited Q7,10, and the WQBEL schedules below.
- **Reported effluent record (DMR):** [`wwtp-in0032191.dmr.yaml`](wwtp-in0032191.dmr.yaml) —
  `watermark dmr IN0032191 --start 2023-01-01 --end 2026-06-30 --design-flow 74.0`.
- **Maumee Watershed Nutrient TMDL** (Ohio EPA 2023, US EPA-approved) — `data/documents/maumee-tmdl/`
  (Table ES1, boundary conditions).
- ECHO inventory entry: `data/reference/echo/maumee-wwtp.potw.yaml` (IN0032191).

## 1. The facility

| Field | Value | Tag |
|---|---|---|
| Permit | NPDES **IN0032191**, individual, **major** | `[verified: ECHO / permit]` |
| Facility | **City of Fort Wayne P.L. Brunner Water Pollution Control Plant**, 2601 Dwenger Ave | `[verified: permit]` |
| Status | permit **Admin Continued** (prior term expired 2026-02-28); 5-yr renewal proposed | `[verified: ECHO / permit]` |
| Design flow | **74.0 MGD** average (≈ 114.5 cfs); **100 MGD peak** (the mass-limit basis) | `[verified: permit]` |
| Receiving water | **Maumee River** via **Outfall 001** — Bullerman Ditch-Maumee River watershed, HUC-12 **041000050102**, AU_ID **INA0512-02** | `[verified: permit]` |
| Outfalls | continuous effluent **001** (+ **002**) plus **39 CSO/bypass outfalls** — a combined-sewer system | `[verified: ECHO DMR / permit]` |

**Receiving-water correction.** The ECHO inventory labels the receptor "Baldwin Ditch"; the draft
permit's Fact Sheet is authoritative and states the continuous discharge (Outfall 001) is to the
**Maumee River** directly. Baldwin Ditch is one of the *CSO-impacted* segments (CSO Outfalls 061/062,
joining the Maumee near CSO Ponds 1–2) governed by the wet-weather subcategory below — not the
Outfall 001 receptor. The Maumee-mainstem read stands. `[verified: permit]`

## 2. The corrected low-flow denominator — now a *cited* regulatory value (#358) `[verified: permit]`

The draft permit Fact Sheet gives the receiving water's **cited seven-day, ten-year low flow**:

> "The receiving water has a seven day, ten year low flow (Q₇,₁₀) of **40 cubic feet per second
> (26 MGD)** at the outfall location; this provides a **dilution ratio of receiving stream flow to
> treated effluent of 0.35:1**." — Fact Sheet, "Receiving Stream"

This **supersedes** the derived headwaters proxy this file previously carried (the LP3 sum of the
St. Joseph + St. Marys near-Fort-Wayne gages, 54.06 + 15.65 = **69.71 cfs**, `source=derived`). The
old §6 open item — "a cited regulatory 7Q10 / WLA would replace the derived proxy with a
`source=document` value" — is now **closed**.

Notably, the regulatory Q₇,₁₀ (**40 cfs**) is *materially lower* than the naive tributary-sum proxy
(70 cfs): IDEM's low flow at the specific outfall reach is not the arithmetic sum of the two
tributaries' independent minima. The regulatory value governs, and it makes the assimilative picture
**tighter**, not looser.

### Screen against the cited denominator

| Discharge basis | MGD | cfs | dilution (Q₇,₁₀ ÷ discharge) | band |
|---|---|---|---|---|
| Design 74.0 MGD (permit basis) | 74.0 | 114.5 | **0.35 : 1** | **effluent-dominant** |
| Actual mean 44.26 MGD (2023–2026 DMR) | 44.3 | 68.5 | **0.58 : 1** | effluent-dominant |

**Verdict (revised).** At the outfall, the Fort Wayne WWTP is **effluent-dominant at low flow** on the
permit's own numbers: the receiving Maumee carries roughly one-third the plant's design flow, and only
~0.6× its realistic annual flow, at Q₇,₁₀. This is **more effluent-dominated than the earlier derived
read suggested** (0.35:1 vs the proxy's 0.61:1) and revises the #358-era "mainstem = far more dilution
than Lima" framing: the Maumee at Fort Wayne is effluent-dominated at low flow, materially so through
the Aug-2025 → Mar-2026 drought. `[verified: permit + DMR]`

## 3. Actual discharge vs. permitted design `[verified: ECHO DMR, 2023–2026]`

The extended DMR pull (primary outfall 001, parameter 50050, 41 reported monthly-average months over
2023-01 → 2026-06):

- **mean 44.26 MGD** (≈ 68.5 cfs), min 28.23, max 87.88 — **59.8% of the 74.0 MGD design flow**

The plant runs at roughly three-fifths of its permitted average design on an annual-average basis;
the design flow is a conservative (worst-case) screening numerator for utilisation, but — per §2 —
even the *realistic* flow is effluent-dominant against the cited Q₇,₁₀.

## 4. New WQBELs and the renewal terms `[verified: permit Fact Sheet]`

The renewal adds water-quality-based effluent limits from RPE analyses in the **2025-12-23** WLA
(supplementing the 2021-10-21 WLA). Mass limits for CBOD₅/TSS/TRC/ammonia are computed at the
**100 MGD peak** design flow per IDEM's CSO max-flow policy.

| Parameter | Renewal term | Note |
|---|---|---|
| **Total phosphorus** | 1.0 mg/l (sliding scale or 1.0, whichever more stringent) | unchanged from prior permit |
| **Total nitrogen** | **monitor-only** (≥ 1×/month; report conc. + load, TKN + NO₂/NO₃) | first-cycle TN data collection |
| **Cadmium** *(new)* | final 0.0015 mg/l MO / 0.0031 mg/l daily max | **60-month** compliance schedule (Part I.E) |
| **Cyanide** *(new)* | final 0.0046 mg/l MO / 0.0093 mg/l daily max | **60-month** compliance schedule |
| **Lead** *(new)* | final 0.010 mg/l MO / 0.020 mg/l daily max | **60-month** compliance schedule |
| **Copper** | no limit (PEQ < PEL); quarterly monitoring retained | RPE did not trigger a limit |
| **Mercury (SMV)** | interim **1.8 ng/l** (12-mo rolling avg of daily max); final WQBELs 1.3 / 3.2 ng/l | Streamlined Mercury Variance renewed (in effect since 2007); wildlife criterion, no mixing zone |
| TSS | 10 mg/l MO / 15 mg/l weekly (mass @ 100 MGD) | see §5 |
| CBOD₅ | 5.0 mg/l MO / 7.5 mg/l weekly (mass @ 100 MGD) | 85% removal waived (CSO policy) |

The new Cd/CN/Pb limits were added because prior-cycle monitoring showed a **reasonable potential to
exceed** water-quality criteria; each carries a 60-month schedule of compliance with interim weekly
monitoring. `[verified: permit]`

## 5. Compliance — the TSS SNC mechanics, quantified (#359) `[verified: ECHO DMR]`

Over the full 2023-01 → 2026-06 DMR window, ECHO flags **exactly two** effluent numeric exceedances —
**both TSS, both at Outfall 001, both ECHO violation code E90** ("DMR, Limited - Numeric Violation"),
**both severity 2 ("Non-Reportable Noncompliance")**:

| Period | Parameter | Basis | Reported | Limit | Exceedance | ECHO class |
|---|---|---|---|---|---|---|
| 2024-01-31 | TSS | weekly avg (MX WK AV) | 17 mg/l | 15 mg/l | **+13%** | E90 / NRNC (sev. 2) |
| 2026-02-28 | TSS | monthly avg (MO AVG) | 10.2 mg/l | 10 mg/l | **+2%** | E90 / NRNC (sev. 2) |

The ECHO effluent-chart header carries the facility SNC label **"Effluent – Monthly Average Limit"**,
consistent with the Feb-2026 monthly-average TSS exceedance. ECHO's facility-level compliance roll-up
additionally shows **Category I SNC** (status date 2026-03-31; 8 quarters NC / 7 SNC, pollutant TSS)
— a figure from ECHO's **Detailed Facility Report / quarterly-noncompliance history**, a different
service than the effluent chart and not carried in the committed DMR artifact. `[reference: ECHO DFR]`

**Read it precisely, not as a headline.** The only numeric exceedances of record are two *minor* TSS
overages (+13% weekly and +2% monthly), and ECHO itself classifies **both as Non-Reportable
Noncompliance** (the lowest severity). Two NRNC TSS overages do not by themselves constitute a pattern
of significant effluent exceedance; the Category-I SNC flag reflects **unresolved-RNC quarterly
accounting**, not a "significant violator" story. This **resolves** the prior open reconciliation item
(which read the SNC label as uncorroborated by *any* exceedance). `[verified: ECHO DMR]`

> **Connector fix (#1453).** The earlier artifact reported *zero* exceedances because ECHO returns
> `ExceedencePct` as a percent **string** (`"13%"`) that the parser dropped on the `%`. The DMR
> connector now parses that string and surfaces each row's ECHO-reported `NPDESViolations`
> (code / description / severity) — so the two E90 TSS violations are captured through the documented
> ECHO path, never computed here by comparing a value to its limit.

## 6. The Maumee TMDL — Fort Wayne is a boundary condition, not an allocated source (closes #235's scope question) `[verified: TMDL]`

The 2023 Ohio EPA **Maumee Watershed Nutrient TMDL** (US EPA-approved) does **not** allocate Indiana
sources. Its executive summary is explicit:

> "The Maumee watershed extends into the neighboring states of Michigan and Indiana. **Ohio's
> delegated Clean Water Act authority does not extend to sources in these states.** Therefore,
> allocations do not include sources in these states; rather, **a boundary condition load is set**
> that can be used by those states in their water quality planning processes." — TMDL, Executive Summary

**Table ES1** sets that load for Indiana:

| Allocation type | Spring-season TP (metric tons) | Daily TP (kg) |
|---|---|---|
| Boundary condition: Michigan | 180.7 | 1,180.9 |
| **Boundary condition: Indiana** | **48.0** | **313.6** |
| Ohio wasteload allocation | 109.3 | 714.6 |
| Ohio load allocation | 555.9 | 3,633.2 |

Fort Wayne WWTP (IN0032191) is **absent** from the TMDL's individual NPDES wasteload allocations
(Appendix 4 lists Ohio permits only — the "IN00…" entries there are Ohio industrial permit numbers,
e.g. GM Defiance, not Indiana permits). **Net: Fort Wayne is the basin's upstream boundary-condition
load (part of Indiana's 48.0 MT spring-TP / 313.6 kg/day boundary condition), not an allocated
source.** This answers the scope question #235 held open — the cross-state TMDL does not reach the
Fort Wayne discharge. `[verified: TMDL]`

- Indiana's counterpart instrument (the GLWQA **Domestic Action Plan**) has had **no public update
  since 2023** — itself a finding on the accountability gap on the Indiana side. `[reference / open]`
- The TMDL / research pass flags the **St. Marys** tributaries as among the highest-DRP monitored
  waters; not yet grounded to a specific TMDL table here. `[open]`

## 7. The CSO consent-decree endgame (#1453) `[verified: permit]`

The draft permit's Compliance Status and CSO sections state the enforcement posture directly:

- The city is under **Federal Consent Decree No. 2:07-cv-00445** (N.D. Ind.) and **IDEM Agreed Order
  2008-178333-W** for its CSO Long Term Control Plan.
- **All CSO LTCP control measures were fully implemented in 2025**; the city is now in
  **post-construction monitoring (PCM)**.
- The **Final Post-Construction Monitoring Report** (with the PCM conclusions) is **still owed**,
  required "in accordance with Federal Consent Decree No. 2:07-cv-00445."
- The **CSO Wet Weather Limited Use Subcategory** (EPA-approved 2023-10-18; effective on full LTCP
  implementation) applies to the CSO-impacted waters — St. Mary's River, Natural Drain #4, St. Joseph
  River, Spy Run Creek, **Baldwin Ditch**, Harvester Drain, and the Maumee River.
- Adjacent: City Utilities won a **$135k IDEM CWA §205(j) grant** (2026-06-19) to update the Lower
  St. Joseph watershed plan. `[reference]`

## 8. Open

- **PACER docket pull (2:07-cv-00445, N.D. Ind.):** the PCM filings and any termination/satisfaction
  motion on the docket are not yet pulled (PACER is paywalled). The permit is the primary-source anchor
  for the posture above; the docket entries themselves remain an unmet, documented pull. `[open]`
- **Final permit + responsiveness summary:** not yet issued as of 2026-07-13 (comments closed
  2026-06-29). Commit + extract when IDEM issues them, and reconcile any change from the draft terms. `[open]`
- The 39-outfall **CSO/combined-sewer** dimension is wet-weather, distinct from the continuous
  effluent screened here; not separately characterized. `[open]`
