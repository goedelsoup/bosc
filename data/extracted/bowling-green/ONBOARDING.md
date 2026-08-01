# Onboarding — Bowling Green · Middleton Twp (bowling-green)

Living record for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

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
| basin-screen | skipped | 0/0 dischargers screened (0 violations, 0 tight) |
| econ-baseline | ok | reference/economics/bowling-green/baseline.yaml |
| rsei | ok | reference/rsei/bowling-green/inventory.yaml |
| consumer-energy | ok | reference/eia/bowling-green/consumer-energy.yaml |
| demand-pressure | ok | reference/eia/bowling-green/demand-pressure.yaml |
| grid-profile | ok | reference/eia/bowling-green/grid-profile.yaml (utility #2054, regenerated after the profile's EIA-861 number was resolved) |

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **#1436: the profile was updated.** The survey returns the DUAL group `C/D` — 428 of 428 interior points over the committed campus, at 6×6 / 8×8 / 10×10 / 12×12 / 16×16 — against a profile that carried a plain `D` inferred from the Great Black Swamp lakebed clays. The letter was not the error; the *form* of the rating was. `dominant_hsg` now records `C/D` verbatim and `pre_drainage_condition` / `post_drainage_condition` resolve it per scenario.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). **#1436: `wood_gis` (`WOOD_PARCEL_SCHEMA`, the county's own Vision CAMA join) + `middleton_gis` (`MIDDLETON_ZONING_SCHEMA`, the TOWNSHIP's parcel-joined districts — the campus is 6 mi outside the city, so the City of Bowling Green's zoning layer is the wrong instrument for it).**
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'bowling-green' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
