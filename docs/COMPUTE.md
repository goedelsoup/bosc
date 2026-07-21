# Compute — the facility's AI capacity, derived from disclosed plans

> **Status:** hand-written (as of 2026-07-02) — the figures are **derived** by
> `watermark compute` (`watermark.facility`), which *prints* the three-method bracket to
> the console; this document is authored from that output (unlike [HYDROLOGY](HYDROLOGY.md),
> there is no compute-doc writer yet). Like
> [HYDROLOGY](HYDROLOGY.md), this is a screening derivation, not a measurement.
> Every figure is tagged `[verified]` (read from a record), `[reference]` (a
> published vendor spec), or `[inference]` (assumption/derived). **Nothing here is
> a measured fact about the facility** — the accelerator type, count, and
> utilization are undisclosed; per-chip results are labeled *scenarios*.

This extends the chain [HYDROLOGY](HYDROLOGY.md) already builds — air-permit
gensets → ~275 MW IT load → cooling water — one step further: power / water /
footprint → accelerator count → aggregate FLOPS → "AI capacity." It answers a
single question the disclosures dance around: **how much AI compute does this
facility provide?** The facility's end user is Google (corpus-verified, PAAC
minutes), so the accelerator could be an NVIDIA GPU or a Google TPU; both are
carried as scenarios.

## The method: bracket the IT load three independent ways, then size the silicon

The whole derivation hangs on one number — the campus **IT load (MW)** — which we
estimate three independent ways so the answer is a bracket, not a point. Then a
single accelerator chain turns the IT load into a count and a FLOPS figure for each
candidate chip.

### Method 1 — power / gensets (PRIMARY, best-grounded)

The Ohio EPA air permit **P0138965** (Facility 0302022054) lists **114 emergency
generators at 2.75 ekW** ≈ **313 MW** of backup `[verified: document]`. At hyperscale
N+1 ratios the backup ≈ the IT load, so the campus IT load is **~250–300 MW**
(central **275 MW**). This is the same document-anchored figure
[`watermark.hydrology.cooling`](HYDROLOGY.md) uses for the cooling-water balance; it lives
in [`watermark.facility.power`](../src/watermark/facility/power.py).

#### Cooling / mechanical overhead — total facility draw (PUE)

