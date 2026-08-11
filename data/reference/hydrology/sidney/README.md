# Sidney (sidney) — hydrology connector outputs

Per-site onboarding tree for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard sidney` (#326). Values come from the portable reach connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard sidney` over the Sidney `SiteProfile` (reach connectors: NWIS / NOAA Atlas-14 / SSURGO / NASA-POWER).

## What in here is authored, and what is regenerated

The "regenerate, don't hand-edit" rule above governs the **connector outputs** —
`nasa-power-climatology.yaml` and `atlas14-corridor-ddf.yaml`. Four files beside them are the
opposite, and editing them is how the reach network changes (#1995, #1996):

- `routing.yaml` — the WWTP's receiving reach + structured design flow, hand-authored from the
  NPDES fact sheet.
- `reach-nav.yaml` — the NLDI navigation plan (gage anchors, distances, junction trims).
- `network.yaml` — the magnitude-free confluence topology.
- `reaches.yaml` — per-reach channel lengths. ⚠️ These are cut **ratios**: editing one length moves
  a reach *boundary*, so re-run `watermark --site sidney reaches --write` and write the reported km
  back, or the committed `reaches/sidney.geojson` and this table drift apart.

`reaches/sidney.geojson` (one level up, keyed by slug) IS regenerated — from the three tables plus
the committed NLDI fixtures under `tests/fixtures/hydrology/nldi/`, so
`watermark --site sidney reaches --offline --write` reproduces it byte-for-byte offline.

## Known gaps & caveats

- **Geometry-grade only.** `reaches.yaml` carries `catchments: {}` — no cited CN / Tc / area
  screening set exists for this basin, so there is no routed storm model and the
  `routed-hydrograph` feed correctly self-skips. The reach slopes are schema placeholders that
  feed no computation; a routed model must replace them with cited values first.
- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).

## Regenerate

`watermark onboard sidney`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
