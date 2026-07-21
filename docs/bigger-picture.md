# The bigger picture — Project BOSC and the data-center boom

Project BOSC is one campus in a national build-out. This page places it against the
broader pattern: what its disclosed plant implies about *compute capacity and
workloads*, whether its *water* problem generalizes across the Maumee basin, and
where Lima is typical of the boom versus an outlier.

> Evidence discipline as elsewhere: `[verified]` (read from a cited record or live
> connector), `[inference]` (a labelled reading), `[open]` (a question, not a finding).

## 1. Compute capacity & workloads

**The disclosed plant.** The Ohio EPA air permit (P0138965) lists **114 backup
generators at ~2,750 ekW** → **~313 MW of backup**, and the design carries **36
cooling towers**. `[verified: data/extracted/permits/3987141.epa.yaml]` Backup is
sized N+1 to the critical IT load, so the campus IT load is on the order of **~275
MW**. `[inference]`

**What ~275 MW buys.** Rack power density is the swing factor. At the conventional
**5–15 kW/rack** the data appendix cites, 275 MW of IT is on the order of **~18,000–
55,000 racks**; at the **40–140 kW/rack** of dense AI/accelerator halls, it is
**~2,000–7,000 racks**. `[inference: data appendix rack-density bands]` The 36
cooling towers and the **1.8–1.9 L/kWh** WUE put the central consumptive draw at
**~3.1 MGD**, with a **3.84 MGD** upper bound at the ~2.2 L/kWh physical evaporative
ceiling — the [hydrology](HYDROLOGY.md) headline. `[inference: derived]`

**Which workloads — the GovCloud question, substantially answered.** Asked directly
about the campus, **Liz Schwab answered in indirect language — "classification
levels"** — which is the tell: this is **regulated / classified-data compute**
(GovCloud-style), not generic commercial hosting. GovCloud capacity carries a **~20–
30% premium** over commercial, and the dedicated, hardened, anti-ram /
security-fenced site plan is consistent with that tier rather than a cost-optimized
commercial build. `[verified: data appendix; site plan]` / `[inference: workload
class]` The end user is **Google** ([Dossier §1](DOSSIER.md)); the workload class is
the regulated-compute tier its government cloud serves. `[inference]`

## 2. The Maumee watershed comparison — does the dilution thesis generalize?

**Lima's finding.** At design low flow, the county plants discharge **more than the
entire 7Q10** of their receiving streams — effluent effectively *undiluted*
([Hydrology](HYDROLOGY.md); [water balance](../data/extracted/commissioners/bosc-water-balance.analysis.md)).
The distinctive cause is **what they discharge into**: tiny tributaries — **Dug Run,
Pike Run** — not a mainstem.

**Basin context (EPA ECHO).** The committed [Maumee NPDES inventory](../data/reference/echo/README.md)
holds **129 POTWs**. Ranked by design flow: `[verified: data/reference/echo/maumee-wwtp.potw.yaml]`

| WWTP | Design flow | Receiving water |
|---|---|---|
| **Fort Wayne WWTP** (IN) | 74.0 MGD | Baldwin Ditch → **Maumee River** |
| Lucas Co WRRF (Toledo) | 22.5 MGD | (Maumee tidal/Lake Erie) |
| **Lima WWTP** | 18.5 MGD | Ottawa River |
| City of Findlay | 15.0 MGD | Blanchard River |
| Defiance WWTP | 12.0 MGD | **Maumee River** |

**Does Fort Wayne mirror Lima?** Partly, and instructively. Fort Wayne is the
basin's **largest** discharger (74 MGD, ~4× Lima) and ECHO flags it on an **effluent
monthly-average limit** — so even the big mainstem plant runs against its permit.
`[verified: ECHO compliance_status]` But Fort Wayne discharges to **Baldwin Ditch →
the Maumee mainstem**, which carries far more dilution than Lima's under-flow
tributaries. So Lima is **distinctive not in size but in receiving-water choice**:
small county plants on intermittent tributaries, where 7Q10 ≈ the discharge itself.

