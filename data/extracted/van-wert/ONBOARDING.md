# Onboarding — Van Wert (van-wert)

Living record for the Van Wert watershed point (basin: maumee), scaffolded by `watermark onboard van-wert`. Check items as you complete them; the site is **not** promoted (`web/src/lib/sites.ts` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [x] **OEPA permit ingest** — NPDES permit `2PD00006` (OH0027910) + fact sheet `2PD00006.fs` fetched and extracted (`data/documents/oepa/van-wert/`, `data/extracted/oepa/2PD00006*.npdes.yaml`). Town Creek 7Q10 = 0.16 cfs (annual; summer/winter = 0 — intermittent). Design flow confirmed 4.0 MGD. See `data/reference/hydrology/low-flow-7q10.yaml`. Resolves #837.
- [~] **Data-center activity** — QTS/Thor confirmed same project (Phase 6 research, 2026-07-02); Van Wert-jurisdiction instruments exist but **not yet ingested** — see Phase 6 below. Closes #378/#840; #377 tracks ingest.
- [~] **Per-jurisdiction GIS** — flood = shared national NFHL (wired). Parcels/zoning `[open]` — see GIS discovery below; no clean queryable district catalog like Findlay's, so nothing committed yet

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/van-wert/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | skipped | footprint missing: extracted/van-wert/bosc-site-footprint.yaml |
| climatology | ok | reference/hydrology/van-wert/nasa-power-climatology.yaml |
| basin-screen | ok | 8/129 dischargers screened (2 violations, 2 tight) — OH0027910 now screened |
| econ-baseline | ok | reference/economics/van-wert/baseline.yaml |
| rsei | ok | reference/rsei/van-wert/inventory.yaml |
| consumer-energy | ok | reference/eia/van-wert/consumer-energy.yaml |
| grid-profile | ok | reference/eia/van-wert/grid-profile.yaml |

## GIS discovery (2026-06-19; schema-driven GIS, #237)

Endpoints probed against the schema-driven GIS connector. Like Fort Wayne (and unlike
Findlay's clean City zoning FeatureServer), Van Wert has **no cleanly-consumable queryable
district catalog**, so nothing is committed yet; flood is the shared national NFHL.

| layer | finding | status |
|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) — wired in the profile (`gis_flood`) | wired |
| parcels (county) | Van Wert County PAT MapServer (`ags.bhamaps.com/.../VanWertOH/VanWertOH_PAT_Search/MapServer`, Bruce Harris & Assoc) exists but its **TLS certificate is expired** — `cached_get`/httpx can't consume it without disabling verification; parcels are otherwise distributed as Engineer's-office shapefiles + a Beacon-style auditor parcel app | `[open]` |
| zoning | no separate City of Van Wert zoning REST catalog found (small city; zoning appears map-only) | `[open]` |

Follow-up (a research/issue lead): re-probe the county PAT MapServer once its TLS cert is
renewed (then register a `GisParcelSchema` from the live field list), or fall back to the
Engineer's-office parcel shapefile; locate a Van Wert zoning layer (or accept map-only here).

## Self-research (Phase 5; #247) — 2026-06-21

First automated-research pass (`watermark onboard van-wert --research`, 27 turns, $1.28, read-only over the corpus) →
`data/research/onboard-van-wert-van-wert-data-center-activity-r-2026-06-19/` (`findings.md` + `manifest.yaml`).

**Headline — the effluent-dominance end-member, `[verified]` (resolves #376).** Van Wert is
the basin's small-stream end-member: a 4.0 MGD plant (Van Wert WWTP, OH0027910, design flow
6.1889 cfs) on a tiny tributary (Town Creek). Town Creek 7Q10 = **0.16 cfs** (annual;
source=document, NPDES fact sheet 2PD00006, Table 12 via USGS drainage-area ratio —
see `data/reference/hydrology/low-flow-7q10.yaml`). Basin-screen result: **dilution ratio
0.03:1 → violation** — 39× effluent dominance. Summer and winter 7Q10 = 0 cfs (intermittent);
acute dilution ratio 1.02:1 per the fact sheet. Design flow confirmed 4.0 MGD (fact sheet
Table 7). `[inference]` caveat on effluent dominance is upgraded to `[verified]`.
ECHO's `receiving_water` field was null for OH0027910; corrected to "Town Creek" per
fact sheet (see `data/reference/echo/maumee-wwtp.potw.yaml` meta caveats). Proposals
#375 and #376 closed.

**Data-center activity — documented, but only secondhand through Allen-County records.** Unlike the
other comparators (no disclosed facility), Van Wert carries **two** proponent threads, both
`[verified]` as present in the corpus, both `[open]` at the parcel/entity level:

- **QTS** — a **$10B Van Wert County campus**, up to 4,500 construction jobs, in sworn-equivalent
  Select-Committee testimony (`qts-2026-06-03.pdf`; `select-committee-2026/witness-submissions.digest.yaml`).
  Proponent figures, not BOSC-verified; the closed-loop "no additional water" claim is design-specific
  (cf. `docs/legal/proponent-analysis.md`).
- **Thor Equities** — a developer "also doing a Van Wert data center; brought by AEP," a 1-yr LOI at
  $50K/ac on Perry Industrial Park (PAAC board minutes, `paac-board-minutes.minutes.yaml`).
- `[open]`: whether QTS and Thor name the **same** project, and the whole thread at the parcel level —
  there are **zero Van-Wert-jurisdiction primary documents** in the ingested corpus (proposals #377/#378).

**The economic shape is the basin's most extreme.** Van Wert County: manufacturing LQ **3.14**,
information LQ **0.09** — the strongest "load onto a shrinking industrial base, not jobs" signature in
the network (cf. the cross-site scorecard on `/directory/basin`).

**Serving utility — VERIFIED (the "Bryan trap" checked & cleared).** Van Wert is **not** a municipal:
the grid connector's EIA-861S short-form fallback found no City of Van Wert filer, and the EIA-861
service-territory file + PUCO certified-territory confirm **AEP Ohio (Ohio Power Co #14006, PJM AEP
zone)** distributes (`data/reference/eia/van-wert/grid-profile.yaml`). The profile's
`eia861_utility_number=14006` + the PUCO/PJM grid path are correct — the same Ohio/AEP/PUCO axis as
Lima and Findlay, so the cross-state connector axis is not re-exercised.

**Proposals — all 5 distilled proposals are filed as sub-issues of #363:** #375 (ingest the OH0027910
NPDES permit + Town Creek 7Q10), #376 (re-screen once the 7Q10 lands), #377 (obtain a primary QTS
instrument), #378 (resolve QTS-vs-Thor), #379 (disambiguate OH0135569 vs OH0027910 — **resolved**, see
NPDES permit disambiguation section below: OH0135569 is the City of Van Wert water treatment
plant, not an MS4). The GIS lift
(the Van Wert County PAT MapServer on `ags.bhamaps.com` with an expired TLS cert) is the shared-host
case tracked under GIS discovery above — re-probe once the cert is renewed; **don't weaken TLS** for it.

