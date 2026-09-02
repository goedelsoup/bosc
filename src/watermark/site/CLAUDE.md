# CLAUDE.md — `watermark.site`

The site's **data tier**: turns the committed corpus into the typed **content bundle**
(`watermark export` → `data/site/bundles/<slug>/`, per network site #724/#727) that the Astro
frontend (`web/`) reads at build time. The committed, site-agnostic contract
(`README`, `schemas/`, example manifest) stays shared at `data/site/bundle/`. Defers to the
root [`CLAUDE.md`](../../../CLAUDE.md).

- **`export.py` is the entry point** (`export_bundle`): loads the corpus once through the
  shared loaders (`load_corpus`, `build_timeline`, `build_entity_graph`, `load_people`,
  `load_pois`, …) + the per-section builders here, and writes versioned, schema-validated
  JSON feeds plus a `manifest.json` carrying a `CONTRACT_VERSION`. The contract (README,
  `schemas/`, `manifest.example.json`) is committed; the generated `manifest.json` + `feeds/`
  are regenerable and git-ignored.
- **The feed models live in `feeds.py`** — JSON Schemas are generated from them (serialization
  mode), so schema and code never drift. Add a feed by adding its Pydantic model there + a
  builder; never hand-write a schema.
- **Per-section builders** (`records`, `economics`, `candidates`, `documents`, `exhibits`,
  `gleif`, `graph`, `meetings`, `people`, `places`, `concepts`, `rsei`, `gismap`) each emit
  one or more typed feeds **from committed corpus data** — don't fabricate records or links.
- **`gismap.py`** lifts the committed `data/site/gis-findings.geojson` into typed per-layer
  `GeoFeatureCollection` feeds for the frontend's DeckGL map (`export_geo` /
  `export_watershed_geo` / `export_imagery_geo`); `merge_rsei_layer` / `merge_corridor_layer`
  fold the RSEI facility points + the frozen-Periplus corridor in first. Geometry is WGS84
  verbatim (display-only, no reprojection). Two per-site land layers sit beside them and are
  **not interchangeable**: `campus_from_parcels` (county CAMA — owner / situs / transfer date)
  and `enclave_from_federal_land` (#1664, the DoD MIRTA boundary — reporting component /
  operational status). A federal enclave is off the tax rolls, so the second is the *only* land
  path it can ever have; `readiness.PLACES_GEOMETRY_FEEDS` activates `places` on either.
- **`enclave.py`** publishes the committed federal-enclave profile
  (`data/reference/<slug>/enclave.yaml`, built by `watermark enclave`) as the `enclave` object
  feed — the peer of `rsei.py`: the artifact is already a provenance-carrying model, so the feed
  **is** the model. It is where the enclave's own RSEI/TRI row and the county-scope severance
  that hides it from the site's `rsei` backdrop are published.
- **The yidam mirror is three modules, and they are one artifact** (#2134): `corpus_mirror.py`
  projects the nodes, `corpus_catalog.py` projects `.yidam/catalog/` from BOSC's own
  `data/catalog/**`, and `corpus_records.py` loads the committed extractions the `record` class
  is built from. `Mirror` carries its catalog and `write_mirror` writes both — a corpus written
  without its registry has dangling citations and fails the projection's own edge invariant.
  A citation is a **link resolving to the catalog file**, never a mention; see the root
  `CLAUDE.md` for why `rests-on` stays undeclared in every `.ont.yml`.
- **`objectstore.py`** backs the object-store CLI (serving real source bytes from R2), not the
  bundle.
- The legacy Python SSG (`build.py` / `render.py` / `nav` / `templates/` / `assets/`, the
  `watermark site build|serve` CLI, the generated `web/` + `site/` trees) was **removed at the
  parity cutover** — the Astro `web/` is now the sole presentation tier.
