# POI subsystem — design

*Forward-looking design. **Nothing here is built yet** — there is no `bosc.poi`
package and no `data/poi/` store. This is the plan for deriving **points of interest**
from the corpus, geocoding them, and — when a POI is flagged — feeding it to the
imagery tracking machinery (`bosc.gis`, see [`imagery-subsystem.md`](imagery-subsystem.md)).
Hand-written design note; fold steady-state guidance into a `bosc.poi` `CLAUDE.md`
once code exists.*

*Note: `bosc site build` mirrors every `.md` under `docs/` into the published site
([`build.py`](../src/bosc/site/build.py)). This is an internal engineering plan — keep
it out of a public deploy unless intended (deploy is manual `workflow_dispatch`).*

## Executive summary / the abstraction

A **POI is the third curated entity type — *place* — peer to *person*
([`data/people/`](../data/people/)) and *org* ([`data/entities/`](../data/entities/)).**
Same artifact shape: a markdown file with frontmatter, cited to the corpus,
**depth-marked**, linked into the entity graph. The place-specific *enrichment* is
**geometry** (geocoding), and the deepest depth rung is **imagery tracking**.

So a POI is to a place what a person profile is to a person. Tracking is not a separate
system — it is what a POI looks like at maximum depth, the way federal-award enrichment
is something a deeply-researched org gets.

Locked decisions (this design):

1. **POI = curated markdown + frontmatter** under `data/poi/<slug>.md`, depth-marked,
   cited, relationship-linked. A new node type in the entity graph (*place*).
2. **Depth ladder** `mention → located → characterized → watched`, **human-set** except
   the mechanical `mention → located` (geocode) advance. Depth gates cost.
3. **Pipeline** `discover → resolve → curate`, with `bosc.gis` consuming the `watched`
   POIs. Mirrors the civic/person candidate→profile machinery.
4. **Dedup is two problems** — *atomic resolution* (mechanical, parcel-anchored) and
   *composite assembly* (curatorial). They must not be conflated.
5. **Canonical identity = the Allen County parcel number** where one exists; otherwise a
   fallback `(kind, geohash)` key plus a human-assigned slug.
6. **Geometry/AOI:** store the richest geometry geocoding yields; the tracking AOI is the
   footprint bbox, or a buffered box around a point when there is no footprint.
7. **`track: true` in frontmatter is the single source of truth** for what gets imagery.
   `bosc.gis.load_tracking_sites` reads `data/poi/`, **retiring `gis_tracking_layers`**;
   `gis-findings.geojson` becomes a generated/display-only map layer.
8. **Merge strictness (the dial):** auto-merge **only on exact parcel-id equality**;
   every geocoded/spatial/name match (address↔parcel, coord↔parcel, name↔owner) is a
   **human-confirmed proposal**, not an automatic merge. Tunable via a confidence
   threshold — but the conservative default is correct for litigation evidence.

## 1. Goal & scope

Turn the unstructured place references scattered through the corpus (addresses, parcel
ids, facility names, named features) into a **deduplicated, geocoded, cited registry of
places**, each carrying a research depth. Places flagged `watched` flow into the imagery
time-series machinery already built. Out of scope: drawing new geometry by hand
(fabricated evidence) and any geocoding that is not regenerable from a cited source.

## 2. Depth ladder (the frontmatter-depth parallel)

Depth is descriptive **and** an operational cost gate — you don't deep-research every
person, and you don't track every place.

| rung | what's known | unlocks | cost | who advances |
|---|---|---|---|---|
| `mention` | cited in the corpus; a name/address/id string | a candidate, nothing fetched | ~0 | discover |
| `located` | geocoded → point or footprint + method/confidence | map placement; AOI derivable | one cached geocode | **auto** (resolve) |
| `characterized` | kind, owner/operator, parcel(s), graph links | entity-graph node + a place page | curation | **human** |
| `watched` | `track: true` + cadence/collections | imagery pull time-series (`bosc.gis`) | repeated pulls + LFS | **human** |

