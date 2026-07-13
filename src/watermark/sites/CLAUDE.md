# CLAUDE.md — `watermark.sites`

The **site axis** of the BOSC network: one `SiteProfile` per watershed point, and
the registry + selection plumbing that lets every other subsystem read per-site
values instead of baking in Lima's. Defers to the root [`CLAUDE.md`](../../../CLAUDE.md)
(read its **Site axis** section first). Onboarding runbook:
[`docs/onboarding.md`](../../../docs/onboarding.md).

- **This package is the Python peer of `web/src/lib/sites.ts`.** The two registries stay
  in sync via `watermark sites sync` (writes `web/src/lib/sites-registry.json` from
  `data/sites.yaml`); `is_reference_site` here is the peer of the frontend's `isReferenceSite`
  in `web/src/lib/readiness.ts`. Change a site's identity in **`data/sites.yaml`**, not in
  two places — the profile back-fills identity from it (below).
- **`SiteProfile` (`_model.py`) is a frozen, `extra="forbid"` Pydantic model** — the master
  record for a site. Its fields fall in bands: identity (slug/place/basin); the
  connector/data **config knobs** that feed `Settings`; optional **GIS schemas**
  (`gis_parcel`/`gis_zoning`/`gis_flood`, `None` = "connector not wired for this site yet",
  and the connector refuses cleanly); stormwater/hydrology constants (design point, HSG,
  refill + abstraction gages, receiving waters); per-site **onboard output relpaths**; the
  optional disclosed `SiteFacility` (gensets/IT load/cooling model); grid/market identity;
  and the `corpus_relpaths` scope. `*_relpath`s are relative to `settings.data_dir`.
- **Only `PROFILE_SETTINGS_FIELDS` (`_model.py`) crosses into `Settings`.** `Settings`
  copies each of those knobs (`nwis_sites`, `rsei_fips`, `econ_fips`, `eia861_utility_number`,
  `eia_state`, the GIS URLs, `nasa_power_lat/lon`, `gnis_default_state`, `hydro_utm_epsg`,
  `lsc_default_ga`) from `active_profile(settings)` **unless the caller set it explicitly**
  (env/`.env`/kwarg wins, checked via `model_fields_set`). Add a new per-site knob → add the
  field **and** the tuple entry, or `Settings` won't see it. Deeper constants (GIS schemas,
  corridor bbox, facility) are read directly off `active_profile(settings)`, not via `Settings`.
- **`SITES` (`_profiles.py`) is the registry** — a `dict[str, SiteProfile]` keyed by slug
  (a CI test enforces `key == profile.slug`). `get_profile(slug)` → profile (KeyError if
  unknown); `active_profile(settings)` keys off `settings.site` (`WATERMARK_SITE`, default
  `lima`). **Add a site by registering a profile here; never re-hardcode a Lima/Allen-County
  value** anywhere downstream — thread it through a profile field. Lima's flat, un-slugged
  legacy paths are pre-#325; **a new site slug-scopes all six `PER_SITE_OUTPUT_FIELDS`**
  (`output_path_collisions(slug)` is the CI guard — outputs must be unique across sites, but
  corpus geometry inputs like `parcels_relpath` are per-site *authored* inputs, a different rule).
- **`is_reference_site(slug)` (Lima) gates the reference-only surface** — the whole-corpus
  reads, the cross-site hypothesis matrix, Lima's flat committed layout. `effective_corpus_scope`
  returns a `CorpusScope` (`_scope.py`, `include`/`exclude`): Lima's is `include=None` (whole tree)
  **minus** every registered peer's own prefixes (`_peer_scope_prefixes`), so the reference build
  no longer swallows a sibling's slug-scoped records — a Piqua NPDES permit under `oepa/troy-piqua/`
  or a Fort Wayne §401 under `idem/fort-wayne/` stops rendering in Lima's Allen-County record
  (#1505). Non-Lima sites default to `corpus_relpaths = (slug,)` (the #762/#780 safe default): a
  fresh site reads **only its own** extracted subtree and never silently inherits Lima's record.
- **GIS field maps are data, not code (`_gis_schemas.py`).** The schema *models*
  (`GisParcelSchema`/`GisZoningSchema`/`GisFloodSchema`) live in `watermark.connectors.gis_schema`
  (broken out to avoid an import cycle); this file holds the per-jurisdiction *instances*
  (`LIMA_PARCEL_SCHEMA`, `OHIO_STATEWIDE_PARCEL_SCHEMA`, `ALLEN_IN_PARCEL_SCHEMA`, the shared
  `NATIONAL_NFHL_FLOOD_SCHEMA`, …). A connector (e.g. `hydrology.connectors.allen_gis`) reads
  `active_profile(settings).gis_parcel` for `out_fields`, `id_field`, `deed_id_regex`,
  `id_normalize`, `date_decode`, `meta`, etc. and builds the live ArcGIS query — **jurisdiction-
  agnostic code, per-site schema.** Same idiom as the OPC `Profile`: fields come from the data.
  The parcel `deed_id_regex` is the one the corpus scan (`scan_parcel_ids`) and `poi.discover`
  mirror — not a module constant. **Champaign County is Ohio (FIPS 39021), not Illinois** — the
  schema guards this.
- **Adding a site, end to end** (full runbook: `docs/onboarding.md`): register identity in
  `data/sites.yaml` → `watermark sites new <slug>` scaffolds a paste-ready `SiteProfile(...)` stub
  (`scaffold_profile_src`, pre-slug-scoped outputs + typed TODOs) → paste into `_profiles.py`
  and fill each TODO **from a cited source** → add GIS schema instances if the site publishes
  layers → `profile_readiness(slug)` / `watermark onboard <slug>` lints unfilled placeholders and
  values still copied from Lima → run `watermark onboard <slug>` → **manual, parity-gated**
  promotion to `live`/`selectable` in `data/sites.yaml` + `web/src/lib/sites.ts`. Registered ≠
  selectable; a thin peer still degrades gracefully via the readiness layer.
