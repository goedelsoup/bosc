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
  framing is the #1409 discrepancy). It **recommends, never
  mutates** `cooling_model` (re-archetyping is a reviewed B1–B6 edit). Each facility is derived under
  its OWN site's `Settings` so a cross-site cohort never leaks the active site's climatology. Written
  to `data/reference/oepa/cooling-reconciliation.yaml` by `watermark cooling-reconcile --write`; the
  cohort is A2's registry-derived set, **plus the Troy-Piqua B1 reservation conflict**
  (`reconcile_troy_piqua`, #1681 — Troy-Piqua pins `UNKNOWN` so it is NOT in A2's cohort, but its
  closed-loop-FAQ-vs-2.0-MGD-reservation conflict is reconciled explicitly as a live
  `reservation_conflict`), **plus Van Wert** (`reconcile_van_wert`, #1682 — a cohort member reconciled
  explicitly so its disclosed ~660k gal figure + the #1409 initial-fill sharpen its gap), **plus the
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
