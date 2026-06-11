# Economics — regional cloud-consumer demand & the public benefits extended to it

> A demand-side companion to [HYDROLOGY.md](HYDROLOGY.md). **Unlike HYDROLOGY, this
> document is not `bosc`-generated** — it is hand-assembled analysis over cited
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
| Implied IT load | **~250–300 MW** (midpoint 275) | `[inference]` | N+1 backup≈IT (`bosc.hydrology.cooling`) |
| Cooling towers | **36** | `[verified]` | air permit |
| Consumptive water | **3.1–10 MGD** | `[inference]` | power × WUE / blowdown × cycles ([HYDROLOGY §3](HYDROLOGY.md)) |

A ~275 MW IT load is a **large** consumer — roughly the scale of a mid-size city's
electricity demand, sited on one corridor. The water consequence is already
modeled in HYDROLOGY (net basin loss ≈ 24–77× the Ottawa 7Q10). This page is the
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

- **~275 MW IT load** and **3.1–10 MGD** consumptive water, against
- **~50 permanent jobs** and a **15-yr/75%** abatement on a **~$500M** build.

That is on the order of **~5–6 MW per job** and a multi-MGD basin draw for a
headcount a single big-box store would exceed. The economic argument the corpus
*substantiates* is structural: **the public subsidizes load and consumption, not
employment** — and does so for a counterparty it cannot name (the Delaware shell;
see DOSSIER §2). `[inference]` This is the demand-side mirror of HYDROLOGY's
"burden already maxed" finding (the 1996 SSO consent decree, the $11.8M I/I
backlog).

## 4. Why this load exists *here* — demand-side drivers `[open]`

These explain the *incentive* to site authorized cloud capacity in a low-cost,
low-scrutiny jurisdiction. The magnitudes are now **document-backed industry
reference ranges** — from the relator's [data appendix](../data/extracted/legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md),
with its cited sources — though whether each applies to *this* campus stays
`[inference]`/`[open]`:

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
| 3.1–10 MGD consumptive; basin-loss multiple | `[inference]` (see HYDROLOGY) |
| ~5–6 MW/job; "subsidizes load not jobs" | `[inference]` |
| GovCloud premium ~20–30%; GPU/rack/facility magnitudes | `[verified: data appendix]` (industry ranges) |
| Whether those magnitudes apply to *this* campus | `[open]` / `[inference]` |

## 6. Consumer energy-price pressure — the demand spillover `[inference]`

The 2026-06-10 facility-design call asked to *"bring in fuel costs at the consumer
level due to macro pressures and data-center demand."* The
[`bosc.economics.energy`](../src/bosc/economics/energy.py) thread sizes that spillover
against **committed EIA consumer prices** (`bosc eia` →
[`data/reference/eia/`](../data/reference/eia/)): Ohio residential electricity (¢/kWh),
residential natural gas ($/Mcf), and total state retail electricity sales.

The link is the facility's first-class total **`facility_draw`** (§1 + the PUE model,
issue #87 — IT load × PUE), not IT load alone:

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

**Nothing on this page promotes a defense-intelligence thesis.** Defense-ecosystem
actors enter only as `[open]` context where the public record already names them
(see COURSE §1.4); the load, the benefits, and the consumption are the findings.