## NPDES permit disambiguation — OH0135569 vs OH0027910 (#379) — 2026-07-02

Resolves #379. The ECHO Maumee inventory carried **two** Van Wert permits; OH0135569 was
flagged as "likely a distinct MS4/industrial coverage worth disambiguating." Looked up in the
ECHO detailed facility report + effluent chart (FRS `110008587421`). **It is the City of Van
Wert WATER TREATMENT PLANT** (drinking-water surface plant, 1260 S Washington St, SIC **4941
Water Supply**) discharging filter/softening residuals — **not** an MS4, not industrial process,
not a CSO, and not the WWTP. The city draws its raw water *from* Town Creek reservoirs and
discharges treatment residuals back to **Lower Town Creek**.

| permit | facility | type | receiving water | design flow | effluent limits | in basin-screen denominator? |
|---|---|---|---|---|---|---|
| OH0027910 | Van Wert WWTP | POTW (individual) | Town Creek (RM 13.87, outfall 2PD00006001) | 4.0 MGD | full mass/conc suite | **yes** — screened, 0.03:1 dilution → violation |
| OH0135569 | City of Van Wert Water Treatment Plant | NON-POTW water-supply plant (Non-Major individual) | **Lower Town Creek** (WBD12 041000070804, outfall 001 at 40.8476/-84.5748, ~2.5 mi S of WWTP) | none (flow monitor-only) | **pH 6.5–11 SU only**; flow reported, no numeric limit | **no** — WTP residuals, no design flow, no mass limit |

