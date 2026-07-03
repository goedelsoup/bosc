# `data/reference/` — committed authoritative data from outside sources

This tree holds **committed reference datasets pulled from authoritative outside
sources** (EPA, USGS/NOAA, EIA, GLEIF, USAspending, county GIS, …). It is one of the
three data tiers described in [`../README.md`](../README.md); this file is the **index
across the sources**, which that one doesn't cover.

The rules (from the root [`CLAUDE.md`](../../CLAUDE.md), *Data discipline*):

- **Each folder carries its own `README.md`** naming its source, the regenerating `watermark`
  subcommand, and its gaps. That per-folder README is the **authority** — start there. Many
  carry a catalog-maintained generated block (`watermark catalog render`); don't hand-edit inside
  the markers.
- Raw API responses stay cached under git-ignored `data/cache/`, so every committed CSV/YAML
  here is **regenerable**. Columns are selected by source field **name**, never index.
- **The machine index is the catalog**, not this file: `data/catalog/<scope>/<id>.yaml` declares
  every dataset and `data/catalog/COMPLETENESS.md` is the generated coverage audit. See
  [`watermark.catalog`](../../src/watermark/catalog/CLAUDE.md).

## Source datasets (network-shared)

Authoritative pulls that back the whole network, grouped by domain. Each is regenerated
by the noted connector/command; see the folder's README for the exact scope and caveats.

| Domain | Folders |
|---|---|
| Water / environmental | `echo` (EPA ECHO NPDES), `rsei` (EPA RSEI toxics), `hydrology` (USGS NWIS / NOAA Atlas-14 / NASA-POWER), `imagery` (satellite captures) |
| Energy / grid | `eia` (EIA prices/861/930), `pjm` (PJM market), `ferc` (FERC filings), `federal` (EIA + LBNL/DOE + IRA backdrop), `compute` + `datacenter-industry` (AI-capacity priors) |
| Economic / entity | `economics` (BLS QCEW + Census), `gleif` (LEI), `usaspending` (federal awards), `lsc` (Ohio LSC legislation), `orc` (Ohio Revised Code), `odd` (ODD incentives), `allen-boe` (Allen County OH elections) |
| Civic / corridor | `subdivisions` (Allen County subdivision records), `periplus` (frozen Periplus corridor), `network` (the watershed-point synthesis) |

## Per-site trees

- **GIS field-mapped layers** live in `<county>-gis/` (`lima-gis`, `allen-gis`, `findlay-gis`, …),
  parameterized by the site's `GisParcelSchema`/`GisZoningSchema`/`GisFloodSchema` — see
  [`watermark.sites`](../../src/watermark/sites/CLAUDE.md).
- **Per-site onboarding outputs** live in slug-named folders (`fort-wayne/`, `urbana/`,
  `springfield/`, `defiance/`, …) — the climatology / baseline / consumer-energy / grid / RSEI
  artifacts `watermark onboard <slug>` writes. These are **slug-scoped so a site never clobbers
  another** (Lima's are the un-slugged legacy peers). The registered slugs are the network in
  `data/sites.yaml`; a folder appears once a site has been onboarded.
