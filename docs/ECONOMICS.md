# Economics — regional cloud-consumer demand & the public benefits extended to it

> A demand-side companion to [HYDROLOGY.md](HYDROLOGY.md). **Unlike HYDROLOGY, this
> document is not `watermark`-generated** — it is hand-assembled analysis over cited
> records. Every figure is tagged: `[verified]` (read from a committed extraction
> or cited record), `[inference]` (a labelled derivation), `[assumption]`, or
> `[open]` (a question, not a finding). The spine is civil/land/hydrology; this is
> the second axis — **what the campus consumes, and what the public gives it** —
> not a claim about who benefits.
>
> **Localized baseline.** For the quantitative ground beneath this — Allen County's
> employment by industry, its export-orientation, and the employment trend — see the
> generated [localized economic baseline](../economics-baseline.md) (BLS QCEW), the
> place the ~50 promised jobs and the 75% abatement actually land.

## 1. The load — what the campus draws

The one hard, document-anchored magnitude is electrical:

| Quantity | Value | Tag | Source |
|---|---|---|---|
| Backup generation | **114 gensets × 2,750 ekW ≈ 313 MW** | `[verified]` | OEPA Air PTI **P0138965** (`data/extracted/permits/3987141.epa.yaml`) |
| Implied IT load | **~250–300 MW** (midpoint 275) | `[inference]` | N+1 backup≈IT (`watermark.hydrology.cooling`) |
| Cooling towers | **36** | `[verified]` | air permit |
| Consumptive water | **3.1–3.84 MGD** | `[inference]` | power × WUE / blowdown × cycles, WUE-ceiling capped ([HYDROLOGY §3](HYDROLOGY.md)) |

A ~275 MW IT load is a **large** consumer — roughly the scale of a mid-size city's
electricity demand, sited on one corridor. The water consequence is already
modeled in HYDROLOGY (net basin loss ≈ 24–30× the Ottawa 7Q10). This page is the
*power and tax-base* half of that consumption story.

## 2. The public benefits extended to it

