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
| `paac-board-minutes.minutes.yaml` | PAAC board minutes 2023-05→2026-04 — **the codename decoder**. Confirms BOSC=Bistrozzi=**Google** and Nadella=**Microsoft** (terminated); land-assembly→Bistrozzi assignment; proposed $200K→$250K/yr Elida school PILOT; Eagle Bridge ~$3.52M actual roundabout award vs $14.5M budget; transparency complaints + Google well concerns; full actor roster. Bundle pp.1–79 (native text). |
| `seller-land-packets.land.yaml` | The land-assembly chain (pp.91–295): PAAC option agreements (Brenneman $1,000/81 ac, Miller $2,000/55 ac, Neff eff 2023-06-21) → assigned to **Bistrozzi LLC** 2025-07-03 (Vorys/Tangeman). Prices **withheld** (DTE-100 dollar fields left blank; deeds say only "valuable consideration"); only Neighbors disclosed ($600K/5 ac). CAUV recoupment (Elida LSD). |
| `aedg-data-center-release.release.yaml` | **Web capture, not the PRR bundle.** The AEDG "Data Center Updates" release set — AEDG publicly **reveals Google as the entity behind Project BOSC** (2026-03-16): $500M investment, $50M local infrastructure, $250K/yr Elida PILOT, a named Google official (Molly Kocour Boyle), plus AEDG's proponent FAQ (closed-loop-cooling / behind-the-meter-power claims to weigh against the record). Source HTML under [`data/documents/aedg/data-center-updates/`](../../documents/aedg/data-center-updates/). |

## Bundle coverage

The 328-page bundle is now extracted end-to-end: OPC (roundabouts.*), Roadwork
Development Agreement (pp.296–316), PAAC records policy (pp.80–90), board minutes
(pp.1–79), and seller land packets (pp.91–295).

## Conventions

- Figures are read off the 300 DPI render, **not** the garbled OCR text layer.
- Dollar totals/subtotals are high-confidence; uncertain quantities carry the `~`
  approximate marker (see [`data/README.md`](../../README.md)).
- Validated by `watermark.models`; `watermark reconcile` checks line-item → subtotal → total
  arithmetic and the contingency convention. Provenance is in each file's `meta`.
