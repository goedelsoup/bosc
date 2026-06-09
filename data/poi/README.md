# data/poi/

Curated **point-of-interest (place)** profiles — the place peer of
[`data/people/`](../people/). Each `<slug>.md` is a YAML frontmatter header (validated by
`bosc.poi.model.POIFrontmatter`) over a hand-written markdown body. Design + roadmap:
[`docs/poi-subsystem.md`](../../docs/poi-subsystem.md).

## What a POI is

A place derived from the corpus, geocoded, deduplicated, and **depth-marked**
(`mention → located → characterized → watched`). A POI flagged `watched` (with
`track.enabled`) is an imagery tracking site — `bosc.gis` reads those.

- **Identity** anchors on the Allen County **parcel number** where one exists; a
  *composite* (e.g. a multi-parcel campus) groups member parcels/POIs by hand.
- **Chain of custody:** every POI carries `citations` (a POI with none is not evidence);
  geometry is `location.method`/`confidence`/`asof`-tagged and derived from a cited
  source, never fabricated.

## Editing

Hand-curated, like `data/people/`. Advance `depth` deliberately — `characterized` and
`watched` are human gates. `bosc poi list` / `bosc poi show <slug>` read this store.

## Gaps

Seeded with the first composite (`data-center-campus`, ported from the `gis-findings`
`campus` layer). The `discover` (corpus → candidates) and `resolve` (parcel-anchored
dedup) layers that populate this store are not built yet.