**Determination:** OH0135569 does **not** require inclusion in the effluent-dominance basin-screen
denominator. It is a low-volume water-treatment-residuals discharge with **no design flow** and **no
mass/concentration effluent-quality limit** (flow is monitor-only; pH is the only numeric limit), so
it carries no municipal-sewage load and cannot drive the receiving-water dilution screen. It is on the
**same Town Creek reach** as OH0027910 (the Lower Town Creek segment, ~2.5 mi downstream of the WWTP
outfall) — relevant context, but not an additional screened discharger. The ambiguity about "what is
being screened" is resolved: the municipal-discharge footprint on Town Creek is **OH0027910 (WWTP) only**.
ECHO's null `receiving_water` for OH0135569 is documented as "Lower Town Creek" in a
`meta.caveats` note in `data/reference/echo/maumee-wwtp.all-npdes.yaml` — the raw field
mirrors ECHO's `CWPStateWaterBodyName` (regenerated by `watermark npdes`) and is left null
rather than hand-backfilled, matching the OH0027910 correction convention. Permit period 04/01/2023–06/26/2026
(effluent chart) with limits effective through 12/31/2029; DMR pollutant loadings ~7.7–8.2 k lb/yr (TSS-class).

## Phase 6 research — QTS/Thor identity + Van Wert-jurisdiction documents (2026-07-02)

External web research conducted 2026-07-02 (not yet corpus-ingested). All findings are `[reference]`
until primary instruments land in `data/documents/van-wert/` and `data/extracted/van-wert/`.
Sources: DCD, VW Independent, 21Alive/WPTA, Hometown Stations, Mercer County Outlook,
vanwertcountyohio.gov commissioner agendas, q.com/data-centers/van-wert.

### QTS / Thor Equities are the same project — confirmed (#378/#840 resolved)

**Thor Equities** (via its Form8tion data center division, founded March 2023) is the
developer/land-banking agent. **QTS Data Centers** (Blackstone subsidiary, "QTS Realty Trust") is
the end-user/operator. The joint city/QTS announcement of May 29, 2026 stated that "Thor Equities
purchased the land on QTS's behalf." AEP Ohio is the utility partner — consistent with the PAAC
board minutes' "brought by AEP."

Timeline:

- Jan 2025: AEP in discussions with unnamed developer (DCD); VWAEDC director cites 500 MW, ~1.5M gal/day water
- Aug 2025: Thor Equities acquires 221 acres from Marsh Foundation at ~$51K/ac (deed: Van Wert County Recorder)
- May 11, 2026: Van Wert City Council 6-0 approves annexation/rezoning (see below)
- May 27, 2026: VW Independent reports "data center tax exemptions paused" (moratorium signed May 29)
- May 29, 2026: Joint city/QTS announcement; Governor DeWine suspends Ohio sales tax exemption (R.C. §122.175) same day
- Jun 3, 2026: QTS testifies at Ohio House Select Committee on Data Centers

