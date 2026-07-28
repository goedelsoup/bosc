# The content bundle — the data tier contract

This directory is the **committed, site-agnostic contract** for the versioned,
schema-validated content bundle the frontend reads (Project BOSC two-tier site refactor,
[#53](../../../README.md) Tier 1). Python turns the committed corpus into typed JSON feeds;
the Astro frontend (Epic 2) and the DeckGL visualizations (Epic 3) consume them. The Astro
`web/` is the sole presentation tier — this bundle is its build-time input.

The bundle is generated **per network site** (#724/#727): the feeds + manifest land under
`data/site/bundles/<slug>/`, one directory per site, so the network's sites never clobber
each other. The **contract** (this README, `schemas/`, `manifest.example.json`) is the same
for every site and stays committed here under `data/site/bundle/`.

**Regenerate a site's bundle:**

```sh
watermark export                          # → data/site/bundles/<active-site>/ (default: lima)
watermark --site fort-wayne export        # → data/site/bundles/fort-wayne/
watermark export --out /tmp/b             # → anywhere
```

The generator is [`watermark.site.export.export_bundle`](../../../src/watermark/site/export.py); each
feed comes from an `export_X()` next to the matching `render_X()` in `watermark.site.*`. The
frontend resolves a site's bundle by slug (`bundleFor(slug)` in
[`web/packages/core/src/bundle.ts`](../../../web/packages/core/src/bundle.ts)).

## Layout

```
data/site/bundle/                 # ← the committed, site-agnostic CONTRACT (this dir)
  README.md                       # this contract
  manifest.example.json           # a committed example manifest (counts/structure)
  schemas/
    manifest.schema.json          # the manifest shape (see watermark.site.feeds.Manifest)
    citation.schema.json          # the shared provenance shape (see "Provenance" below)
    <feed>.schema.json            # one JSON Schema per feed
    geo.schema.json               # shared by every geo/* feed

data/site/bundles/<slug>/         # ← generated per site, git-ignored
  schemas/                        # a regenerated copy (self-contained bundle)
  feeds/
    <feed>.json                   # a JSON array (a "collection") or single object
    <feed>.ndjson                 # a collection above the NDJSON threshold (one row/line)
    geo/<feed>.geojson            # a typed GeoJSON FeatureCollection
  manifest.json                   # timestamped
```

### Committed vs generated

The **contract** is committed and reviewable: `README.md`, every `schemas/*.schema.json`,
and `manifest.example.json`. The **feed data** (`feeds/**`) and the live, timestamped
`manifest.json` are **generated artifacts** — regenerable with `watermark export`, and kept out
of git (`.gitignore`), the same discipline as the regenerable `web/` + `site/` trees. Two
reasons feeds aren't committed: they churn on every corpus edit, and the `documents` feed's
`size_bytes` / `available` depend on whether the Git-LFS binaries are materialized locally,
so a committed copy would be wrong in most checkouts. The schemas, by contrast, are
generated from the Pydantic models in [`watermark.site.feeds`](../../../src/watermark/site/feeds.py)
and are deterministic, so they're committed and a test guards them against drift.

## The manifest

`manifest.json` is the index. Read it first, then fetch the feeds it lists.

| field | meaning |
|---|---|
| `bundle_version` | the data generation's version (bumped when the *data* changes shape/content) |
| `contract_version` | the schema/contract version these feeds conform to (`watermark.site.feeds.CONTRACT_VERSION`) |
| `generated_at` | ISO-8601 UTC timestamp of the export |
| `feed_count` / `row_total` | quick internal-consistency checks (counts must match the feed list) |
| `feeds[]` | one entry per feed: `name`, `path`, `media_type`, `schema`, `kind`, `count` |
| `exports[]` | optional (contract ≥ 1.29.0): downloadable graph serializations of the corpus mirror — see below |

`kind` is `collection` (a JSON array / NDJSON of rows), `object` (a single object — an
inventory or baseline), or `geojson` (a `FeatureCollection`). `media_type` is
`application/json`, `application/x-ndjson` (one JSON row per line — used for any collection
over 500 rows), or `application/geo+json`. `count` is rows, features, or `1` for an object.

### Graph exports (`exports[]`, #1574)

On a canonical `watermark export` the corpus mirror (`watermark corpus-mirror`, #1561 — the
committed corpus projected into yidam nodes) is also serialized into `exports/` as downloadable
interchange artifacts for external graph tools; the wiki graph page links them. Each `exports[]`
entry is `name`, `path` (`exports/corpus.<ext>`), `media_type`, `format`, `node_count`,
`edge_count`. Formats (yidam's `export rdf|graphml`, replicated in Python):

| format | file | media type | for |
|---|---|---|---|
| `turtle` | `exports/corpus.ttl` | `text/turtle` | RDF / SPARQL (`yidam:` ontology + owl/rdfs/skos/prov) |
| `jsonld` | `exports/corpus.jsonld` | `application/ld+json` | RDF as JSON — same vocabulary, `@graph` document |
| `graphml` | `exports/corpus.graphml` | `application/graphml+xml` | Gephi / Cytoscape / yEd (directed link graph) |

The block is absent from a redirected/test export (`--out`); the SQLite export (yidam's vector
DB) is deferred to a follow-up (needs the vector index, #1564).

## Feeds

| feed | kind | what it holds |
|---|---|---|
| `records` | collection | every committed extraction (deeds, EPA/USACE & NPDES permits, SoS filings, plans, OPC) — the payload verbatim (`~` markers intact), `approximate_paths`, and a structured citation |
| `timeline` | collection | the cross-document chronology; each event cites its extraction |
| `entities` | collection | resolved parties in the entity graph, keyed by canonical `key` |
| `relationships` | collection | directed edges between entity `key`s, each traceable to one document |
| `people` | collection | curated (expanded-research) individual profiles; `entity_key` links into `entities` |
| `concepts` | collection | the wiki concept-glossary store (`data/concepts/*.md`); `related` links sibling concepts, body carries `[[wiki links]]` |
| `places` | collection | curated POI profiles; `slug` is the cross-feed key; relationships link entity keys |
| `candidates` | collection | demand-fit cloud-consumer candidates; `entity_key` set when matched in the graph |
| `defense-contractors` | object | DoD prime seed list + corpus matches (entity keys) + the Allen County parcel scan; each contractor carries a `tag` register for its corridor-presence claim, each parcel a `record_tag` (GIS columns) kept distinct from its `attribution_tag` (what the scan says the parcel is) |
| `meetings` | collection | corridor-relevant subdivision meeting summaries, each citing its source artifact |
| `documents` | collection | the source-document catalog grouped by collection (as-received paths, chain of custody) |
| `exhibits` | collection | the curated, published exhibit allowlist + availability |
| `rsei` | object | the EPA RSEI toxic-release inventory (already provenanced — `meta.source`) |
| `lei` | object | the GLEIF LEI resolution inventory (already provenanced) |
| `economics-baseline` | object | the localized BLS QCEW / Census ACS baseline (every value a `ProvenancedValue`) |
| `grid` | object | the per-site **grid backdrop** (#1642) — the cited electric-service chain (serving utility / holding company / balancing authority / wholesale RTO / retail regulator, each a `CitedFact`), the EIA-861 utility and EIA-930 balancing-authority annual profiles, and the campus `load_share` against the utility / BA / state denominators. A **backdrop-floor** feed: it describes the *place*, so a site with no disclosed facility carries it with `load_share: null` rather than a fabricated share |
| `hydrology-scenarios` | collection | committed water-balance scenario results (`data/scenarios/*.scenario.yaml`) |
| `drawdown` | object | the groundwater well-drawdown screen (#well-drawdown) — a Theis cone of depression over the ODNR well-log census + literature aquifer parameters. Carries the `[inference]` apex drawdown (a transmissivity-bracketed `ProvenancedValue`), the radius of influence + the count of domestic census wells within it, the cone `profile` for the AquiferSection figure, and the hypothetical-pumping `scenario` + `caveats`. Reference-gated by construction (a site without a committed census + resolvable cooling basis carries no cone) |
| `facts` | collection | the normalized `(subject, predicate, value, unit, status, evidence)` projection over the bundle's provenanced numeric facts (#1587) — a `catalog-index`-style post-pass that re-keys each `ProvenancedValue` in the economics/greenops/hydrology/air feeds (+ the derived facility `PowerBasis`) into one queryable table; `status` is the evidence tag off the value's `source_kind`, `evidence.page` stays null where the source carries none. Powers the `get_facts` MCP tool |
| `catalog-index` | object | the hydrated catalog (epic #1090) — addressable "grabbable" atoms (`handle` = `<kind>:<site>:<local_id>`, a live pointer into its source feed) that user-authored Stories cite; `catalog_version` stamps the set for handle-drift revalidation |
| `corpus-index` | collection | the browsable node map of the site's yidam corpus mirror (#1573) — one row per node with its display `kind`, in/out degree, line count, and freshness (`updated`, the newest commit of the committed source it derives from; null when aggregated/code-derived). A post-pass over the just-built mirror; always emitted (never empty). Backs the `/wiki/corpus` page |
| `geo/campus` | geojson | recorded campus footprint (Bistrozzi parcels) |
| `geo/jsmc` | geojson | federally-held JSMC / Lima Army Tank Plant land |
| `geo/femaflood` | geojson | FEMA regulatory floodway + 1%-annual-chance floodplain |
| `geo/corridor` | geojson | the Periplus North Cole Street study area + roadwork centerline |
| `geo/wwtp` | geojson | county WWTP NPDES discharge points |
| `geo/rsei` | geojson | RSEI toxic-release facility points, sized by Score |
| `geo/watershed` | geojson | USGS WBD watershed boundaries framing the campus (HU12 Pike Run + HU10 Middle Ottawa River) |
| `geo/imagery` | geojson | imagery tracking-AOI footprints + the dated Esri Wayback ladder (`meta.wayback`, for the before/during/after slider) |

Most geo feeds reproduce the layers of the committed
[`gis-findings.geojson`](../README.md) as typed `FeatureCollection`s — geometry **WGS84
verbatim** (display-only, no reprojection), with `layer` / `label` / `color` / `role` and
the source popup fields carried as feature `properties`. Two are assembled outside
gis-findings (#61): `geo/watershed` from the committed USGS WBD boundaries
(`data/reference/hydrology/wbd/`, regenerable via `watermark wbd`), and `geo/imagery` from the
imagery tracking AOIs (a watched POI's bbox) plus the dated Wayback releases in `meta` —
both source the Maumee-watershed map and imagery time-slider (#72).

## Provenance (structured citation & approximate values)

Every figure-bearing feed carries provenance as **data**, so a consumer renders
`[verified] cite p.X` or an approximate `~` value without re-deriving anything
([#60](../../../README.md)). Two shapes, both in
[`watermark.site.feeds`](../../../src/watermark/site/feeds.py) (and `schemas/citation.schema.json`):

* **`Citation`** — `{ source, source_kind, page, confidence, note, verified }`. `source_kind`
  is `document` / `connector` / `reference` / `assumption` / `derived`; `verified` is a
  derived boolean (`document`/`connector` → `true`), mirroring the hydrology
  `ProvenancedValue` evidence discipline so the whole bundle speaks one provenance language.
* **`Figure`** — `{ value, approximate, unit, citation }`. `approximate` is the transcription
  `~` marker lifted out of the YAML string, preserved as a boolean rather than formatted text.

The already-provenanced feeds (`rsei`, `lei`, `economics-baseline`, `hydrology-scenarios`)
export their existing Pydantic models, which already carry `ProvenancedValue` /
`meta.source` — so they satisfy the same discipline natively.

The `facts` feed (#1587) is a **projection** over those provenanced values: every `FactItem`
re-keys one `ProvenancedValue` into a `(subject, predicate, value, unit, status, evidence)`
tuple, where `evidence` is the same `Citation` shape (page populated only where the source
carries one — never invented) and `status` is the evidence tag derived from the value's
`source_kind` (`watermark.provenance.evidence_tag`).

## Versioning & backward compatibility

`contract_version` is semver over the schemas:

* **PATCH** — additive, optional fields only. Consumers need no change.
* **MINOR** — a new feed, or a new required field with a safe default. Old consumers keep working.
* **MAJOR** — a field is removed/renamed/retyped, or a feed is removed. Breaking; coordinate with the frontend.

`bundle_version` is independent and tracks the *data* generation (a re-export with materially
different corpus content), not the schema. Consumers should read `contract_version`, ignore
unknown feeds and unknown object fields (forward-compatible), and treat a MAJOR bump as a
required migration.

## Integrity

`tests/test_site_bundle.py` exports a bundle to a temp dir and asserts: every feed validates
against its JSON Schema; the manifest is internally consistent (feed list, counts, row total);
the committed `schemas/` match what the models generate (drift guard); and cross-feed
references resolve (people→entities, candidates→entities, relationships→entities,
defense matches→entities, document paths). `mise run check` runs it — hermetic, no network.
