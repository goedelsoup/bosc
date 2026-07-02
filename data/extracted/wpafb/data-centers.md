# Wright-Patterson AFB / Dayton (Greene + Montgomery Co.), OH — Data-Center Activity Register

Discover-and-pin register for the WPAFB watershed point — the **Mad River / Great Miami**
corridor and the Dayton defense metro. Status **as of 2026-07-02**. Tags are BOSC evidentiary
discipline: `[verified]` = on-record in a government/primary source (often two+), `[reported]` =
credible secondary / investigative journalism, not officially confirmed, `[reference]` =
published-record assertion carried in the corpus, `[inference]`, `[open]`.

**This is a scaffold, not a completed sweep (#467).** Unlike the greenfield Miami sites, WPAFB is
the **one Miami node that already carries a corpus thread** — but that thread is *published-record
DoD-cloud context, not a sited facility*. This register (a) records the corpus-grounded DoD-cloud
thread and (b) frames the sited-facility scan whose expected outcome is a **flat no-primary-record
finding**. The web-research pass (parcel / SOS / OEPA permit) is still **to-run**; every
open item below names the primary instrument to pull. **Nothing here is fabricated.**

## Register discipline — two distinct registers, kept separate

1. **The DoD-cloud *customer* register** (below, §1) — legitimately WPAFB's relevance: the
   regulated/air-gapped defense-cloud thread. It is **entity-level published record**, not a sited
   facility, and is **not** the Lima Bistrozzi land-assembly graph — do **not** bridge them.
2. **The sited-facility scan** (§2) — a parcel/SOS/permit search for any *sited* data-center land
   assembly in the Dayton/WPAFB corridor. Handle the **WPAFB federal enclave** (military land
   absent from county CAMA) as its own register (cf. Lima's `UNITED STATES` parcel-owner entity).

## 1 — The DoD-cloud thread (published record, in-corpus) `[reference]`

The distinctive data-center variant here is **regulated/air-gapped DoD cloud (IL5/IL6)**, not
hyperscale. It is already in the BOSC corpus as published record:

- **Written testimony §8 "Ohio defense footprint"** — Google Distributed Cloud air-gapped
  appliance holds DoD **IL5**, MIL-STD-810H; the Air Force **Rapid Sustainment Office (RSO)** a
  named early customer; **GDIT + Google Public Sector** demoed at **Exercise Mobility Guardian
  2025**. `[reference]` Source (in-corpus):
  `data/extracted/legal/select-committee-2026/relator-testimony/bosc-written-testimony-2026-06-01.md`
  (cited to Google Cloud blog, Breaking Defense, Defense One, GDIT). This is a **secondary /
  published-record** assertion inside a relator's own testimony — defensible as published record,
  **not** a primary land or permit instrument.
- **Cloud-consumer profile** — Tier-3 entry "Wright-Patterson AFB-adjacent suppliers (corridor)",
  `confirmed_cloud_relationship: GDIT (WPAFB Rapid Sustainment Office hub, per published record)`,
  location "corridor (Greene County hub)". `[reference]` Source (in-corpus):
  `data/entities/profiles/cloud-consumer-candidates.yaml` (the WPAFB-adjacent-suppliers entry).
- **IL5/IL6 is entity-level, explicitly not tied to a sited facility.** `docs/legal/mandamus-analysis.md`
  records Google Distributed Cloud + air-gapped appliance reaching IL6 / Top Secret as an
  *entity-level* capability, "not tied to the Lima site" — the same caution applies at WPAFB.
  `[reference]`

**Analytical frame (keep, don't overclaim):** the "government-cloud premium" (≈20–30% above
commercial) and the **structurally-barred-local-tenants** argument — an IL5/IL6 enclave cannot
host a local hospital, bank, or county. This is the corpus's own framing (written testimony
§ government-cloud premium), carried as `[reference]`. `[inference]` on the exact premium band.

### To confirm / expand (§1 instruments)

- **RSO / GDIT cloud hub** — pull the primary sources behind the testimony (Google Cloud public-
  sector blog; Breaking Defense; Defense One; GDIT press) and pin whether any **sited** RSO cloud
  facility exists vs. an entity-level authorization only. `[open]`
- **Google Distributed Cloud IL5/IL6 authorization record** — DISA Provisional Authorization / the
  Google Cloud IL6 announcement (already linked in `mandamus-analysis.md:495`). `[open]`
- **Exercise Mobility Guardian 2025** — GDIT/Google Public Sector role, primary press. `[open]`

## 2 — Sited-facility scan (expected: flat no-primary-record) `[open]`

`[verified]` **The BOSC corpus holds zero primary records** — no Montgomery/Greene County deed,
NPDES permit, SOS shell filing, or meeting record — of a *sited* data-center facility in the
Dayton/WPAFB corridor (the corpus is entirely Lima/Allen County; see the onboarding findings pass,
`data/research/onboard-wpafb-*/findings.md`). The county employment mix is consistent with **no
existing IT-hosting cluster**: Montgomery Information (NAICS 51) LQ **0.90**, Prof/Sci/Tech (NAICS
54) LQ **0.81** — neither elevated (BLS QCEW 2023, `data/reference/economics/wpafb/baseline.yaml`).

This scan is **to-run**; commit a **dated, sourced flat no-activity finding** if the web pass
confirms nothing sited. Do **not** infer a facility from the DoD-cloud thread in §1.

### Instruments to pull (priority order)

1. **Montgomery County Auditor / GIS + Greene County Auditor / GIS** — parcel sweep for large
   contiguous industrial assembly near the base / I-675 / Dayton corridor; owner of record,
   transfer dates. (GIS endpoints are `[open]` on the profile — `parcels_url="TODO"`.)
2. **Ohio SOS business search** — new LLC/shell formations tied to any assembly (the Lima/Piqua
   pattern: a single-purpose shell holding the entitlements). Keep any find a **separate register**.
3. **Ohio EPA / EPA ECHO** — data-center stormwater coverage under draft general permit
   **OHD000001**; any new industrial NPDES near the corridor. (ECHO Great-Miami inventory is
   already committed: `data/reference/echo/great-miami-wwtp.potw.yaml`.)
4. **AES Ohio (DP&L) large-load / PJM interconnection queue** — a >100 MW tap in the DAY zone is
   the earliest hard signal of a sited campus. `[open]`
5. **City/County zoning & rezoning dockets** — Dayton, Riverside, Beavercreek, Fairborn, Huber
   Heights; heavy-industrial rezonings 2023–2026. `[open]`
6. **WPAFB federal enclave** — treat separately; federal/military land won't appear in county CAMA.
   The base's own IT/cloud footprint is a DoD real-property question, not a county parcel. `[open]`

## Hydrology hook (for any sited find)

The WPAFB receiving-water story is **groundwater**, not surface 7Q10 — see the groundwater screen
(`data/extracted/wpafb/groundwater-screen.md`, #463): the Great Miami / Mad River **Buried Valley
sole-source aquifer** + the TCE/PFAS plume. Any sited campus's consumptive draw must be screened
against the **buried-valley supply**, not just in-stream low flow. Surface dischargers of record
(committed ECHO): Fairborn WRC (OH0025062, 6.0 MGD → Mad River); Western Regional WRF (OH0026638,
20.0 MGD → Great Miami River). `[connector]`

## Sources

- Written testimony §8 (in-corpus, published record):
  `data/extracted/legal/select-committee-2026/relator-testimony/bosc-written-testimony-2026-06-01.md`
- Cloud-consumer profile (in-corpus): `data/entities/profiles/cloud-consumer-candidates.yaml`
- Mandamus analysis (IL5/IL6 entity-level caution): `docs/legal/mandamus-analysis.md:495`
- Google Cloud (GDC air-gapped appliance IL6): [google-distributed-cloud … IL6 authorization](https://cloud.google.com/blog/topics/public-sector/google-distributed-cloud-gdc-gdc-air-gapped-appliance-achieve-dod-impact-level-6-il6-authorization)
- Onboarding self-research pass: `data/research/onboard-wpafb-wright-patterson-afb-data-center-a-2026-06-22/findings.md`
- Ohio EPA (data-center general permit OHD000001): [wastewater-discharges-from-data-centers--general-permit](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit)
