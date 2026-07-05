# BOSC PRR — Allen County production batch 2 (2026-06-12)

**As-received:** `Parent Records June 12.pdf` (single bundle). Structured index: [`bosc-prr-production-2026-06-12.response-index.yaml`](bosc-prr-production-2026-06-12.response-index.yaml). Source binary belongs at `data/documents/legal/prr-mandamus/prr-production-2026-06-12/` (to be added; keep the as-received name).

> Analysis, not legal advice. Dollar totals, resolution numbers, and dates are transcribed from the produced PDFs (high confidence); verify against the originals before quoting in a filing.

## What it is

The **second rolling production** — and specifically the **Category-B wastewater works (items 5–15)** that [batch 1](bosc-prr-production-2026-06-05.response-index.yaml) deferred to the Sanitary Engineer ("better suited for the Sanitary Engineer"). No cover letter accompanies the bundle; it is a dump of the Commissioners' resolutions and the Sanitary Engineering instruments behind the corridor's wastewater build-out. **It moves the Project BOSC pump-station/forcemain procurement from secondhand citation to primary record, and it produces the first document tying the data center to the sanitary system.** This closes issue **#134** and produces the central hole in **#35**.

## The three things that matter

1. **The data-center → WWTP keystone.** Resolution **#679-24** (2024-08-22) approves MS Consultants **Task Order #5**, a *"WWTP Data Center Flows Treatment Evaluation"* for **$47,600**. Its scope evaluates the campus **blowdown flow stream** — demands, flows over a typical year, and water-quality parameters — for storage and treatment at the **American Bath WWTP**, with the County to gather data from *"the developer and data center manufacturer."* This is the **first primary-source link** between the data center's cooling system and the sanitary system; until now that connection lived only in secondhand citations behind `watermark.hydrology.cooling` and `sanitary-economics.yaml`.

2. **The BOSC CMAR procurement, end to end.** Three resolutions complete the chain #134 asked for:
   - **#469-25** (2025-06-12) — advertise for engineering; Legal Notice: 2.5 MGD peak, ~17,000 ft, **construction cost $20,250,000**.
   - **#137-26** (2026-02-26) — CMAR RFQ; **estimated construction $29,834,256**; suction-lift PS (2.5 MGD firm at full build); **dual forcemains** — 10″ from the BOSC PS to the American Bath Plant (splitting to 8″) and a 16″ to the City of Lima's existing **78″ gravity sewer at Woodward & Grand** (~20,100 LF + ~17,900 LF).
   - **#378-26** (2026-05-14) — **Peterson Construction Company** CMAR pre-construction contract, **$108,000**, plus the full ConsensusDocs 500 CM-at-Risk agreement (ms consultants = design professional). *This is the `A051426` agenda item the civic meeting-index flagged.*

3. **A ~47% cost escalation.** The construction-cost estimate rose **$20.25M → $29.83M** in eight months (2025-06 engineering ad → 2026-02 CMAR RFQ). That belongs in any public-ROI / cost-benefit discussion — and the cost-benefit analysis itself is the still-**withheld** item 4 (held under §9.66(D)).

## Item 5–15: deferred → **produced**

| Thread | Resolutions | What |
|---|---|---|
| **BOSC PS & forcemain** | #469-25, #137-26, #378-26 | engineering ad → CMAR RFQ → Peterson CMAR pre-construction contract |
| **Data-center flows** | #679-24 (TO5) | blowdown treatment evaluation @ American Bath WWTP |
| **Shawnee Oaks** | #113-26, #136-26 | Access Engineering design ($161k) + WPCLF loan (#136-26, $1.6M) |
| **Hamlet of Hume** | #135-26 | WPCLF principal-forgiveness loan ($2.0M) |
| **Shawnee II Phase 2** | #220-24, #478-20, #228-23, #937-23 | OWDA agreement, CMAR RFQ, $1.5M MOU, Mod #4 ($1.29M) |
| **Stormwater** | #651-23 | updated SWMP to OEPA (MS4 permit) |

**Still outstanding** (watch later batches): the BOSC construction **bids/award** (the CMAR is at pre-construction/design stage). The other items once tracked here — permits **DSWPTI-260294 / DSW-6756**, the **1996 CWA consent decree**, and **Cridersville WWTP** records — are **already in-corpus** (permits under [`data/extracted/permits/`](../permits/) 4074527/4074529/4074551; consent decree in [`regulatory/wastewater-enforcement-history.yaml`](../regulatory/wastewater-enforcement-history.yaml); Cridersville NPDES OH0020222 in the EPA ECHO inventory), per [`corpus-completeness-audit.md`](../corpus-completeness-audit.md).

## One correction to the corpus

Batch 1's minutes-corroboration note and the resolution-ledger read **#113-26 / #136-26** as "MS Consultants forcemain feasibility" and conflated **#135-26 / #136-26** as a single "Hamlet of Hume $2M" loan. This batch disambiguates them from the primary records:

- **#113-26** = Shawnee Oaks Sewer System **engineering contract** (Access Engineering, $161k) — not a feasibility study.
- **#135-26** = **Hamlet of Hume** WPCLF principal-forgiveness loan (**$2.0M**).
- **#136-26** = **unincorporated Shawnee Township** (Shawnee Rd / Hume Rd / "Shawnee Oaks subdivision") WPCLF loan (**$1.6M**) — funds the same Shawnee Oaks sewering #113-26 designs.

(Confirmed by reading pages 79–82 of the source; the prior note recorded a single "$2M Hamlet of Hume" loan for #135/#136 and is superseded.)

To fix: [`bosc-resolution-ledger.yaml`](../../commissioners/bosc-resolution-ledger.yaml) and the `reconciliation_note` in [`commissioners/minutes/README.md`](../../commissioners/minutes/README.md).

## Why it matters

The corridor's sanitary build-out is now legible as one program: failing septics at **Hume / Shawnee Oaks** get sewered (WPCLF loans #135/#136, Access design #113-26) to the **Shawnee II Phase 2** plant (expanded 15 → 25 MGD firm, #220-24), while **Project BOSC** builds its own pump station and dual forcemains (#469-25 → #137-26 → #378-26) to discharge into **both** the American Bath WWTP and the Lima 78″ interceptor — and the data center's **blowdown** is being engineered into that same treatment capacity (#679-24). The keystone documents are committed evidence now, not citations.

## Cross-refs

- [`bosc-prr-production-2026-06-05.response-index.yaml`](bosc-prr-production-2026-06-05.response-index.yaml) — batch 1 (where items 5–15 were deferred)
- [`../../commissioners/bosc-resolution-ledger.yaml`](../../commissioners/bosc-resolution-ledger.yaml) · [`../../commissioners/sanitary-economics.yaml`](../../commissioners/sanitary-economics.yaml)
- [`corpus-completeness-audit.md`](../corpus-completeness-audit.md) §1 — items 5–15 worklist
- [`../../../../docs/COMPUTE.md`](../../../../docs/COMPUTE.md) — the blowdown link ties cooling capacity to sanitary load