What the public side committed, from the county's own production `[verified:
data/extracted/legal/prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml]`:

| Benefit | Term | Tag |
|---|---|---|
| CRA real-property tax abatement | **15-year / 75%** | `[verified]` (Res #548-25) |
| Capital investment (stated) | **~$500M** | `[verified]` |
| Jobs / payroll committed | **~50 jobs / ~$4M payroll by 2030** | `[verified]` |
| Roadwork (publicly-routed) | **$14.2M** via the Port Authority | `[verified]` (OPC + DOSSIER §6) |

## 3. The mismatch — benefit vs. jobs vs. consumption `[inference]`

Set the verified columns side by side:

- **~275 MW IT load** and **3.1–3.84 MGD** consumptive water, against
- **~50 permanent jobs** and a **15-yr/75%** abatement on a **~$500M** build.

That is on the order of **~5–6 MW per job** and a multi-MGD basin draw for a
headcount a single big-box store would exceed. The economic argument the corpus
*substantiates* is structural: **the public subsidizes load and consumption, not
employment** — and does so for a counterparty it cannot name (the Delaware shell;
see DOSSIER §2). `[inference]` This is the demand-side mirror of HYDROLOGY's
"burden already maxed" finding (the 1996 SSO consent decree, the $11.8M I/I
backlog).

The MW-per-job figure is **modeled, not transcribed here** (issue #1665): it is the
`load_per_job` line of the [`economics-scenarios`](#7-the-scenario-bands--where-these-numbers-are-computed)
feed, and the feed states it as a band — **~5.0–10.0 MW/job**, with the ~5.5 above as
its *reference corner* (the disclosed IT-load central over the agreement's own stated
headcount). The ~5–6 quoted here is that corner; the lean-ops end of the band is roughly
twice it. Quote the band or quote the corner, but say which.

## 4. Why this load exists *here* — demand-side drivers `[open]`

These explain the *incentive* to site authorized cloud capacity in a low-cost,
low-scrutiny jurisdiction. The magnitudes are now **document-backed industry
reference ranges** — from the relator's [data appendix](../data/extracted/legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md),
with its cited sources — though whether each applies to *this* campus stays
`[inference]`/`[open]`.

> **These four are modeled, not asserted here** (issue #1665). Each is an `axis` of the
> [`economics-scenarios`](#7-the-scenario-bands--where-these-numbers-are-computed) feed,
> computed from the committed pooled priors
> ([`data/reference/datacenter-industry/priors.yaml`](../data/reference/datacenter-industry/priors.yaml))
> and carrying every published source behind its band. The numbers below are quoted *from*
> that feed; if the two ever disagree, the feed is right and this page is stale.

- **Authorized-region premium.** Government/sovereign cloud (GovCloud-class,
  FedRAMP / DoD IL2–IL6) runs **~20–30% above commercial** (BCG: up to 30%; AWS
  GovCloud EC2/S3 examples) — a *recurring* premium per hour and per GB. That
  rewards building dedicated, hardened capacity. `[verified: appendix §1]` /
  application-to-campus `[open]`
- **Tax-base forecasting risk.** Ohio's data-center **sales-tax exemption** (DCTE)
  is scored against an equipment-purchase forecast — but AI-class hardware breaks
  that forecast: **GPU servers $200k–$515k**, replaced on a short cycle, ~30–40%
  of cost annually in opex. The abated base may never materialize against the
  consumption. `[verified: appendix §2]` / fiscal outcome `[open]`
- **Refresh / AI-rack cost curve.** Rack power density jumps **5–15 kW → 40–140 kW**
  (conventional → AI/GB200), with projections of 250–900 kW/rack by 2027 — i.e.
  MW/water per rack trend *up*, not flat, across the abatement window.
  `[verified: appendix §2]`
- **Facility footprint.** A single site is a community-scale draw: **25 MW** (the
  Ohio tariff/amendment reference) to 100 MW–1 GW, WUE **~1.8–1.9 L/kWh**, up to
  **~5M gal/day** evaporative — and **blowdown discharge ~20–40%** of cooling
  water, the wastewater tie-in to the WWTP capacity in [HYDROLOGY](HYDROLOGY.md).
  `[verified: appendix §3]`

> These drivers are the substance of the relator's committee **data appendix**
> ([reproduction](../data/extracted/legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md);
> prepared but not submitted). The figures are *industry reference ranges* with
> cited sources — real, documented magnitudes — not facility-specific values for
> the Bistrozzi campus.

## 5. Document-backed vs. analysis — the discipline line

| Claim | State |
|---|---|
| ~313 MW backup / ~275 MW IT; 36 cooling towers | `[verified]` / `[inference]` |
| 15-yr/75% CRA; ~$500M; ~50 jobs; $14.2M roadwork | `[verified]` |
| 3.1–3.84 MGD consumptive; basin-loss multiple | `[inference]` (see HYDROLOGY) |
| ~5–6 MW/job; "subsidizes load not jobs" | `[inference]` |
| GovCloud premium ~20–30%; GPU/rack/facility magnitudes | `[verified: data appendix]` (industry ranges) |
| Whether those magnitudes apply to *this* campus | `[open]` / `[inference]` |

## 6. Consumer energy-price pressure — the demand spillover `[inference]`

The 2026-06-10 facility-design call asked to *"bring in fuel costs at the consumer
level due to macro pressures and data-center demand."* The
[`watermark.economics.energy`](../src/watermark/economics/energy.py) thread sizes that spillover
against **committed EIA consumer prices** (`watermark eia` →
[`data/reference/eia/`](../data/reference/eia/)): Ohio residential electricity (¢/kWh),
residential natural gas ($/Mcf), and total state retail electricity sales.

The link is the facility's first-class total **`facility_draw`** (§1 + the PUE model,
issue #87 — IT load × PUE), not IT load alone. `derive_demand_pressure` persists this
sensitivity to [`data/reference/eia/demand-pressure.yaml`](../data/reference/eia/demand-pressure.yaml)
(per-site, facility-gated) and exposes it as the `economics-demand-pressure` bundle feed
(issue #1105), so the frontend sources these figures rather than the docs hand-copying a
console printout:

| Quantity | Value | Tag |
|---|---|---|
| Annual consumption (draw × 8760 h × ~0.9 load factor) | **~2,700 GWh/yr** | `[inference: derived]` |
| Share of Ohio retail electricity sales (EIA) | **~1.8%** | `[inference: derived]`, EIA-cited |
| Households-equivalent (÷ ~10,500 kWh/home·yr) | **~260,000 Ohio homes** | `[inference: derived]` |
| Stylized price pressure (share × 0.5–1.0 transmission) | **~0.9–1.8%** | `[inference, low]` — *screening only* |

The **demand share and households-equivalent are the robust, EIA-cited headline**; the
price-pressure band is a **deliberately stylized screening sensitivity, not a
forecast** (retail price formation is far more complex than one coefficient, and the
campus buys at wholesale/industrial rates, not the residential price shown). This is
the consumer-cost mirror of the §3 "subsidizes load, not jobs" finding.

## 7. The scenario bands — where these numbers are computed

Everything in §3 and §4 that is not a straight record read is **modeled**, and since
issue #1665 (epic #1659, cluster ME-F) it is modeled *in code* rather than in this page's
prose. [`watermark.economics.scenarios`](../src/watermark/economics/scenarios.py) assembles
it from three committed inputs and publishes the **`economics-scenarios`** bundle feed:

| Input | What it supplies |
|---|---|
| [`cra-agreement.cra.yaml`](../data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml) | the abatement instrument — percent, term, stated capex, stated jobs (**read**, never re-keyed) |
| [`reference/economics/abatement-parameters.yaml`](../data/reference/economics/abatement-parameters.yaml) | this county's cited tax mechanics + the withheld knobs + the what-if corners |
| [`reference/datacenter-industry/priors.yaml`](../data/reference/datacenter-industry/priors.yaml) | the pooled published industry bands (the §4 drivers), each with its sources |

Run it with `watermark scenarios`. What the feed carries:

- **`profiles`** — the four what-if corners (building share × jobs), each priced for
  forgone property tax, un-abated tax kept, sales-tax exemption, net subsidy and per-job.
  These used to be a hardcoded array in the frontend and a table in
  [the-economic-ledger.md](the-economic-ledger.md); there is now one computation.
- **`lines`** — each ledger line as a **band over those corners**.
- **`load_per_job`** — the §3 MW-per-job ratio, as a band.
- **`withheld`** — the four figures the record does not fix, each naming the record that
  would collapse its band.
- **`constants`** — every modeling constant as a cited `ProvenancedValue` (including the
  effective millage, which announces itself as an `[assumption]`).
- **`axes`** — the §4 drivers, with every published source pooled into each band.

**The discipline is enforced in the type system, not asked for in prose.** A band refuses
`low == high`, and every axis, line and withheld input refuses the `verified` tag and any
confidence above `low` — so a scenario *structurally cannot* be published as an assertion.
The feed is also **instrument-gated**: a watershed point with no abatement agreement on its
record has no feed at all, and its report locks and asks for that agreement rather than
being priced off Allen County's mills.

**Nothing on this page promotes a defense-intelligence thesis.** Defense-ecosystem
actors enter only as `[open]` context where the public record already names them
(see COURSE §1.4); the load, the benefits, and the consumption are the findings. The
GovCloud / defense-hardened *scenario profile* is a labeled counterfactual on two knobs —
it prices what such a facility would cost the public and asserts nothing about what this
one is. That question is open; see [defense-nexus.md](defense-nexus.md).
