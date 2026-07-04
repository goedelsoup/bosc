# CLAUDE.md — `watermark.economics`

The demand-side reference layer: a county economic baseline and state consumer-energy
costs, plus the stylized facility→price-pressure sensitivity. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md). Domain narrative:
[`docs/ECONOMICS.md`](../../../docs/ECONOMICS.md) (grid peer: [`docs/GRID.md`](../../../docs/GRID.md)).

- **Three connectors, one discipline (`connectors/`).** `qcew.py` (BLS QCEW, keyless — county
  employment by NAICS sector + published location quotients), `census.py` (Census ACS5 — county
  population series, live fetch needs a key; a warm cache/fixture is served keyless), `eia.py`
  (EIA API v2 — state residential electricity price,
  retail sales, residential natural-gas price). All go through the shared
  `watermark.connectors.cached_get` (on-disk cache + fixture fallback); an **API key is never part
  of a cache key**; an offline miss raises `OfflineError` naming the key; columns are read **by
  name, not index** (defends against upstream format drift). New state → add it to `eia.py`'s
  `_STATE_NAME` map (the three series are templated by state code).
- **`baseline.py` → `EconomicBaseline`.** QCEW across two trend years (default 2018/2023) folded
  with an optional ACS5 population series → the newest year's full sector mix (`latest`), the
  employment `trend`, `population` (omitted, not faked, when no Census key/fixture), and a
  provenance `note`. LQ ≥ 1.2 marks an export-oriented sector. Persisted per-site to
  `baseline_relpath` (`data/reference/economics/<slug>/baseline.yaml`; Lima's is the un-slugged
  legacy path).
- **`energy.py` → `ConsumerEnergyCosts` + `FacilityDemandPressure`.** Consumer costs are
  state-level EIA data (all sites in a state share the numbers) but stored per-site at
  `consumer_energy_relpath`. `derive_demand_pressure` sizes a disclosed facility's draw
  (`watermark.facility.power`) against state retail sales → `demand_share_pct` and
  `households_equivalent` (robust, cited) plus a `price_pressure_pct_low/high` band that is
  **deliberately STYLIZED screening, not a forecast** — keep the caveat in the model, never
  present the band as a projection. Requires an active `SiteProfile.facility` (else `ValueError`).
  Persisted per-site to `demand_pressure_relpath` via `write_demand_pressure`/`load_demand_pressure`
  and exported as the **`economics-demand-pressure`** bundle feed (`watermark.site.economics`, #1105);
  both the write (`watermark eia`) and the feed are facility-gated — a thin site simply omits them.
- **Per-site config flows in through the profile, not constants.** `econ_fips`, `eia_state`,
  `eia861_utility_number` come off `active_profile(settings)`/`Settings` (see
  [`watermark.sites`](../sites/CLAUDE.md)); the output relpaths are per-site (#326/#606). **Never
  hardcode Allen County's FIPS or Ohio** — read the profile.
- **Every value is a `ProvenancedValue`** (from `watermark.hydrology.model`) carrying its citation;
  models are `extra="forbid"`. The baseline is a pass-through feed: `watermark.site.economics`
  exports the model as-is to the **`economics-baseline`** bundle feed (schema at
  `schemas/economics-baseline.schema.json`). Consumer energy also feeds the grid profile
  (`watermark.grid.utility`), a separate feed.
- **CLI (all under `watermark grid`, `cli/grid.py`):** `economics` (build/write the baseline),
  `eia` (consumer energy + optional demand pressure), `grid` (the grid profile that consumes
  consumer energy). Each takes `--write/--no-write` and `--offline`; `watermark onboard <slug>`
  runs the baseline + consumer-energy steps as part of onboarding.
