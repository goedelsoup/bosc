# CLAUDE.md — `watermark.hydrology`

Water-balance / stormwater modeling of the Lima municipal loop. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md).

- **Tag every quantity with provenance.** Inputs/outputs carry `source`
  (`assumption` / `reference` / `connector` / `derived`), `citation`, `confidence`,
  `asof`. An `assumption` is a stated modeling input, never presented as fact.
  Committed reference inputs live in [`data/reference/hydrology/`](../../../data/reference/hydrology/);
  scenarios in [`data/scenarios/`](../../../data/scenarios/).
- **Live external data goes through `connectors/`** (see its own CLAUDE.md), never
  ad-hoc HTTP elsewhere in this package.
- **Tiers matter:** Tier-0/Tier-1 SCS screening (`tier1.py`, `solver/`) is auditable
  and fast — *not* a substitute for SWMM/HEC-RAS. The `swmm/` subpackage builds INP
  decks for the real engine; don't blur the two.
- The cited regulatory **7Q10** lives in `lowflow.py`; the NWIS observed minimum only
  sanity-checks it — don't substitute one for the other.
- **The design-storm peak has three coupled knobs — don't touch one alone** (WS-10 / #1610).
  (1) The **rainfall distribution** (`solver/rainfall.py`) is *built*, not tabulated: the NRCS
  WinTR-20 algorithm published in NEH-630 Ch. 4 §630.0407, driven by the duration ratios embedded
  in the standard Type II (fig. 4-46 col. 3), at its native 0.1-hr (6-minute) step. A 1-hour table
  interpolated onto a 0.1-hr grid understates the central burst ~3x, which biases every short-Tc
  catchment low. `build_distribution(ratios)` is the seam a site-specific NOAA Atlas-14 ratio set
  plugs into — NEH-630 §630.0403 B(8) says the legacy Type II should be *discontinued* in Atlas-14
  areas, and Lima's own committed Atlas-14 point gives a 60-min/24-hr ratio of 0.51 against Type
  II's 0.454, so Type II still under-states this corridor's burst. (2) The **peak factor** sets the
  dimensionless UH's SHAPE, not just its height: `peak_factor = 645.33 / K` where `K` is the area
  under the curve, so `solver/runoff.py` solves the NEH-630 Ch. 16 gamma shape parameter from the
  factor and volume is conserved at any value. Per-site via `SiteProfile.uh_peak_factor` (cited),
  per-call via `simulate_runoff(peak_factor=)`, else the cited 484. **A flat-terrain 300 lowers the
  peak ~30% and leaves runoff VOLUME untouched** — adopting one for a site is a reviewed, cited
  profile edit, never a screen's own decision. (3) The **unit-rainfall duration** `D <= 0.133*Tc`
  is not the output step: `simulate_runoff` refines `dt_hr` to an integer sub-multiple satisfying
  it and returns the series on that finer grid. A caller superposing several catchments (the
  confluence graph in `hydrograph_routing.py`) must therefore share ONE grid — it drops the whole
  network to the finest step required and warns, rather than summing series on different clocks.
