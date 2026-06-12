# PRR & mandamus — source instruments + the withholding map

The public-records-request thread: the consolidated **records-withholding map**, the
source instruments it draws on, and the production record.

## The map

[`records-withholding-map.yaml`](records-withholding-map.yaml) — one map of Project
BOSC's **layered withholding architecture**, along the records lifecycle:

1. **R.C. 4582.58** front-end non-record shield (developer info via AEDG/PAAC).
2. **NDA §6(f)** (≥10 business days developer notice) + **RDA §9.13** (≥5 business days).
3. **CRA §22** attorney-fee indemnity insulating the County from losing a records suit.
4. **ORC 121.22(G)(8)** closed deliberations (first used 2025-05-27 for the CRA, NDA-cited).
5. **Non-production** (cost-benefit item 4; wastewater items 5–15; CMS audit trail item 16).
6. **Blank production** (land prices on blank DTE-100s; non-public school-compensation terms).
7. **Infrastructure-record + trade-secret shield** — a *third* agency (Allen SWCD) withholds the
   site plan sets under **R.C. 149.433** (25-yr "infrastructure record" + express statement) **and**
   **R.C. 1333.61** trade secret ("water and wastewater usage for a data center"), and redacts plan
   links inside produced emails.

## Source instruments

| File | What |
|---|---|
| [`mutual-nda-bistrozzi.nda.yaml`](mutual-nda-bistrozzi.nda.yaml) | The County–Bistrozzi Mutual NDA; §6(f) is the prior-notice/minimize records mechanism (originated by Asst. Prosecutor Willamowski Jr.). |
| [`cra-agreement.cra.yaml`](cra-agreement.cra.yaml) | The Community Reinvestment Area Agreement; §22 public-records indemnity; §13(A) Fortune-100 parent assurance. |
| [`school-district-notice-letters.notice.yaml`](school-district-notice-letters.notice.yaml) · [`school-district-notice-resolution.notice.yaml`](school-district-notice-resolution.notice.yaml) | The Elida LSD / Apollo school-district CRA notices. |
| [`bosc-prr-production-2026-06-05.response-index.yaml`](bosc-prr-production-2026-06-05.response-index.yaml) · [`bosc-prr-production-2026-06-05.analysis.md`](bosc-prr-production-2026-06-05.analysis.md) | The County's item-by-item PRR production + analysis (batch 1). |
| [`bosc-prr-production-2026-06-12.response-index.yaml`](bosc-prr-production-2026-06-12.response-index.yaml) · [`bosc-prr-production-2026-06-12.analysis.md`](bosc-prr-production-2026-06-12.analysis.md) | County batch 2 — the Category-B wastewater works (items 5–15). |
| [`bosc-prr-production-2026-06-12-aswcd.response-index.yaml`](bosc-prr-production-2026-06-12-aswcd.response-index.yaml) · [`bosc-prr-production-2026-06-12-aswcd.analysis.md`](bosc-prr-production-2026-06-12-aswcd.analysis.md) | **Allen SWCD** production — the *site-level* stormwater/erosion record (ESC inspections, SW1225, plan-review emails); plans withheld under §149.433 + §1333.61. A separate 11-item (Parts A–E) request to a separate agency. |

The **RDA §9.13** clause lives in
[`../../aedg/roadwork-development-agreement.rda.yaml`](../../aedg/roadwork-development-agreement.rda.yaml);
the **R.C. 4582.58** shield in
[`../../aedg/paac-records-policy.policy.yaml`](../../aedg/paac-records-policy.policy.yaml);
the **(G)(8)** executive-session census in
[`../../commissioners/closed-deliberation-and-corridor.yaml`](../../commissioners/closed-deliberation-and-corridor.yaml);
and the standing completeness audit at
[`../corpus-completeness-audit.md`](../corpus-completeness-audit.md).