The `characterized → watched` jump is the expensive, deliberately human-gated one —
which is exactly why it lives in frontmatter, not in inference.

## 3. Dedup — the crux, split in two

Conflating these is what makes place dedup feel intractable; separating them makes it
fall out.

### (a) Atomic resolution — mechanical, automatable

Collapse the surface forms of **one atomic place**. Every in-county surface form is
pushed through a single **resolve-to-parcel funnel**; the canonical Allen County parcel
number becomes the identity:

| surface form | → parcel via | new vs. reuse |
|---|---|---|
| parcel id (any format) | `allen_gis.normalize_parcel_id` (digits only) | **have it** |
| address / situs | Census Geocoder → point → **parcel-at-point** | new spatial query, same shape as `lima_gis` floodzone |
| facility lat/lon (ECHO/RSEI) | parcel-at-point | new spatial query |
| name ("the X property") | CAMA owner/situs fuzzy (`allen_gis.parcels_by_owner`) | reuse + human confirm |

In-county → a parcel number (strong, stable key). Out-of-county / road / water body /
no parcel → a fallback `(kind, geohash-of-point)` key plus a human-assigned slug at
curation. The one genuinely new connector capability is **parcel-at-point** (an ArcGIS
REST `intersects` query) — and `lima_gis`'s floodzone spatial lookup already proves the
pattern, so it is a small lift.

### (b) Composite assembly — curatorial, human

Group atomic places into a named whole (a multi-parcel site, a corridor). This is **not
dedup — it is curation.** You already do it: `gis-findings.geojson`'s `layer` grouping
over member parcel polygons **is a composite POI today**, just expressed as a GeoJSON
layer rather than a first-class record. Promote it, and a composite becomes a curated
set of member parcels/atomic-POIs with a slug + frontmatter.

### The granularity guard

Places nest: `point ⊂ parcel ⊂ composite ⊂ jurisdiction`. A parcel and the composite
that contains it share geometry but are **different POIs on different rungs** — atomic
resolution merges *within* a level; composites span levels only by hand. So the merge
key is never "shares a parcel"; it is "is the same atomic place," guarded by `kind`.

### The merge step & its provenance