- **Cooling is dispatched by archetype** (`cooling_models.py`, epic #1060): the
  `CoolingModelType` enum is keyed on physical **mechanism** — "open loop / closed
  loop" are ambiguous industry labels kept only as documented per-spec aliases.
  Archetypes: `off` (explicit zero), `evaporative_tower` (Lima; alias "open loop"),
  `once_through`, `closed_loop_dry` (alias "closed loop"), `hybrid_adiabatic`
  (month-varying, wired into `evaluate_seasonal`), `unknown` (disclosed facility,
  undisclosed method → **bracketed range**, `method_disclosed=False`, never a single
  headline). Select per site via `SiteFacility.cooling_model` — never hardcode; a
  facility with no method on record stays `unknown`, and `facility=None` ⇒ `off`.
  Add an archetype by registering a `CoolingModelSpec`, mirroring `watermark.profiles`.
  Lima's evaporative figures are regression-locked against the committed
  `data/scenarios/buildout.scenario.yaml` (`tests/test_hydro_cooling.py`).
- **Closed-loop cycling reconciliation (epic #1676).** To test a "closed-loop" cooling
  claim against records, two harness pieces live here. (1) `connectors.echo_dmr.flow_seasonality`
  reduces a DMR flow outfall's monthly series to a **warm/cool ratio** — a temperature-driven
  evaporative blowdown peaks in summer (ratio ≫ 1), a genuinely dry loop is flat (ratio ~ 1);
  the ratio is an `[inference]` shape indicator, never a discharge magnitude, and rides on
  `DischargeSummary.seasonality` / the `dmr_document()` `seasonality:` block. (2) `blowdown.py`
  resolves **OHD000001** (Ohio's draft data-center NPDES general permit) coverage per closed-loop
  candidate: while the permit is draft it is gated to `not_available` (a `[verified]` cited
  absence), written to `data/reference/oepa/ohd000001-coverage.yaml` by `watermark oepa coverage
  --write`. The cohort is registry-derived (`SiteFacility.cooling_model` in
  {`closed_loop_dry`, `hybrid_adiabatic`}); a facility-own discharge absence stays an `[open]`
  gap (→ a C2 records request), never read as "confirmed dry". (3) `cooling_reconcile.py` (A3,
  #1679) is the **reconciliation harness** over (1)+(2): per cohort facility it assembles the
  water account — the pinned archetype's PREDICTED makeup/blowdown (via `cooling_models`) vs the
  DOCUMENTED makeup (A1) / blowdown (A2) — back-solves cycles-of-concentration where both are on
  record (always an `[inference]` **bracket**, never a scalar), and classifies each as
  `discrepancy` (a low-water claim contradicted by a **metered** documented flow → re-archetype up),
  `corroborated` (documents consistent with the claim), `reservation_conflict` (a low-water claim
  contradicted by a disclosed **RESERVATION CEILING** — a will-serve / water-service agreement figure,
  NOT a metered use and NOT a discharge/withdrawal instrument, so it keeps the pin + sharpens the
  site's water lead, never re-archetyping; the reserved figures feed `reserved_makeup`/`reserved_blowdown`,
  kept distinct from `documented_*`, and the back-solved CoC is labeled *ceilings, not metered use* —
  never a headline consumptive), or `gap` (no documents → a C2 lead payload). A gap the operator has
  **DISCLOSED** into (B2 Van Wert, #1682) records the self-reported ongoing draw on `disclosed_makeup`
  (a third provenance category, kept distinct from BOTH `documented_*` (metered) and `reserved_*`
  (ceiling)): a self-report of the very claim under test is not an instrument, so it **never feeds the
  classifier and never upgrades the source** — it stays a `gap` with the `[reference]` pin KEPT, and
  its lead names the specific open quantity (Van Wert's initial closed-loop fill, whose fill-vs-annual
  framing is the #1409 discrepancy). A gap the claim's own source has bounded with a self-disclosed
  permit **CEILING** (B3 Springfield, #1683 — the City 5C FAQ's "up to 300,000 gal/day" permitted at a
  >80 °F extreme-heat max, "near zero" most of the year) records it on `disclosed_ceiling` (a fourth
  provenance slot): a permitted PEAK ceiling from the claim's OWN source is **not** a
  `reservation_conflict` — unlike B1's independently-negotiated reservation it is not a demand signal
  that contradicts the dry claim (a dry loop sits far below it) — so, like `disclosed_makeup`, it never
  feeds the classifier or upgrades the source; it stays a `gap` with the `[reference]` pin KEPT, and its
  lead names the actual-vs-ceiling denominator (the metered municipal withdrawal, #1415). It
  **recommends, never
  mutates** `cooling_model` (re-archetyping is a reviewed B1–B6 edit). Each facility is derived under
  its OWN site's `Settings` so a cross-site cohort never leaks the active site's climatology. Written
  to `data/reference/oepa/cooling-reconciliation.yaml` by `watermark cooling-reconcile --write`; the
  cohort is A2's registry-derived set, **plus the Troy-Piqua B1 reservation conflict**
  (`reconcile_troy_piqua`, #1681 — Troy-Piqua pins `UNKNOWN` so it is NOT in A2's cohort, but its
  closed-loop-FAQ-vs-2.0-MGD-reservation conflict is reconciled explicitly as a live
  `reservation_conflict`), **plus Van Wert** (`reconcile_van_wert`, #1682 — a cohort member reconciled
  explicitly so its disclosed ~660k gal figure + the #1409 initial-fill sharpen its gap), **plus
  Springfield** (`reconcile_springfield`, #1683 — a cohort member reconciled explicitly so its
  self-disclosed 300k gal/day permitted ceiling — not a `reservation_conflict` — + the #1415
  actual-vs-ceiling denominator sharpen its "not evaporative" gap), **plus the
  Intel evaporative positive control** (`INTEL_CONTROL_FACILITY`,
  a constructed calibration vector — NOT a registered site, NOT documented Intel data) the harness
  must classify `corroborated`, the no-false-positive gate. (4) `cooling_corroborators.py` (A4,
  #1680) adds two **independent corroborators** to each A3 record — the facility's own **air
  permit** listing cooling towers as PM (drift) sources (read from `SiteFacility.air_permit_relpath`;
  a listing CONTRADICTS a `closed_loop_dry` claim, CORROBORATES an evaporative/hybrid one — Lima's
  `permits/4132514.epa.yaml` lists 36) and its **Tier II / EPCRA-312** cooling-water treatment
  chemistry (a forward seam, SERC/LEPC-held, `not_on_record` for the live cohort). They are
  **SECONDARY**: recorded + reconciled against the claim (`CoolingCorroborators.net_stance`), folded
  into the finding + the gap's C2 records-request, but **never change the A3 `outcome` and never the
  sole basis for a re-archetype** (an air permit is not a discharge/withdrawal instrument). The Intel
  control carries both `corroborates`.
- Sync throughout (`httpx.Client`) to match the rest of the pipeline.
