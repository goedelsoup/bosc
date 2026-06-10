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
  `POICandidate`s (parcel ids, addresses, **facility/business names**) with citations +
  a store-`covered` flag. Read-only worklist; the uncovered parcel-ids are the leads.
  Each kind is **divergence-guarded** so the pass can't invent a place: the parcel regex
  mirrors `allen_gis._PARCEL_ID_RE` (a test cross-checks the two), and the facility-name
  vocabulary is the **entity-graph facility + corporate nodes** — discover only proposes
  a name the entity resolver already produced. Name candidates are `feature`-kind, so
  they funnel through GNIS (`_resolve_feature`); `--no-names` skips the graph pass.
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
- **`curate` (built — scaffolding):** `curate.py` scaffolds a resolved `MergeGroup` into a
  `data/poi/<slug>.md` profile at depth `located` (members → `surface_forms`, owner →
  relationship, citations carried through; no AOI). `write_profile` refuses to overwrite
  unless `force`. `bosc poi curate <parcel-no> [--write]`. Promotion to
  `characterized`/`watched` (+ a tracking `bbox`) is a human edit, never auto.
- **`gnis` (built — non-parcel branch):** `connectors/gnis.py` resolves a named feature
  (river, water body, landform) via USGS GNIS (National Map *geonames* ArcGIS service) →
  a stable `gnis-<gaz_id>` key + a point. `resolve_value("feature", name)` returns a
  `review` proposal (`fallback_key`); the geocode-only-no-parcel path gets a `geo-<geohash>`
  key. `merge` blocks by `Resolution.key` (`parcel_no` else fallback), so feature surface
  forms group. `bosc poi resolve "<name>" --kind feature`.
- **Wired to imagery (P4):** `bosc.gis.load_tracking_sites` reads `tracked_pois()`; a
  `watched` POI *is* a tracking site.
- **In the graph + on the site (P5):** `pipeline.entities.enrich_with_places` folds the
  store in as `place` nodes (linked to owner orgs via `relationships`); `bosc.site.places`
  renders a page per POI + `places/index.md`. The arc — discover → resolve → merge →
  curate → (watched) imagery, and place node + page — is complete.
