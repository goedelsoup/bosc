# Onboarding — Defiance (defiance)

Living record for the Defiance watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile (Toledo Edison / ATSI, #236)
- [~] **Data-center activity** — self-research first pass run (`watermark research run`); see research summary + proposals below (#247)
- [~] **Per-jurisdiction GIS** — flood = shared national NFHL (wired). County parcels/zoning `[open]` — Defiance County GIS is on **bhamaps with an expired TLS cert** (same host/case as Van Wert); no AGOL opendata hub; City of Defiance zoning is map-only. See GIS discovery below.

## GIS discovery (2026-06-19; schema-driven GIS, #237)

Unlike Williams (rich AGOL) and Putnam (self-hosted valid ArcGIS), **Defiance County is the
bhamaps / expired-cert case — identical to Van Wert**: parcels are served through Bruce Harris &
Associates at `ags.bhamaps.com` (folder `DefianceOH`), whose **TLS certificate is expired**
(`curl: (60) SSL certificate problem: certificate has expired`; `ssl_verify=10`), so
`cached_get`/httpx cannot consume it without disabling verification (not done — won't weaken TLS
for an external host). No Defiance County ArcGIS Online opendata hub was found, and the City of
Defiance publishes zoning as map/PDF (`cityofdefiance.com/167/Districts-Zones-Maps`), not a REST
service.

| layer | endpoint | finding | status |
|---|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) | wired in the profile (`gis_flood`) | wired |
| parcels (county) | `ags.bhamaps.com/.../DefianceOH/...` (Bruce Harris & Assoc); auditor Beacon at `auditor.defiance-county.com` | **TLS cert expired** — not consumable by the connector; parcels otherwise via the auditor Beacon viewer + Engineer's-office line work | `[open]` |
| zoning | City of Defiance "Districts, Zones & Maps" | map/PDF only; no zoning REST catalog found | `[open]` |

Follow-up (a research/issue lead): re-probe the Defiance County bhamaps PAT MapServer once its TLS
cert is renewed (then register a `GisParcelSchema` from the live field list) — this is the **same
fix as Van Wert's** (shared `ags.bhamaps.com` host), so renewal would unblock both at once; or fall
back to the Engineer's-office parcel shapefile. Accept City zoning as map-only here.

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/defiance/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/defiance/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/defiance/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/defiance/baseline.yaml |
| rsei | ok | reference/rsei/defiance/inventory.yaml |
| consumer-energy | ok | reference/eia/defiance/consumer-energy.yaml |
| grid-profile | ok | reference/eia/defiance/grid-profile.yaml |

## Self-research (Phase 5; #247) — 2026-06-19

First automated-research pass (`watermark research run`, 21 turns, $1.58, read-only over the corpus) →
`data/research/onboard-defiance-maumee-mainstem-2026-06-19/` (`findings.md` + `manifest.yaml`).

**Headline — the mainstem thesis confirmed.** Defiance WWTP (OH0024899, 12 MGD ≈ 18.6 cfs) → Maumee
mainstem, dilution ≈ **6.2:1** ("tight," not a violation) vs. Lima's tributary plants at **0.01–0.42:1
(violations)** on the same screen. Same model, same basin, comparable plant size — the only variable
is the receiving water. **Lima's effluent-dominance is driven by receiving-water *choice*, not plant
size; Defiance is the clean confirmation** (cf. `docs/bigger-picture.md` §2). Caveat: the 6.2:1 uses
the Waterville (04193500) proxy ~50 mi downstream; the reach gage 04192500 is registered but not in
the derived 7Q10, so the true reach dilution is **likely tighter** (proposal #1 below).

**Data-center activity:** nothing on the BOSC record today (no permits / deeds / entity-graph parties
/ land assembly) — a finding, but **provisional** pending the GIS + `--research` discovery the
connector can't yet run (proposal #4). Adjacent energy-corridor lead noted: ANR Pipeline Defiance
Compressor Station (NPDES OH0079294).

**Serving utility — VERIFIED this pass (the "Bryan trap" checked & cleared).** Defiance is **not** a
municipal: the City of Defiance is absent from the EIA-861S short form, and the EIA-861 service-
territory file + utility sources confirm **The Toledo Edison Co (#18997, FirstEnergy / PJM ATSI)**
distributes to the city (the county's other IOU is AEP Ohio #14006; two rural co-ops also serve the
county). The profile's `eia861_utility_number=18997` and the PUCO/ATSI grid path are **correct** — so
the distilled "verify serving utility" proposal is **resolved here and not filed** as an open issue.

**Proposals filed as sub-issues of #238** (4 of the 5 distilled; the utility proposal is resolved above):

1. **Derive reach-specific Defiance 7Q10** (USGS 04192500 + 04191500) — replace the Waterville proxy; the reach dilution is likely tighter than 6.2:1.
2. **Pull the OH0024899 NPDES fact sheet** — characterize the 1 informal + 1 formal enforcement action, anchor the permit-cited 7Q10, populate `plant_receiving`.
3. **Audit RSEI currency** (all 19 facilities cap at `last_year: 2014`) + define a non-zero `toxic_corridor_bbox`. — **RESOLVED (#393, 2026-06-21):**
   - *Currency is the RSEI v234 vintage ceiling, NOT a Defiance truncation.* Every one of the network's 7 committed site inventories (Lima/Findlay/Ottawa/Van Wert/Fort Wayne/Toledo/Bryan) caps at `last_year: 2014` — that is the data ceiling of EPA RSEI **v234** (`Settings.rsei_version`), not a partial pull. A post-2014 refresh requires a *global* `rsei_version` bump (all sites + the network), filed as **#436** — **not** a per-site re-pull.
   - *Operating status (live EPA TRI / Envirofacts, 2026-06-21 — a post-2014 source):* **GM Defiance Casting is active** — now "GENERAL MOTORS LLC GLOBAL PROPULSION SYSTEMS," `fac_closed_ind=0`, TRI forms through **2024**; the three **Johns Manville** plants are all `fac_closed_ind=0` (Plants 2 & 8 reporting through 2014, Plant 3 last 2003). So the RSEI picture (frozen ≤2014) **understates** current Maumee-corridor risk where this heavy industry remains active — exactly the failure mode the issue flagged.
   - *`toxic_corridor_bbox` defined:* `(41.26, 41.31, -84.40, -84.28)` — the Defiance industrial cluster on the Maumee/Auglaize from the Auglaize/Tiffin confluence downstream (captures GM Defiance Casting + all three Johns Manville plants + GT Technologies; excludes the far-west Hicksville cluster). The box is the screen-time scoping instrument (`toxics._in_corridor`), tagged `assumption` for any facility without an independently-cited receiving water.
4. **Register the Defiance County GIS connector + run `--research`** to populate the data-center dimension — `--research` **done** (Phase-5, 2026-06-19); the GIS half is the **bhamaps / expired-cert** case (#394, shared host with Van Wert #421 — blocked until renewal).

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (Phase 5, 2026-06-19; serving-utility verified, 4 proposals filed as sub-issues of #238; triage data/research/onboard-defiance-maumee-mainstem-2026-06-19/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'defiance' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
