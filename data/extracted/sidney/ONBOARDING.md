# Onboarding — Sidney (sidney)

Living record for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics (Shelby Co; 39 facilities, 32 scored; top by RSEI Score = THERMOSEAL INC), consumer energy, grid profile (serving utility **Dayton Power & Light Co** / AES Ohio, EIA-861 #4922, PJM / PUCO — pinned from EIA-861 2024 Service_Territory for Sidney; *not* "City of Shelby" #17043, a Richland-County muni)
- [~] **Data-center activity** — self-research first pass run (#247, 2026-06-22). `[verified]` **zero** Sidney / Shelby-County records in the corpus (no documents, extractions, or entity-graph nodes) — a flat no-data finding, *not* evidence none is proposed. `facility=None`. `[open]` sweep target: the **Sidney / I-75 manufacturing corridor** (Emerson/Copeland refrigeration HQ). **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- [ ] **Per-jurisdiction GIS** — Shelby County parcels / City of Sidney zoning connector (the known lift; see docs/onboarding.md). Flood = national NFHL (wired).

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/sidney/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/sidney/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/sidney/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/sidney/baseline.yaml |
| rsei | ok | reference/rsei/sidney/inventory.yaml — 39 facilities (32 scored) |
| consumer-energy | ok | reference/eia/sidney/consumer-energy.yaml |
| grid-profile | ok | reference/eia/sidney/grid-profile.yaml — Dayton Power & Light #4922, PJM |

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'sidney' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.

## Self-research (Phase 5; #247) — 2026-06-22

- [x] Self-research first pass reviewed (`watermark onboard sidney --research`; ~$1.2, 33 turns; 5 proposals in `data/research/onboard-sidney-…-2026-06-22/`). The **upper-upper Great Miami headwaters** node (Shelby Co), the next mainstem city *upstream* of Troy/Piqua — the distinctive angle is the **compressor/refrigeration manufacturing** base (Emerson/Copeland HQ) on the upper Great Miami buried-valley aquifer.
- `[verified]` **zero** Sidney/Shelby-County records in the BOSC corpus as of 2026-06-22 — a no-data finding (not a weak one). The receiving-water screen has **no committed at-site 7Q10** for the Great Miami at Sidney / Loramie Creek yet — the derived low-flow file remains Maumee-only.
- Proposals filed as sub-issues of **#481**: derive the Great Miami / Loramie 7Q10; build the Great Miami ECHO NPDES discharger inventory; ~~pin the Shelby County retail utility + EIA-861 number (unblocks `grid-profile`)~~ **done** — Dayton Power & Light Co (AES Ohio) #4922, from EIA-861 2024 Service_Territory; `grid-profile` now runs; run the Sidney / Shelby-County data-center sweep.
