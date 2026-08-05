# Onboarding — West Union · Adams Co (west-union)

Living record for the West Union · Adams Co watershed point (basin: ohio-brush-creek), scaffolded by `bosc onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [ ] **Data-center activity** — extracted permits/records + entity graph (corpus extraction; seed proposals via `bosc onboard --research`, #247)
- [ ] **Per-jurisdiction GIS** — parcels/zoning connector (the known lift; see docs/onboarding.md)

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/west-union/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | parcel geometry missing: reference/west-union/parcel-assemblage.geojson |
| climatology | ok | reference/hydrology/west-union/nasa-power-climatology.yaml |
| basin-screen | ok | 5/23 dischargers screened (0 violations, 0 tight) |
| econ-baseline | ok | reference/economics/west-union/baseline.yaml |
| rsei | ok | reference/rsei/west-union/inventory.yaml |
| consumer-energy | error | Client error '403 Forbidden' for url '<https://api.eia.gov/v2/seriesid/ELEC.PRICE.OH-RES.A>' |
| grid-profile | error | Client error '403 Forbidden' for url '<https://api.eia.gov/v2/electricity/rto/daily-region-data/data?frequency=daily&data%5B0%5D=value&facets%5Brespondent%5D%5B%5D=PJM&facets%5Btype%5D%5B%5D=D&facets%5Btimezone%5D%5B%5D=Eastern&start=2024-01-01&end=2024-12-31&sort%5B0%5D%5Bcolumn%5D=period&sort%5B0%5D%5Bdirection%5D=asc&length=5000>' |

The **basin-screen** row was re-verified on 2026-08-05 after #1120 registered the
`ohio-brush-creek` basin and committed its ECHO inventory; it moved `skipped 0/0` → `ok 5/23`.
Every other row is from the last full onboard run (`onboard` writes this file only when it is
absent, so a human's checkmarks survive a re-run). The two EIA `error` rows both succeeded on the
2026-08-05 re-run — refreshing their committed outputs is a separate change, so it was
deliberately not folded in here. Both are **EIA API v2** pulls — `consumer-energy` via
`watermark.economics.connectors.eia`, `grid-profile` via `watermark.grid.interchange` (EIA-930)
— not BLS QCEW: QCEW is the series behind `econ-baseline`, which ran clean here, and an earlier
version of this note misattributed the deferral to a QCEW vintage move.

**What the 5/23 does and does not say.** The five screened POTWs are the ones whose ECHO
receiving water is the **Ohio River mainstem** and nothing else — none is on Ohio Brush Creek,
and none is in Adams County except Manchester. A sixth (New Richmond WWTP) names the Ohio River
*and* Twelve Mile Creek; ECHO does not say which carries its flow, so it is refused rather than
credited with the river's denominator. The West Union WWTP itself is still unscreened, for two
independent reasons that are both `[open]`: ECHO carries no receiving water for it, and its
documented receiver (Beasley Fork) is ungaged. See `data/reference/echo/README.md` § Ohio Brush
Creek basin.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'west-union' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
