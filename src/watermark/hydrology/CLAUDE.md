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
- **The erosion denominator is bankfull, never the 7Q10** (WS-12 / #1612). Channel stability and
  bank erosion are governed by the **channel-forming** (bankfull / effective) discharge — the
  moderate, frequent flow that does most of the long-term geomorphic work (Wolman & Miller 1960),
  recurring at ~1-2 yr. The 7Q10 is a 7-day 10-**year** *low* flow: a storm peak is hundreds of
  times any small stream's 7Q10 almost by construction, so that ratio maps to no geomorphic
  threshold. `stormwater.py` therefore reports **three** things where it used to report one
  multiple: `channel_forming` (the receiving tributary's own 2-yr peak over its committed
  `reaches.yaml` subcatchment — the **same** SCS chain the campus peaks run on, so the method's
  biases largely cancel in the ratio, which they cannot do against a log-Pearson low-flow
  statistic from a different record), `reach_conveyance` (Manning **normal depth** at the cited
  reach section: depth / velocity / boundary shear `tau = gamma*R*S` at the design peak vs at
  bankfull — the conveyance question the 60-inch pipe screen stops short of), and the
  pre-vs-post pair **at the channel-forming recurrence**, which is why that return period joins
  the reported peak set and carries the standard `channel-protection` criterion (post <= pre).
  `peak_to_7q10_ratio` survives, re-labeled, for the **dilution** framing only. Two directions a
  reviewer is owed and the caveats state: the recurrence is pinned at the **conservative** end of
  the published 1-2 yr band (largest denominator ⇒ smallest ratio), and the catchment is taken at
  the tributary's **mainstem confluence**, downstream of where the outfall enters, so the ratio is
  a **lower bound** on what the channel actually sees. Bankfull *stage* is self-consistent (the
  normal depth of the channel-forming discharge in that same section), so the within-bank verdict
  is geometry-free while the velocity/shear are not — a reach on the Tier-0 default trapezoid
  says so (`geometry_source: tier0_default`) and a surveyed cross-section is the upgrade.
  No committed catchment for the receiving tributary ⇒ **no erosion signal**, stated as such;
  the 7Q10 multiple never stands in for it.
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
- **A dual hydrologic soil group is two drainage conditions, not a spelling** (WS-20 / #1620).
  SSURGO rates a drainable, naturally-`D` soil into `A/D` / `B/D` / `C/D`: the **first** letter
  is the group where field tile is installed **and maintained**, the second the natural,
  undrained condition. The vocabulary + resolver are the leaf `watermark.hsg`
  (`resolve_hsg(group, condition)`); `cn_for` and the SWMM Horton table **refuse** an
  unresolved dual group rather than slicing one, and `connectors.ssurgo` reports the group
  verbatim with no default condition of its own (`SoilHsgSurvey.letter_for(condition)`). The
  choice is per **scenario**, per site, and provenance-tagged: `SiteProfile.pre_drainage_condition`
  (default `drained` — the prior cover is tile-drained cropland) and `post_drainage_condition`
  (default `undrained` — site work severs tile it doesn't then maintain, so the natural group is
  the conservative design basis), resolved once into an `HsgDrainageBasis` that rides on
  `StormRunoff` / `CampusDischargeScreen`. Within the post scenario it is per **part**: the
  developed acres take the post condition, the undeveloped remainder keeps the pre one — it is
  still being farmed, and severing its tile is not in the record. This is worth real numbers
  (Lima's `B/D`: composite post CN 80.6 all-drained → 85.2 as modeled → 89.9 all-undrained), so
  the screen states that bracket in a caveat rather than picking silently. **Record a dual group
  verbatim in the profile** — a profile that answers `C` to a surveyed `C/D` has pre-committed
  the low-runoff letter where no scenario can see or override it.
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
  resolves **OHD000001** (Ohio's data-center NPDES general permit — **withdrawn 2026-07-21**, Ohio
  EPA declined to finalize it, so its non-coverage is now a permanent absence rather than a pending
  one, and on the NPDES path an individual permit is the only instrument left — but a
  sewer-discharging facility holds no NPDES permit at all and is disclosed by the City's
  IU/pretreatment record instead, which is what the C2 ask targets) coverage per closed-loop
  candidate: a permit that is not effective — draft or withdrawn — gates every candidate to
  `not_available` (a `[verified]` cited absence; the two share that status but not the finding, a
  draft absence being pending and a withdrawn one permanent), written to
  `data/reference/oepa/ohd000001-coverage.yaml` by `watermark oepa coverage
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
  actual-vs-ceiling denominator sharpen its "not evaporative" gap), **plus Bowling Green**
  (`reconcile_bowling_green`, #1685 — a cohort member reconciled explicitly because its two
  quantified figures split across two provenance families: see the reservation-vs-blind-route note
  below), **plus New Albany / Intel**
  (`reconcile_intel_new_albany`, #1686 — see below), **plus the
  Intel evaporative positive control** (`INTEL_CONTROL_FACILITY`,
  a constructed calibration vector — NOT a registered site, NOT documented Intel data) the harness
  must classify `corroborated`, the no-false-positive gate.
- **An instrument that cannot REACH a facility returns absence, not zero** (B6 #1686, the New
  Albany / Intel positive control). A1 (the Ohio DNR WWFRP) meters withdrawals **from waters of the
  state**, and A2 (ECHO/NPDES) covers **discharges to them**. A campus that BUYS its water from a
  municipal system and sends its wastewater to a POTW sanitary sewer is outside both, so both return
  **~0 by construction** — and `_classify` was reading that ~0 as "documented ≈ 0 → `corroborated`
  dry", which would have silently upgraded the whole (municipally-supplied) closed-loop cohort to
  document-grade. So a record can carry a **cited** `WaterRoute` (`supply`: self_supplied/municipal/
  unknown; `discharge`: surface_npdes/sanitary_sewer/unknown — set only where the record establishes
  it, never assumed) and the classifier gains a fifth outcome **`route_blind`**. The guard
  invalidates a **negative** read only: a documented flow is still a `discrepancy`, a reservation
  ceiling still a `reservation_conflict`, a wet claim matched by real water still `corroborated`.
  Two slots serve it — `nonprocess_makeup` (a documented, metered withdrawal that IS on record but
  is NOT the cooling account: Intel's 0.0435 MGD construction-phase groundwater, ~89% returned,
  peaking in May while Jul–Aug are the year's lowest — the inverse of an evaporative signature) and
  `prediction_refused`, which leaves `it_load` + all three `predicted_*` **null** because every
  archetype is IT-load-parameterized and **a semiconductor fab has no IT load** (running a
  data-center WUE against a fab's electrical load would fabricate). A `WaterAccount` validator makes
  the refusal total and cited — a half-refused account would read downstream as a real zero.
  `meta.reference_band` records the per-IT-MW evaporative screening band, derived from the
  **archetype spec**, explicitly NOT from the fab that was supposed to ground it.
- **A blind instrument still reaches the SUPPLIER — and that is the denominator** (B4 #1684, the
  Urbana origin claim). Urbana is where "closed loop undercuts the water thesis" entered this
  network, and its claim is the one that carries **no number at all**: "water use comparable to a
  standard office building" is a comparison, so nothing lands on `disclosed_makeup`/
  `disclosed_ceiling` the way Van Wert's ~660k gal or Springfield's 300k gpd ceiling did. Its route
  is `route_blind`, established on a stronger instrument than New Albany's — the City's **own**
  Pre-Annexation Agreement (Ord. 4612-24) obliges it to "provide water and sewer", so the campus is
  absent from all 31 Champaign County WWFRP registrations (a *searched* absence) and files no DMR.
  What the registry does reach is the **City**, and its withdrawal rides on a sixth slot,
  `supplier_withdrawal`. Same rule as every non-`documented_*` register: it **never feeds
  `_classify`** — a system total aggregates every customer on it, so it can neither corroborate nor
  contradict one facility's claim — and a `WaterAccount` validator **refuses it without a cited
  municipal supply route** (off that route it has no referent; a self-supplied facility's own
  withdrawal is `documented_makeup`). It is carried because it turns a bare negative into a
  quantified one: the City reported **1.76 MGD** in 2024, an evaporative read of the same campus at
  its `[inference]` screening IT-load bracket implies **0.49-1.64 MGD** (28-93% of that), and the
  office-building reading sits below the 0.01 MGD noise floor — three orders of magnitude, and no
  instrument on either side can tell them apart. That is what makes the untested question material
  rather than academic, and it is why the ask is re-aimed at the supplier's **capacity /
  supply-adequacy analysis** — the draw the utility planned for, which is the figure the operator's
  claim never states.
- **A blind route does not erase a reservation, and two conflicting figures are split by
  PROVENANCE rather than by size** (B5 #1685, Bowling Green). This is the guard above exercised on a
  real second site, and it matters because it is what stops `route_blind` from swallowing every
  municipally-supplied campus into "we cannot see". Meta's campus buys finished water from a
  regional district, so the makeup side IS blind — yet the row reads `reservation_conflict`, not
  `route_blind`, because a **negotiated ceiling is not something A1 or A2 could ever have metered**,
  so blinding them cannot invalidate it. Keying the guard on a blind route alone would have
  destroyed the finding. The second rule is the harder one: Bowling Green carries **two** quantified
  figures that conflict 12-fold — a district-linked "up to ~600,000 gpd" design commitment and
  Meta's own announced ~50,000 gpd — and they are separated by **where they come from, not by which
  is bigger or more convenient**. The district's figure is a demand signal independent of the claim's
  source, so it lands on `reserved_makeup` and classifies; Meta's is a self-report of the very claim
  under test, so it lands on `disclosed_makeup` and never classifies. The conflict itself is
  **reported, not resolved** (it is #1439's, and no instrument in the corpus settles it). Note also
  what makes the A1 negative *readable*: the Wood County registry carries no Meta/Liames/NWWSD
  registration at all, but the Apollo plant registered a 0.27 MGD intake in the campus's own HUC-12
  on 2026-03-26 — the register is demonstrably live at that site, so the absence is a route rather
  than a coverage hole. **A dated negative needs a positive next to it before it can be read.**
  (4) `cooling_corroborators.py` (A4,
  #1680) adds two **independent corroborators** to each A3 record — the facility's own **air
  permit** listing cooling towers as PM (drift) sources (read from `SiteFacility.air_permit_relpath`;
  a listing CONTRADICTS a `closed_loop_dry` claim, CORROBORATES an evaporative/hybrid one — Lima's
  `permits/4132514.epa.yaml` lists 36) and its **Tier II / EPCRA-312** cooling-water treatment
  chemistry (a forward seam, SERC/LEPC-held, `not_on_record` for the live cohort). They are
  **SECONDARY**: recorded + reconciled against the claim (`CoolingCorroborators.net_stance`), folded
  into the finding + the gap's C2 records-request, but **never change the A3 `outcome` and never the
  sole basis for a re-archetype** (an air permit is not a discharge/withdrawal instrument). The Intel
  control carries both `corroborates`.
- **The thermal screen has two kinds of row and they must never be conflated** (`thermal.py`,
  epic #1715). It is the heat-side clone of the toxics screen — heat load → fully-mixed
  temperature at the cited design low flows → Ohio's daily-maximum criterion
  (`thermal_criteria.py`) plus the Great Lakes RIS tolerances → a CWA §316(a) / mixing-zone flag.
  A **`data_center`** row's load is MODELLED (`cooling_models.reject_heat_load`, an inference
  about a facility that is not yet discharging); a **`permitted_discharger`** row's is OBSERVED —
  `rho*cp*Q_reported*(T_reported - T_ambient)` from that permit's own ECHO DMR record (#1718).
  Same reach, same flows, same
  criterion from there on; read `kind` before quoting a number. Three rules that are easy to get
  wrong: (1) **the flag is the temperature test, not the heat test** — Ohio's criterion is a
  daily maximum in °C, so where the mixed temperature is computable the flag comes from
  `headroom_fraction` (which has the discharge's own flow in the mixing denominator); the
  `exceedance_factor` loading ratio divides by the reach's design flow alone and on its own calls a
  large, barely-warm discharge an exceedance (Lima's 12.8 MGD WWTP reads ~26x "over capacity" while
  mixing to 4 °C *under* the criterion). (2) The **design ambient** ladder is live NWIS 00010 →
  the reach's own reported in-stream (upstream/downstream) DMR station → the zone's seasonal-average
  criterion as a stated design ambient; every rung degrades quietly, including on a live-service
  HTTP failure. (3) **Cooling scenarios span the heat PARTITION, not load uncertainty**:
  `once_through` sends the whole rejection downstream by definition, `evaporative_blowdown` sends
  only the blowdown's sensible heat at a temperature CALIBRATED to an observed corridor analog (an
  [inference] by analogy — the campus holds no discharge permit of its own), `conservative_bound`
  is the ceiling. Running all three is what makes "robust to the partition" a number instead of a
  claim. The cohort is per-site by construction (`SiteProfile.basin` → the ECHO basin inventory,
  `toxic_corridor_bbox` → the corridor), resolved on the *same* receiving-water ladder as
  `toxics.py`; a permit ECHO cites to a different water body is excluded, never re-pointed.
  Committed to `data/reference/hydrology/thermal-discharge-screen.yaml`
  by `watermark thermal --offline --write`, where `--offline` serves the committed **fixtures**
  so the artifact regenerates byte-stable on a clean checkout — a bare `hydro_offline=True` with
  an empty `data/cache/` silently writes a screen with no reported record in it.
- Sync throughout (`httpx.Client`) to match the rest of the pipeline.
