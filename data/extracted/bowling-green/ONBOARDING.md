# Onboarding — Bowling Green · Middleton Twp (bowling-green)

Living record for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [ ] **Data-center activity** — extracted permits/records + entity graph (corpus extraction; seed proposals via `watermark onboard --research`, #247)
- [ ] **Per-jurisdiction GIS** — parcels/zoning connector (the known lift; see docs/onboarding.md)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/bowling-green/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | parcel geometry missing: reference/bowling-green/parcel-assemblage.geojson |
| climatology | ok | reference/hydrology/bowling-green/nasa-power-climatology.yaml |
| basin-screen | skipped | 0/0 dischargers screened (0 violations, 0 tight) |
| econ-baseline | ok | reference/economics/bowling-green/baseline.yaml |
| rsei | ok | reference/rsei/bowling-green/inventory.yaml |
| consumer-energy | ok | reference/eia/bowling-green/consumer-energy.yaml |
| demand-pressure | ok | reference/eia/bowling-green/demand-pressure.yaml |
| grid-profile | ok | reference/eia/bowling-green/grid-profile.yaml (utility #2054, regenerated after the profile's EIA-861 number was resolved) |

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'bowling-green' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
