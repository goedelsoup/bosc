# IDEM — Fort Wayne source documents

Indiana Department of Environmental Management (IDEM) source documents for the Fort Wayne
(Allen County) watershed point. The first non-Ohio jurisdiction in the corpus; `idem/` is
the Indiana peer of `oepa/`, scoped per site (`idem/<site>/`). Two subjects live here:

1. **Hatchworks LLC / Project Zodiac** — Google's data-center campus air permits (Office of
   Air Quality) and the Phase 3 §401 Water Quality Certification (Office of Water Quality),
   7510 Zodiac Way, Fort Wayne, IN 46816.
2. **City of Fort Wayne P.L. Brunner Water Pollution Control Plant** — the municipal WWTP's
   NPDES discharge permit (IN0032191), the receiving-water record (#1453).

This is **raw, immutable, LFS-tracked source evidence** (chain of custody). Files keep
their AS-RECEIVED IDEM portal names (permit/document number + a stage suffix — `f` final,
`d` draft); canonical names + content-verified dates are recorded non-destructively in
[`filename-map.yaml`](filename-map.yaml). Do not rename or alter a source byte in place.

## Source

Indiana DEM Permit Status Search — <https://apps.idem.in.gov/PermitStatusSearch/>
(facility: Hatchworks LLC; IDEM **AI ID 133680**; OAQ Stationary Source ID **1800300530**).

## Contents

| File | Permit | Level | Date | Pages |
|---|---|---|---|---|
| `47378f.pdf` | `003-47378-00530` | Title V New Source Construction (Minor PSD/EO) | 2024-09-06 | 226 |
| `47378PN-JS.pdf` | `003-47378-00530` | NSC/Part 70 — public-comment notice (procedural) | 2024 | 2 |
| `caats-confidentiality.pdf` | `003-47378C-00530` | **Confidentiality Claim** (CBI on the engine rating) | 2023-12-27 | 1 |
| `48739d.pdf` | `003-48739-00530` (+ `003-48840-00530`) | Part 70 Significant Modification — public-hearing draft | 2025-11-13 | 187 |

The **confidentiality claim** (`caats-confidentiality.pdf`) is why the air permit discloses only heat
input (26.4 MMBTU/hr) and not the engine electrical rating — the genset nameplate was claimed as CBI
(received 2023-12-27, contact Robin Fried), so `SiteProfile.facility.genset_mw` stays *derived* (#360).

The facility is a **Title V (major) air source** — for a data center, the permitted units
are the standby/backup engine fleet. The 2024 NSC permit is the construction authorization;
the 2025 filing is the significant Part 70 operating-permit modification (public-hearing
stage). Ties to `watermark.sites` `_FORT_WAYNE` (#360/#362) and the Hatchworks parcel assemblage
(`data/reference/fort-wayne/bosc-parcels.geojson`).

### §401 Water Quality Certification WQC001454 (Phase 3 — the contested-permit record)

IDEM Office of Water Quality, Waterways Section. The complete administrative record of the
**Section 401 Water Quality Certification** for **Project Zodiac Phase 3** — the campus
expansion (USACE `LRE-2023-00646-102`). The documents name the applicant verbatim as
**"Google Data Center"** (applicant Marc Stern / Hatchworks LLC; agent EMH&T). Phase 3 relocates
**Adams Ditch** (3,415 lf / 0.78 ac) and fills **0.84 ac of forested wetland** to build DC06/DC07,
with mitigation via the Maumee Service Area + Openings stream/wetland banks. The cert was **issued
2026-06-05 over organized public opposition** (Hoosier Environmental Council et al.).

| File | Stage | Date | Pages |
|---|---|---|---|
| `notice_20260403_401_wqc001454.pdf` | public notice (application summary) | 2026-03-13 | 9 |
| `043026-IDEM-Hearing-ORIGINAL.pdf` | public hearing transcript | 2026-04-30 | 90 |
| `public-comments-compiled.pdf` | compiled public comments | 2026-04 | 295 |
| `Response-to-Public-Comments-WQC001454-...pdf` | IDEM response to comments | 2026-06-05 | 11 |
| `WQC001454-Section-401-WQC-Approval.pdf` | **APPROVAL (final, issued)** | 2026-06-05 | 14 |

The campus stormwater receiving water is **Adams Ditch** (an unnamed tributary of Doctor Ditch;
**Maumee watershed, HUC 04100005**) — distinct from the Fort Wayne WWTP's Maumee-mainstem receptor.

### NPDES IN0032191 major renewal + Streamlined Mercury Variance (the WWTP receiving-water record)

IDEM Office of Water Quality. The **draft NPDES renewal** for the **City of Fort Wayne P.L.
Brunner Water Pollution Control Plant** (NPDES **IN0032191**, 2601 Dwenger Avenue) — the basin's
largest POTW, discharging to the **Maumee River** via Outfalls 001/002 (average design flow **74
MGD**, peak **100 MGD**). This is the municipal WWTP's own discharge permit, distinct from the
Google/Hatchworks campus §401 record above. Public-noticed **2026-05-29** (comments closed
2026-06-29); the **final permit + responsiveness summary are not yet issued** (imminent pulls).

| File | Stage | Date | Pages |
|---|---|---|---|
| `notice_20260629_npdes_in0032191.pdf` | **DRAFT** package — public notice + cover letter + draft permit + Fact Sheet | 2026-05-29 | 87 |

The single as-received file is the full draft package. Its Fact Sheet is the permit-grounded source
for [`../../../extracted/fort-wayne/wwtp-receiving-water.md`](../../../extracted/fort-wayne/wwtp-receiving-water.md):
the **cited Q7,10 = 40 cfs (26 MGD)** at the outfall → **0.35:1 dilution** (Bullerman Ditch-Maumee
River watershed, HUC-12 041000050102, AU_ID INA0512-02); new cadmium/cyanide/lead WQBELs on 60-month
compliance schedules; the mercury SMV renewal (interim 1.8 ng/l); TP 1.0 mg/l; TN monitor-only; and
the Federal Consent Decree **2:07-cv-00445** / Agreed Order 2008-178333-W CSO endgame (LTCP fully
implemented 2025; Final Post-Construction Monitoring Report still owed).

## Known gaps & caveats

- The IDEM table lists further authorizations not yet captured here: the issued `003-48739`
  (2026-04-10) and `003-48840` TV SPM (2026-06-01) final permits, plus a 2023 confidentiality
  claim (`47378C`) and a Hazardous Waste ID (`INR000158436`, 2025-03-11). Pull as needed.
- Extraction (structured air-permit data → `data/extracted/idem/fort-wayne/`) is a separate,
  later effort — the extract pipeline's profiles do not yet cover air permits.
- A stray file in the source drop (`23665f.pdf` = Keller Crescent Company, Indianapolis) was
  **not** ingested; it is an unrelated facility. The exclusion is recorded in `filename-map.yaml`.
