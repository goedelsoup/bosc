# Onboarding — Wilmington (wilmington)

Living record for the Wilmington watershed point (basin: little-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics (Clinton Co, 21 facilities / 13 scored; top = Stanley Works), consumer energy, grid profile pinned to **Dayton Power & Light** (AES Ohio #4922, PJM/PUCO; EIA-861 2024 Service_Territory — the Wilmington Air Park LSE)
- [~] **Data-center activity** — self-research first pass run (#247, 2026-06-22). `[verified]` **zero** Wilmington / Clinton-County records in the corpus — a flat no-data finding, *not* evidence none is proposed. `facility=None`. Sweep register + load-driver record committed: `data-centers.md` (#519 / #891) — the Air Park comparator thread + the six-instrument load-driver pass (JobsOhio, AES Ohio DAY-zone interconnect, OEPA air/NPDES, recorder/SOS, Port Authority), all `[open]`/to-run. **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- [x] **Per-jurisdiction GIS** — **parcels and zoning both wired to county/city layers** (#1470, superseding the #887 substitute). `gis_parcel` = `CLINTON_PARCEL_SCHEMA` (`clinton_gis`) — the Clinton County GIS Department's `cntyparcelsRealPropData_gdb` layer 0, the full auditor CAMA join (owner, deed instrument, conveyance date + consideration, appraised values, legal description, tax district). It **replaced** the #887 OGRIP statewide substitute, which is owner-redacted *and* reports a null `CurrentTo` for Clinton — it could name no grantee, so the whole corridor was invisible through it. `gis_zoning` = `WILMINGTON_ZONING_SCHEMA` — the City's published districts via CCRPC `ProposedZoning9` layer 0 (13 districts, polygon-only, city limits only). Flood = national NFHL (wired).

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/wilmington/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | ok | HSG C; matches profile (was `skipped` for want of committed parcel geometry — #1470) |
| climatology | ok | reference/hydrology/wilmington/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/wilmington/baseline.yaml |
| rsei | ok | reference/rsei/wilmington/inventory.yaml — 21 facilities (13 scored) |
| consumer-energy | ok | reference/eia/wilmington/consumer-energy.yaml |
| grid-profile | ok | reference/eia/wilmington/grid-profile.yaml — Dayton Power & Light #4922, PJM DAY zone (AES Ohio holding co, #888) |

## Batch follow-up (2026-07-03) — #516 / #519 / #886 / #887 / #888 / #891

- **#888 grid** — grid-profile `serving_utility` enriched to the `_UTILITY_GRID[4922]` citation (The AES Corporation (AES Ohio) holding co; PJM **DAY** transmission zone). Utility number + BA + LMP zone all cited.
- **#516 / #886 low-flow** — upstream Little Miami reach at Oldtown (`03240000`) added to `basin._MAINSTEM_GAGES`, bracketing the ungaged Todd Fork with Milford (`03245500`); the drainage-area-ratio method + instruments-to-pull documented in `low-flow-screen.md`. Receiving water = Todd Fork → Little Miami (HUC 05090202); WWTP → Lytle Creek (NPDES OH0028134, cited). `[open]` the specific drainage areas (StreamStats / NWIS) and the `hydrology_balance`/`hydrology_scenario` scope-guard (needs an identified footprint, #887).
- **#887 GIS parcels** — OGRIP Clinton connector wired; footprint geometry `[open]` (no identified site). **Superseded 2026-08-01 by #1470** — see below.
- **#519 / #891 sweep** — `data-centers.md` register + load-driver verification record committed; corpus records zero; six external instruments to-run.

## Places domain (2026-08-01) — #1470

The corridor geometry is committed and `readiness.places` goes **absent → live**. The tier was
already **case** — #1405 derived a site's corpus scope from its slug, which pulled the
`oepa/wilmington` permits into scope and floated `record` to live. Nothing else moves here:
`facility` stays `seeded` (the #1630 documentary-depth rule — the IT load is a floor-area
SCREENING bracket, not a permit) and `story` stays `absent`.

- **`data/reference/wilmington/parcel-assemblage.geojson`** — seven contiguous Clinton County
  parcels, **1,023.764 ac deeded / 1,023.786 ac planar**, in two groups (`corridor_role`): the
  three deeded to **Amazon Data Services, Inc.** (478.885 ac; the 471.609-ac campus tract at
  1488 S US 68 plus two ROW strips, one deed — instrument **2025-00005287**, 2025-12-10,
  **$86,436,000**) and the four rezoned by **O-26-04 – O-26-07** (544.879 ac, ownership
  unchanged — **no Ardent/TAC entity holds land in Clinton County**). Their union is a **single**
  polygon whose area equals the sum of the parts, so the register's "~1,000+ ac corridor" is now a
  measurement rather than a sum of press acreages.
- **`data/extracted/wilmington/bosc-site-footprint.yaml`** — the parcel-grounded footprint record;
  `dominant_hsg` **`C`** `[verified]` (SSURGO, grid-stable over the campus at 8×8–16×16), zoning
  **`LI`** `[verified]` for the campus. Building / impervious / developed stay `[open]`.
- **Profile** — `parcels_url` + `gis_parcel` re-pointed to the county auditor CAMA;
  `zoning_url` + `gis_zoning` wired to the City layer; `dominant_hsg` `C` upgraded
  `[inference] → [verified]`; `pre_cover` / `post_cover` / `developed_pervious_cover` set to
  `cropland` / `developed_campus` / `open_space` from the corridor's own auditor land use (all
  seven parcels are Ohio use 110/111, CAUV farmland); `toxic_corridor_bbox` set to
  `(39.400, 39.429, -83.870, -83.833)` — the committed geometry's own envelope rounded outward,
  not a drawn box.
- **Still `[open]`** — the site-plan PDFs and therefore the 9-vs-12 building count (the City
  publishes agendas but no exhibits and no 2026 minutes; the county GIS site-plan layers stop at
  2024 — the pull is an R.C. 149.43 request); the four petitioned tracts' city zoning district
  (the City layer predates their rezoning by nine days); the grantor and recorded easements.
  What *was* obtained from the Planning Commission record: the **2026-01-06** and **2026-03-25**
  agendas, both listing *Property Owner: Amazon Data Services, Inc / Address: 1488 S US 68 /
  Agent: **Bohler Engineering** / Zoning: Light Industrial*. Ingesting those two PDFs is left to
  **#1471** with the rest of the ordinance stack — corpus ingest is that issue's subject.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'wilmington' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.

## Self-research (Phase 5; #247) — 2026-06-22

- [x] Self-research first pass reviewed (`watermark onboard wilmington --research`; ~$1.0, 30 turns; 5 proposals in `data/research/onboard-wilmington-…-2026-06-22/`). The Little Miami's second tracking point (with Xenia), defined by a single dominant large-load tenant — the **Wilmington Air Park** (ex-DHL super-hub → Amazon Air / ATSG). Receiving water is **Todd Fork → Little Miami** (a National & State Scenic River, the same anti-degradation overlay as Xenia).
- `[verified]` **zero** Wilmington/Clinton-County records in the BOSC corpus as of 2026-06-22 — a flat no-data finding. **Gage gap:** Todd Fork is **ungaged** (the old 03244000 is discontinued; Clinton County has no active gage), so the profile brackets it with the downstream Little Miami integrator (Milford, 03245500) + the upstream Oldtown reach — a drainage-area-ratio adjustment is needed before the at-site screen is trustworthy.
- Proposals filed as sub-issues of **#492**: derive the Little Miami / Todd Fork 7Q10 + re-run basin-screen; document a **drainage-area-ratio adjustment** for ungaged Todd Fork; run the Air-Park data-center sweep; ~~pin the Clinton County EIA-861 utility (grid-profile)~~ **done** — Dayton Power & Light #4922 (AES Ohio), PJM/PUCO, from EIA-861 2024 Service_Territory; stand up the Clinton County GIS connector (situs-verified).
