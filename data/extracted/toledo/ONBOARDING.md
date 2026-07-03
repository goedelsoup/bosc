# Onboarding — Toledo (toledo)

Living record for the Toledo watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [ ] **Data-center activity** — extracted permits/records + entity graph (corpus extraction; seed proposals via `watermark onboard --research`, #247)
- [x] **Per-jurisdiction GIS** — **wired** (#384): parcels = Lucas County AREIS layer 38 (owner-bearing — owner + situs + land-use) and zoning = AREIS Parcel_Zoning (parcel-level, with a `PARID` join); flood = shared national NFHL. The richest GIS in the network. See GIS discovery below. Deferred follow-ups: the appraised-value PARID join (layer 83) + the Waterville land-assembly screen.

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/toledo/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/toledo/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/toledo/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/toledo/baseline.yaml |
| rsei | ok | reference/rsei/toledo/inventory.yaml |
| consumer-energy | ok | reference/eia/toledo/consumer-energy.yaml |
| grid-profile | ok | reference/eia/toledo/grid-profile.yaml |

## GIS discovery (2026-06-19; wired 2026-06-21 — schema-driven GIS, #237 / #384)

Unlike Fort Wayne/Van Wert (no clean catalog) — and even richer than Findlay's single zoning
FeatureServer — **Lucas County's AREIS is a full, valid-cert, queryable ArcGIS REST**
(`lcaudgis.co.lucas.oh.us/gisaudserver/rest/services`, host verified Lucas Co **Ohio**: situs in
Waterville/Maumee/Toledo). It is the richest GIS in the network and is now **wired** (#384):
parcels = the **owner-bearing** AREIS land-use-classification layer (38) — the network's first
parcel layer with owner+address+land-use wired from a county's *own* REST since Lima/Putnam — and
zoning = the parcel-level Parcel_Zoning layer (with a `PARID` join, unlike Findlay's polygon-only).
Field-maps confirmed from the live `?f=json` + Waterville samples; offline fixtures + decode tests.

| layer | endpoint | finding | status |
|---|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) | wired in the profile (`gis_flood`) | wired |
| parcels (CAMA) | `AREIS_Web_Map_MIL1/MapServer/38` ("Parcels Land Use Classification") | `PARID`, `OWNER`, `PROPERTY_ADDRESS` (situs), `MAILING_ADDRESS`, `LUC` (use code), `ACREAGE`, `TAXDIST`, `ZONING` — owner + use on one polygon layer | **wired** (`gis_parcel`, #384) |
| zoning | `LandUse_Zoning/Parcel_Zoning/MapServer/0` | parcel-level zoning catalog (`PARID`, `ZONING`, e.g. `17-R3`) — supports the per-parcel join | **wired** (`gis_zoning`, #384) |
| parcels (values) | `AREIS_Web_Map_MIL1/MapServer/83` ("Land Values") | `APRLAND`/`APRBLDG`/`APRTOT`, joined by `PARID` — NOT on layer 38 | follow-up (the PARID value-join; the single-layer connector can't join yet) |
| parcels (geometry) | `Tyler/Parcels/MapServer/0` | polygon + tax-map numbering only (no owner/value CAMA) | not needed (layer 38 is the join target) |

Follow-ups: (1) the appraised-value **PARID join** (AREIS layer 83 → `market_*_value`) — the
network's first multi-layer parcel connector; (2) a **land-assembly screen** near Waterville
(ownership-consolidation + industrial/utility rezoning from layer 38, value step-ups once the join
lands), output committed to `data/extracted/toledo/gis/`. Both filed as issues off #384.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Lucas County AREIS parcels + zoning wired (#384); appraised-value PARID join + land-assembly screen are tracked follow-ups.
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'toledo' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
