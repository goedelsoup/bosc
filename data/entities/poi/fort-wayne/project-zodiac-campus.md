---
name: Project Zodiac campus
slug: project-zodiac-campus
kind: composite
depth: watched
parcels:
- "021327100001000077"
- "021327451001000077"
- "021327451001003039"
- "021327451001004039"
- "021327476001001039"
- "021327476002000039"
- "021327476003000039"
- "021327476004000039"
- "021327476005000039"
- "021327476006000039"
- "021327476007000039"
location:
  method: parcel-cama
  confidence: high
  asof: '2026-06-26'
  bbox:
  - -85.057758
  - 41.018893
  - -85.036133
  - 41.040715
track:
  enabled: true
  collections:
  - sentinel-2-l2a
  - naip
  - landsat-c2-l2
  since: '2023-01-01'
surface_forms:
- type: parcel-id
  value: "021327100001000077"
  citation: 'data/reference/fort-wayne/bosc-parcels.geojson (situs 6015 Adams Center Rd; owner mailing Mountain View CA 94043 — the Hatchworks→Google link)'
- type: parcel-id
  value: "021327451001003039"
  citation: 'data/reference/fort-wayne/bosc-parcels.geojson (situs 7101 Tillman Rd; transfer 2024-01-16)'
- type: parcel-id
  value: "021327476007000039"
  citation: 'data/reference/fort-wayne/bosc-parcels.geojson (situs 7721 E Tillman Rd; transfer 2025-10-31 — the second assemblage wave)'
relationships:
- role: owner
  entity: Hatchworks LLC
- role: operator
  entity: Google
citations:
- 'data/reference/fort-wayne/bosc-parcels.geojson (Allen County, IN iMap — 11 parcels, owner of record Hatchworks LLC; bbox derived from the committed geometry)'
- 'data/extracted/fort-wayne/datacenter-facility.md (Google "Project Zodiac", $2B, ~700 ac, operational Dec 11 2025; serving utility I&M)'
- 'data/extracted/idem/fort-wayne/wqc001454.idem.yaml (IDEM §401 WQC001454; applicant Marc Stern, Hatchworks LLC; 7510 Zodiac Way)'
aliases:
- Hatchworks campus
- Google Fort Wayne data center
tags:
- datacenter
- campus
- project-zodiac
- hatchworks
- google
---

Composite POI of the **11 Hatchworks LLC parcels** that make up the Project Zodiac data-center
campus in southeast Fort Wayne, Allen County, **Indiana** — the network's first confirmed
operational data-center facility ([`datacenter-facility.md`](../../extracted/fort-wayne/datacenter-facility.md),
#360). It is the active imagery tracking site (`depth: watched`); the AOI `bbox` here — derived
from the committed parcel geometry — is what `watermark imagery search/pull` clips to.

Geometry and identity are the Allen County, IN CAMA parcels listed in `parcels` (the county
iMap `QueryLayers` Parcel_Poly layer, owner-of-record joined), committed verbatim as
[`bosc-parcels.geojson`](../../reference/fort-wayne/bosc-parcels.geojson). The campus grouping is
an analyst composite, not a county object; member parcels are not yet broken out as atomic POIs.

**The assemblage tells the story.** The block was bought in **two waves** — four parcels in
January 2024 (around the April 2024 $2B groundbreaking) and seven more on **2025-10-31** (the
Phase II/III expansion). Every parcel is held by **Hatchworks LLC**, a Delaware-registered-agent
shell (mailing `2801 Centerville Rd, Wilmington DE 19808`) — except the situs parcel **6015 Adams
Center Rd**, whose owner mailing is **Mountain View, CA 94043**: the on-record link from the shell
to **Google**, the operator the local "Project Zodiac" filings keep at arm's length.