**The shared constraint.** All 129 sit under the **2023 Maumee Watershed Nutrient
TMDL**'s binding phosphorus cap (Lake Erie's largest tributary; the basin
future-growth reserve is only **~1.4–1.5 mt P/spring**). `[verified:
data/reference/hydrology/maumee-tmdl-budget.yaml]` So a new data-center sanitary load
enters a *fully-allocated* basin regardless of which plant takes it.

**Extended basin-wide `[v]`.** The per-plant 7Q10 dilution screen now runs over the
full ECHO POTW inventory (`watermark basin-screen`), not just Lima's plants. The
denominators are the cited fact-sheet 7Q10s plus a **derived** LP3 7Q10 for the four
major USGS-gaged mainstems (Maumee, Auglaize, St. Marys, St. Joseph;
`data/reference/hydrology/low-flow-7q10.derived.yaml`). The honest result: only **8 of
129** POTWs are screenable — **76** have no receiving water in ECHO, **44** discharge
to ungaged tributaries/ditches (reported "no 7Q10" rather than screened against a
downstream river's larger flow), and **1** has no design flow on record. Of the
screenable, two are violations — Lima's **American Bath → Pike Run (0.01:1)** and
**Van Wert → Town Creek (0.03:1)** — while **Decatur → St. Marys (3.1:1)** and
**Defiance → Maumee (6.2:1)** screen "tight." (The Defiance 6.2:1 uses the basin-wide Waterville
proxy; the reach-specific denominator — USGS 04192500, Maumee near Defiance, LP3 7Q10 139.24 cfs —
gives **7.5:1**, still "tight" and slightly *looser* than the proxy, since the near-Defiance mainstem
gage already includes the Auglaize and reads higher than Waterville ~50 mi downstream; #391.) The wide
data gap is itself the finding — Lima's plants are unusually
well-documented, and a basin-wide answer needs each tributary's own cited/gaged 7Q10.

**The network view `[v]`.** The screen is one dimension of a wider cross-site comparison: see
[**The BOSC network**](NETWORK.md) for the full scorecard — the eight onboarded watershed points
as nested nodes on one connected basin (all draining through Defiance → Toledo to Lake Erie under
one TMDL cap), compared across receiving-water regime, grid, economy, and toxics. The headline
holds across every dimension: Lima is distinctive only in its receiving-water *choice* — its
economic shape (manufacturing-heavy, information-sector-absent) and its place in the basin are
typical of the network.

## 3. Boom patterns — where Lima is typical, where it is the outlier

**Typical of the boom `[inference]`:**

- **Secrecy architecture** — a Delaware shell counterparty, NDA-by-default, and an
  economic-development disclosure exemption (ORC §9.66(D)). The thin record is a
  pattern, not a Lima quirk ([Dossier §1](DOSSIER.md)).
- **Incentive shape** — a 15-yr/75% property-tax abatement and publicly-financed
  roadwork for a multi-hundred-MW load and **~50 jobs**: the load-not-jobs subsidy
  the [Economics](ECONOMICS.md) page anatomizes is the boom's standard trade.
- **Demand drivers** — GovCloud premium, the AI rack-density jump, and a sales-tax
  exemption on fast-refreshed hardware are national, not local.

**Where Lima is the outlier `[inference]`:**

- **Water** — siting hundreds of MW of evaporative cooling on a basin whose design
  low flow is *zero* (Ottawa 1Q10 = 0 cfs) and whose tributaries are already
  undiluted is a sharper water constraint than most boom sites face.
- **The local economy** — the [localized baseline](../economics-baseline.md) shows a
  county whose employment **shrank 2.5% (2018→2023)**, concentrated in
  **manufacturing (location quotient 2.08)** with a near-absent **information sector
  (LQ 0.37)**. The campus lands a regulated-compute use onto a shrinking industrial
  base — not onto an existing tech cluster. `[verified: BLS QCEW]`

These tracks deepen as the basin 7Q10 ingest and the capacity model mature; the
[Research course §1.5](COURSE.md) carries them forward.
