# Onboarding — Troy · Piqua (troy-piqua)

Living record for the Troy · Piqua watershed point (basin: great-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

Troy · Piqua is the **upper Great Miami mainstem** node (Miami County) — the I-75 corridor between the Great Miami headwaters (Indian Lake / Sidney) and Dayton, **upstream of WPAFB** (#442) and the **upstream complement** to the lower-mainstem Hamilton/Middletown node (#443). Same buried-valley sole-source aquifer, but a **mid-size manufacturing** county (Hobart commercial food-equipment HQ in Troy, auto parts) rather than Butler's heavy steel, and a distinctive **municipal-power split**: Piqua runs its own AMP-member electric utility (Great Miami hydro), while Troy/Miami County is likely AES Ohio. The site also carries a second supply water — the **Stillwater River** (gage 03265000). (UTM 16N, like WPAFB / Hamilton-Middletown — west of the 84°W meridian.) Tracking #475.

## Dimension coverage

- [~] **Hydrology** — corridor-DDF + climatology connectors ran (Troy-centroid, cited; Atlas-14 24h 2-yr 2.67 in → 100-yr 5.71 in; annual precip 2.83 mm/day). The receiving-water screen is unbuilt: no Great Miami / Stillwater 7Q10 (the derived table is Maumee mainstems only — none of the three gages 03262700 [Troy] / 03262500 [Piqua] / 03265000 [Stillwater] has a low flow) and no WWTP ingested (`plant_receiving={}`). SSURGO skipped → HSG B stays `[inference]` (the buried-valley "inverse of Black Swamp" claim, footprint-dependent).
- [x] **Economics** — Miami County baseline + consumer-energy ran (high-confidence: BLS QCEW 2023 / Census ACS5). The signature is **mid-size manufacturing** (the Hobart / auto-parts base), the upstream-mainstem complement to Butler's heavy steel. RSEI toxics ran (Miami Co, 40 facilities / 33 scored; top by modeled Score: Hobart Brothers filler-metals — the manufacturing base named above). grid-profile ran on the now-pinned serving utility **Dayton Power & Light** (AES Ohio, EIA-861 #4922; PJM/PUCO; verified from the EIA-861 2024 Service_Territory) — the county-dominant IOU (Troy); the City of Piqua municipal (#15095) is the Piqua-side split [inference].
- [~] **Data-center activity** — self-research first pass run (#247). `[verified]` **zero** Troy/Piqua/Miami-County records in the corpus (0 matches across 1,485 document lines; entity graph entirely Lima). `facility=None`; *the BOSC corpus contains no Troy/Piqua data-center records as of 2026-06-22* — a no-data finding (not evidence none is proposed). The `[open]` sweep target is the **Piqua / Troy / Tipp City I-75** corridor. **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- [ ] **Per-jurisdiction GIS** — Miami County parcels / City of Troy + Piqua zoning connector (the known lift). **Heed the same-name trap:** there are multiple "Miami County"s nationally (and Miami-Dade FL) — verify the situs is **Miami County OH** from a live `?f=json` sample before wiring any discovered service (or fall back to OGRIP statewide scoped `County='Miami'`). Flood = national NFHL (wired).

## Last onboard run (2026-06-22, `--research`)

| step | status | output |
|---|---|---|
| scaffold | ok | per-site dirs + READMEs |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml (Maumee mainstems only — no Great Miami) |
| corridor-ddf | ok | reference/hydrology/troy-piqua/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/troy-piqua/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/troy-piqua/nasa-power-climatology.yaml |
| basin-screen | ok (Maumee) | 7/129 dischargers — the Maumee inventory; **no Great-Miami coverage** |
| econ-baseline | ok | reference/economics/troy-piqua/baseline.yaml (Miami Co 39109) |
| rsei | ok | reference/rsei/troy-piqua/inventory.yaml — 40 facilities (33 scored) |
| consumer-energy | ok | reference/eia/troy-piqua/consumer-energy.yaml |
| grid-profile | ok | reference/eia/troy-piqua/grid-profile.yaml — Dayton Power & Light #4922, PJM |
| self-research | ok | research/onboard-troy-piqua-troy-piqua-data-center-activi-2026-06-22/ |

## Self-research (Phase 5; #247) — 2026-06-22

`watermark onboard troy-piqua --research` (claude-opus-4-8, 31 turns, $1.23). Findings + manifest in
`data/research/onboard-troy-piqua-troy-piqua-data-center-activi-2026-06-22/`.

**Bottom line.** A registered, half-seeded upper-Great-Miami node — solid hydrometeorology + Miami
County economics, but no receiving-water screen inputs, no RSEI, no GIS, and no data-center record.
Its distinctive angle is the **municipal-power split** (Piqua/AMP vs AES Ohio).

- **Receiving-water screen — blocked.** No Great Miami / Stillwater 7Q10 (derived file is Maumee-only;
  `derive-low-flows` not extended to this Ohio-River-basin reach) and no Troy/Piqua WWTP NPDES ingested
  (`plant_receiving={}`). The Great Miami here is an upper-mainstem reach with the Stillwater as a second
  supply — derive both gages' 7Q10 and cite before any screen statement.
- **Data-center activity — none documented (a no-data finding).** Zero corpus records; `facility=None`.
  Absence means no extracted record, **not** that nothing is proposed in Miami County — the open work is
  an I-75-corridor sweep (commissioners / city councils / OEPA air PTI / recorder deeds) that pins
  activity or records a flat no-activity finding.
- **The distinctive angle — municipal power.** Piqua runs its own AMP-member electric utility (with
  Great Miami hydro); Troy/Miami County is likely AES Ohio (DAY zone). This is the second muni-power
  story in the network (cf. Hamilton) — expect the **EIA-861S short-form** path for the muni (the one
  that bit Bryan). Pin the EIA-861 number(s) + PJM zone before any grid figure.
- **Toxics — measured.** Mid-size manufacturing, not Butler's active heavy-steel discharger
  — the RSEI inventory is now pulled (`fips=39109`, 40 facilities / 33 scored; top by modeled Score:
  Hobart Brothers filler-metals); only `toxic_corridor_bbox` stays empty (`[open]`).
- **Geography caution.** The gage→reach mapping is profile-asserted `[verified]` (confirmed against the
  live USGS Miami-County site list at onboarding); SSURGO HSG stays `[inference]` pending a footprint.

**Proposals — triaged.** The run's SSURGO-HSG draft is a footprint-dependent **gate item** (recorded in
the gate, not filed, like the siblings); the missing-artifacts work is done by this PR. The genuinely-open
work is filed as sub-issues of #475: the Great Miami / Stillwater 7Q10 (extend `derive-low-flows`) + the
Troy/Piqua WWTP NPDES; the RSEI inventory (Miami 39109) is **DONE** (40 facilities / 33 scored), leaving
`toxic_corridor_bbox` open; the Piqua-muni vs AES Ohio split is **DONE** — utility pinned to **DP&L #4922**
(PJM/PUCO, Troy/county-dominant), Piqua municipal #15095 the split `[inference]`; and the I-75-corridor
data-center activity sweep.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. (HSG B is `[inference]`; footprint needed.)
- [ ] basin-screen coverage is sane for this site's receiving waters. (**Currently the Maumee inventory — a Great Miami / Stillwater 7Q10 + an upper-Great-Miami ECHO inventory are required.**)
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md; verify Miami County **OH**, not another Miami County).
- [x] Self-research first pass reviewed (Phase 5, 2026-06-22; upper-mainstem manufacturing node, muni-power split the distinctive angle; 4 proposals filed as sub-issues of #475, SSURGO-HSG kept as a gate item).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'troy-piqua' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
