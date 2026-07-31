# Onboarding — Sidney (sidney)

Living record for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics (Shelby Co; 39 facilities, 32 scored; top by RSEI Score = THERMOSEAL INC), consumer energy, grid profile (serving utility **Dayton Power & Light Co** / AES Ohio, EIA-861 #4922, PJM / PUCO — pinned from EIA-861 2024 Service_Territory for Sidney; *not* "City of Shelby" #17043, a Richland-County muni)
- [~] **Data-center activity** — self-research first pass run (#247, 2026-06-22). `[verified]` **zero** Sidney / Shelby-County records in the corpus (no documents, extractions, or entity-graph nodes) — a flat no-data finding, *not* evidence none is proposed. `facility=None`. `[open]` sweep target: the **Sidney / I-75 manufacturing corridor** (Emerson/Copeland refrigeration HQ). **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- [x] **Per-jurisdiction GIS** — **wired (#1379).** Parcels = `SHELBY_PARCEL_SCHEMA` (`shelby_gis`), the Shelby County Engineer's Office AGOL `Parcels` layer carrying the full auditor CAMA join — it **replaced** the OGRIP statewide substitute, which for Shelby is both owner-redacted *and* a 2023-05-23 extract (it predates the entire Project Galaxy transfer). Zoning = `SIDNEY_ZONING_SCHEMA` (`sidney_gis`), City of Sidney `SidneyGIS_AllLayers` layer 270 — polygon-only (district catalog only, no parcel joins), city-limits-only, 2016-adopted; the campus parcel falls in a currency hole in it, so its district stays `[open]`. Flood = national NFHL (wired).

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/sidney/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | ok | HSG D; matches profile (#1379 — was `skipped` for want of parcel geometry) |
| climatology | ok | reference/hydrology/sidney/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/sidney/baseline.yaml |
| rsei | ok | reference/rsei/sidney/inventory.yaml — 39 facilities (32 scored) |
| consumer-energy | ok | reference/eia/sidney/consumer-energy.yaml |
| grid-profile | ok | reference/eia/sidney/grid-profile.yaml — Dayton Power & Light #4922, PJM |

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **(#1379 — the profile was updated: `[inference]` "B" → `[verified]` "D".** The old inference argued from the Great Miami buried-valley sole-source aquifer, but the campus sits ~2 mi west of the valley on the Wisconsinan end moraine — Blount / Glynwood silt loams, HSG D at 62 of 64 sampled points. Same surface-vs-aquifer correction as Urbana and Troy·Piqua.)
- [ ] basin-screen coverage is sane for this site's receiving waters.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). **(#1379 — `shelby_gis` parcels + `sidney_gis` zoning.)**
- [ ] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'sidney' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.

## Self-research (Phase 5; #247) — 2026-06-22

- [x] Self-research first pass reviewed (`watermark onboard sidney --research`; ~$1.2, 33 turns; 5 proposals in `data/research/onboard-sidney-…-2026-06-22/`). The **upper-upper Great Miami headwaters** node (Shelby Co), the next mainstem city *upstream* of Troy/Piqua — the distinctive angle is the **compressor/refrigeration manufacturing** base (Emerson/Copeland HQ) on the upper Great Miami buried-valley aquifer.
- `[verified]` **zero** Sidney/Shelby-County records in the BOSC corpus as of 2026-06-22 — a no-data finding (not a weak one). The receiving-water screen has **no committed at-site 7Q10** for the Great Miami at Sidney / Loramie Creek yet — the derived low-flow file remains Maumee-only.
- Proposals filed as sub-issues of **#481**: derive the Great Miami / Loramie 7Q10; build the Great Miami ECHO NPDES discharger inventory; ~~pin the Shelby County retail utility + EIA-861 number (unblocks `grid-profile`)~~ **done** — Dayton Power & Light Co (AES Ohio) #4922, from EIA-861 2024 Service_Territory; `grid-profile` now runs; run the Sidney / Shelby-County data-center sweep.
