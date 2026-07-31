# BOSC PRR — Allen County production batch 3 (2026-07-24)

**As-received:** a USB flash drive (volume "STORE N GO", folder "Sanitary Records 7:24") with five item-numbered folders — `9`, `11`, `13 - See 9`, `14`, `15`. Ingested at [`data/documents/legal/prr-mandamus/prr-production-2026-07-24-sanitary/`](../../documents/legal/prr-mandamus/prr-production-2026-07-24-sanitary/); per-file custody in [`bosc-prr-production-2026-07-24.custody-manifest.yaml`](bosc-prr-production-2026-07-24.custody-manifest.yaml); item-by-item posture in [`bosc-prr-production-2026-07-24.response-index.yaml`](bosc-prr-production-2026-07-24.response-index.yaml).

> Analysis, not legal advice. Dollar totals, resolution numbers, and dates are transcribed from the produced records (high confidence); verify against the originals before quoting in a filing.

## What it is

The **third rolling production** and the first delivered in **native format** — 1,610 files / ~1.04 GB of the Sanitary Engineer's own working files (594 `.doc`, 472 `.pdf`, 69 `.docx`, 34 `.xls`, media, …) with original file-server modification times (2003–2026) and Office authorship metadata intact. Where batch 2 produced an assembled 135-page scan of resolutions, batch 3 produces the **departmental case files** behind five of the Category-B items: the SSO/DFFO enforcement record, the SECAP Phase-1 construction and its OWDA financing, the 2019 SSO reports, the live Shawnee Oaks / Cridersville reroute, and the Hume Road WPCLF application.

The substance is extracted into the instrument layer at [`prr-production-2026-07-24/`](prr-production-2026-07-24/) (the DFFO chain as `order` records, Loan 6718 + Hume Road as `finance` records, the Cridersville agreement + reroute + 2019 SSO reports as corpus artifacts) and folded into the enforcement arc at [`regulatory/wastewater-enforcement-history.yaml`](../regulatory/wastewater-enforcement-history.yaml) (`dffo_chain`).

## The three things that matter

1. **The 25-year SSO-compliance arc, now a single documented chain.** The 2023-02-02 OEPA letter recites it in the agency's own words: the county's **1997** General Plan promised all SSOs eliminated by **2003**; the **2005** DFFO (with a **$49,226** civil penalty) extended that to **2015**; the **2014** Modified DFFO to **2020**; and the county's 2022 request moves Phase-2 completion to **2028** — *"25 years after the original proposal."* The equalization-basin overflow the 2014 order required **eliminated as "temporary"** is the same unit the county now argues *"was always part of the design."* The plant at the end of this chain is the one being expanded to receive the corridor's new load.

2. **Item 9's literal ask was not produced.** Item 9 requested *"every record referencing the 12.6 MGD peak hydraulic capacity figure … not appearing in the … draft NPDES permit or fact sheet for Shawnee II."* A text sweep of all **1,245 machine-readable files** in the production found **zero** referencing that figure — and zero mentioning "BOSC." The produced item-9 tree documents Phase **1** (2008–2016: Loan 6718, the force main, the Ft Amanda pump station, the 2019 SSO reports), not the Phase **2** capacity justification the request targets.

3. **Item 13 reads as a constructive denial.** The county answered item 13 — *all MS Consultants contracts/task orders/invoices/correspondence from 2024-01-01 covering the BOSC pump station & forcemain, the Shawnee II SECAP improvements, and the Hume/Shawnee feasibility study* — with an **empty folder literally named "13 - See 9."** But the item-9 tree is Phase-1-era; the survey found **no** 2024-onward MS Consultants task orders, invoices, or BOSC pump-station/forcemain correspondence in it. The cross-reference points at records that are not there.

## Item-by-item: requested → produced

| Item | Requested | Produced | Posture |
|---|---|---|---|
| **9** | Shawnee II Phase 2 OWDA loan app + capacity justification; **every 12.6 MGD peak record** | Phase-1 SSO/SECAP tree: OWDA Loan **6718** ($15.36M), Ottawa River force main, Ft Amanda PS, 2019 SSO reports | **Partial** — Phase-1 financing produced; the Phase-2 12.6 MGD record was **not** (0/1,245 files) |
| **11** | #113-26 feasibility study incl. **forcemain design MGD**; #136-26 WPCLF app + engineering attachments; any non-residential users | `WPCLF Application.pdf` (Hume Road, $1.76M) — all 11 pages a financial/loan form | **Partial** — application produced; **no** feasibility study, **no** forcemain MGD, **no** engineering attachment (verified across all 11 pages) |
| **13** | All MS Consultants records 2024→ re BOSC PS/forcemain, Shawnee II SECAP, Hume/Shawnee study | Empty "13 - See 9" folder | **Constructive denial** — the referenced item-9 tree contains no 2024→ MS Consultants / BOSC records |
| **14** | OEPA review of the Cridersville agreement; Prosecutor's analysis; **termination** records | 2014 Cridersville treatment agreement + the live 2026 reroute (Buchanan parcel, easements, WPCLF) | **Produced (subject) / partial (form)** — the agreement + its **Section-16 termination mechanism** are here; no standalone OEPA-review or Prosecutor memo identified |
| **15** | 1996 CWA consent decree; DFFOs modifying county obligations; compliance correspondence | The full DFFO chain 2005/2014/2023 + SECAP + SSO closure notices | **Produced** — the state DFFO chain is complete; the 1996 federal decree itself is in-corpus from another source |

