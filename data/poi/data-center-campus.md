---
name: Data-center campus
slug: data-center-campus
kind: composite
depth: watched
parcels:
- 36-0100-03-002.000
- 36-1200-02-001.001
- 36-1200-03-001.000
- 36-1200-03-001.001
- 36-1200-03-001.002
- 36-1200-03-001.003
- 36-1200-03-001.004
- 36-1200-03-001.005
- 36-1200-03-001.006
- 36-1200-03-002.000
location:
  method: parcel-cama
  confidence: high
  asof: '2026-06-09'
  bbox:
  - -84.128403
  - 40.787748
  - -84.118419
  - 40.806044
track:
  enabled: true
  collections:
  - sentinel-2-l2a
  - naip
  - landsat-c2-l2
citations:
- 'data/site/gis-findings.geojson (layer: campus; Allen County CAMA parcels, grantee
  Bistrozzi LLC)'
tags:
- datacenter
- campus
- bistrozzi
---

Composite POI of the **10 Bistrozzi LLC parcels** that make up the data-center campus,
ported from the `campus` layer of
[gis-findings.geojson](../site/gis-findings.geojson) — the seed that proves the store and
the first composite. It is the active imagery tracking site (`depth: watched`): the AOI
bbox here is what `bosc imagery search/pull` clips to.

Geometry/identity are the Allen County CAMA parcels listed in `parcels` (deed format);
the dedup `resolve` layer normalizes those to the county `PARCEL_NO` anchor. Members are
not yet broken out as atomic parcel POIs — the composite references its parcels directly
until `discover`/`resolve` land. Values are verbatim from the county GIS via the
committed findings; the campus grouping is an analyst composite, not a county object.
