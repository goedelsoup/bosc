# Onboarding — Fort Wayne (fort-wayne)

Living record for the Fort Wayne watershed point (basin: maumee), scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [x] **Data-center activity** — DOCUMENTED (#360, 2026-06-23): the disclosed facility is **Google's $2B "Project Zodiac" campus** (700+ ac, SE Fort Wayne, served by I&M, operational Dec 2025) — see [`datacenter-facility.md`](datacenter-facility.md). Primary-record *extraction* (IDEM air permit → MW, IURC filings, abatement ordinance, wetland permits) is the open follow-up, so the `facility` power basis stays `None`.
- [~] **Per-jurisdiction GIS** — flood = shared national NFHL (wired). Parcels/zoning `[open]` — see GIS discovery below; no clean queryable district catalog like Findlay's, and the 2026-06-19 `acimap.us` parcel endpoints now 404 (re-verified 2026-06-23, #362), so nothing committed yet

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/fort-wayne/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/fort-wayne/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/fort-wayne/nasa-power-climatology.yaml |
| basin-screen | ok | 7/129 dischargers screened (1 violations, 2 tight) |
| econ-baseline | ok | reference/economics/fort-wayne/baseline.yaml |
| rsei | ok | reference/rsei/fort-wayne/inventory.yaml |
| consumer-energy | ok | reference/eia/fort-wayne/consumer-energy.yaml |
| grid-profile | ok | reference/eia/fort-wayne/grid-profile.yaml |

## GIS discovery (2026-06-19; schema-driven GIS, #237)

Endpoints probed against the schema-driven GIS connector. Unlike Findlay (a clean City zoning
FeatureServer → a committed district catalog), Fort Wayne has **no clean queryable
district-catalog layer**, so nothing is committed yet; flood is the shared national NFHL.

| layer | finding | status |
|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) — wired in the profile (`gis_flood`) | wired |
| parcels (county) | Allen County IN — `gis1.acimap.us/.../Accela/Accela_Production/MapServer/8` is queryable but **geometry + PIN only** (no CAMA owner/value/acres) | `[open]` |
| parcels (city) | City of Fort Wayne — `gis.acimap.us/.../CFW/Parcels_With_Ownership_Information/MapServer/0` carries **owner + addresses + transfer date** but no value/acres/land-use, and fully-qualified field names (`sde.CurrentOwner.OwnerofRecord`, …). Partial CAMA; wiring deferred (no corpus parcels to query yet) | `[open]` |
| zoning | county `Reference_Zoning` is a tiled basemap (`layers:[]`, not queryable); no City zoning REST district catalog found (the city interactive map renders zoning but not as a clean catalog service) | `[open]` |

Follow-up (a research/issue lead): wire the City of Fort Wayne partial-CAMA parcel layer behind
a `GisParcelSchema` once there are corpus parcels to resolve; locate a queryable Fort Wayne
zoning layer (or accept that zoning is map-only here).

**Re-verify 2026-06-23 (#362):** both `acimap.us` REST endpoints above now **404** (the abbreviated
2026-06-19 paths no longer resolve), and the IndianaMap statewide hosted parcel layer times out — so a
**surveyed parcel boundary is not reachable** by REST today. The facility *location* IS now sourced
(Google "Project Zodiac", 6015 Adams Center Rd → −85.045/41.031, ArcGIS World geocoder + #360), but per
the conservative discipline (no constructed AOI; mirrors Findlay #355) **no footprint geometry is
committed**. #362 stays open; the unblock is the #360 deed/rezoning/stormwater-permit extraction (a
surveyed boundary), which also feeds the SSURGO HSG validation below.

## Self-research (Phase 5; #247) — 2026-06-21

First automated-research pass (`watermark onboard --research`, 35 turns, $1.38, read-only over the corpus)
→ `data/research/onboard-fort-wayne-fort-wayne-data-center-activi-2026-06-19/` (`findings.md` +
`manifest.yaml`).

**Headline — the basin's largest discharger, the network's only confirmed data-center facility, and
the cross-state test, all at once.** Fort Wayne is the first **out-of-state** point (Allen County,
**Indiana**, FIPS 18003 — *not* Lima's Allen County, OH 39003; the cross-state trap the per-site axis
exists to catch). It carries the basin's **largest POTW** — Fort Wayne WWTP (IN0032191, **74 MGD ≈
114 cfs**) discharging to the Maumee at the headwaters under an active "Effluent – Monthly Average
Limit" ECHO flag (1 informal enforcement).