The genset-derived figure is the **IT** load. `PowerBasis` makes the IT → total-draw
translation a first-class output (issue #87): **`facility_draw` = IT load × PUE**,
where PUE (total facility power ÷ IT power) is a banded `[inference: assumption]` read
from [`rack-density.yaml`](../data/reference/compute/rack-density.yaml). The 2026-06-10
facility-design call indicated **cooling can reach ~30% of *facility* power**, i.e.
IT/total ≈ 0.70 → **PUE ≈ 1.43**, so the band is **1.1–1.43** (cooling share =
`(PUE−1)/PUE`). At the central 275 MW IT load that is a **~303–393 MW** total draw
(central ~348 MW). This is the figure downstream demand/economics ([#91](ECONOMICS.md))
should consume — not IT load alone.

**N+1 cross-check ([#33](../src/watermark/facility/power.py)).** The ~313 MW backup is sized
to IT + mechanical, which implies a PUE of only **~1.14** (313.5 ÷ 275). So the disclosed
backup envelope is consistent with the 275 MW IT figure *only at the efficient end* of
the PUE band; a cooling-dominated PUE (~1.43) would imply either a lower IT load or that
the backup does not cover full mechanical — an open tension, not resolved here. PUE is
**not** used to inflate the accelerator count.

#### On-site generation cycle — simple vs combined (efficiency coefficient)

Beyond *how much* power, `PowerBasis` carries *how* it is generated (issue #90, from
the 2026-06-10 call's "single- vs double-phase" distinction):

- **simple-cycle (single-phase)** — the prime mover drives the generator directly;
  exhaust heat is lost. Net electrical efficiency ~**0.38** `[inference: assumption]`
  (band 0.33–0.43), heat rate ~9.0 MMBtu/MWh.
- **combined-cycle (double-phase)** — exhaust heat is recovered to raise steam and
  drive a second-stage steam turbine (cogeneration). Net efficiency ~**0.55**
  `[inference: assumption]` (band 0.50–0.62), heat rate ~6.2 MMBtu/MWh — less fuel
  per MWh (the lever the consumer fuel-cost thread, [#91](ECONOMICS.md), needs) **at
  the cost of a steam/condenser water loop**: an *additional* ~**1.3 MGD** consumptive
  pathway beyond data-hall cooling, cross-referenced to
  [`watermark.hydrology.cooling`](HYDROLOGY.md).

The net electrical efficiency is the **"power-loss coefficient"** (fuel chemical
energy → delivered MWh) as a banded assumption per cycle. **Open evidence question:**
the disclosed 114 × 2.75 ekW units are emergency **backup** reciprocating gensets
(simple-cycle by nature); whether any *primary* on-site generation exists, and its
cycle, is unproven (depends on [#33](../src/watermark/facility/power.py)) — so both configs
are labeled **scenarios**, and the combined-cycle steam water is conditional (likely
ruled out today, not added to the water balance).

The accelerator chain:

> IT load (MW) → **usable accelerator power** = IT load × *accelerator-power fraction*
> (the share of IT power reaching accelerators vs CPU host / storage / network,
> assumed **0.50–0.70** `[inference: assumption]`) → **accelerator count** =
> accelerator power ÷ per-accelerator all-in power → **aggregate FLOPS** = count ×
> per-accelerator peak FLOPS.

#### Per-data-center-profile chip-level overhead

The per-accelerator **all-in power** is `chip TDP × overhead` (host CPU / NIC / PSU /
in-rack conversion). A single global `host_overhead_factor` (**1.30**) is the default
the per-chip scenarios use, but that overhead differs by deployment (issue #89), so
`rack-density.yaml` carries named **`datacenter_profiles`** — each with the overhead
split into a **host** and a **network** share (the network share reflecting the 1
InfiniBand + 1 Ethernet NIC complement, [#88](../data/reference/compute/rack-density.yaml)),
plus the cooling / PUE it pairs with ([#87](#method-1--power--gensets-primary-best-grounded)):

| profile | host × net = total | all-in W (H100) | ≈ H100 @ central IT |
|---|---|---|---|
| Air-cooled HGX | 1.20 × 1.09 = 1.31 | ~916 W | ~180,000 |
| Liquid HGX | 1.18 × 1.07 = 1.26 | ~884 W | ~187,000 |
| Liquid GB200 NVL72 | 1.10 × 1.05 = 1.16 | ~808 W | ~204,000 |

`derive_compute_capacity` runs these as additional labeled `[inference: assumption]`
scenarios (counts in equivalent-H100 units at the central IT load, so profiles are
comparable); the legacy single-overhead per-chip behavior is preserved as the default.
Lower-overhead liquid deployments fit *more* accelerators at the same IT power. Every
figure is an assumption — no deployment is disclosed.

### Method 2 — cooling-water back-solve (independent cross-check)

The disclosed cooling consumptive figures from `CoolingBasis` — power × WUE low
≈ **3.1 MGD**, WUE-ceiling-capped high ≈ **3.84 MGD** — divided back by the
water-use effectiveness (WUE ≈ 1.8 L/kWh) recover an IT energy → IT load. The low
figure inverts to **~275 MW** `[inference: derived]`, exactly recovering Method 1 —
the loop closes (the buildout scenario *derived* 3.1–3.84 MGD *from* 275 MW, so going
backward validates it). The FM-2 blowdown method would put the high at 10 MGD, but
that implies ~5.7 L/kWh — unreachable for cooling — so it is capped at the physical
evaporative-WUE ceiling (FM-2 is industrial discharge, not pure cooling blowdown); the
capped high inverts to **~336 MW**, reported as an **upper bound only**
`[inference, low confidence]`. This method **shares Method 1's WUE assumption**, so
it is a consistency check, not a fully independent line of evidence — stated plainly.

### Method 3 — building footprint / floorspace (WEAKEST — flagged heavily)

The assembled campus **land** area is **~340 acres** (recorded Bistrozzi parcels,
[`data/reference/periplus/bosc-parcels.geojson`](../data/reference/periplus/);
see [seller-land-packets](../data/extracted/aedg/seller-land-packets.land.yaml)). The
chain: land × assumed *building-coverage fraction* (0.15–0.30) → building floor area
× assumed *data-hall white-space fraction* (0.40–0.55) → rack count at AI rack
density (**40–140 kW/rack**) → IT power. This lands at **~1,100–10,300 MW**
`[inference: assumption]` — far above Methods 1–2.

**Per-rack floor area comes from a documented `rack_profile`** (issue #88), not a bare
scalar: floor area = `depth × width × aisle factor`. The 2026-06-10 call specified
**32U+ racks** with a **non-standard (extended) depth** for GPU / liquid-cooling
layouts — modeled as **1200 mm** (vs the standard ~1070 mm), giving **~33 sqft/rack**
(the aisle factor is tuned so the *standard* depth reproduces the legacy ~30 sqft).
The extended depth raises floor area per rack, so it **shrinks** the rack count the
land could hold — a representable lever on the envelope. Still an assumption: no rack
layout is in the 95% SPS plans (sheet 1A-C-3104 is grading/storm only).

That is the *point*, and the honest reading of it: **land is not floor area**, and
no building footprint is documented in the 95% SPS plans (sheet **1A-C-3104** is
grading & storm only — no floor schedule; see
[`plans/`](../data/extracted/plans/)). The data-hall footprint that *would* anchor
this method — the **air permit (PTI P0138965)** groups its emission units in **three
generator/cooling-tower blocks**, corroborating roughly **three halls** — is now
**committed** ([`permits/4132514.epa.yaml`](../data/extracted/permits/4132514.epa.yaml),
final PTI; completeness audit §4). But the issued permit gives the emission-unit
*grouping*, **not a building footprint or floor schedule**.

**A building footprint is now documented, from a different instrument.** The Allen
County Recorder **Notice of Commencement** (R.C. 1311.04, Instr. **202606250006699**,
recorded 2026-06-25) states the building footprint plainly in item 1: **283,497 sf**
`[verified: document]`
([`recorder/202606250006699.notice.yaml`](../data/extracted/recorder/202606250006699.notice.yaml)).
This is the first primary-source floorspace figure for the campus — it does not
change the calculation above (which still derives floor area from land × an
assumed coverage fraction, not from this disclosed number) or resolve Method 3's
other caveats, but the method's own footprint envelope can now be sanity-checked
against a documented figure rather than an assumption alone: at the low end of the
coverage-fraction band (0.15) the ~340-ac campus implies **~2.2M sf** of building
footprint — the disclosed 283,497 sf is one building (the improvement this Notice
covers), well within that envelope, not the whole campus footprint. Method 3 bounds
the *physical envelope* the land could hold, and it sits an order of magnitude
above the power method precisely because **power, not floor space, is the binding
constraint**. Every input is an assumption; this is the loosest bracket and is
presented as such.

## The derived bracket

**IT load.** Methods 1 and 2-low agree to within ~0.1 MW (the loop closes); Method 2's
cooling-water upper bound and Method 3's footprint envelope flag how much *room* exists
above the operative figure. The operative, document-anchored figure is **~250–300 MW**.

| method | IT load (MW) | tag |
|---|--:|---|
| 1. power / gensets (primary) | **250–300** (central 275) | `[verified: document]` — air permit P0138965 |
| 2. cooling-water back-solve | 275 (low, recovers #1) … 336 (capped upper bound) | `[inference: derived]` — shares the WUE assumption |
| 3. building footprint (weakest) | ~1,100 … ~10,300 (physical envelope) | `[inference: assumption]` — land ≠ floor area |

**Equivalent H100-class GPUs** at the central IT load: **~137,000–231,000**
`[inference: derived]` — a hyperscale-AI deployment by any measure.

**Per-chip scenarios** over the power-method IT load. Counts are conditional on the
chip; FLOPS are **peak / nameplate** (delivered throughput is derated separately by
a model-FLOPS-utilization assumption, MFU ≈ 0.40):

| if the accelerator is … | accelerators | peak BF16 dense (EFLOP/s) | peak FP8 dense (EFLOP/s) | delivered BF16 @MFU (EFLOP/s) |
|---|---|--:|--:|--:|
| H100-class (Hopper) | 137k–231k | 136–228 | ≤457 | ~72 |
| H200-class (Hopper) | 137k–231k | 136–228 | ≤457 | ~72 |
| B200-class (Blackwell) | 96k–162k | 216–364 | ≤727 | ~114 |
| GB200 NVL72 (Blackwell) | 80k–135k | 200–337 | ≤673 | ~106 |
| TPU v5e (Google) | 548k–921k | 108–181 | — (INT8) | ~57 |
| TPU v5p (Google) | 349k–587k | 160–269 | — (INT8) | ~85 |
| TPU v6e Trillium (Google) | 321k–538k | 294–494 | — (INT8) | ~155 |

Across every plausible chip the facility lands at **hundreds of EFLOP/s of peak
dense BF16** and **tens of thousands to hundreds of thousands of accelerators**. The
methods disagree on the *ceiling* (footprint says the land could hold far more), but
they agree on the *operative* figure (power), and the conclusion — a frontier-scale
AI compute facility — is robust to the disagreement.

## Inputs and their provenance

| input | value | source |
|---|---|---|
| Genset count × rating → backup → IT load | 114 × 2.75 ekW → 313 MW → 275 MW | `[verified: document]` OEPA Air PTI P0138965 |
| PUE → total facility draw | 1.1–1.43 → ~303–393 MW (central ~348 MW) | `[inference: assumption]`/`[inference: derived]` cooling ≤~30% of facility power (#87) |
| Generation net efficiency — simple / combined cycle | 0.38 / 0.55 (heat rate ~9.0 / ~6.2 MMBtu/MWh) | `[inference: assumption]` power-loss coefficient per cycle (#90) |
| Combined-cycle steam-loop water | ~1.3 MGD additional | `[inference: assumption]` conditional; cross-ref `watermark.hydrology.cooling` (#90) |
| Cooling consumptive (low / high) | 3.1 / 3.84 MGD | `[inference: derived]` `CoolingBasis` (power×WUE; FM-2 blowdown×cycles capped at the WUE ceiling) |
| WUE | 1.8 L/kWh | `[inference: assumption]` evaporative hyperscale (shared with cooling) |
| Campus land area | ~340 acres | `[verified: document]` recorded Bistrozzi parcels geojson |
| Accelerator chip specs (TDP, peak FLOPS) | per chip | `[reference]` [`data/reference/compute/accelerators.yaml`](../data/reference/compute/) (vendor datasheets, as of 2026-06) |
| Rack power density (40–140 kW) | bands | `[reference]` in-corpus relator data appendix (cites NVIDIA HGX guidance) |
| Accelerator-power fraction | 0.50–0.70 | `[inference: assumption]` share of IT power to accelerators |
| Host overhead (chip→all-in W) — default | ×1.30 | `[inference: assumption]` CPU/NIC/PSU share |
| Per-profile overhead (host × network) | 1.16–1.31 | `[inference: assumption]` `datacenter_profiles`; 1 IB + 1 NIC (#89, 2026-06-10 call) |
| Rack profile (32U+, non-standard depth) | 1200×600 mm → ~33 ft²/rack | `[inference: assumption]` `rack_profile` (#88, 2026-06-10 call) |
| Building coverage / white-space | 0.15–0.30 / 0.40–0.55 | `[inference: assumption]` footprint method only |
| MFU (delivered throughput) | 0.40 | `[inference: assumption]` typical large-scale training |

## Caveats (read these)

- **The accelerator is undisclosed.** We do not know Google's chip, count, or
  utilization. Every per-chip row is an "if X" scenario; none is a claim about the
  facility's contents.
- **Peak ≠ delivered.** The headline FLOPS are nameplate. Real training throughput is
  a fraction (MFU) of peak; the delivered column applies a labeled 40% MFU and is
  kept strictly separate.
- **The footprint method is weak.** Land area is not floor area; no building footprint
  or data-hall area is documented in the plans. Method 3 is a physical upper envelope,
  not a likely value.
- **The keystone power figure is now document-committed — with one caveat.** The Ohio
  EPA air permit (PTI **P0138965**) is **committed** as of 2026-06-15
  ([`permits/4132514.epa.yaml`](../data/extracted/permits/4132514.epa.yaml), final PTI;
  completeness audit §4): it confirms the **115-genset count** (114 hall + 1 HUBGEN) and
  the **three-block emission-unit grouping**. But the per-engine **2.75 ekW** behind the
  313 MW backup is **redacted as trade secret** in the final permit (it rests on the draft
  public notice), and the permit carries **no plot plan / floor schedule** — so the
  **three-hall footprint** that would re-ground Method 3 to a floor area is still not in hand.
- **Method 2 is not fully independent.** It reuses Method 1's WUE assumption, so it
  cross-checks the loop rather than corroborating from a wholly separate source.
- **Specs drift.** The accelerator reference data is as of June 2026 with cited
  sources ([`data/reference/compute/README.md`](../data/reference/compute/README.md));
  vendor figures change generation to generation.

See [`watermark.facility`](../src/watermark/facility/) for the code and
[`tests/facility/`](../tests/facility/) for the offline checks (including the
assertion that `facility.power`'s IT load stays equal to `cooling.py`'s).
