# The content bundle — the data tier contract

This directory is the **versioned, schema-validated content bundle** the frontend reads
(Project BOSC two-tier site refactor, [#53](../../../README.md) Tier 1). Python turns the
committed corpus into typed JSON feeds here; the Astro frontend (Epic 2) and the DeckGL
visualizations (Epic 3) consume them. It is the data peer of the legacy markdown
generator — `bosc site build` still works unchanged; this is built alongside it.

**Regenerate the whole bundle:**

```sh
bosc export                 # → data/site/bundle/
bosc export --out /tmp/b    # → anywhere
```

The generator is [`bosc.site.export.export_bundle`](../../../src/bosc/site/export.py); each
feed comes from an `export_X()` next to the matching `render_X()` in `bosc.site.*`.

## Layout

```
data/site/bundle/
  README.md                     # this contract
  manifest.example.json         # a committed example manifest (counts/structure)
  schemas/
    manifest.schema.json        # the manifest shape (see bosc.site.feeds.Manifest)
    citation.schema.json        # the shared provenance shape (see "Provenance" below)
    <feed>.schema.json          # one JSON Schema per feed
    geo.schema.json             # shared by every geo/* feed
  feeds/                        # ← generated, git-ignored
    <feed>.json                 # a JSON array (a "collection") or single object
    <feed>.ndjson               # a collection above the NDJSON threshold (one row/line)
    geo/<feed>.geojson          # a typed GeoJSON FeatureCollection
  manifest.json                 # ← generated, git-ignored (timestamped)
```

### Committed vs generated

The **contract** is committed and reviewable: `README.md`, every `schemas/*.schema.json`,
and `manifest.example.json`. The **feed data** (`feeds/**`) and the live, timestamped
`manifest.json` are **generated artifacts** — regenerable with `bosc export`, and kept out
of git (`.gitignore`), the same discipline as the regenerable `web/` + `site/` trees. Two
reasons feeds aren't committed: they churn on every corpus edit, and the `documents` feed's
`size_bytes` / `available` depend on whether the Git-LFS binaries are materialized locally,
so a committed copy would be wrong in most checkouts. The schemas, by contrast, are
generated from the Pydantic models in [`bosc.site.feeds`](../../../src/bosc/site/feeds.py)
and are deterministic, so they're committed and a test guards them against drift.

## The manifest

`manifest.json` is the index. Read it first, then fetch the feeds it lists.

| field | meaning |
|---|---|
| `bundle_version` | the data generation's version (bumped when the *data* changes shape/content) |
| `contract_version` | the schema/contract version these feeds conform to (`bosc.site.feeds.CONTRACT_VERSION`) |
| `generated_at` | ISO-8601 UTC timestamp of the export |
| `feed_count` / `row_total` | quick internal-consistency checks (counts must match the feed list) |
| `feeds[]` | one entry per feed: `name`, `path`, `media_type`, `schema`, `kind`, `count` |

`kind` is `collection` (a JSON array / NDJSON of rows), `object` (a single object — an
inventory or baseline), or `geojson` (a `FeatureCollection`). `media_type` is
`application/json`, `application/x-ndjson` (one JSON row per line — used for any collection
over 500 rows), or `application/geo+json`. `count` is rows, features, or `1` for an object.

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
| `defense-contractors` | object | DoD prime seed list + corpus matches (entity keys) + the Allen County parcel scan |
| `meetings` | collection | corridor-relevant subdivision meeting summaries, each citing its source artifact |
| `documents` | collection | the source-document catalog grouped by collection (as-received paths, chain of custody) |
| `exhibits` | collection | the curated, published exhibit allowlist + availability |
| `rsei` | object | the EPA RSEI toxic-release inventory (already provenanced — `meta.source`) |
| `lei` | object | the GLEIF LEI resolution inventory (already provenanced) |
| `economics-baseline` | object | the localized BLS QCEW / Census ACS baseline (every value a `ProvenancedValue`) |
| `hydrology-scenarios` | collection | committed water-balance scenario results (`data/scenarios/*.scenario.yaml`) |
| `geo/campus` | geojson | recorded campus footprint (Bistrozzi parcels) |
| `geo/jsmc` | geojson | federally-held JSMC / Lima Army Tank Plant land |
| `geo/femaflood` | geojson | FEMA regulatory floodway + 1%-annual-chance floodplain |
| `geo/corridor` | geojson | the Periplus North Cole Street study area + roadwork centerline |
| `geo/wwtp` | geojson | county WWTP NPDES discharge points |
| `geo/rsei` | geojson | RSEI toxic-release facility points, sized by Score |

The geo feeds reproduce the layers of the committed
[`gis-findings.geojson`](../README.md) as typed `FeatureCollection`s — geometry **WGS84
verbatim** (display-only, no reprojection), with `layer` / `label` / `color` / `role` and
the source popup fields carried as feature `properties`. Two layers named in the Epic-3
scope — the Maumee / Lost Creek **watershed** and **imagery footprints** — have no committed
geometry yet, so they are intentionally **not** emitted (omission over invention); add them
here when their source geometry lands.

## Provenance (structured citation & approximate values)

Every figure-bearing feed carries provenance as **data**, so a consumer renders
`[verified] cite p.X` or an approximate `~` value without re-deriving anything
([#60](../../../README.md)). Two shapes, both in
[`bosc.site.feeds`](../../../src/bosc/site/feeds.py) (and `schemas/citation.schema.json`):

* **`Citation`** — `{ source, source_kind, page, confidence, note, verified }`. `source_kind`
  is `document` / `connector` / `reference` / `assumption` / `derived`; `verified` is a
  derived boolean (`document`/`connector` → `true`), mirroring the hydrology
  `ProvenancedValue` evidence discipline so the whole bundle speaks one provenance language.
* **`Figure`** — `{ value, approximate, unit, citation }`. `approximate` is the transcription
  `~` marker lifted out of the YAML string, preserved as a boolean rather than formatted text.

The already-provenanced feeds (`rsei`, `lei`, `economics-baseline`, `hydrology-scenarios`)
export their existing Pydantic models, which already carry `ProvenancedValue` /
`meta.source` — so they satisfy the same discipline natively.

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
