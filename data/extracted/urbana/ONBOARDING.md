# Onboarding — Urbana (urbana)

Living record for the Urbana watershed point (basin: great-miami), scaffolded by `watermark onboard`. **PROMOTED 2026-07-01** (`status: live`, `selectable: true` in `web/packages/core/src/sites.ts`); the site is the network's second live site (after Lima).

Urbana is the network's **first Miami-basin site** (epic #440 / onboarding #441): the clean *headwaters* of the **Mad River buried-valley sole-source aquifer**, upstream of the Springfield/Dayton/Wright-Patterson corridor — the deliberate geological **inverse** of the Maumee lake-plain sites (groundwater-dominated HSG B vs. poorly-drained Black Swamp clays HSG D; sink = Ohio River, not Lake Erie; no Maumee-style nutrient TMDL).

## Dimension coverage

- [~] **Hydrology** — corridor-DDF + climatology connectors ran (cited); **Great Miami ECHO inventory committed** (PR #455: 81 POTWs); basin-screen correct: **14/81 screened, 0 violations, 1 tight**. **Mad River 7Q10 derived** (PR #803, closes #445): LP3 53.67 cfs at USGS 03267000, 39 climatic years 1980–2024 — since **superseded** by the regulatory annual **7Q10 = 35 cfs** [verified] from the OEPA NPDES fact sheet for 1PD00011 (`oepa/urbana/1PD00011.fs.pdf`, #1355); `plant_receiving` set (Urbana WPCF → Mad River, OH0027880/1PD00011, design flow 4.5 MGD [verified]); **`passby_primary_cfs=35.0`** [verified]. **SSURGO ran (#1326):** footprint committed (`extracted/urbana/bosc-site-footprint.yaml`), area-weighted **dominant HSG corrected to C** [verified] (was `[inference]` B).
- [x] **Economics** — county baseline + consumer-energy ran (high-confidence: Champaign Co, manufacturing LQ 4.14, information LQ 0.18 = greenfield signature). RSEI toxics ran (Champaign Co, 12 facilities / 9 scored; top by modeled Score: C V Materials); grid-profile ran on the now-pinned serving utility **Dayton Power & Light** (AES Ohio, EIA-861 #4922; PJM/PUCO; verified from the EIA-861 2024 Service_Territory).
- [x] **Data-center activity** — **RESOLVED** (#1327/#1328/#1330). Highland55 is the **"Urbana Technology Hub" data-center campus** (Thor Equities via its Form8tion unit — Urbana Owner I LLC + Highland55 Investments LLC), disclosed at the **Feb-2026 City of Urbana meeting + site-plan application**: 460,000 sq ft, single-story, ~$1B, closed-loop cooling. This answers the corpus's central `[open]` question — *is Highland55 a data center?* → **yes** — and activates the `facility` readiness domain from `absent` → `seeded` (#1327; a site-plan SCREENING `[inference]` facility seeds the domain rather than lifting it to `live` under the #1630 documentary-depth rule — the committed `manifest.json` carries `facility: seeded`). End-use is `[reference]` (public disclosure; the naming site-plan/permit instrument was not reachable to ingest → not yet `[verified]`); land assembly / developer / deeds are `[verified]` from the Champaign County auditor (#1328). **Methodology correction (#1330):** the disclosed **closed-loop** design (water use "comparable to a standard office building") **undercuts the Mad River water-abstraction thesis** — the binding constraint for this facility is **grid/power** (end-user-funded transmission upgrades, AES Ohio / PJM DAY) + **land use**, not consumptive cooling draw. The MW load, PJM queue position, and any air permit stay `[open]` (#1263 sub-leads); the profile carries an `[inference]` floor-area screening bracket only. See `data/extracted/urbana/datacenter-facility.md` + `highland55-findings.md`. (Earlier record: Highland55 instruments read #447, 2026-06-28 — the §401 WQC named a dedicated **electrical substation**, then the strongest signal.) **Honda "Champaign-area" candidate** stays downgraded [2026-06-28]: `corridor_context: true`; no primary instrument pins to Urbana/Champaign County. See self-research summary below.
- [~] **Per-jurisdiction GIS** — **Champaign County parcel connector wired** (`CHAMPAIGN_PARCEL_SCHEMA`, CCEO parcel_joined layer 0, PR #800 [verified]). **City of Urbana / Champaign Co zoning layer** not found — no public per-parcel REST identified; `gis_zoning=None` [open]. Flood = national NFHL (wired).

## Last onboard run (2026-06-21, `--research`)

| step | status | output |
|---|---|---|
| scaffold | ok | per-site dirs + READMEs |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml (Maumee mainstems only — no Mad River) |
| corridor-ddf | ok | reference/hydrology/urbana/atlas14-corridor-ddf.yaml (24h-100yr 5.54 in) |
| ssurgo-hsg | skipped | footprint missing: extracted/urbana/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/urbana/nasa-power-climatology.yaml |
| basin-screen | ok (Maumee) | 7/129 dischargers — the Maumee inventory; **no Great-Miami coverage** **(superseded — see #446)** |
| basin-screen | ok (Great Miami) | 14/81 screened (0 violations, 1 tight) — `great-miami-wwtp.potw.yaml` (PR #455); 39 no receiving water, 28 no 7Q10 |
| derive-7q10 | ok | `mad river at urbana` — 53.67 cfs LP3 at USGS 03267000, 39 yr (PR #803, closes #445) |
| econ-baseline | ok | reference/economics/urbana/baseline.yaml |
| rsei | ok | reference/rsei/urbana/inventory.yaml — 12 facilities (9 scored) |
| consumer-energy | ok | reference/eia/urbana/consumer-energy.yaml |
| grid-profile | ok | reference/eia/urbana/grid-profile.yaml — Dayton Power & Light #4922, PJM |
| self-research | ok | research/onboard-urbana-urbana-data-center-activity-recei-2026-06-21/ |

## Self-research (Phase 5; #247) — 2026-06-21

`watermark onboard urbana --research` (claude-opus-4-8, 27 turns, $1.02). Findings + manifest in
`data/research/onboard-urbana-urbana-data-center-activity-recei-2026-06-21/`.

**Bottom line.** Urbana is scaffolded but **not promotable** — its two load-bearing dimensions are
both open: data-center activity is the **weakest in the network** and the receiving-water screen has
**no Mad-River denominator at all**.

- **Data-center activity — `[open]`/`[inference]`, no primary record.** The only Urbana-specific signal is **Highland55** (a one-line `[open]` lead in `docs/COURSE.md`; it appears only in analysis text — no deed/NPDES/LLC/CRA/zoning instrument). A second, adjacent signal — **Honda's announced "own Ohio data center" in the "Marysville / Clark / Champaign area"** (`cloud-consumer-candidates.yaml`) — is a demand-fit *candidate profile*, not pinned to Urbana/Champaign. `[verified]` **zero** Urbana/Champaign/Mad-River primary documents are in the corpus. **Method note:** the Lima/Allen Bistrozzi land-assembly graph is **not** bridged in — there is no evidentiary link; any Urbana land assembly stays a separate register. [2026-06-28 update: Highland55 primary instruments now in corpus (PR #803); Honda downgraded to `corridor_context: true` — no pinning instrument found.]
- **Receiving-water screen — unblocked (PR #803, closes #445).** Mad River 7Q10 at USGS 03267000 derived: **53.67 cfs** (LP3, 39 climatic years 1980–2024); committed to `low-flow-7q10.derived.yaml` as `mad river at urbana` (distinct alias from the Springfield proxy). `plant_receiving` populated: Urbana WPCF (OH0027880/1PD00011) → Mad River, design flow 4.5 MGD [verified — permit renewal app eDoc 3832476]. `passby_primary_cfs=53.67` [derived]; regulatory value pending the OEPA permit fact sheet (renewal submitted 2025-05-29, not yet issued). Basin-screen remains 14/81, 0 violations, 1 tight. [2026-07-10 update (#1355): the OEPA 1PD00011 fact sheet supplies the regulatory 7Q10 = **35 cfs**; the profile now carries `passby_primary_cfs=35.0` [verified], superseding this 53.67 LP3.]
- **The screen should be a *source-water / abstraction* screen, not effluent-dominance.** Lima's thesis is effluent-vs-tiny-tributary-7Q10; Urbana's is **consumptive cooling draw vs. Mad River baseflow + the sole-source buried-valley aquifer** (which is exactly why the profile carries `abstraction_gage`/`supply_gage`/`passby` fields). The methodology must not copy Lima's denominator logic onto it.
  - **[2026-07-10 correction (#1330) — SUPERSEDED for the disclosed facility.]** The Urbana Technology Hub disclosed **closed-loop cooling** ("water use comparable to a standard office building"; Urbana Daily Citizen 2026-02-18). If that holds, the consumptive-abstraction screen is **not the binding constraint** for this facility — the live constraint is **grid/power + land use** (end-user-funded transmission upgrades, AES Ohio / PJM DAY). The `abstraction_gage`/`supply_gage`/`passby` fields are **retained as a reach-level source-water screen** (still valid for the Mad River sole-source aquifer generally, and for any future high-water abstractor), but they do **not** bind this closed-loop facility. Per BOSC method, the closed-loop disclosure stands as reported — no water figure was invented to preserve the old thesis. See `datacenter-facility.md` §5.
- **Grid is a different zone than Lima.** Likely **AES Ohio / DAY PJM zone**, not AEP — pin the EIA-861 utility number + PJM zone before publishing any grid figure (Ohio, so the cross-state connector axis isn't re-triggered).

**Proposals — 5 filed as sub-issues of #441:** ~~Mad-River 7Q10 + Urbana WWTP NPDES~~ **done** (PR #803 — 53.67 cfs derived, OEPA corpus ingested); ~~a Great-Miami / Ohio-River ECHO discharger inventory~~ **done** (PR #455); ~~source Highland55 via primary instruments~~ **done** (PR #803 — `permits/highland55/` corpus); ~~pin-or-downgrade the Honda Champaign-area data center~~ **downgraded** [2026-06-28] — `corridor_context: true`, no pinning instrument found, excluded from Urbana promotion criteria; ~~resolve the Champaign-County utility + PJM zone~~ **done** (Dayton Power & Light #4922, PJM/PUCO).

## Review gate (blocking)

- [x] Every written reference value is reviewed against a cited source (no fabricated values). All connector outputs are [reference]/[derived] with citations; Highland55 facts are [verified] from primary instruments; open/inference items tagged.
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. (Resolved #1326: footprint committed (`extracted/urbana/bosc-site-footprint.yaml`); area-weighted SSURGO **dominant HSG C** `[verified]` now matches the profile, correcting the prior `[inference]` B. Facility CONFIRMED #1327.)
- [x] basin-screen coverage is sane for this site's receiving waters. (Great Miami inventory PR #455; Mad River regulatory 7Q10 = **35 cfs** `[verified]` (OEPA 1PD00011 fact sheet, #1355; superseding the derived 53.67 LP3) at USGS 03267000; screen 14/81, 0 violations, 1 tight. `passby_primary_cfs=35.0` `[verified]`.)
- [~] A per-jurisdiction County/City GIS connector exists. (Parcel: CHAMPAIGN_PARCEL_SCHEMA [verified]. Zoning: not found [open].)
- [x] Self-research first pass reviewed (Phase 5, 2026-06-21; data-center = weakest leg, receiving-water screen empty; 5 proposals filed as sub-issues of #441 — all resolved).
- [x] PROMOTION DONE 2026-07-01: status→live, selectable→true in web/packages/core/src/sites.ts; sample-bundle committed to web/sample-bundle/urbana/; pages.yml exports urbana.
