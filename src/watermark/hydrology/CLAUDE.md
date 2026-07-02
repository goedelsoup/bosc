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
- Sync throughout (`httpx.Client`) to match the rest of the pipeline.