**The screen verdict — RESOLVED (#358/#359, 2026-06-23).** See the reviewed characterization
[`wwtp-receiving-water.md`](wwtp-receiving-water.md). Two corrections to
the hypothesis above: (1) the basin-screen **never** used the Waterville proxy for this plant — its
primary receiver is **Baldwin Ditch** (ungaged), so it is correctly left **unscreened** (omit-don't-
guess), and (2) the "~45 cfs / 2.5:1" figure used the *upstream* St. Joseph gage (Newville 04178000,
29.69 cfs). The correct near-Fort-Wayne gages give a derived **headwaters 7Q10 ≈ 69.7 cfs** (St.
Joseph nr FW 04180500 = 54.06 + St. Marys nr FW 04182000 = 15.65). Against it: design 74 MGD →
**0.61:1 (effluent-dominant)**; actual 43.9 MGD (2023 DMR mean, ≈ 59% of design) → **1.03:1 (tight)**.
The plant is effluent-balanced-to-dominant at low flow — significant, but milder than the hypothesis.
The DMR record shows **no monthly-average exceedance 2021–2025** (the ECHO SNC label is uncorroborated
by a recent exceedance — an open reconciliation item, likely historical).

**Data-center activity — DOCUMENTED (#360, 2026-06-23).** The disclosed facility is **Google's "Project
Zodiac" campus** — $2B, 700+ ac in SE Fort Wayne (Tillman/Adams Center/Paulding Rds), ~200 permanent
jobs, served by **I&M** (matching the grid profile), a 50%/$55.5M 10-yr abatement, operational Dec
2025, with a Google–I&M IURC-approved demand-response program and a contested IDEM wetland-fill
permit (6+ ac). See [`datacenter-facility.md`](datacenter-facility.md). **Still `facility=None`:** the
`SiteFacility` power basis needs air-permit-grounded MW, and neither an IDEM air permit nor a disclosed
IT load exists yet — the campus MW is genuinely undisclosed (the I&M demand-response framing substitutes
for a capacity figure). So the *activity* is confirmed and characterized; *corpus extraction* of the
primary records (air permit → MW, IURC dockets, abatement ordinance, wetland permits) is the open
follow-up. On-thesis: $2B + ~200 jobs is the load-not-jobs shape (info-sector LQ 0.44), and the wetland
fill sits in the Maumee headwaters drainage the WWTP discharges to ([`wwtp-receiving-water.md`](wwtp-receiving-water.md)).

**Serving utility — VERIFIED across the state line.** Indiana Michigan Power (I&M, EIA #9324, an AEP
subsidiary), regulator **IURC** (Indiana — correctly *not* PUCO), RTO PJM — the cross-state grid path
(#356 fixed the Ohio-hardcoding the per-site axis had missed). **LMP resolved (#361, 2026-06-21):**
the $35 placeholder is replaced with the connector-sourced **AEP-zone** day-ahead annual mean
(**$45.81/MWh**, PJM Data Miner 2). I&M settles in the PJM **AEP zone** — the live Data Miner 2 zone
list carries no separate I&M zone — so Fort Wayne's zonal LMP is the AEP zone (pinned `lmp_pnode_id`,
same fixture as the OH AEP sites), `source=connector`.

**Read-side note.** The cross-document MCP tools (`entities`/`timeline`/`hydrology_balance`) are
**Lima-keyed** and return zero Fort Wayne content — the documented "read side stays Lima-keyed until
parity" deferral, not a corpus gap. All Fort Wayne findings come from the slug-scoped onboarding
outputs + the basin-shared ECHO inventory.

**Proposals — 5 filed as sub-issues of #235:** ~~#358 (resolve the headwaters 7Q10 denominator
mismatch)~~ **— resolved 2026-06-23: derived headwaters 7Q10 ≈ 69.7 cfs; FW correctly unscreened
(Baldwin Ditch); see [`wwtp-receiving-water.md`](wwtp-receiving-water.md)**,
~~#359 (extract the IN0032191 NPDES permit + DMR + ECHO detail)~~ **— resolved 2026-06-23: `watermark dmr`
connector + [`wwtp-in0032191.dmr.yaml`](wwtp-in0032191.dmr.yaml); actual ≈ 43.9 MGD vs 74 design, no
2021–2025 exceedance; the "1 violation" is American-Bath, not FW**, ~~#360 (investigate the disclosed
Fort Wayne / NE-Indiana data-center facility)~~ **— resolved 2026-06-23: Google "Project Zodiac" $2B
campus documented from the public record (see [`datacenter-facility.md`](datacenter-facility.md));
primary-record extraction (air permit → MW, IURC, abatement, wetlands) listed as follow-up targets in
§7 of that doc; `facility` power basis stays None until the MW is grounded**, ~~#361 (verify the I&M LMP, replace the $35/MWh
placeholder)~~ **— resolved 2026-06-21: I&M is in the PJM AEP zone, LMP now connector-sourced
$45.81/MWh**, #362 (commit a site footprint to unblock SSURGO HSG + GIS discovery). The GIS
lift (Allen Co IN / City of Fort Wayne partial-CAMA parcel layers, no clean zoning catalog) is
tracked under GIS discovery above.

