# Regulatory enforcement & framework extractions

Reviewed reads of the enforcement / capacity instruments governing the Allen County
sanitary system — the binding history the BOSC-1A wastewater routing must be read
against — plus the standing **regulatory-framework** permits the data-center site
itself is governed by. Sources under [`data/documents/regulatory/`](../../documents/regulatory/README.md)
and [`data/documents/sanitary/`](../../documents/sanitary/README.md).

A **peer site's** instruments nest in a `<slug>/` subdirectory, mirroring the source
tree's site attribution (`*/<slug>`, #1405) — see [Per-site](#per-site-slug) below.

## Files

| File | What |
|---|---|
| `wastewater-enforcement-history.yaml` | The 1996 federal CWA consent decree (US & Ohio v. Allen County, 3:96 CV 7134; effluent violations at American Bath 2PH00007 + Shawnee No.2 2PK00002), the 2005 10-Year Capital Needs Assessment + the 2005-04-21 OEPA SSO-elimination agreement (American No.2 0.80→1.2 MGD; $35M CIP doubling sewer rates), and the Indianbrook PS as-built title sheet (Shawnee collection asset). |
| `ohc000006-construction-stormwater-gp.yaml` | Ohio EPA statewide NPDES Construction Stormwater General Permit **OHC000006** (eff. 2023-04-23) + its Response to Comments — the 1-acre/larger-common-plan applicability threshold, the **NOI ≥21 days before commencement + coverage-not-effective-until-approval-letter** rule, and the SWP3 content requirements. The *standard* the BOSC site's documented "TBD" coverage and 2025-12-08 disturbance are read against; **not** the site's own coverage record (still owed — audit #143). |

## Per-site (`<slug>/`)

| File | What |
|---|---|
| `west-union/west-union-consent-order-1993.order.yaml` | *State of Ohio ex rel. Fisher v. Village of West Union*, Adams County C.P. **89-CIV-228**, entered 1993-06-29 (Judge Elmer Spencer). R.C. Ch. 6111 consent order on NPDES **`0PC00019*CD`**: the Appendix "A" interim effluent limits for outfall 0PC00019001 (0.6 MGD loading basis), a $5,000 civil penalty, two stipulated-penalty schedules, a court-ordered obligation to **eliminate all sanitary-sewer overflows and bypasses**, and a seven-milestone plant-improvement schedule to 1995-05-01 — with jurisdiction retained and **no termination provision**. Records three internal defects in the instrument and the site's [open] targets. The first record in the West Union corpus. |

## Notes

- The West Union order was read from **600 DPI page images**, not its OCR text layer
  (present, 2014 Acrobat Paper Capture, and untrusted for every figure per the root
  `CLAUDE.md` rule). Its committed bytes were hashed against the live Ohio AG source.
- The consent decree + CNA were read from the OCR text layer; the Indianbrook
  as-built is image-only drawings (only the title sheet was transcribed). OHC000006
  - its RTC were read from clean PDF text layers.
- These plants are the BOSC-1A receiving facilities (PRR items 8/9) and the same
  ones carrying TP wasteload allocations in the Maumee TMDL — cross-referenced to
  the hydrology references and the OEPA permit extractions.
- `ohc000006-...` is a statewide framework permit (`kind: general_permit`, not
  classified by the typed corpus loader, so parse-only validation applies). It is
  the regulatory backbone for the site permit-sequence reconstruction
  ([`../legal/prr-mandamus/bosc-site-permit-sequence.md`](../legal/prr-mandamus/bosc-site-permit-sequence.md)).
