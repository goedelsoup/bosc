# CLAUDE.md — `bosc.poi`

The point-of-interest (place) research store. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md). Design + roadmap:
[`docs/poi-subsystem.md`](../../../docs/poi-subsystem.md).

- **A POI is the place peer of a person profile.** Same shape as `bosc.people`:
  `data/poi/<slug>.md` = a `---` YAML frontmatter header (validated by
  `POIFrontmatter`, `extra="forbid"`) + hand-written markdown body. `depth`/`kind` are
  `Literal` ladders — an out-of-vocabulary value is a loud validation error.
- **Depth is a cost gate** (`mention → located → characterized → watched`), human-set
  except the mechanical `mention → located` (geocode) advance. `watched` +
  `track.enabled` is the **single source of truth** for what gets imagery —
  `tracked_pois()` is the view `bosc.gis` consumes (replacing `gis_tracking_layers`).
- **Identity = the Allen County parcel number** where one exists (the dedup anchor);
  composites group member POIs/parcels by hand via `members`. Atomic resolution merges
  *within* a level; never auto-merge a parcel with the composite that contains it.
- **Chain of custody:** every POI carries `citations` (a POI with none is not evidence);
  geometry is `location.method`/`confidence`/`asof`-tagged, derived from a cited source,
  **never fabricated**. The `surface_forms` list is the dedup audit trail (record *why*
  aliases unified). Geocoding (P2) caches raw responses under git-ignored `data/cache/`.
- **`discover` (built):** `discover.py` scans the committed corpus text →
  `POICandidate`s (parcel ids + addresses) with citations + a store-`covered` flag.
  Read-only worklist; the uncovered parcel-ids are the leads. Its parcel regex mirrors
  `allen_gis._PARCEL_ID_RE` — a test cross-checks the two so they can't drift.
- **`resolve` (built — funnel core):** `resolve.py` funnels one candidate to a parcel —
  parcel-id → CAMA (exact, `confidence=high`, `auto_mergeable=True`); address →
  `census_geocoder` (US Census, in `connectors/`) → point → `allen_gis.parcel_at_point`
  (a **proposal**, `confidence=medium`, `auto_mergeable=False`, because geocoding is
  fuzzy). `bosc poi resolve <value>`. Connector fixtures: `tests/fixtures/poi/` +
  `tests/fixtures/hydrology/allen_gis/`.
- **`merge` (built):** `merge.py` resolves + **blocks by canonical parcel** into
  `MergeGroup`s with the gate `covered`/`auto`/`review`/`unresolved` (only an exact
  parcel-id makes a group `auto`). `merge_resolutions` is pure (group logic testable on
  synthetic resolutions); `bosc poi merge`. Atomic merge keeps distinct parcels distinct —
  a *composite* unifies them by hand in curate, not here.
- **Not built yet:** **GNIS** (non-parcel features) and **curate** (promote a group to a
  `data/poi/` profile — a human step, writing the grouped members as `surface_forms`).