1. **Block** by canonical parcel (else spatial geohash, else name token).
2. **Score** within a block; **auto-merge only on exact parcel-id equality** (decision
   #8); everything else drops into a **human review queue** — the candidate→profile gate
   already used for people/civic.
3. **Record every surface form + its citation** on the merged POI, and *why* it merged.
   A merge is itself an evidentiary claim; never silently collapse.
4. **Idempotency:** the merged POI in `data/poi/<slug>.md` carries its surface forms, so
   re-running `discover` matches existing POIs instead of spawning duplicates — same as
   the civic/person registries.

## 4. Architecture

### Package `bosc.poi`

- `model.py` — the Pydantic models (below).
- `discover.py` — scan the committed corpus for place references → `POICandidate`s with
  citations. Reuses `allen_gis.scan_parcel_ids` / `_PARCEL_ID_RE`; adds address +
  facility-name extraction.
- `resolve.py` — the resolve-to-parcel funnel + the merge/blocking logic.
- `store.py` — read/write `data/poi/<slug>.md` profiles (frontmatter + body), like the
  people/civic stores.
- New connectors under the shared connector pattern: `census_geocoder` (address →
  point), `allen_gis.parcel_at_point` (extend the existing connector), and later
  optionally `gnis` (named features → point).

`bosc.gis` becomes a **consumer**: `load_tracking_sites` reads `data/poi/` for
`track: true`, replacing the layer-grouping over `gis-findings.geojson`.

### Data models (Pydantic)

- `SurfaceForm` — one alias: `type` (parcel-id | address | coord | name | gnis),
  `value`, `citation` (corpus ref), `resolved_parcel` (nullable), `method`, `confidence`.
- `POICandidate` — a discovered, pre-resolution surface form (raw locator + citation +
  kind hint).
- `PointOfInterest` — `id` (slug), `name`, `kind` (parcel | facility | address | feature
  | jurisdiction | **composite**), `depth`, `parcels` (anchors), `members` (for
  composites), `geometry` (point/footprint, or a ref), `location` (method/confidence/
  `asof`), `surface_forms`, `relationships`, `track` (optional block), `citations`.

### Frontmatter schema (structure)

```yaml
---
id: <slug>
name: <canonical name>
kind: parcel | facility | address | feature | jurisdiction | composite
depth: mention | located | characterized | watched
parcels: [<parcel-no>, ...]          # canonical anchor(s)
members: [<poi-id>, ...]             # composites only
location:
  geometry_ref: <point|footprint>
  method: parcel-cama | census-geocode | gnis | echo | curated
  confidence: high | medium | low
  asof: <date>
surface_forms:                        # the dedup audit trail
  - {type: parcel-id, value: ..., citation: ..., resolved_parcel: ...}
track:                                # present only at depth: watched
  enabled: true
  collections: [...]
  since: <baseline date>
citations: [<corpus refs>]            # required — a POI with no citation is not evidence
relationships: [{role: owner, entity: <id>}, ...]
---
<hand-written analysis>
```

## 5. Chain of custody

POIs are litigation-adjacent, so the hydrology/imagery provenance discipline applies:

- **Every POI cites its corpus source(s).** A POI with no citation is not evidence.
- **Geometry is `connector`/`derived`-tagged** with `method` + `confidence` + `asof`,
  **never fabricated**; raw geocoder/parcel responses cache under git-ignored
  `data/cache/`, the committed POI is regenerable.
- **The merge audit trail** (`surface_forms`) records *why* aliases were unified — a
  dedup decision is an evidentiary claim, kept reviewable.
- **Human gates** at `characterized`/`watched` and on every non-parcel-id merge.

## 6. Connectors & dependencies

Mostly reuse — no heavy new deps:

- **US Census Geocoder** (`geocoding.geo.census.gov`) — free, **no key, public domain**;
  address → lat/lon. A pure `httpx` connector through the shared `cached_get` (fixtures
  under `tests/fixtures/...`), same as every other connector.
- **`allen_gis.parcel_at_point`** — extend the existing ArcGIS connector with an
  `intersects` spatial query (pattern proven by `lima_gis` floodzone).
- **GNIS** (USGS Geographic Names) — optional, later; named features → point.
- Reuse `allen_gis` (parcel by number/owner), ECHO/RSEI (facility coords already
  geocoded). A small inline **geohash** for the fallback key (no dependency).

## 7. CLI surface (`bosc poi`)

Mirrors `bosc subdivisions`: `discover` (corpus → candidates), `resolve <candidate|all>`
(funnel + propose merges), `list` / `show <slug>`, `track <slug> --on/--off` (flip the
flag + tracking block), and the curation is hand-editing `data/poi/` (like people).

## 8. Roadmap

- **P0 — store + model. ✅ done.** `bosc.poi` package, `POIFrontmatter` schema,
  `data/poi/`, `store.py`, `bosc poi list/show`; seeded by porting the `gis-findings`
  `campus` layer as the first composite POI.
- **P1 — discover. ✅ done.** `discover.py` scans the committed corpus text →
  `POICandidate`s (deed-format **parcel ids**, **addresses**, and **facility/business
  names**) with citations and a store-`covered` flag; `bosc poi discover [--uncovered]
  [--no-names]`. Idempotent and read-only — the uncovered parcel-ids are the worklist.
  Both pattern passes are **divergence-guarded** so neither can invent a place: the
  parcel regex is cross-checked against `allen_gis.scan_parcel_ids`, and the
  facility-name vocabulary is the **entity-graph facility + corporate nodes** (a name the
  entity resolver already produced from the corpus). Names are emitted as `feature`
  candidates, so they funnel through the GNIS branch (`_resolve_feature`).
- **P2 — resolve.** The resolve-to-parcel funnel + the merge:
  - **P2a (✅ done) — funnel core.** `census_geocoder` connector (address → point) +
    `allen_gis.parcel_at_point` (point → parcel) + `resolve.py` (`resolve_candidate`):
    parcel-id → CAMA (exact, auto-mergeable); address → geocode → parcel (a *proposal*,
    medium confidence). `bosc poi resolve`. Real committed fixtures for both connectors.
  - **P2b (✅ done) — non-parcel.** `gnis` connector (USGS GNIS via the National Map
    *geonames* ArcGIS service) resolves a named feature → a **stable `gnis-<gaz_id>` key**
    + a point (a `review` proposal). `resolve_value("feature", …)`; the geocode-only path
    gets a `geo-<geohash>` fallback; `merge` blocks by `Resolution.key` (parcel else
    fallback). `bosc poi resolve "<name>" --kind feature`.
  - **P2c (✅ done) — merge.** `merge.py` resolves + **blocks by canonical parcel** into
    `MergeGroup`s with the gate: `covered` (already a POI) / `auto` (identity fixed by an
    exact parcel-id) / `review` (rests on a geocode) / `unresolved`. `merge_resolutions`
    is pure (testable on synthetic resolutions); `bosc poi merge [--addresses --status]`.
    Distinct parcels stay distinct — a composite unifies them by hand in curate, not here.
- **P3 — curate. ✅ done (scaffolding).** `curate.py` scaffolds a resolved `MergeGroup`
  into a `data/poi/<slug>.md` profile at depth `located` (parcel id + `surface_forms` +
  owner relationship + citations; no AOI yet). `bosc poi curate <parcel-no> [--write]`
  refuses to overwrite and warns on already-covered parcels. Promotion to
  `characterized`/`watched` (and adding a tracking `bbox`) stays a human step; composite
  assembly via `members` is hand-curated.
- **P4 — wire tracking. ✅ done.** `bosc.gis.load_tracking_sites` / `get_site` read the
  POI store (`tracked_pois()` — `watched` + a `location.bbox`) and project each to a
  `TrackingSite` (id = POI slug). `gis_tracking_layers` and the `gis-findings` layer
  grouping are retired; the campus composite POI is now the source of the campus AOI, so
  `bosc imagery search/pull <slug>` runs off the store. `gis-findings.geojson` remains a
  display-only map layer.
- **P5 — graph + site. ✅ done.** `enrich_with_places` folds the POI store into the
  entity graph as `place` nodes (keyed by slug, carrying parcels/depth), linking a POI's
  `relationships` to existing org nodes via `normalize_name` (skip+log unknown targets,
  never fabricate). `bosc.site.places` renders a page per POI + a `places/index.md`
  directory (the place peer of `people/`), cross-linked to the entity graph; nav gains
  *Places and parcels*. The graph→place back-link in the entities table is a later polish.

## 9. Open decisions

- **GNIS for named features** — **decided: in P2.** Roads/water bodies have no parcel, so
  the funnel can't anchor them; GNIS is how non-parcel places reach `located`.
- **Composite authoring** — **decided: in the composite's own frontmatter** (`members`),
  one source of truth (no separate manifest).
- **Slug scheme** for parcel-anchored POIs (parcel-derived vs. human name) — open; lean
  human name for composites, parcel-derived for atomic parcel POIs.
- **Entity-graph coupling** — is `data/poi/` the place-node source, or a parallel store
  the graph reads? (Recommend: the source.)
- **Merge-strictness threshold** (decision #8 is the conservative default; expose it as a
  setting if a looser auto-merge is ever wanted).

## Sources / prior art in-repo

- People store + depth idiom: [`data/people/`](../data/people/), `bosc.people`.
- Candidate→profile machinery: `bosc.candidates`, `bosc.civic` (discover/registry).
- Geocoding anchors: `bosc.hydrology.connectors.allen_gis` (parcels),
  `lima_gis` (spatial floodzone queries), ECHO/RSEI (facility coords).
- Downstream consumer: [`docs/imagery-subsystem.md`](imagery-subsystem.md), `bosc.gis`.
- [US Census Geocoder](https://geocoding.geo.census.gov/geocoder/) ·
  [USGS GNIS](https://www.usgs.gov/us-board-on-geographic-names/domestic-names)