## Bring the site live — content + story (#741)

The **plumbing is done**: the content bundle is per-site (#762, via #763/#764/#765 — `watermark --site
fort-wayne export` carries no Lima data), the site-page chrome reads the active site (#766), and the
curation stores + the Project Zodiac story are scaffolded (#767). What remains is **sourced
authoring** written into the scaffolded slots, then promotion. Each item cites a committed source —
**never fabricate** a person, place, exhibit, or claim (chain of custody). This is the runbook in
[`docs/onboarding.md`](../../../docs/onboarding.md) → "Bringing a site's story live", tracked here.

- [ ] **Write the Project Zodiac story prose + flip each chapter `live: true`.** Fill the four
  scaffold files under [`web/src/content/stories/fort-wayne/project-zodiac/`](../../../web/src/content/stories/fort-wayne/project-zodiac/)
  — `_home.mdx` (on-ramp) + `who.mdx` / `power.mdx` / `water.mdx`, each already anchored to its
  committed record (the parcel footprint, the IDEM Title V air permit [`idem/fort-wayne/47378f.idem.yaml`](../idem/fort-wayne/47378f.idem.yaml),
  the §401 WQC [`idem/fort-wayne/wqc001454.idem.yaml`](../idem/fort-wayne/wqc001454.idem.yaml)).
  Re-add the record-teardown islands / bundle-count imports as in `stories/lima/project-bosc/`; set
  each chapter `live: true` as it's finished. Figures carry their source + confidence.
- [ ] **Curate the real FW people / places / exhibits.** Add profiles under
  [`data/entities/people/fort-wayne/`](../../people/fort-wayne/) (the Hatchworks principals, permit contacts,
  IURC/abatement parties) and [`data/entities/poi/fort-wayne/`](../../poi/fort-wayne/) (the 11-parcel campus
  composite, the WWTP IN0032191), and exhibits to [`data/site/fort-wayne/exhibits.yaml`](../../site/fort-wayne/exhibits.yaml)
  (candidate IDEM sources noted there). The `people`/`places`/`exhibits` feeds stay empty until these land.
- [ ] **Register the story** on the Fort Wayne entry in
  [`web/src/lib/sites.ts`](../../../web/src/lib/sites.ts) (`stories: [{ codename:
  "project-zodiac", title, dek }]`) so the switcher/nav surface it.
- [ ] **Meet the parity gate (#746/#742) → flip `selectable: true`** (and `status: "live"`) for
  `fort-wayne` in `web/src/lib/sites.ts` — the one manual, parity-gated edit (also the last
  Review-gate box) that makes every `network/[site]/…` route, including the story, render for Fort
  Wayne. The page chrome (#766) already reads "Fort Wayne, Indiana"; the Lima-specific *prose* on the
  hero/report pages still needs its FW equivalent before this flip.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **(#362, footprint-gated — still `[inference]`: no surveyed boundary reachable by REST as of 2026-06-23; conservative, no constructed AOI; unblocks on the #360 deed/rezoning extraction.)**
- [x] basin-screen coverage is sane for this site's receiving waters — IN0032191's primary receiver is the ungaged Baldwin Ditch, so it is correctly unscreened (omit-don't-guess); the receiving-water read is documented in [`wwtp-receiving-water.md`](wwtp-receiving-water.md) against the derived headwaters 7Q10 (#358/#359).
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; 5 proposals filed as sub-issues of #235 (#358–362).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'fort-wayne' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
