# Places (POIs) — Fort Wayne (Project Zodiac)

The Fort Wayne site's point-of-interest (place) store — the place peer of
[`data/entities/people/fort-wayne/`](../../people/fort-wayne/README.md). Same format and discipline as
the network root [`data/entities/poi/`](../README.md): one `data/entities/poi/fort-wayne/<slug>.md` per place, a
YAML frontmatter header (validated by `watermark.poi.model.POIFrontmatter`) over a markdown body.

Per-site by construction (#762): `watermark --site fort-wayne export` reads `data/entities/poi/fort-wayne/`
via `watermark.sites.site_scoped_path`, so the `places` feed — **and the imagery tracking sites**,
which derive from `watched` POIs — carry Fort Wayne's own places, never Lima's. Empty today.

## What goes here

Places in the Project Zodiac record: the 11-parcel Hatchworks campus assemblage
(`data/reference/fort-wayne/bosc-parcels.geojson`), the Fort Wayne WWTP (IN0032191), and any
other corridor place. Identity anchors on the **Allen County, IN parcel number** where one
exists; a multi-parcel campus is a *composite* grouping members by hand.

## Chain of custody

Every POI carries `citations` (a POI with none is not evidence); geometry is
`location.method`/`confidence`/`asof`-tagged and derived from a cited source, **never
fabricated**. Advance `depth` (`mention → located → characterized → watched`) deliberately —
`characterized` and `watched` are human gates, and only `watched` + `track.enabled` makes a
place an imagery tracking site.
