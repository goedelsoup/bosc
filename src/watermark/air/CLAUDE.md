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
  per the readiness layer). The air-permit path is `SiteFacility.air_permit_relpath` (**#1180**,
  wired): `emissions._permit_path` resolves it per-site (Lima sets `permits/4132514.epa.yaml`);
  a facility-bearing site that hasn't wired its own (`air_permit_relpath is None`) refuses cleanly
  rather than inheriting another site's rates/caps.
- **Tier-1 AERMOD engine** (`air/aermod/`, #1178) **is built**: the deck builders + the
  binary wrapper (located on disk, degrades when absent) + plotfile parsing + the NAAQS
  concentration screen (`aermod/dispersion.py`, **#1182**). Stack geometry is `assumption`
  (the permit redacts engine specs as CBI) unless the site discloses it via
  `SiteFacility.genset_stack_*` (`inp.stack_params_from_profile`, **#1180**); the emission
  rate is grounded. See [`aermod/CLAUDE.md`](aermod/CLAUDE.md) and
  [`docs/AERMOD.md`](../../../docs/AERMOD.md).
- **NAAQS screen** (`aermod/dispersion.py`, **#1182**): `run_dispersion` /
  `run_calibration_dispersion` build the deck, run the (absent-degrading) engine, and screen the
  peak concentration per averaging period against the committed NAAQS reference table
  (`data/reference/air/naaqs/naaqs.yaml`, `reference`). Screening only — one source, no
  monitored background: a peak over the standard flags a full demonstration, not a violation.
  The calibration run is event-anchored (permit load-point rate, cited to the captured order);
  the window is `[verified]`, facility dispatch stays `[open]`. Absent binary ⇒ `available=False`,
  empty screens — the deck + NAAQS basis are real, no concentration is fabricated.
- **AERMET/AERMAP preprocessing connectors** (`connectors/`, #1179) **are built**: the AERMOD
  met/terrain input layer, under the same offline/cache/committed-fixture discipline as
  hydrology (`connectors/_cache.py` → `AirOfflineError`, fixtures at
  `tests/fixtures/air/<connector>/`). Three live pulls — `isd.py` (NOAA ISD hourly surface,
  the AERMET SURFACE/ISHD input), `igra.py` (NOAA IGRA v2 upper-air soundings, the AERMET
  UPPERAIR input), `ned.py` (USGS 3DEP/NED DEM raster, the AERMAP terrain input; a raster, so
  it follows `gis/raster.py`'s fixture-GeoTIFF discipline, **not** the JSON cache) — and two
  emitters, `aermet.py` (surface + upper-air → AERMET-ready files + a Stage-1→MERGE runstream)
  and `aermap.py` (DEM → bilinearly-sampled receptor/source elevations + an AERMAP control
  file). CLI: `watermark air aermet` / `watermark air aermap`. **No fabricated meteorology:** the
  AERMET runstream stops at MERGE — the METPREP surface characteristics (albedo/Bowen/
  roughness) are the modeller's land-use inputs, emitted only as a commented template; the
  `.SFC`/`.PFL` and the AERMAP hill-height scale come from the **binaries** (#1178). Sampled
  elevations are a deterministic DEM read, tagged `[derived]`. Per-site station IDs are now
  `SiteProfile.air_surface_station` / `air_upperair_station` (**#1180**, `PROFILE_SETTINGS_FIELDS`
  → the `air_*` `Settings` knobs); the terrain domain is the profile's centroid +
  `air_terrain_halfwidth_deg`. The minimal run still defaults to flat terrain + canned met.
- **Feeds / CLI / ledger** (**#1181**, wired): the bundle exports `air-scenarios` (Tier-0) +
  `air-dispersion` (Tier-1) feeds (`site/export.py`, contract 1.17.0, facility+permit-gated);
  `watermark air scenarios|calibrate|dispersion` (`cli/air.py`, alongside `aermet`/`aermap`)
  is the thin CLI; `ledger._burden_air` now cites the modeled cap-exceedance from the committed
  air scenario (degrades to the static permit fact when unmodeled).
- **Status.** The epic's threads have landed: the Tier-0 inventory + dispatch + event-anchored
  calibration, the #1179 AERMET/AERMAP connectors, the #1182 NAAQS dispersion screen, the #1180
  profile stack/permit/met knobs, and the #1181 feeds/CLI/ledger wiring. What's *not* automated
  is a real AERMOD run in CI (no vendored binary + no validated canned met) — the engine + screen
  degrade honestly rather than fabricating a concentration.
