# Data-center industry reference priors

A pooled **meta-analysis** of published data-center industry sources, assembled to
**bound the uncertainty engine's `[assumption]` inputs** (epic #271, flagship #269)
where the Lima record is silent, non-binding, or modeled. These are
**published reference ranges / standing assumptions**, not document-derived figures —
the demand-side analogue of the hydrology reference parameters, and a structured
companion to the relator's committee
[data appendix](../../extracted/legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md).

## What this is, and isn't

The five `#233` report narratives all turn on numbers the public record withholds — the
building share of the build, the job count, the cooling design, the equipment spend.
The honest move is not to blank them or guess a point estimate, but to **model each as a
band across explicit, sourced scenarios**. This dataset is the _prior-elicitation_ step:
for each load-bearing unknown, it pools multiple **independent** published estimates into
a low / central / high band that the engine reads.

**The discipline is load-bearing.** Every prior here is `[reference]` / `[assumption]` —
**"industry reference, _not_ this campus."** A meta-analysis bounds the unknowns so the
engine's output bands are defensible; it does **not** resolve the `[open]` questions
(which workload class Lima is, the cooling design, the defense nexus). Only disclosure
closes those. This elicits priors; it never manufactures a facility fact. Each prior
carries a `lima_status` to keep that line explicit.

## Files

| File | What | Source |
|---|---|---|
| `priors.yaml` | The pooled priors: per-unknown low/central/high band + every source it pools + a `lima_status`. Read by `watermark.*`/the frontend engine for the `[assumption]` bounds. | Hand-assembled from published sources (`source: reference`); curated, not connector-regenerable. Citations carry URLs. |

## The priors, and what the supplement adds

| Prior | Pooled band | What the independent sources establish |
|---|---|---|
| **Building (abated real-property) share of capex** | 0.20 – **0.30** – 0.45 | The building _shell_ is only ~15–21% of total cost (Epoch AI, US Chamber CTEC, McKinsey, BlueCap); Ohio's CRA abates real property while the DCTE exempts equipment + construction materials (R.C. 122.175). The split is genuinely fuzzy — which is the case _for_ a band. The corpus's prior single 0.35 sits inside it. |
| **Jobs per MW (automated hyperscale)** | 0.10 – **0.18** – 0.30 /MW | ~20–40 operators per 100 MW (Brookings, Good Jobs First, Built In, Broadstaff). For ~275–348 MW that's ~28–105 jobs — independently brackets the CRA's non-binding ~50 and the leaner 30. |
| **Subsidy per job (benchmark)** | $1.4M – **$2.0M** – $6.4M | Good Jobs First: data-center megadeals average ~$2M/job. BOSC's modeled per-job subsidy lands squarely in the band — **typical, not anomalous**. (A corroboration of the ledger output, not an input.) |
| **Sales-tax exemption is the dominant subsidy** | corroboration | Virginia JLARC: the exemption was **81% of all state incentive spend** ($1.02B, FY2024). Ohio's DCTE ballooned to **~$16B**, prompting a move to suspend new grants (HB957). Independent confirmation of the ledger's "second subsidy no one scores." |
| **GovCloud / sovereign-cloud premium** | 0.20 – **0.25** – 0.30 | ~20–30% recurring (BCG, AWS, CapLinked, Matlock — already in the data appendix; homed here). |
| **Cooling WUE (evaporative vs closed-loop)** | 0.2 ‖ **1.8** – 1.9 L/kWh | Bimodal by design — evaporative ~1.8–1.9 vs closed-loop ~0.2–0.3 (Green Grid, EESI, Vertiv, Meta/MS, LBNL county-water layer; Danfoss/Google as a deployed named-vendor closed-loop datapoint — `[reference]`, band unchanged). The water draw swings an order of magnitude on a design fact the record withholds. |
| **Waste-heat reuse (dump vs. recover)** | reference | A third cooling-design axis: rejected heat dumped (towers/dry coolers) vs recovered to on-site / district heat. Named as a deployed hyperscale option by one vendor release (Danfoss/Google, Jan 2024) — `[reference]`, no band on a single promotional source; `lima_status` open. Couples to the WUE `[open]` where recovery displaces evaporative rejection. |
| **National data-center load share** | 4.4% (2023) | The **primary** DOE/LBNL report (176 TWh, 4.4%, 2–3× by 2028) — upgrades the second-hand figure GRID.md cites. |
| **AI refresh + rack density** | reference | 3–5 yr refresh (~30–40% opex/yr), rack density 5–15 kW → 120–140 kW (NVIDIA HGX, IntuitionLabs, McKinsey/Dell'Oro — data appendix §2). Drives the _recurrence_ of the DCTE exemption. |

## Gaps

- **No facility-specific values.** Nothing here is read from a Lima record; every prior's
  `lima_status` is `open` / `comparative` / `context`. The engine bands are only as tight
  as disclosure allows — that is the point.
- **Curated, not auto-regenerable.** Unlike the connector pulls (EIA, ECHO, USGS), this is
  hand-assembled from published reports and re-checked by hand. Reference figures as of
  **June 2026**; cloud pricing, GPU costs, and refresh cycles move fast.
- **Two priors lean on the data appendix's own pool** (GovCloud premium, AI refresh) rather
  than fresh independent sources — corroboration there is the relator's, re-homed for the
  engine.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `datacenter-industry` — Data-Center Industry Reference Priors (Uncertainty Bands)

Source: Pooled meta-analysis of published industry reports (Epoch AI, US Chamber CTEC, McKinsey, Good Jobs First, Brookings, Virginia JLARC, DOE/LBNL, Green Grid/Vertiv) · License: Pooled third-party published reports (per-prior sources cited) · Access: public · Site scope: basin-shared · Refresh: on-demand, last 2026-06-17

| file | type | lfs |
| --- | --- | --- |
| `reference/datacenter-industry/priors.yaml` | application/x-yaml | no |

<!-- catalog:end -->
