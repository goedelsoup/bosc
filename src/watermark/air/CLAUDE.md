# CLAUDE.md — `watermark.air`

Air-quality & backup-generation dispatch modeling (epic #1172). The direct sibling of
[`watermark.hydrology`](../hydrology/CLAUDE.md): a **Tier-0 analytic emissions inventory**
(this package) escalating to a **Tier-1 AERMOD dispersion** engine
([`air/aermod/`](aermod/CLAUDE.md), #1178 — deck generation + binary wrapper built, gated
behind Tier-0). Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

The investigable question: when grid reliability stress forces the "emergency" diesel
backup fleet into runtime, what is the air burden — and does forced generation breach the
**synthetic-minor NSR caps** the permit was engineered to stay under?

- **Tag every quantity with provenance** (`ProvenancedValue`, reused from
  `watermark.hydrology.model`). AP-42 factors are `reference` (a published prior, *not* a
  fact about the site); permit rates/caps are `document`; the grid→runtime bridge and the
  runtime band are `assumption`/`[inference]`; tonnages are `derived`.
- **Two emission-factor sources, reconciled** (`emissions.py`): **AP-42 §3.4** (generic
  prior, the `#1175` model default) vs the **site air permit** certified rates.
  `reconcile()` reports the ratio — AP-42 "uncontrolled" runs ~15–75% hot vs a Tier-2
  engine, which is the point of carrying the permit cross-check. The AP-42 table is
  committed under `data/reference/air/emission-factors/` (regenerable from the cited EPA
  PDF; not connector-fetched).
- **Load regime is not optional** (`LoadRegime`). A genset's per-hour emissions depend on
  load: readiness testing is `idle` (≤25% load), a reliability dispatch carries real load
  (`load`, >25%). The permit isolates both points and the cap is tracked against them —
  so `baseline_scenario` (idle testing) is **compliant**, while a sustained forced
  dispatch at load can breach. Never model testing at full-load rates (it false-breaches).
- **The scenario runner defaults to the `permit` basis** (`scenario.py`), not AP-42:
  it carries both load points and is the source the synthetic-minor cap is tracked
  against, so the cap-exceedance check is faithful. AP-42 (`factors_basis="ap42"`) is the
  conservative cross-check, at `load` only. (The `#1175` *factor model* stays AP-42-primary
  per its reconciliation — a separate concern from the compliance question.)
- **No new grid work** (`dispatch.py`): consume `watermark.grid` interchange outputs
  (`net_import_hours_fraction`, `in_ba_generation_headroom_mw`, `met_by_in_ba_generation`).
  The grid→runtime magnitude is `[inference]` (the escalation fraction) and stays so until
  the real reliability-triggered event is captured (#1174). For PJM's comfortable window
  the BA-wide band is small and honestly says so — don't inflate it.
- **Event-anchored calibration** (`calibration.py`, #1174 → the Tier-0 half of #1182):
  #1174 captured a real event — the PJM §202(c) order (`data/extracted/grid/*.event.yaml`).
  The calibration reads it and dimensions the runtime band by the order's **verified
  authorization window** (`runtime = window_hours × duty_fraction × events_per_year`),
  a firmer anchor than the abstract fraction. Discipline: the window is `[verified]`/
  `[derived]`; the intra-window **duty** and the annual **recurrence** stay `[inference]`;
  and `facility_dispatch_confirmed` stays **False** — the order is RTO-wide and names no
  facility, so this never asserts a specific fleet ran (omission over invention).
- **Site-agnostic.** Engine rating, fleet count, permit rates, and caps resolve from the
  active site's `SiteFacility` / permit extraction — never hardcoded to Bistrozzi/Lima. A
  site with `facility=None` has no fleet: the loaders return `None` (grid-backdrop only,
  per the readiness layer). The permit path is currently the Lima default in `emissions.py`
  (`_DEFAULT_PERMIT_RELPATH`) — the seam for **#1180**, which adds
  `SiteFacility.air_permit_relpath`.
- **Tier-1 AERMOD engine** (`air/aermod/`, #1178) **is built**: the deck builders + the
  binary wrapper (located on disk, degrades when absent) + plotfile parsing. Stack geometry
  is `assumption` (the permit redacts engine specs as CBI); the emission rate is grounded.
  See [`aermod/CLAUDE.md`](aermod/CLAUDE.md) and [`docs/AERMOD.md`](../../../docs/AERMOD.md).
- **Deferred (gated behind Tier-0):** AERMET/AERMAP met + terrain connectors (#1179; the
  minimal run uses flat terrain + canned met), the NAAQS-comparison dispersion half of
  #1182, the site-profile stack/permit knobs (#1180), and feeds/CLI/ledger wiring (#1181).
  Tier-0 ships standalone —
  including the event-anchored **calibration** half of #1182 (`calibration.py`), which needs
  only the captured event, not AERMOD.
