# Onboarding — Wilmington (wilmington)

Living record for the Wilmington watershed point (basin: little-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics (Clinton Co, 21 facilities / 13 scored; top = Stanley Works), consumer energy, grid profile pinned to **Dayton Power & Light** (AES Ohio #4922, PJM/PUCO; EIA-861 2024 Service_Territory — the Wilmington Air Park LSE)
- [~] **Data-center activity** — self-research first pass run (#247, 2026-06-22). `[verified]` **zero** Wilmington / Clinton-County records in the corpus — a flat no-data finding, *not* evidence none is proposed. `facility=None`. Sweep register + load-driver record committed: `data-centers.md` (#519 / #891) — the Air Park comparator thread + the six-instrument load-driver pass (JobsOhio, AES Ohio DAY-zone interconnect, OEPA air/NPDES, recorder/SOS, Port Authority), all `[open]`/to-run. **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- [~] **Per-jurisdiction GIS** — **parcels wired** (#887): OGRIP Ohio statewide view scoped to `County='Clinton'` (Ohio-only → situs-safe; 26,962 parcels, ~99% with situs + StateLUC + geometry, e.g. "1475 TODDS FORK RD" — verified 2026-07-03). `gis_parcel` + `parcels_url` populated. `[open]` **zoning** — City of Wilmington / Clinton County zoning REST not yet discovered (same lift New Albany left open). Flood = national NFHL (wired).

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/wilmington/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/wilmington/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/wilmington/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/wilmington/baseline.yaml |
| rsei | ok | reference/rsei/wilmington/inventory.yaml — 21 facilities (13 scored) |
| consumer-energy | ok | reference/eia/wilmington/consumer-energy.yaml |
| grid-profile | ok | reference/eia/wilmington/grid-profile.yaml — Dayton Power & Light #4922, PJM DAY zone (AES Ohio holding co, #888) |

## Batch follow-up (2026-07-03) — #516 / #519 / #886 / #887 / #888 / #891

- **#888 grid** — grid-profile `serving_utility` enriched to the `_UTILITY_GRID[4922]` citation (The AES Corporation (AES Ohio) holding co; PJM **DAY** transmission zone). Utility number + BA + LMP zone all cited.
- **#516 / #886 low-flow** — upstream Little Miami reach at Oldtown (`03240000`) added to `basin._MAINSTEM_GAGES`, bracketing the ungaged Todd Fork with Milford (`03245500`); the drainage-area-ratio method + instruments-to-pull documented in `low-flow-screen.md`. Receiving water = Todd Fork → Little Miami (HUC 05090202); WWTP → Lytle Creek (NPDES OH0028134, cited). `[open]` the specific drainage areas (StreamStats / NWIS) and the `hydrology_balance`/`hydrology_scenario` scope-guard (needs an identified footprint, #887).
- **#887 GIS parcels** — OGRIP Clinton connector wired (see above); footprint geometry still `[open]` (no identified site).
- **#519 / #891 sweep** — `data-centers.md` register + load-driver verification record committed; corpus records zero; six external instruments to-run.

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
