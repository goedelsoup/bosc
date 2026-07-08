# Ohio EPA NPDES documents — Urbana WPCF (original records)

**Collection:** `oepa/urbana/` · immutable source evidence

Ohio EPA compliance documents for Urbana: the City of Urbana Water Pollution Control
Facility (WPCF), the Municipal Separate Storm Sewer System (MS4), and collection-system
permits. WWTP federal permit: **OH0027880**; Ohio EPA permit: **1PD00011**.
Outfall 001 discharges to the **Mad River** at 40.095278, -83.797222 (0.38 mi south of SR 36).
Design flow: **4.5 MGD**. Raw bytes are never edited; canonical names are in `filename-map.yaml`.

## Contents

| eDoc ID | Type | Date | Permit |
|---|---|---|---|
| `2663158.pdf` | Surface Water Permit to Install (PTI) — South High Street sewer | 2023-10-19 | DSWPTI1586541 |
| `2784672.pdf` | NPDES Compliance Evaluation Inspection (CEI) | 2024-03-14 | 1PD00011 |
| `3492222.pdf` | NPDES Permit Renewal Application (Form 1, 2A, 2S) — 2020 cycle | 2020-02-13 | OH0027880 |
| `3816773.pdf` | NPDES Compliance Evaluation Inspection (CEI) | 2025-08-13 | 1PD00011 |
| `3832476.pdf` | NPDES Permit Renewal Application (Form 1, 2A, 2S) — 2025 cycle | 2025-05-29 | OH0027880 |
| `3832477.pdf` | Sludge process flow diagram (exhibit to 3832476) | undated | OH0027880 |
| `3832478.pdf` | Full plant process flow diagram "Urbana WRF" (exhibit to 3832476) | undated | OH0027880 |
| `3832479.pdf` | Survey elevation sheet (exhibit to 3832476) | undated | OH0027880 |
| `3858475.pdf` | Pretreatment Compliance Inspection (PCI) | 2025-09-09 | 1PD00011 |
| `3858492.pdf` | Notice of Violation (NOV) — pretreatment SNC | 2025-10-07 | 1PD00011 |
| `3613310.pdf` | MS4 Annual Report (OHQ000003) | n/d | OHQ000003 |
| `3959035.pdf` | MS4 Notice of Violation (NOV) | 2026-01-05 | 1GQ00062 |
| `1PD00011.pdf` | Issued NPDES permit (2020 cycle) | 2020-10-26 | 1PD00011 |
| `1PD00011.fs.pdf` | NPDES fact sheet (2020 cycle) — regulatory 7Q10 | 2020-09-22 | 1PD00011 |

The last two are Ohio EPA's published, currently-effective issued instruments (from the
permits document library, not eDoc). The **fact sheet's Stream Flows table cites the
regulatory design low flow** for the Mad River outfall: annual **7Q10 = 35 cfs** (USGS
gage 03267000, 1997 flow document) — the value OEPA uses for the wasteload allocation. It
supersedes the earlier `[derived]` LP3 passby (53.67 cfs) on `SiteProfile('urbana')`.

The **2025-cycle renewal** (application eDoc `3832476`, filed 2025-05-29) had **not issued**
as of 2026-07: the permit expired 2025-11-30 and is in administrative continuance, so the
2020 fact sheet remains the effective regulatory instrument. When the 2025 renewal issues,
its fact sheet (which may revise the 7Q10) should be ingested and the passby re-verified.

Enforcement follow-up (as of 2026-07): no resolution instrument for the 2025-10 pretreatment
**NOV (SNC)** (`3858492.pdf`) or the 2026-01 **MS4 NOV** (`3959035.pdf`) has surfaced in the
Ohio EPA eDoc portal — both remain open on the record.
