# AEDG / PAAC PRR-bundle extractions

Reviewed structured reads from [`data/documents/aedg/PRR-01-bundle.ocr.pdf`](../../documents/aedg/README.md)
— the 328-page Port Authority of Allen County (PAAC) public-records production
("Allen County — Responsive Records — Parent PRR"). Navigation map:
[`PRR-01-bundle.ocr.pdf.index.yaml`](../../documents/aedg/PRR-01-bundle.ocr.pdf.index.yaml).

The Tetra Tech roundabout **OPC** (Opinion of Probable Cost) estimates are the
project's **reference extraction** — the target the extract stage is built against
(summary at 0-based PDF page 317, detail 318–327).

## Files

| File | What |
|---|---|
| `roundabouts.summary.opc.yaml` | Tetra Tech OPC — section subtotals, markups (25% contingency), construction subtotal ($14,223,081), and total per roundabout. |
| `roundabouts.detail.opc.yaml` | Tetra Tech OPC — full per-section line items (item number, description, quantity, unit, unit rate, extended amount). |
| `roadwork-development-agreement.rda.yaml` | The BOSC Roadwork Development Agreement (PAAC / Allen County / Bistrozzi LLC), eff. 2025-09-15. $14.5M Company Contribution (basis = the Tetra Tech OPC via Exhibit D), grant-refund mechanism (§5.5), 4 roundabouts + 2 rehabs (Exhibit B), parcels (Exhibit A), §9.13 records-notice clause, §9.17 no-procurement. Bundle pp.296–316. |
| `paac-records-policy.policy.yaml` | PAAC Public Records Availability + Retention/Destruction Policy (adopted 2022-07-28). R.C. 4582.58 econ-dev trade-secret shield, legal-hold, 2-yr PRR retention; establishes PAAC has no employees and Cynthia Leis directs both AEDG and the Authority. Bundle pp.80–90. |

## Still un-extracted from the bundle

- **PAAC board minutes** (pp.1–79) — BOSC/Nadella/Gunsmoke/P&G/REV LNG/Amazon threads.
- **Seller land packets** (pp.91–295) — Brenneman, Miller, Neff, Neighbors option/assignment → Bistrozzi chain.

## Conventions

- Figures are read off the 300 DPI render, **not** the garbled OCR text layer.
- Dollar totals/subtotals are high-confidence; uncertain quantities carry the `~`
  approximate marker (see [`data/README.md`](../../README.md)).
- Validated by `bosc.models`; `bosc reconcile` checks line-item → subtotal → total
  arithmetic and the contingency convention. Provenance is in each file's `meta`.
