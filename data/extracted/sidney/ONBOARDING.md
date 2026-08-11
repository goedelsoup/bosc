# Onboarding — Sidney (sidney)

Living record for the Sidney watershed point (basin: great-miami), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics (Shelby Co; 39 facilities, 32 scored; top by RSEI Score = THERMOSEAL INC), consumer energy, grid profile (serving utility **Dayton Power & Light Co** / AES Ohio, EIA-861 #4922, PJM / PUCO — pinned from EIA-861 2024 Service_Territory for Sidney; *not* "City of Shelby" #17043, a Richland-County muni)
- [~] **Data-center activity** — self-research first pass run (#247, 2026-06-22). `[verified]` **zero** Sidney / Shelby-County records in the corpus (no documents, extractions, or entity-graph nodes) — a flat no-data finding, *not* evidence none is proposed. Source: [`data/research/onboard-sidney-sidney-data-center-activity-recei-2026-06-22/findings.md`](../../research/onboard-sidney-sidney-data-center-activity-recei-2026-06-22/findings.md) — the `list_documents` / `list_extractions` / `entities` / `timeline` sweep returned zero matches for Sidney / Shelby / Great Miami / Loramie ("There are no in-corpus primary records for Sidney"); tool list in the run's `manifest.yaml`. `facility=None`. `[open]` sweep target: the **Sidney / I-75 manufacturing corridor** (Emerson/Copeland refrigeration HQ). **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in. *Superseded as a present-tense statement by #1378/#1379 — the site now carries a `SiteFacility`, a DMR extraction, the register, and the committed campus geometry; the line stands as the dated record of that onboarding pass.*
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

- [x] Every written reference value is reviewed against a cited source (no fabricated values). **(#1992 — audited 2026-08-10.)** The connector outputs under `data/reference/*/sidney/` are regenerable and cited by construction; the audit therefore targeted the hand-authored values — the `SiteProfile` knobs and citation strings, which are what the exported `facility` feed publishes.

  **Four `[verified]` figures in `_SIDNEY`'s facility citations were stale**, all of them figures #1380 had already corrected in `incentive-instruments.yaml`'s own `corrections_to_the_register` block without the correction propagating back into the profile:

  | field | was | now |
  |---|---|---|
  | CRA legislation | "Res 18-25" | **Res. 69-25**, adopted 2025-09-08, city-wide — "Res. 18-25 of October 2025" does not exist |
  | PILOT | "$50M PILOT over 15 yr" | **$46,000,000 over 14 years** (CRA Agmt §7(b) + Exh. E) **plus** a separate one-time **$4,000,000** (§8); schools' half divides $21,220,529 SCSD / $3,779,471 UVCC |
  | grading permit | issued 2026-05-14 (×4 sites in the profile, plus a cross-reference in Van Wert's) | signed **2026-05-15** — 5-14-2026 is the City's upload *filename*, which is not evidence of a date |
  | coverage→permit interval | 160 days | **161 days** — derived from the date above, so it moved with it |

  Also annotated rather than changed: the disclosed address "2388 W. Millcreek Road" is kept as the address **as disclosed**, with the note that the situs was retired by the Lot 7658 Consolidation Plat and the parcel of record is now `26-03-201-002` / 1151 S Vandemark Rd (#1379).

  Everything else held. The `[open]`s are honestly marked and stay `[open]` — the campus MW, the zoning district, `noaa_fallback_24h_depth_in`, the cooling design.
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **(#1379 — the profile was updated: `[inference]` "B" → `[verified]` "D".** The old inference argued from the Great Miami buried-valley sole-source aquifer, but the campus sits ~2 mi west of the valley on the Wisconsinan end moraine — Blount / Glynwood silt loams, HSG D at 62 of 64 sampled points. Same surface-vs-aquifer correction as Urbana and Troy·Piqua.)
- [x] basin-screen coverage is sane for this site's receiving waters. **(#1992 — checked 2026-08-10.)** The screen runs the **Great Miami** inventory (`data/reference/echo/great-miami-wwtp.potw.yaml`, 81 POTWs), selected by `SiteProfile.basin` — not the Maumee one; the 129-discharger figure in the run table below is the pre-multi-basin number and is stale. Coverage is 17 of 81 screened (0 violation, 5 tight, 12 ok), 39 unscreenable for no receiving water in ECHO and 25 for an ungaged tributary — reported, not guessed.

  **The check found a real defect, now fixed.** The SIDNEY WWTP was screening at **37.64:1 `ok`** against the *derived* Hamilton mainstem proxy (407.67 cfs), because the cited value that belongs at this outfall was not bound to this permit. Ohio EPA's own denominator for outfall 1PD00009001 is the **24.0 cfs** annual 7Q10 for "GMR above Sidney" (USGS 03261500, 1927–2021; fact sheet Table 14, printed p.32, read off the source PDF text layer) against the fact sheet's own 10.83 cfs (7.0 MGD) design flow — **2.22:1, `tight`**. A 17× overstatement of available dilution. Fixed by a permit-scoped entry (`permits: ["OH0027421", "1PD00009"]`) in `data/reference/hydrology/low-flow-7q10.yaml`, the #1458 mechanism. The bare `great miami river` key still resolves to the derived proxy — verified, so no other discharger moved.

  Follow-up, deliberately **not** taken here: the neighbouring `upper great miami river` entry carries the same 24.0 cfs from Piqua's own fact sheet (1PD00008) and is likewise unbound, so the PIQUA WWTP still screens at 30.29:1 against the proxy rather than ~1.78:1. That is Troy·Piqua's call to make deliberately (#1274), not a side effect of Sidney's promotion.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). **(#1379 — `shelby_gis` parcels + `sidney_gis` zoning.)**
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/). **(Satisfied 2026-06-22 — this box was simply never ticked; see the Self-research section below, which records the run, its cost, and all five proposals filed as sub-issues of #481. Reconciled in #1992.)**
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'sidney' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.

## Self-research (Phase 5; #247) — 2026-06-22

- [x] Self-research first pass reviewed (`watermark onboard sidney --research`; ~$1.2, 33 turns; 5 proposals in `data/research/onboard-sidney-…-2026-06-22/`). The **upper-upper Great Miami headwaters** node (Shelby Co), the next mainstem city *upstream* of Troy/Piqua — the distinctive angle is the **compressor/refrigeration manufacturing** base (Emerson/Copeland HQ) on the upper Great Miami corridor. ⚠️ *This line read "on the upper Great Miami buried-valley aquifer" until #1997 — the refuted premise, still live here after #1379 corrected it everywhere else. The campus is ~2 mi west of the buried valley and 1.68 mi outside the designated sole-source aquifer; see [groundwater.md](groundwater.md).*
- `[verified]` **zero** Sidney/Shelby-County records in the BOSC corpus as of 2026-06-22 — a no-data finding (not a weak one). The receiving-water screen has **no committed at-site 7Q10** for the Great Miami at Sidney / Loramie Creek yet — the derived low-flow file remains Maumee-only.
- Proposals filed as sub-issues of **#481**: derive the Great Miami / Loramie 7Q10; build the Great Miami ECHO NPDES discharger inventory; ~~pin the Shelby County retail utility + EIA-861 number (unblocks `grid-profile`)~~ **done** — Dayton Power & Light Co (AES Ohio) #4922, from EIA-861 2024 Service_Territory; `grid-profile` now runs; run the Sidney / Shelby-County data-center sweep.
