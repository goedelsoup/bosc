# Onboarding — Xenia (xenia)

Living record for the Xenia watershed point (basin: little-miami), scaffolded by `bosc onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

Xenia is the network's **first Little Miami-basin site** — a **third basin branch** after the Maumee lake plain and the Great Miami / Mad River corridor (tracking #444 / epic #440). It is the **WPAFB-adjacent** Greene County node, SE of Wright-Patterson AFB. Its distinguishing influence is **not a new geology** but a heightened **regulatory overlay** the other sites lack: the **Little Miami is a National & State Scenic River** (NPS Wild & Scenic + Ohio Scenic River) `[reference]` — a protected receiving water whose anti-degradation status materially constrains a large new discharger/withdrawal and likely raises the in-stream passby minimum. The aquifer is the same buried-valley sole-source system (the Xenia/Beavercreek well fields draw on the Mad River / Little Miami outwash valleys), but the inter-valley till uplands at Xenia proper are less permeable than the Mad River outwash — so the dominant HSG is footprint-dependent.

## Dimension coverage

- [~] **Hydrology** — corridor-DDF + climatology connectors ran (Xenia-specific, cited; Atlas-14 24h 2-yr 2.73 in → 100-yr 5.51 in). But the receiving-water screen is **substantively empty**: there is **no Little Miami 7Q10** (the derived table is Maumee mainstems only — none of the three Xenia gages 03240000/03241500/03242050 has a derived low flow; `derive-low-flows` is not extended to this basin), and the basin-screen ran against the *Maumee* ECHO inventory (no Little Miami coverage). **The distinctive blocker:** the Little Miami's **Scenic-River anti-degradation overlay** `[reference]` is unquantified — it is the site's defining constraint and likely raises the passby minimums (currently `0.0 [open]`). SSURGO skipped (no footprint → HSG B stays `[inference]`, footprint-dependent: valley outwash A/B vs. till-upland C/D).
- [x] **Economics** — county baseline + consumer-energy ran (high-confidence: Greene Co, pop 168,531). The economics **cut against** an existing data-center cluster: **Professional/Scientific/Technical (NAICS 54) LQ 2.11** is the WPAFB defense-contractor signature (`[inference]`, *not* data-center), while **Information (NAICS 51) LQ 0.29** is well below national — no existing IT-hosting concentration. RSEI toxics ran (Greene Co, 20 facilities / 17 scored; top by modeled Score: Unison Industries — aerospace); grid-profile ran on the now-pinned serving utility **Dayton Power & Light** (AES Ohio, EIA-861 #4922; PJM/PUCO; verified from the EIA-861 2024 Service_Territory).
- [~] **Data-center activity** — self-research first pass run (#247). `[verified]` **zero** Xenia/Greene/Little-Miami/Beavercreek records in the corpus (0 matches across 1,485 document lines; entity graph entirely Lima). `facility=None`; *as of this corpus there is no Xenia data-center land assembly or permit record* — a finding, not a gap. The `[open]` overlays are the **WPAFB defense-supplier corridor** (the GDIT/RSO ecosystem in `cloud-consumer-candidates.yaml`) and the **WPAFB groundwater plume** intersecting the same sole-source aquifer. See self-research summary below.
- [ ] **Per-jurisdiction GIS** — Greene County parcels / City of Xenia zoning connector (the known lift; see docs/onboarding.md). Flood = national NFHL (wired).

## Last onboard run (2026-06-21, `--research`)

| step | status | output |
|---|---|---|
| scaffold | ok | per-site dirs + READMEs |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml (Maumee mainstems only — no Little Miami) |
| corridor-ddf | ok | reference/hydrology/xenia/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/xenia/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/xenia/nasa-power-climatology.yaml |
| basin-screen | ok (Maumee) | 7/129 dischargers — the Maumee inventory; **no Little Miami coverage** |
| econ-baseline | ok | reference/economics/xenia/baseline.yaml |
| rsei | ok | reference/rsei/xenia/inventory.yaml — 20 facilities (17 scored) |
| consumer-energy | ok | reference/eia/xenia/consumer-energy.yaml |
| grid-profile | ok | reference/eia/xenia/grid-profile.yaml — Dayton Power & Light #4922, PJM |
| self-research | ok | research/onboard-xenia-xenia-data-center-activity-receivi-2026-06-21/ |

## Self-research (Phase 5; #247) — 2026-06-21

`bosc onboard xenia --research` (claude-opus-4-8, 33 turns, $1.07). Findings + manifest in
`data/research/onboard-xenia-xenia-data-center-activity-receivi-2026-06-21/`.

**Bottom line.** Xenia is registered and half-seeded (good hydrometeorology + economics scaffolding)
but **not promotable** — its two load-bearing dimensions are open and its *differentiator* is the
thing still unquantified: the **Scenic-River receiving water**.

- **Receiving-water screen — empty, and the distinctive constraint is unbuilt.** `receiving_water_name`
  is the Little Miami `[verified]`, a **National & State Scenic River** `[reference]` — but there is no
  Little Miami 7Q10 (the derived table is Maumee-only; `derive-low-flows` has not been extended to this
  basin) and no Xenia/Beavercreek WWTP NPDES ingested (`plant_receiving={}`). The Scenic-River
  anti-degradation overlay — the single most important thing to verify here — is not yet captured into
  the passby minimums. The Little Miami **is gaged at/near Xenia (03240000)**, so a derived 7Q10 is
  obtainable.
- **Data-center activity — none documented, and the economics argue against a cluster.** `[verified]`
  zero Xenia primary documents in the corpus. The county employment mix is a **defense-contractor**
  signature (NAICS 54 LQ 2.11 = the WPAFB ecosystem), **not** a data/IT-hosting one (NAICS 51 LQ 0.29,
  well below national) — consistent with "no data-center cluster here yet." The `[open]` work is to
  sweep the Xenia/Beavercreek + WPAFB-corridor for any land assembly/rezoning/utility-tap and either
  pin it or record a flat no-activity finding, with the WPAFB groundwater plume as the contamination
  overlay. **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in.
- **The screen framing.** Like the Mad River sites, the thesis is consumptive draw vs. baseflow on a
  sole-source supply — but with a **regulatory multiplier**: the Scenic-River status is an extra
  constraint on top of the buried-valley abstraction question. Do not copy a Maumee/Lima effluent-
  dominance denominator onto it.
- **Grid is unpinned at the AEP/DAY territory.** Greene County is AES Ohio (Dayton) territory — pin the
  EIA-861 utility number + PJM zone (likely DAY) before publishing any grid figure (Ohio, so the
  cross-state connector axis isn't re-triggered).

**Proposals — triaged.** Of the run's 5 drafts, one is **resolved by this onboarding** (generate the
missing artifacts: this `ONBOARDING.md` + the `--research` pass), so it is recorded here rather than
filed. The genuinely-open work is filed as sub-issues of #444: extend `derive-low-flows` to the Little
Miami basin + ingest the Xenia/Beavercreek WWTP NPDES (the receiving-water inputs); quantify the Little
Miami Scenic-River anti-degradation overlay + passby minimums (the distinctive constraint); and discover/pin
Xenia/Beavercreek + WPAFB-corridor data-center activity (incl. the plume overlay). **Done:** the Greene
County utility + PJM zone is pinned (Dayton Power & Light, EIA-861 #4922, PJM/PUCO) and the RSEI toxics
inventory is run (Greene Co, 20 facilities / 17 scored).

## Batch progress (2026-07-02, #460/#461)

- **#461 grid (DONE).** Already pinned to DP&L / **AES Ohio #4922** / PJM **DAY**; the citation was
  upgraded — #4922 is now registered in `watermark.grid.utility._UTILITY_GRID` (holding company
  **The AES Corporation (AES Ohio)**, DAY zone), so the Xenia grid profile carries a specific
  holding-company citation instead of the generic EIA-861 fallback.
- **#460 data-center sweep (scaffold DONE; web pass to-run).** Committed and catalogued
  `extracted/xenia/data-centers.md`: the flat-no-activity prior (`[verified]` zero corpus records;
  Info NAICS 51 LQ 0.29 vs. the defense-signature NAICS 54 LQ 2.11), the instruments to pull
  (Greene Auditor GIS, Ohio SOS, zoning, OEPA/ECHO OHD000001, AES Ohio DAY large-load queue), and
  the WPAFB TCE/PFAS plume as the `[open]` contamination overlay on the shared buried-valley
  aquifer. Discipline preserved: the Lima/Allen Bistrozzi graph is **not** bridged onto Xenia.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. (HSG B is `[inference]`, footprint-dependent; footprint needed.)
- [ ] basin-screen coverage is sane for this site's receiving waters. (**Currently the Maumee inventory — a Little Miami 7Q10 + the Scenic-River overlay are required.**)
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (Phase 5, 2026-06-21; receiving-water screen empty + Scenic-River overlay unquantified, data-center economics argue against a cluster; proposals triaged — 4 filed as sub-issues of #444, 1 resolved recorded above).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'xenia' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