**Perry Industrial Park thread (PAAC minutes) is a SEPARATE site.** The PAAC board minutes
entry "Thor Equities, Perry Industrial Park (remainder, N of power line)... also doing a Van Wert
data center; brought by AEP" records Thor simultaneously pursuing an Allen County, OH site (Perry
Industrial Park) as a separate AEP-adjacent transaction. Do not conflate with the Van Wert Mega Site.

### Van Wert-jurisdiction primary documents identified — not yet ingested (#377 tracks ingest)

This is **not** a zero-document situation. Documents to ingest in priority order:

1. **Van Wert City Council ordinances — May 11, 2026** (highest priority): Three ordinances passed 6-0
   with emergency clauses (three readings waived): (1) annexation of ~962 acres purchased by Thor from
   Marsh Foundation; (2) I-2 General Industrial zoning permitting data centers; (3) conditional zoning
   petition. Councilman Greg Roberts (Marsh Foundation employee) recused. Obtain from Van Wert City Clerk.
2. **Van Wert County Commissioner agendas — June 12, 2025** (already public online):
   Agenda lists "Chuck Koch, Attorney Re: Annexation – Megasite – Project Thor – Data Center."
   Full meeting minutes not posted online — require in-person or public-records request to
   Van Wert County Commissioners, 114 E. Main St., Suite 200, Van Wert, OH 45891.
3. **Thor Equities / Marsh Foundation deed** (2025): Van Wert County Recorder —
   countyfusion14.govos.com (search grantor "Marsh Foundation"). 221-acre initial parcel; site grew
   to 902 acres via subsequent annexation by May 2026.
4. **AEP Ohio PUCO data center tariff (approved July 9, 2025)**: Governs the 500-MW interconnection;
   AEP committed to 100% of infrastructure costs. Public at puco.ohio.gov.
5. **OPSB Case No. 25-0697-EL-BLN**: Van Wert–Haviland 69-kV→138-kV transmission line rebuild
   (~10 miles, Paulding + Van Wert Counties). Separate from the project-specific 345-kV substation
   connection (no OPSB docket found for that as of research date).

### Site geometry (from public sources)

- **Location:** Northern Mega Site between US Route 30, Gilliland Road, and Marsh Road, Van Wert, OH.
  ~902 acres of 1,500-acre Marsh Foundation land north of US-30.
- **Campus:** Up to 7 buildings; $10B capital investment (proponent claim); 1,500 construction jobs
  (QTS announcement) vs. 4,500 (select-committee testimony — possibly multi-phase/induced);
  200 permanent QTS positions.
- **Footprint lead:** Thor Equities / GlobeNewswire press release (Aug 19, 2025) + the Van Wert
  County Recorder deed are the sources for the parcel geometry. Both needed for `bosc-site-footprint.yaml`.

### Water-use tension (relevant to hydrology thesis)

VWAEDC director Brent Stevens quoted in July 2025 (Hometown Stations): "maybe 1.5 million gallons
of water a day, but they are only going to take that from July and August." QTS's May 2026
announcement claims closed-loop glycol cooling — "no ongoing water consumption for cooling once
operational; municipal water serves only bathrooms, kitchens, cleaning, and landscaping —
approximately what 4 households use a month." These claims are in direct tension. The BOSC
cooling-withdrawal screen models evaporative draw, which the closed-loop design would eliminate.
Verification: Ohio EPA air permit application (submitted per QTS FAQ; no permit number found).
`[open]` — resolving this changes the site's effluent-dominance framing.

## Review gate (blocking)

- [ ] Every written reference value is reviewed against a cited source (no fabricated values).
- [ ] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.
- [x] basin-screen coverage is sane for this site's receiving waters. OH0027910 screened against Town Creek 7Q10 (0.16 cfs annual, source=document); dilution ratio 0.03:1 — 39× effluent dominance, `[verified]`. See self-research summary above.
- [ ] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; 5 proposals filed as sub-issues of #363 (#375–379).
- [ ] PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for 'van-wert' in web/src/lib/sites.ts, parity-gated. onboard never auto-promotes; only one live build (/bosc) exists today.
