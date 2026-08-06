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
| `3858492.pdf` | Notice of Violation **/ Resolution of Violation** — pretreatment SNC (also eDoc `3858493`) | 2025-10-07 | 1PD00011 |
| `3613310.pdf` | MS4 Annual Report (OHQ000003) | n/d | OHQ000003 |
| `3959035.pdf` | MS4 Notice of Violation (NOV) | 2026-01-05 | 1GQ00062 |
| `1PD00011.pdf` | Issued NPDES permit (2020 cycle) | 2020-10-26 | 1PD00011 |
| `1PD00011.fs.pdf` | NPDES fact sheet (2020 cycle) — regulatory 7Q10 | 2020-09-22 | 1PD00011 |

The last two are Ohio EPA's published, currently-effective issued instruments (from the
permits document library, not eDoc). The **fact sheet's Stream Flows table cites the
regulatory design low flow** for the Mad River outfall: annual **7Q10 = 35 cfs** (USGS
gage 03267000, 1997 flow document) — the value OEPA uses for the wasteload allocation. It
supersedes the earlier `[derived]` LP3 passby (53.67 cfs) on `SiteProfile('urbana')`.

The **2025-cycle renewal** (application eDoc `3832476`, filed 2025-05-29) had **still not issued**
as of the 2026-08-06 re-check, on three independent checks: the OEPA permits doc library still
serves the 2020 issuance (both `1PD00011.pdf` and `1PD00011.fs.pdf` fetched live are
**byte-identical**, SHA-256 `8e146b28…` / `8bf9f3d6…`, to the committed copies); EPA ECHO
(ICIS-NPDES extract 2026-07-31) still reports the permit status as **Expired**; and the eDoc
index carries **no `Permit` document under 1PD00011 later than the 2025-09-19 application
package** (`3832476`–`3832479`) — the newest 1PD00011 document of any type is a 2026-01-27 SSO
annual report. The permit expired 2025-11-30 and is in administrative continuance, so the 2020
fact sheet remains the effective regulatory instrument and the annual **7Q10 = 35 cfs** remains
the effective passby on `SiteProfile('urbana')` (`passby_primary_cfs`). When the 2025 renewal
issues, its fact sheet (which may revise the 7Q10) should be ingested and the passby re-verified.

### Enforcement — the pretreatment NOV was resolved on its face (corrected 2026-08-06)

**The 2025-10 pretreatment NOV is not open, and never was.** Earlier revisions of this README
recorded it as awaiting a resolution instrument. The committed document refutes that: `3858492.pdf`
is captioned "**Notice of Violation / Resolution of Violation** - Significant Non-Compliance (SNC)"
and carries its own resolution — "*On 9/30/2025 Ohio EPA DSW received Urbana's completed fourth
quarter 2024 QIUVR electronically through the eBusiness center. Therefore, this violation has been
resolved*" (p. 2). The single cited violation was a late Q4-2024 Quarterly Industrial User Violation
Report (ORC 6111.07(A), OAC 3745-3-03(C), permit Part II.W.10) — a Level I Reportable
Non-compliance, which is what triggered the SNC categorization — and it was cured **2025-09-30**,
a week *before* the letter issued. Ohio EPA's own eDoc index says the same thing twice: the identical
bytes are published under **two** docids, `3858492` (doc type *NOV*) and `3858493` (doc type *ROV or
RTC* — Resolution of Violation / Return to Compliance), both dated 2025-10-07, both SHA-256
`61c9e818…`. `[verified]`

The reason the earlier re-checks missed this is worth recording, because it generalizes: they leaned
on **EPA ECHO to corroborate the absence of a resolution**, and ECHO structurally cannot speak to
that. ECHO tracks *formal* enforcement; a state NOV closed by an informal ROV/RTC leaves
`FormalActions` empty and `FormalEnfActCount = 0` whether or not it was resolved. The empty ECHO
enforcement blocks were read as corroboration of "still open" when they were consistent with either
state. **The instrument that answers the question is the eDoc doc-type index** (`ROV or RTC`,
`Director's Final Findings and Orders`), not ECHO — and, in this case, the text of a document the
corpus already held.

**The 2026-01 MS4 NOV (`3959035.pdf`, permit 1GQ00062) remains `[open]`.** It is a genuine open
enforcement item and the contrast is instructive: it contains no resolution language of any kind
(zero occurrences of "Resolution" / "resolved" / "Return to Compliance" across its 36 pages), it
issues five violations each closing with "*please provide a written plan of corrective action*", and
it is the **newest document under 1GQ00062 in eDoc** — no paired ROV/RTC has been filed against it
as of 2026-08-06. No resolution is inferred.

Standing-watch scope (re-checked 2026-08-06, eDoc + ECHO + doc library): the eDoc index lists **6
NOVs and 5 ROV/RTCs** under 1PD00011 across the facility's history — pairing a resolution to a
notice is this office's routine practice, not an exception. The corpus holds one of the six. The
2024-08-05 NOV (`3124246`) and its 2024-09-03 ROV (`3170919`) — the pair behind ECHO informal action
`OH-I00106574` — are **not in corpus**; ingesting them is a `record`-domain gap tracked outside this
watch, not an open enforcement item. This is a standing, externally-gated watch — see issue #1355.
