# CLAUDE.md — `watermark.sites`

The **site axis** of the BOSC network: one `SiteProfile` per watershed point, and
the registry + selection plumbing that lets every other subsystem read per-site
values instead of baking in Lima's. Defers to the root [`CLAUDE.md`](../../../CLAUDE.md)
(read its **Site axis** section first). Onboarding runbook:
[`docs/onboarding.md`](../../../docs/onboarding.md).

- **This package is the Python peer of `web/packages/core/src/sites.ts`.** The two registries stay
  in sync via `watermark sites sync` (writes `web/packages/core/src/sites-registry.json` from
  `data/sites.yaml`); `is_reference_site` here is the peer of the frontend's `isReferenceSite`
  in `web/packages/core/src/readiness.ts`. Change a site's identity in **`data/sites.yaml`**, not in
  two places — the profile back-fills identity from it (below).
- **`SiteProfile` (`_model.py`) is a frozen, `extra="forbid"` Pydantic model** — the master
  record for a site. Its fields fall in bands: identity (slug/place/basin); the
  connector/data **config knobs** that feed `Settings`; optional **GIS schemas**
  (`gis_parcel`/`gis_zoning`/`gis_flood`, `None` = "connector not wired for this site yet",
  and the connector refuses cleanly); stormwater/hydrology constants (design point, HSG,
  refill + abstraction gages, receiving waters); per-site **onboard output relpaths**; the
  optional disclosed `SiteFacility` (gensets/IT load/cooling model); grid/market identity;
  the `corpus_relpaths` scope; and the per-site civic **`corridor_subjects`** vocabulary
  (#1523 — the meeting subjects that reach the project timeline, empty for a peer until it
  declares its own; Findlay declared the first peer set in #1839). `*_relpath`s are relative
  to `settings.data_dir`.
- **A `corridor_subjects` term is an assertion of relevance — cite each one, and leave out
  what the record does not connect** (#1839). Findlay carries
  `("datacenter", "one_power", "mara_holdings")`, each grounded in a committed artifact, and
  deliberately **omits** `interstate_capital` — the applicant on a live rezoning next to the
  site — because `allen-twp-rezoning-interstate-capital-2026.yaml` states outright that nothing
  in the corpus connects it to a data center. Naming it here would manufacture the link that
  artifact refuses to draw. The vocabulary is where a site's editorial thesis can leak into
  what reads as mechanical selection, so hold it to the same standard as prose.
- **"Corridor" names four unrelated things — check which sense before reusing one** (#1634;
  the full glossary is the `SiteProfile` docstring). (1) **design-storm** — `corridor_name` +
  `corridor_ddf_relpath`, a NOAA Atlas-14 *rainfall* subject anchored to `design_lat/lon`, not
  a place; (2) **corroboration geometry** — `corridor_geo_relpath`, the frozen Periplus
  `corridor.geojson` + centerline merged into the GIS findings; (3) **toxics screening
  window** — `toxic_corridor_bbox`, a deliberately coarse lat/lon box for the RSEI inference,
  *not* co-extensive with (2); (4) **civic vocabulary** — `corridor_subjects`, meeting
  keywords with no spatial meaning at all. A fifth, editorial sense ("the corridor" as the
  story's subject area) lives in prose and report slugs and is never a modeled value. None of
  these constrains another — never substitute one for another or assume a shared extent.
- **A `SiteFacility` is not necessarily a data center** (#1664). `kind` discriminates
  `data_center` (every campus; the default, so nothing existing changed) from
  `federal_installation` — a federal enclave like WPAFB, which carries a `FederalInstallation`
  block *instead of* the IT-load / genset / cooling dimensions. Those are **forbidden at the
  type level** for an installation and the cooling archetype is pinned `off`, so the campus
  models cannot size a base as a campus. Read the narrower **`SiteProfile.campus`** (the primary
  facility *if* it is a data center) in anything that models a campus — air dispatch, the
  power/compute basis, the demand→price sensitivity, the basin activity card, the promotion
  funnel — and keep `SiteProfile.facility` for "does this site have a documented facility at
  all" (readiness, the facility feed). Before the enclave seam the two were the same thing, and
  code that still assumes `facility is not None ⇒ there is a campus to size` is now wrong.
  A `FederalInstallation` carries **identifiers, not figures**: its documented water/toxics
  numbers are *projected* from `record_relpath` (a filed federal instrument) by
  `watermark.enclave`, so a profile literal can never drift from the record.
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
- **An *optional* per-site output resolves through `site_reference_path`** (#1645/H2) — the
  `ferc_relpath`/`pjm_relpath`/`federal_relpath` writers, whose field is `None` for every site
  but Lima. `None` means "slug-scope the default" (`reference/<subdir>/<slug>/<file>`), so those
  fields carry no value for `output_path_collisions` to compare and are deliberately **not** in
  `PER_SITE_OUTPUT_FIELDS`; the collision guard for them asserts the *resolved* paths are unique
  across the network (`tests/test_shared_registries.py`). Build the path with the helper rather
  than re-deriving the default — that default is the B1/#1639 clobber-safety property.
- **`is_reference_site(slug)` (Lima) gates the reference-only surface** — the whole-corpus
  reads, the cross-site hypothesis matrix, Lima's flat committed layout. `effective_corpus_scope`
  returns a `CorpusScope` (`_scope.py`, `include`/`exclude`): Lima's is `include=None` (whole tree)
  **minus** every registered peer's own prefixes (`_peer_scope_prefixes`), so the reference build
  no longer swallows a sibling's slug-scoped records — a Piqua NPDES permit under `oepa/troy-piqua/`
  or a Fort Wayne §401 under `idem/fort-wayne/` stops rendering in Lima's Allen-County record
  (#1505). A non-Lima site reads **only its own** extracted subtree and never silently inherits
  Lima's record (the #762/#780 safe default).
- **A site's scope is DERIVED from its slug — don't enumerate what a rule already knows** (#1405).
  `_eponymous_prefixes` gives every site two: its own `<slug>/` collection **and** `*/<slug>` —
  the site subdirectory inside a collection named for the issuing agency (`oepa/van-wert/`,
  `idem/fort-wayne/`, `grid/sidney/`), which is how the corpus files an artifact whose collection
  isn't named for the site. `corpus_relpaths` **adds** to that; it does not replace it, and it is
  for the prefixes no rule can derive — a corpus filed by PROJECT or CASE name
  (`permits/highland55`, `legal/thor-v-urbana`, `permits/dazzler-permits`). List the exceptions,
  derive the rule: enumerating the eponymous ones per profile is what let Van Wert's and
  Wilmington's NPDES permits sit outside the sites they document (and inside Lima's record) for
  as long as they did. **Never read `profile.corpus_relpaths` as a scope** — on its own it is the
  exceptions, so a peer would come back `None`, i.e. Lima's whole tree; always go through
  `effective_corpus_scope`. Two sweeps in `tests/test_cross_site_readside.py` hold both halves:
  no `<collection>/<slug>` directory may fall outside its site's scope, and an extraction whose
  source document is filed under one must land in that site's scope.
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
  promotion to `live`/`selectable` in `data/sites.yaml` + `web/packages/core/src/sites.ts`. Registered ≠
  selectable; a thin peer still degrades gracefully via the readiness layer.