## Item 14 — the reroute is the termination

Item 14 asked for records "relating to termination" of the Cridersville agreement. The county produced no formal termination notice — but it produced something more consequential: the **mechanism and its execution**. The 2014 agreement's **Section 16** lets the County terminate *"in its sole discretion"* upon deciding to **build its own wastewater project**. The item-14 tree is that project: the "Shawnee Oaks reroute to Shawnee WWTP" — a new County pump station + force main (Access Engineering, Res #113-26) financed by WPCLF (Res #136-26), assembling the **Buchanan parcel** (0.095 ac, $1,903.57 quitclaim, Res 2026-07-02) and the Ricketts/Burgess/Cridersville easements. The county is exiting the ~$102k/yr Cridersville treatment payment by moving the Shawnee Oaks flow onto its own Shawnee II plant — the same plant at the end of the DFFO chain.

## The money, wired to the enforcement

**OWDA Loan #6718** ($15,364,513, Apr-2014, 20-yr, user-charge-pledged) built Shawnee II SECAP Phase 1 — Ottawa River Force Main ($1.79M), Fort Amanda Pump Station ($2.52M), WWTP improvements ($9.26M). Its RCAP cover letter requests a rate discount expressly because *"the County is under a Findings and Orders to address CSO/SSO's."* The ratepayer side is visible in the Hume Road WPCLF application's own financials: sewer rates **+8.5% (2025), +6% (2026), +3% (2027)** on a system already carrying **$13.8M** of outstanding debt — consistent with the 2011 extension letter's "+64% over six years." The application's FY2024 **ten-largest-users** list carries **no data-center customer**: the campus load is entirely prospective.

## Cross-reconciliation with batch 2

- **#113-26 amount.** Batch 2 established #113-26 = Shawnee Oaks **engineering** (Access Engineering, $161k), correcting the earlier "forcemain feasibility" mislabel. Batch 3's item-14 tree is the project that contract designs — consistent.
- **Hume $1.76M vs $2.0M/$1.6M.** The batch-3 Hume Road WPCLF application requests **$1,760,000**, matching neither the batch-2 grant-authorization figures (#135-26 Hamlet of Hume **$2.0M**; #136-26 unincorporated Shawnee Twp / Shawnee Oaks **$1.6M**). Whether the application is a revised-scope successor to one of those authorizations, or a distinct third project, is unresolved on the produced records. **[open]**
- **Still outstanding after three batches:** the **item-4** cost-benefit (withheld under §9.66(D)); the **12.6 MGD** Phase-2 capacity record (item 9); the **forcemain design MGD** (items 9/11); and the **corridor environmental-permit layer** (NPDES/SWPPP/ESC), which every county body refers to Ohio EPA or the townships (`cross-production-referral-map.yaml`; leads GH-161 / FORCEMAIN-MGD).

## What it changes in the corpus

- The `record` domain gains the enforcement chain + two loans (contract-1.34.0 `enforcement`/`finance` groups).
- The production's only two **archives** are read and closed out. `cap001.zip` and `ConcDr.zip` (both filed under items 9 *and* 15, in the American-Bath Final Change Order Correspondence) hold **20 GPS-stamped video frames — 16 unique — of a 2009-05-13 Cole Street condition survey**, shot ~4 weeks before the claimed work began (2009-06-09). They hid nothing: at item 9 the county produced the same files **expanded and byte-identical** beside the archives, already custody-manifested. So no bytes were committed — only a reviewed, georeferenced frame inventory at [`american-bath-cole-street-condition-survey-2009.yaml`](prr-production-2026-07-24/american-bath-cole-street-condition-survey-2009.yaml), which also carries the Beaverdam Contracting **Claim #1** figures the frames sit beside and one **[open]** item: at the same settled 4 ft trench width, URS's 2010-05-20 letter books aggregate as a **$17,097.60 credit** and its 2010-06-25 memo as a **$29,212.88 charge** — a $46,310.48 swing whose May basis is not in the produced folder.
- The [completeness audit](../legal/corpus-completeness-audit.md) §1 items-5–15 row reflects the batch-3 posture; the item-13 adequacy gap is documented.
- Leads **FORCEMAIN-MGD**, **GH-35**, **GH-161** carry the batch-3 findings; **item 13** is flagged for the constructive-denial follow-up.
