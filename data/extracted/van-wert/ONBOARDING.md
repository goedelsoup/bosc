# Onboarding — Van Wert (van-wert)

Living record for the Van Wert watershed point (basin: maumee), scaffolded by `watermark onboard van-wert`. Check items as you complete them; the site is not promoted (`data/sites.yaml` `status`/`selectable`) until the gate is clear.

## Dimension coverage

- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)
- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile
- [x] **OEPA permit ingest** — NPDES permit `2PD00006` (OH0027910) + fact sheet `2PD00006.fs` fetched and extracted (`data/documents/oepa/van-wert/`, `data/extracted/oepa/van-wert/2PD00006*.npdes.yaml`). Town Creek 7Q10 = 0.16 cfs (annual; summer/winter = 0 — intermittent). Design flow confirmed 4.0 MGD. See `data/reference/hydrology/low-flow-7q10.yaml`. Resolves #837.
- [~] **Data-center activity** — QTS/Thor confirmed same project (Phase 6 research, 2026-07-02); Van Wert-jurisdiction instruments exist but **not yet ingested** — see Phase 6 below. Closes #378/#840; #377 tracks ingest.
- [x] **Per-jurisdiction GIS** — parcels **wired** (`VAN_WERT_PARCEL_SCHEMA`, #421 — the county's ArcGIS Online auditor-CAMA join `parcel_joinedVWOH`; the bhamaps PAT MapServer died with its expired cert and was retired, never re-wired) and flood = shared national NFHL (wired). Zoning stays `[open]` (no REST anywhere — townships map-only, city zoning static PDFs + amlegal). See GIS discovery below.

## Last onboard run

| step | status | output |
|---|---|---|
| scaffold | ok | created 6 dir(s); 6 README(s) |
| derive-low-flows | ok | reference/hydrology/low-flow-7q10.derived.yaml |
| corridor-ddf | ok | reference/hydrology/van-wert/atlas14-corridor-ddf.yaml |
| ssurgo-hsg | ok | HSG C/D; matches profile (dual group: drained C / undrained D) (#1403 — was `skipped` for want of parcel geometry) |
| climatology | ok | reference/hydrology/van-wert/nasa-power-climatology.yaml |
| basin-screen | ok | 8/129 dischargers screened (2 violations, 2 tight) — OH0027910 now screened |
| econ-baseline | ok | reference/economics/van-wert/baseline.yaml |
| rsei | ok | reference/rsei/van-wert/inventory.yaml |
| consumer-energy | ok | reference/eia/van-wert/consumer-energy.yaml |
| grid-profile | ok | reference/eia/van-wert/grid-profile.yaml |

## GIS discovery (2026-06-19; schema-driven GIS, #237 — updated 2026-07-11, parcels wired, #421)

Endpoints probed against the schema-driven GIS connector. The 2026-06-19 pass found the county's
parcels on a Bruce Harris & Assoc. PAT MapServer (`ags.bhamaps.com`, folder `VanWertOH`) blocked
behind an **expired TLS certificate** (the shared-host case with Defiance, #394 — we don't weaken
TLS for an external host). The 2026-07-10 re-probe (#421) found that host **dead, not just
cert-expired** — the wildcard cert lapsed 2026-05-19, the ArcGIS Server was removed (bare
`Microsoft-HTTPAPI/2.0` 404s), and the county's PAT viewer item was retired. **The county migrated
to ArcGIS Online** (`vanwertcountygis.maps.arcgis.com`, org `G5sGKRBVtJMunpVA`), whose
`parcel_joinedVWOH` FeatureServer layer 0 is the owner-bearing auditor-CAMA join — now **wired**
as `VAN_WERT_PARCEL_SCHEMA` (#421), field-map confirmed from the live `?f=json` + samples
(2026-07-11; data vintage 2026-05-01). The field semantics resolved during wiring are recorded in
the schema comment (`PPClassNumber` is the numeric Ohio use code — `PPClassCode` is the coarse
class letter; no owner mailing-address field; `PPOnCauv` is a string flag; the dashed auditor form
`17-034718.0100` normalizes onto the dashless stored `PIN`). The same AGOL org also serves
`RawParcels`, `FloodPlain`, `TaxDistrict`, `SchoolDistrict`, `Sections`, `ROW_Lines` + 2021
aerials (reference leads). The Engineer's-office shapefile fallback (`Current_Parcels.tar.gz`,
2024-12-27) is now strictly inferior. Probe bonus: the roll already shows the Mega Site anchor —
PIN `170347180100`, VAN WERT EAST OWNER LLC, 221.15 ac, sold 2025-08-22 for $10,394,000 (split
from Marsh tract `170347180000`) — all verbatim from the layer's `PPSaleDate`/`PPAmount` roll
fields, recorded in the committed fixture
(`tests/fixtures/hydrology/van_wert_gis/054c1bdf635a4b53.json` — the exact query + response the
connector replays); the deed itself is the Recorder trail in Phase 6 below
(countyfusion14.govos.com, grantor "Marsh Foundation"). Feeds #1403/#1404.

| layer | finding | status |
|---|---|---|
| floodzone | FEMA NFHL (national, layer 28) — wired in the profile (`gis_flood`) | wired |
| parcels (county) | `services8.arcgis.com/G5sGKRBVtJMunpVA/.../parcel_joinedVWOH/FeatureServer/0` (AGOL, valid Esri TLS, 19,956 polygons) — `PIN`, `PPOwner`, `PPAddress` (situs street), `PPClassNumber` (use code), `PPAcres`, `PPLandValue`/`PPImprValue`/`PPTotalValue`, `PPSaleDate`/`PPAmount` — owner **and** values on one layer. Replaces the retired `ags.bhamaps.com` PAT MapServer (host dead; ArcGIS Server removed) | **wired** (`gis_parcel`, #421) |
| zoning | no Van Wert zoning REST anywhere (townships map-only; city zoning = static PDFs + amlegal) — unchanged negative on the 2026-07-10 re-probe | `[open]` |

Follow-up **done (#1403)**: the reviewed Van Wert parcel reference *data* is committed as
`data/reference/van-wert/parcel-assemblage.geojson` — the five parcels deeded to QTS Van Wert LLC
in June 2026 (900.59 ac deeded / 901.502 ac planar, contiguous), which flips the **places**
readiness domain `absent` → `live`. Accept zoning as map-only here.
Defiance (#394) is the shared-vendor sibling — equally unblocked on its own AGOL org
(`services1.arcgis.com/nOy1DpPkzXSFJsGp/.../parcel_joined/FeatureServer/0`), tracked there.

## Self-research (Phase 5; #247) — 2026-06-21

First automated-research pass (`watermark onboard van-wert --research`, 27 turns, $1.28, read-only over the corpus) →
`data/research/onboard-van-wert-van-wert-data-center-activity-r-2026-06-19/` (`findings.md` + `manifest.yaml`).

**Headline — the effluent-dominance end-member, `[verified]` (resolves #376).** Van Wert is
the basin's small-stream end-member: a 4.0 MGD plant (Van Wert WWTP, OH0027910, design flow
6.1889 cfs) on a tiny tributary (Town Creek). Town Creek 7Q10 = **0.16 cfs** (annual;
source=document, NPDES fact sheet 2PD00006, Table 12 via USGS drainage-area ratio —
see `data/reference/hydrology/low-flow-7q10.yaml`). Basin-screen result: **dilution ratio
0.026:1 → violation** — 39× effluent dominance. Summer and winter 7Q10 = 0 cfs (intermittent);
acute dilution ratio 1.02:1 per the fact sheet. Design flow confirmed 4.0 MGD (fact sheet
Table 7). `[inference]` caveat on effluent dominance is upgraded to `[verified]`.
ECHO's `receiving_water` field was null for OH0027910; corrected to "Town Creek" per
fact sheet. Since #1698 that correction is declared in the curated overlay
`data/reference/echo/curation/maumee-wwtp.receiving-water.yaml` and re-applied by every
`watermark npdes --basin maumee` pull (the row carries `receiving_water_source: curated`),
so a basin refresh can no longer drop Van Wert back to `no_receiving_water`. Proposals
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
plant, not an MS4). The GIS lift is **resolved** (#421): the `ags.bhamaps.com` host died (we never
weakened TLS for it) and the county migrated to ArcGIS Online — parcels are now wired; see GIS
discovery above.

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
| OH0027910 | Van Wert WWTP | POTW (individual) | Town Creek (RM 13.87, outfall 2PD00006001) | 4.0 MGD | full mass/conc suite | **yes** — screened, 0.026:1 dilution → violation |
| OH0135569 | City of Van Wert Water Treatment Plant | NON-POTW water-supply plant (Non-Major individual) | **Lower Town Creek** (WBD12 041000070804, outfall 001 at 40.8476/-84.5748, ~2.5 mi S of WWTP) | none (flow monitor-only) | **pH 6.5–11 SU only**; flow reported, no numeric limit | **no** — WTP residuals, no design flow, no mass limit |

**Determination:** OH0135569 does **not** require inclusion in the effluent-dominance basin-screen
denominator. It is a low-volume water-treatment-residuals discharge with **no design flow** and **no
mass/concentration effluent-quality limit** (flow is monitor-only; pH is the only numeric limit), so
it carries no municipal-sewage load and cannot drive the receiving-water dilution screen. It is on the
**same Town Creek reach** as OH0027910 (the Lower Town Creek segment, ~2.5 mi downstream of the WWTP
outfall) — relevant context, but not an additional screened discharger. The ambiguity about "what is
being screened" is resolved: the municipal-discharge footprint on Town Creek is **OH0027910 (WWTP) only**.
ECHO's null `receiving_water` for OH0135569 is documented as "Lower Town Creek" — since
#1698 via a `mode: caveat` entry in the curated overlay
`data/reference/echo/curation/maumee-wwtp.receiving-water.yaml`, which emits it as this row's
`receiving_water_documented` plus a `meta.caveats` note in
`data/reference/echo/maumee-wwtp.all-npdes.yaml`. The raw field is deliberately left mirroring
ECHO's `CWPStateWaterBodyName` verbatim: unlike OH0027910's, this correction rests on ECHO's own
facility report rather than an independent regulatory document, and nothing downstream screens on
it (no design flow, no mass limit). Permit period 04/01/2023–06/26/2026
(effluent chart) with limits effective through 12/31/2029; DMR pollutant loadings ~7.7–8.2 k lb/yr (TSS-class).

## Phase 6 research — QTS/Thor identity + Van Wert-jurisdiction documents (2026-07-02)

External web research conducted 2026-07-02 (not yet corpus-ingested). All findings are `[reference]`
until primary instruments land in `data/documents/van-wert/` and `data/extracted/van-wert/`.
Sources: DCD, VW Independent, 21Alive/WPTA, Hometown Stations, Mercer County Outlook,
vanwertcountyohio.gov commissioner agendas, q.com/data-centers/van-wert.

> ⚠️ **THE INSTRUMENTS HAVE SINCE LANDED, AND THEY RETIRE FOUR FIGURES BELOW.** This section is a
> dated 2026-07-02 press snapshot, preserved as written because it is the record of what was
> believed before the primary documents were pulled. It is **not** the current register — that is
> [`data/extracted/van-wert/data-centers.md`](data-centers.md). Where a press figure below has been
> superseded, the correction is stamped inline. In summary:
>
> | this section says | the instrument says | source |
> |---|---|---|
> | "~962 acres" annexed | **901.698 ± ac** — Exhibit A's four components sum exactly to it; 962 has no support in the record | Ord. 26-05-028 (#1401) |
> | ordinances "passed 6-0" | **no numeric tally is recorded** — "all concurred"; Roberts abstained as a Marsh Foundation employee | Council minutes (#1401) |
> | holding is "61.4 ac short" of the annexation | **1.108 ac (0.12%)** short, once the annexed area is read off the instrument rather than the press | #1401 + #1403 |
> | "QTS Realty Trust, LLC / Overland Park KS" | **QTS Realty Trust Inc., Duluth GA** — certified under penalty of law 2026-07-21 | 2GC08872 NOI (#1402) |
>
> Also landed since: the campus's first state permit (construction-stormwater coverage
> `2GC08872*AG`, approved 2026-07-30) with the applicant's own schedule (start **2026-08-03**,
> completion **2030-08-03**, against the press "Q4 2026 / ~2032" below) and its certification that
> the air permit-to-install is `YET_TO_APPLY`; the NPDES `*WD` modification (#1406); and the
> incentive/water-instrument negative (#1407). Item 1 of the ingest list below is **done**.

### QTS / Thor Equities are the same project — confirmed (#378/#840 resolved)

**Thor Equities** (via its Form8tion data center division, founded March 2023) is the
developer/land-banking agent. **QTS Data Centers** (Blackstone subsidiary, "QTS Realty Trust") is
the end-user/operator. The joint city/QTS announcement of May 29, 2026 stated that "Thor Equities
purchased the land on QTS's behalf." AEP Ohio is the utility partner — consistent with the PAAC
board minutes' "brought by AEP."

Timeline:

- Jan 2025: AEP in discussions with unnamed developer (DCD); VWAEDC director cites 500 MW, ~1.5M gal/day water
- Aug 2025: Thor Equities acquires 221 acres from Marsh Foundation at ~$51K/ac (deed: Van Wert County Recorder)
- May 11, 2026: Van Wert City Council approves annexation/rezoning (see below) — press reported
  "6-0"; the minutes record no numeric tally, only "all concurred" (#1401)
- May 27, 2026: VW Independent reports "data center tax exemptions paused" (moratorium signed May 29)
- May 29, 2026: Joint city/QTS announcement; Governor DeWine suspends Ohio sales tax exemption (R.C. §122.175) same day
- Jun 3, 2026: QTS testifies at Ohio House Select Committee on Data Centers

**Perry Industrial Park thread (PAAC minutes) is a SEPARATE site.** The PAAC board minutes
entry "Thor Equities, Perry Industrial Park (remainder, N of power line)... also doing a Van Wert
data center; brought by AEP" records Thor simultaneously pursuing an Allen County, OH site (Perry
Industrial Park) as a separate AEP-adjacent transaction. Do not conflate with the Van Wert Mega Site.

### Van Wert-jurisdiction primary documents identified — not yet ingested (#377 tracks ingest)

This is **not** a zero-document situation. Documents to ingest in priority order:

1. ~~**Van Wert City Council ordinances — May 11, 2026** (highest priority)~~ — **INGESTED (#1401,
   PR #1880)**: nine City of Van Wert documents at `data/documents/van-wert/council/`, extracted to
   `data/extracted/van-wert/mega-site-instruments.{yaml,md}`. Three ordinances with emergency
   clauses (three readings waived): (1) `26-05-028` annexation of **901.698 ± ac** — not the
   "~962 acres" this line estimated — purchased by Thor from Marsh Foundation; (2) `26-05-029`,
   which created "Data Center" in Van Wert Code §150.03 **for the first time** and made it an I-2
   use in the same sitting that zoned the ground for it; (3) `26-05-030` the conditional zoning
   petition, whose entire "conditional" is Exhibit C — a landscape mound, with no noise, height,
   water-supply or discharge limit. They did **not** pass "6-0": the minutes record no numeric
   tally, only "all concurred", and Councilman Greg Roberts abstained as a Marsh Foundation
   employee. Note what remains open even after ingest — **no signed or certified copy is public**;
   all six ordinance PDFs were uploaded four days before the vote carrying an unfilled
   `Passed this ___ day of ___`, which is why the Type 1 / Type 2 contradiction in the record is
   unsettleable.
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
- **Footprint — closed (#1403).** The geometry came from the county auditor CAMA, not from the
  press release or the Recorder: `data/extracted/van-wert/bosc-site-footprint.yaml` +
  `data/reference/van-wert/parcel-assemblage.geojson`, the five parcels deeded to **QTS Van Wert
  LLC** in June 2026 — **900.59 ac deeded / 901.502 ac planar**, which meets the quoted **902-acre**
  campus figure to 0.16%. Against the annexation it is **1.108 ac (0.12%)** short, not the "61.4 ac"
  this line originally recorded: that gap was measured against the press's ~962 ac, and #1401 read
  the zoned area off Ordinance 26-05-028's Exhibit A as **901.698 ± ac**. Three independent
  acreages now agree to within ~1.1 ac. The Recorder deed is still needed, but for the **grantor /
  instrument numbers**, not the boundary (#1404).

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

- [x] Every written reference value is reviewed against a cited source (no fabricated values).
  **Worked 2026-08-14, not ticked** — the sweep found two real defects, in the same shape the
  Sidney (#1992) and Findlay (#1265) gates found theirs.
  1. **A fabricated provenance claim in litigation evidence (#2001).** Both committed
     `2GC08872` extractions opened "HAND-READ … nothing was OCR'd" and then asserted `dpi: 150`
     — a rasterization that never happened, supplied only because `NpdesExtraction` required a
     render receipt and the alternative was being silently dropped (#1994). Verified three ways
     that agree (pypdf character counts match each file's own stated counts exactly — 2,043 and
     3,573 + 117; the filename-map records `evidence: native_text`; the recorded sha256s match the
     bytes), then the receipt was removed and replaced with `meta.sources`. A corpus-wide test
     (`test_no_committed_hand_read_carries_a_render_receipt`) now refuses the combination
     anywhere in `data/extracted/**`.
  2. **A retired figure that had propagated to six surfaces.** #1401 read the annexed area off
     Ordinance 26-05-028's Exhibit A as **901.698 ± ac** and retired the press's "~962 ac" — but
     the correction reached only `data-centers.md` and the site profile. The stale figure, and the
     **61.4-ac `[open]` gap derived from it**, survived in the footprint extraction, this file, the
     committed `parcel-assemblage.geojson` provenance, `data/reference/van-wert/README.md`, the
     `data-centers-van-wert` catalog notes and the network-wide `parcel-assemblage` catalog entry.
     Corrected in all six; the true shortfall is **1.108 ac (0.12%)**, and three independent
     acreages (901.698 zoned / 901.502 planar / 900.59 deeded) now agree to within ~1.1 ac. The
     same sweep retired "6-0" (no tally is recorded) and "QTS Realty Trust, LLC / Overland Park KS"
     (the applicant of record is QTS Realty Trust **Inc.**, Duluth GA) where each survived.
     **The lesson generalizes:** a `corrections_to_the_register` block records that a figure was
     corrected somewhere, not everywhere. Grep the whole tree for the superseded value.
  What the sweep also confirmed is **sound**, and is worth recording so it is not re-litigated: the
  basin screen's denominator. Town Creek's 7Q10 is 0.16 cfs `source: document`, read at the outfall
  from fact sheet 2PD00006 Table 12 — not a derived basin proxy, which is exactly the defect that
  had overstated Sidney's dilution 17-fold. There is no proxy on this key to collide with.
- [x] SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation. **(#1403 — the profile was updated: `[inference]` flat `"D"` → `[verified]` dual `"C/D"`,** 44 of 45 grid points over the committed campus assemblage. The correction is to the *rating*, not the geology: the old inference read the ground right — Great Black Swamp lake-plain clays, and it named Hoytville — but NRCS rates Hoytville C/D, C where the field tile is installed and maintained, D undrained. A flat D pre-committed the undrained letter for both scenarios, inflating the pre-development CN of ground that is tile-drained CAUV row crop today and so understating the pre-to-post delta. Recorded verbatim per WS-20/#1620.)
- [x] basin-screen coverage is sane for this site's receiving waters. OH0027910 screened against Town Creek 7Q10 (0.16 cfs annual, source=document); dilution ratio 0.026:1 — 39× effluent dominance, `[verified]`. See self-research summary above.
- [x] A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md). Parcels wired via `VAN_WERT_PARCEL_SCHEMA` (#421 — the county's AGOL `parcel_joinedVWOH`, replacing the dead bhamaps host); zoning stays `[open]` (no REST anywhere; map-only/PDF).
- [x] Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/) — see self-research summary above; 5 proposals filed as sub-issues of #363 (#375–379).
- [x] PROMOTION IS A SEPARATE MANUAL EDIT: flip `status: live` + `selectable: true` for `van-wert` in **`data/sites.yaml`**, then run `watermark sites sync`; parity-gated. (The path this line carried, `web/src/lib/sites.ts`, is retired — `data/sites.yaml` is the canonical identity registry and the TypeScript registry is generated from it. The same stale path survives in 19 other sites' ONBOARDING.md and is a network-wide follow-up, not fixed here.) `onboard` never auto-promotes. Promoted on **Sidney / Troy-Piqua parity**: van-wert's readiness block — `case` tier, backdrop/places/record/inquiry `live`, facility `seeded` — is identical to both, and `facility: live` is unreachable here by design (see `_profiles.py`; the NOI certifies the air PTI as `YET_TO_APPLY` and AEP stated no MW for this campus), so it is not a gap being waived.
