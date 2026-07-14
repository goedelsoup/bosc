# Onboarding — Mansfield (mansfield)

Living record for the Mansfield watershed point (basin: muskingum), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [ ] **Data-center activity** — extracted permits/records + entity graph (corpus extraction; seed proposals via `watermark onboard --research`, #247)
- [ ] **Per-jurisdiction GIS** — parcels/zoning connector (the known lift; see docs/onboarding.md)

## Last onboard run (#1427 — backdrop floor)

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml (shared; no muskingum mainstem added — see note) |
| corridor-ddf | ok | reference/hydrology/mansfield/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | ok | HSG D; matches profile |
| climatology | ok | reference/hydrology/mansfield/nasa-power-climatology.yaml |
| basin-screen | skipped | 0/0 dischargers screened — expected: no committed Muskingum POTW inventory (correct, not a gap) |
| econ-baseline | ok | reference/economics/mansfield/baseline.yaml (20 sectors, 2014–2024) |
| rsei | ok | reference/rsei/mansfield/inventory.yaml (v2.3.12; 58 facilities, 44 scored) |
| consumer-energy | ok | reference/eia/mansfield/consumer-energy.yaml |
| demand-pressure | skipped | no documented facility (SiteProfile.facility is None) — #1428 |
| grid-profile | ok | reference/eia/mansfield/grid-profile.yaml (Ohio Edison Co #13998, PJM) |

**Backdrop floor is live** — `watermark --site mansfield export` reports `readiness.backdrop = live`
(economics-baseline + consumer-energy + rsei all present), tier **`case`** (floor live + `places`
already live via #1431). Profile knobs filled for the floor: design point (40.7585/-82.5155 = the
Atlas-14 point), `corridor_name` (Rocky Fork Mohican), `dominant_hsg` = D (SSURGO), the
serving-utility citation (Ohio Edison #13998), and `county_name`.

> **NWIS gage note (deferred to #1429, water domain):** the profile's `nwis_sites`
> (`03131000`/`03130500`/`03132500`) are period-of-record-only gages (last daily streamflow
> 1932/1978/1939). The live downtown gage is **03130647 Touby Run at W 6th St** (data through
> 2026-07-12); Rocky Fork at Lucas **03131122** ran through 2020. `nwis_sites` feeds only the
> hydrology values connector (not the backdrop floor), so this is left for #1429 to reconcile
> alongside the 7Q10 / routing work. Muskingum mainstems are absent from `_MAINSTEM_GAGES`
> (`basin.py`), so `derive-low-flows` adds no Mohican-branch 7Q10 row here — also #1429.

## Review gate (blocking)

- [x] Every written reference value is reviewed against a cited source (no fabricated values) — floor datasets reviewed: QCEW 2024 (Richland Co), RSEI v2.3.12, EIA consumer-energy (OH), grid = Ohio Edison Co #13998, Atlas-14 PDS at the downtown point.
- [x] SSURGO dominant HSG matches the profile — `dominant_hsg` = D committed with SSURGO citation (#1427).
- [x] basin-screen coverage is sane for this site's receiving waters — 0/0 is expected (no committed Muskingum POTW inventory; the Rocky Fork/Mohican reach is a #1429 water-domain lift).
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'mansfield' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
