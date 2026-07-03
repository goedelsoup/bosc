# Onboarding — Ottawa (ottawa)

Living record for the Ottawa watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile (AEP Ohio IOU; standard path)
- [~] **Data-center activity** — self-research first pass run (#247); **affirmatively nothing documented** (no Putnam/Ottawa permit, deed, SOS filing, or meeting record in the corpus). See self-research summary below.
- [x] **Per-jurisdiction GIS** — parcels **wired** (`PUTNAM_PARCEL_SCHEMA`, #420 — Putnam County's self-hosted valid-cert ArcGIS, owner + auditor CAMA values on one layer) and flood = shared national NFHL (wired). Zoning stays `[open]` (no standalone REST — village zoning is class-coded / map-only). See GIS discovery below.

## Same-river sibling of Findlay (#237) — the intra-tributary control

Ottawa and **Findlay** sit on the **same receiving river** (the Blanchard), ~40 river-mi apart — the
network's only *along-one-river* pair (every other comparison is across tributaries). This makes
Findlay↔Ottawa a clean control on watershed identity: same river chemistry/regime, two discharge
points. Both are **AEP Ohio** (PJM AEP zone), so the grid story is identical — the comparison
isolates the hydrology/siting variables. (Disambiguation confirmed: this is the **Village of
Ottawa, Putnam County** on the **Blanchard**, gage 04189260 — *not* Ottawa County / Port Clinton,
*not* the Ottawa River of Lima or Toledo.)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/ottawa/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/ottawa/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/ottawa/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/ottawa/baseline.yaml |
| rsei | ok | reference/rsei/ottawa/inventory.yaml |
| consumer-energy | ok | reference/eia/ottawa/consumer-energy.yaml |
| grid-profile | ok | reference/eia/ottawa/grid-profile.yaml |

## GIS discovery (2026-06-19; schema-driven GIS, #237)

Putnam County **self-hosts** an ArcGIS Server (`putnamcountygis.com/arcgis/rest/services`, valid
TLS, `?f=json` queryable) — discovered via the county GIS hub (`new-pcohio.hub.arcgis.com`). Like
Williams/Lucas it carries owner **and** CAMA values; the `Land Use` layer adds soil type and the
full appraisal split. No standalone zoning FeatureServer (the village's zoning is class-coded /
map-only). The parcel `gis_parcel` schema is now **wired** (#420) — `PUTNAM_PARCEL_SCHEMA` in
`watermark.sites`, field-map confirmed from the live `?f=json` + samples (2026-06-21), with an offline
fixture/decode test; the `?f=json` field semantics resolved during wiring are recorded in the
schema comment (OWNERC/OWNERD = situs vs MAILC/MAILD = mailing; `CLASS_1` is the populated land-use
code, not `Class`; `SALEDATE` is MM-DD-YY). No committed reference *data* yet (a `watermark parcels
--site ottawa` pull is a separate reviewed step). Zoning stays `[open]`.

| layer | endpoint | finding | status |
|---|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) | wired in the profile (`gis_flood`) | wired |
| parcels | `putnamcountygis.com/.../Parcels/Parcels/MapServer/0` (polygon) | `PIN`, `OWNER` + situs (`OWNERC`/`OWNERD`) + mailing (`MAILC`/`MAILD`), `CLASS_1` (use code), `SALEDATE`/`PURPRI`, `ACRESOWNED`, `LANDVALUE`/`BLDGVALUE` — owner **and** values on one layer | **wired** (`gis_parcel`, #420) |
| land use (CAMA) | `putnamcountygis.com/.../Land_Features/LandUseParcels/MapServer/0` (polygon) | full CAMA join: `PPClassCod` (use class), `PPAcres`, `PPLandValu`/`PPImprValu`/`PPTotalVal`, `PPOnCauv`, `PPSaleDate`/`ValidSale`, `SOIL_TYPE` | not needed (Parcels carries owner+value); the CAUV/total/soil split is a follow-up if required |
| villages | `putnamcountygis.com/.../Boundaries/Villages/MapServer/0` | village boundaries (incl. Ottawa) | reference |
| zoning | — | no standalone zoning REST found (village zoning is parcel-class-coded / map-only) | `[open]` |

Follow-up: commit the reviewed Putnam parcel reference *data* (a `watermark parcels --site ottawa`
pull); accept zoning as class-coded/map-only here (or locate a Village of Ottawa zoning layer).

## Self-research (Phase 5; #247) — 2026-06-21

First automated-research pass (`watermark research run`, 28 turns, $1.57, read-only over the corpus) →
`data/research/onboard-ottawa-village-of-ottawa-putnam-county-d-2026-06-21/` (`findings.md` + `manifest.yaml`).

**Headline — the same-river control is structurally sound but not yet computable; one derivation
unblocks both ends.** Findlay (upstream, OH0025135, 15 MGD) and Ottawa (downstream, OH0026921,
3.0 MGD) sit on the **same receiving river (the Blanchard)**, ~40 river-mi apart — the network's only
along-one-river pair, holding watershed identity *and* grid (both AEP Ohio / PJM) constant and varying
only the discharge point. But the control **can't be computed**: there is **no Blanchard River 7Q10**
anywhere in the corpus (cited or derived) — the cited 7Q10s are all Lima's, and the derived mainstems
exclude the Blanchard — so the assimilative screen is unrun at *both* nodes. The single Blanchard 7Q10
derivation unblocks Findlay and Ottawa at once (proposals #414/#415/#417).

**Reconciliation discrepancy (worth fixing).** The onboard run reported `derive-low-flows: ok` and
`basin-screen: ok — 7/129 screened`, yet the derived file holds **no Blanchard value** and the 7/129
figure is **identical to Findlay's** — i.e. basin-screen covers only the 7 streams that have a
denominator (4 derived mainstems + 3 cited Lima tributaries), and the Ottawa WWTP is among the
**unscreened** Blanchard dischargers. The "ok" is misleading for this site (proposal #416).

**Data-center activity — affirmatively nothing documented.** `facility=None`; no Putnam/Ottawa
data-center permit, deed, SOS filing, or meeting record in the corpus — the entity graph + timeline are
entirely Lima/Allen. An affirmative "no disclosed Ottawa facility yet," not an empty cell. (This pass
*is* the self-research run the gate calls for; the distilled "run --research" proposal is therefore
resolved here, not filed.)

**Disambiguation (load-bearing).** This is the **Village of Ottawa, Putnam County** on the
**Blanchard** (gage 04189260) — NOT the Ottawa River of Lima/Allen (whose cited 0.2 cfs 7Q10 must
never be applied here), and NOT Ottawa County / Port Clinton.

**Serving utility — VERIFIED.** AEP Ohio (Ohio Power Co #14006, PJM AEP zone), PUCO-regulated IOU —
identical to Findlay, so the same-river control isolates hydrology/siting, not grid (not a municipal;
the Bryan trap doesn't apply). One caveat: ECHO carries `receiving_water: null` for OH0026921, so the
specific outfall receiving water + dilution must come from the NPDES fact sheet (#415) before being
stated as documented.

**Proposals — 4 filed as sub-issues of #381:** #414 (derive the Blanchard 7Q10 — unblocks both Ottawa
and Findlay), #415 (pull the OH0026921 NPDES fact sheet), #416 (reconcile the misleading
derive/screen "ok"), #417 (build the Findlay↔Ottawa comparison artifact once the 7Q10 lands). The 5th
distilled proposal (run `--research`) is resolved by this pass. The Putnam County GIS (self-hosted,
valid-cert, wireable) is tracked under GIS discovery above.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Parcels wired via `PUTNAM_PARCEL_SCHEMA` (#420); zoning stays `[open]` (village zoning is class-coded / map-only, no REST).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; 4 proposals filed as sub-issues of #381 (#414–417).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'ottawa' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
