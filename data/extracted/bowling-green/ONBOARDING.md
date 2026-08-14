# Onboarding — Bowling Green · Middleton Twp (bowling-green)

Living record for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard`. Check items as you complete them; a site is **not** promoted (`data/sites.yaml` `status`/`selectable`, then `watermark sites sync`) until the gate is clear.

**PROMOTED 2026-08-14 (#1433)** — `status: live` + `selectable: true`, the **8th** selectable site, on **Sidney / Troy-Piqua / Van Wert parity**: the readiness block is byte-identical to all three (`case` tier; backdrop/places/record/inquiry `live`, facility `seeded`).

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [x] **Data-center activity** — extracted permits/records + entity graph (corpus extraction; seed proposals via `watermark onboard --research`, #247)
- [x] **Per-jurisdiction GIS** — parcels/zoning connector (the known lift; see docs/onboarding.md)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/bowling-green/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | ok | HSG C/D; matches profile (dual group: drained C / undrained D; record it verbatim and let pre_drainage_condition/post_drainage_condition resolve it) |
| climatology | ok | reference/hydrology/bowling-green/nasa-power-climatology.yaml |
| basin-screen | ok | 26 POTWs, 1 screened, **1 violation** (was 0/0 — the `portage` basin was unregistered; #1433) |
| econ-baseline | ok | reference/economics/bowling-green/baseline.yaml |
| rsei | ok | reference/rsei/bowling-green/inventory.yaml |
| consumer-energy | ok | reference/eia/bowling-green/consumer-energy.yaml |
| demand-pressure | ok | reference/eia/bowling-green/demand-pressure.yaml |
| grid-profile | ok | reference/eia/bowling-green/grid-profile.yaml (utility #2054, regenerated after the profile's EIA-861 number was resolved) |

## Review gate (blocking)

- [x] Every written reference value is reviewed against a cited source (no fabricated values). **#1433: three defects found and fixed, the fourth site running for four.** (1) The published `disclosure_citation` asserted "Phase 2 signaled in Meta's 2026-01-07 trustees letter" — #1438 read that letter and the word does not appear in it; replaced with the genuine multi-building signal, the zoning inspector's 2025-01-15 report of the applicant's schedule. (2) The same published string carried the press's "~750-ac Liames assembly" while #1436 had *measured* 775.020 ac deeded / 774.878 ac planar off Wood County CAMA; both figures now named, measurement first. (3) The inverted 2026-07-07 roll call survived in `data-centers.md` and twice in `bosc-site-footprint.yaml` — #1438 corrected it only in `record-watch.yaml`, which is the standing lesson that a corrections block records a figure was fixed SOMEWHERE, not everywhere. Arithmetic re-checked: the IT-load screens reproduce exactly (715,000 sq ft x 75 W = 53.625 MW low; x 250 W = 178.75 MW, corroborating the disclosed ~180), and `mgd_to_cfs(10.0)` reproduces the fact sheet's printed 15.47 cfs.
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **#1436: the profile was updated.** The survey returns the DUAL group `C/D` — 428 of 428 interior points over the committed campus, at 6×6 / 8×8 / 10×10 / 12×12 / 16×16 — against a profile that carried a plain `D` inferred from the Great Black Swamp lakebed clays. The letter was not the error; the *form* of the rating was. `dominant_hsg` now records `C/D` verbatim and `pre_drainage_condition` / `post_drainage_condition` resolve it per scenario.
- [x] basin-screen coverage is sane for this site's receiving waters. **#1433: the `portage` basin did not exist.** `SiteProfile.basin` is `portage`, which was registered in neither `echo.BASINS` nor `basin._BASIN_POTW_INVENTORY`, so the screen fell through to a non-existent `portage-wwtp.potw.yaml` and degraded to an empty 0/0 — correctly, but silently. Registered HUC-8 **04100010 "Cedar-Portage"** and pulled the inventory: **26 POTWs**, of which **Bowling Green (OH0024139, 10.0 MGD) is the largest in the basin**. Screen now reads 26 total / **1 screened / 1 violation** — this site's own outfall at **0.024:1 chronic, 0.018:1 acute**, both `[verified]` from fact-sheet Table 12. The other 25 are unscreenable: ECHO carries no receiving water for 21 of them, and the remaining 4 name ungaged tributaries or two waters at once. **No Portage mainstem gage is registered on purpose** — it would screen zero rows today while creating a denominator that could later reach the North Branch and Poe Ditch outfalls above it, which is the 17x-overstatement defect class from #1992/#1995. See `data/reference/echo/README.md`.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). **#1436: `wood_gis` (`WOOD_PARCEL_SCHEMA`, the county's own Vision CAMA join) + `middleton_gis` (`MIDDLETON_ZONING_SCHEMA`, the TOWNSHIP's parcel-joined districts — the campus is 6 mi outside the city, so the City of Bowling Green's zoning layer is the wrong instrument for it).**
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/). **Not run — and not the basis of this promotion.** The eight native sub-issues (#1434-#1441) each did their own sourced research against primary instruments, which is what the record, places, power, water, grid and story domains were built from; a `--research` sweep would be a proposal generator on top of an already-worked corpus. Left open deliberately rather than ticked.
- [x] PROMOTION IS A SEPARATE MANUAL EDIT: flip `status: live` + `selectable: true` for 'bowling-green' in **`data/sites.yaml`** (NOT `web/src/lib/sites.ts` — that path is retired; the frontend registry is generated by `watermark sites sync`), parity-gated. onboard never auto-promotes. **Done 2026-08-14 (#1433)**, together with the two `sites.test.ts` / `sites.multisite.test.ts` selectable arrays and a parity assertion.
