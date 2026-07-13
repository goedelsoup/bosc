# The airport nexus — Mansfield Lahm, the 179th, and the Airport West footprint

**Sub-issue #1431 · `places` domain.** The one data center actually being built in Richland
County is the **military's own** — the Air National Guard's on-base facility at the **179th
Cyberspace Wing** (city-owned Mansfield Lahm Regional Airport). The geometry around it is public
record; this file grounds the committed footprint and holds the instrument ledger.

## Discipline (read first)

Geographic adjacency — the I-2 rezone sits beside the base, beside the water loop, beside the
future substation — is **not** a documented connection. What ties these actions together is the
set of **funding instruments** (a rezone ordinance, a Military Construction Cooperative Agreement,
a design contract, an ARPA/All-Ohio-Future application), and each says only what it says. The base
data center, substation, water loop, and rezone are **documented city/Guard actions**. Any reading
that the city is *assembling capacity for future private data centers* is an **`[inference]`
question**, never a finding — the county publicly **rejected** the private 800 MW "AI factory"
(EnergiAcres) pitch (#1428), and a commissioner noted that social posts conflating the water loop
with EnergiAcres were wrong: the corridor build predates and outlives that pitch.

## The committed footprint — Airport West I-1→I-2 rezone `[verified]`

**City of Mansfield Ordinance 25-086** (Bill 25-087; City Planning Commission **Petition #561**),
passed as an emergency **2025-06-03**, amended the City Zoning Districts Map (Ord. #04-208) to
rezone **16 lots** at and around **Airport West Parkway & Cairns Road** from **I-1** (Limited
Impact Industrial District) to **I-2** (General Impact Industrial District) — "as recorded in the
Richland County Auditor's Office." Sponsor: Mount. Two capped public landfills within the area
cannot be developed and are slated for solar arrays.

- **Committed geometry:** [`data/reference/mansfield/parcel-assemblage.geojson`](../../reference/mansfield/parcel-assemblage.geojson)
  — the recorded parcel polygons from the Richland County Auditor CAMA (`Parcel_CAMA` layer 0),
  via `RICHLAND_PARCEL_SCHEMA`. This is the site's **first committed footprint geometry** and flips
  the `places` readiness domain to **live** (`geo/campus` feed).
- **Vintage reconciliation `[verified]` / `[inference]`:** the ordinance lists 16 lots; the
  **current** auditor parcel fabric resolves **10** of them (~**309.1** recorded legal acres,
  reconciling with the ~321 ac reported for the full schedule). The other 6 —
  `028-90-500-93-002/003/004/006/007` and `028-90-150-51-001` — no longer resolve as separate
  parcels; they were **consolidated or renumbered** after the ordinance was drawn. The specific
  successor parcel(s) are `[inference]` (not confirmed from an auditor parcel-history/deed record);
  the adjacent City lot `028-90-500-93-000` (129.53 ac) is the likely absorber but is unverified.
  Retired IDs are preserved in the geojson provenance; their geometry is **not fabricated**.
- **Ownership `[verified]` / `[reference]`:** the City of Mansfield owns 7 of the 10 resolved lots;
  37 East Fourth Street LTD (an Ohio LLC) owns 3. **Adena Development Corp** — the city-affiliated
  community-improvement corporation named in press coverage — is **not** a current owner-of-record
  on the resolved 10; its historical interest and the disposition of any holdings are **unknown
  here** (no deed / parcel-history record pulled), so the Adena attribution stays `[reference]`.
- **Note:** the auditor `ZONING` column is unpopulated on this layer, so the I-1→I-2 status is the
  **ordinance**, not a CAMA attribute.
- Source: <https://ci.mansfield.oh.us/wp-content/uploads/2025/06/Passed-Legislation-06-03-25.pdf>
  (summary sheet + full Ordinance 25-086 text, pp. 19–20).

## Instrument ledger (the nexus)

The substation, water loop, and PFAS threads below are the **airport nexus** but sit primarily in
sibling domains (`record` #1429/#1430, `facility` #1428). Recorded here as cited leads; full
document ingestion is those issues' work.

### Substation — the 179th's power `[reference]`

An **$8.4M electrical substation**, city-built and **NGB-reimbursed 100%** under a **Military
Construction Cooperative Agreement (MCCA)** (Mansfield City Council approved Aug 2025), taps Ohio
Edison's **Longview–Ontario 138 kV** line. **Encorus Group** design contract **$587,180** (Board
of Control 2026-03-10). City engineer, press-quoted: capacity needed "at the end of 2027, early
2028, when they have additional cybersecurity components"; build deadline 2028. → **#1429/#1430**
should catalog the MCCA ordinance + the Encorus contract; the **substation footprint** is added to
this geometry **when its siting is public**.

### Water loop — redundancy + 500 acres `[reference]`

A **~$15M water-loop connection** (N. Main / Bowman lines) at the airport's north end: redundancy
for the 179th's data center **plus** capacity "opening roughly 500 acres" at Airport West
Industrial Park / the Aero Site (design phase as of 2025-05-29; ARPA + general fund + an All Ohio
Future Fund application). The Bowman-St frontage of several rezoned lots
(`028-90-150-49/50/51-000`, `028-90-500-93-000`) sits on this corridor.

### PFAS at Lahm — from press to filings

- **AFFF MDL `[verified as filed]`:** **City of Mansfield v. 3M Company, No. 2:23-cv-01192
  (D.S.C.), filed 2023-03-27** — a member case of **MDL 2873**, *In Re Aqueous Film-Forming Foams
  Products Liability Litigation* (2:18-mn-02873, D.S.C.). CourtListener docket **67093608**
  (<https://www.courtlistener.com/docket/67093608/city-of-mansfield-v-3m-company/>). This moves the
  PFAS claims from press to the federal record as **allegations** — never as findings of
  contamination extent. The complaint alleges PFOA/PFOS in groundwater, surface water, and soil at
  the former 179th Airlift Wing on city-owned airport property from AFFF use; further soil testing
  was announced Sept 2023.
- **DoD/ANG PA/SI `[verified]`:** OSD *Status of PFAS Preliminary Assessment / Site Inspection*
  (Dec 2023) lists **"Air Force — Ohio National Guard — Mansfield"**: PA start **2023-09**, planned
  horizon 2031-09, status **"PA/SI Underway"** (release area "Mansfield LAHM Fire" training area).
  Retrieved 2026-07-12 (the 2026-07-10 pass's TLS failure on the OSD PDF was transient):
  <https://www.acq.osd.mil/eie/eer/ecc/pfas/docs/reports/Status-of-PFAS-PA-SI-DEC2023.pdf>. The NGB
  PFAS-Library Ohio index (`nationalguard.mil/.../PFAS-Library/Ohio/`) **still returns HTTP 403** to
  automated retrieval — the per-site PA/SI report PDF remains `[open]`.
- **Finished water `[verified]`:** the Mansfield **2024 CCR** shows **no PFAS detections** in
  finished water — PFAS is defined in the report's glossary but does **not** appear in its Table of
  Detected Contaminants (printed p. 4); the only flag on that table is a **TTHM operational-evaluation
  exceedance at 1 of 8 sampling locations (Q4 2024)**, verbatim, marked "No" violation. The PFAS
  record is a source-area/allegation story, not a finished-water contamination finding. Source:
  Mansfield 2024 Consumer Confidence Report, Table of Detected Contaminants (printed p. 4) —
  <https://ci.mansfield.oh.us/wp-content/uploads/2025/04/2024CCR.pdf>.
