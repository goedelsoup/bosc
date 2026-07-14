# Findlay — the flood-mitigation instrument chain

The Hancock County Flood-Risk Reduction Program is the region's defining public-works
program and the anchor of Findlay's **record**, **places**, and **story** domains
(issue #1465, under epic #1265). This file is the human-readable record of the instrument
chain; the two structured record rows it leans on live beside it:

- [`flood/fema-fma-obligation-2026.epa.yaml`](flood/fema-fma-obligation-2026.epa.yaml) — the FEMA FMA $24M obligation `[verified]`
- [`flood/usace-blanchard-review-plan-2024.epa.yaml`](flood/usace-blanchard-review-plan-2024.epa.yaml) — the USACE feasibility Review Plan `[reference]`

Open threads are cross-filed in [`data/site/findlay/leads.yaml`](../../site/findlay/leads.yaml).

## Sourcing discipline (read first)

Chain-of-custody note. Several primary pages refused automated capture: **FEMA.gov**, the
**City of Findlay** newsroom (`News/1818` obligation notice; `News/2009/1375` LOMR notice),
and **wfin.com** all returned HTTP 403; **wtol.com** timed out. Figures attributed to those
pages below are **corroborated across independently-fetched mirrors** (13abc, Spectrum News,
Rep. Latta's release via WKTN) and the project's own site (`hancockcountyflooding.com`, read
directly), but are **not byte-verbatim primary reads**. Where a figure is search-rendered
rather than page-read it is marked `[search-rendered]`. This is high-confidence reporting, not
fabrication — but the FEMA release, the two city notices, and the WFIN bid tabulation should be
re-captured from a non-datacenter IP (or archive.org) to lock the primary text.

The administering district is the **Maumee Watershed Conservancy District (MWCD)** — northwest
Ohio, the Maumee/Lake Erie basin — **not** the *Muskingum* Watershed Conservancy District of
eastern Ohio, which shares the "MWCD" initialism but is a different entity. `[verified]`

## Program spine `[verified]`

- **2016 Memorandum of Agreement** — the Hancock County Commissioners and the Maumee Watershed
  Conservancy District signed an MOA "authorizing the MWCD to identify opportunities for flood
  risk reduction" (`hancockcountyflooding.com/about-us`). The exact 2016 execution date is `[open]`.
- **Engineer of record** — Stantec Consulting Services Inc. (Stantec Project #174316204).
- **Total program value** — ~$160M construction (Stantec project page). The 2018 Benefit-Cost
  Analysis (Jack Faucett Associates for Stantec/MWCD) modeled construction $154,756,000 /
  with-O&M $171,961,000 / NPV $164,981,000, and a **program benefit-cost ratio of 2.94**
  (benefits $484.3M vs costs $165.0M). This local 2.94 BCR is **distinct** from the failed 2015
  USACE federal BCR (below).
- **Local funding** — a **0.25% Hancock County flood-mitigation sales tax**, passed **November
  2009**, which "generated more than $32,000,000 over a ten-year period."
- **State funding** — the Ohio Capital Budget grant totals **$60,000,000** (~$30M received per the
  FAQ; ~$25M remaining per the 2024 year-in-review — a received-vs-remaining framing, not a
  contradiction).
- **Property program** — "acquisition and demolition of **167 flood-prone properties since 2007**"
  (`about-us`).
- **Governance** — MWCD is a 15-county conservancy district organized under ORC Chapter 6101; its
  **Conservancy Court** is composed of the Court of Common Pleas judges of the 15 member counties,
  with the district office in **Defiance, Ohio** (1464 Pinehurst Dr.). That the court formally
  "sits at Defiance C.P." specifically is `[inference]` — sources confirm only the Defiance office
  and the 15-judge composition.

## Funding spine of the current build

| instrument | amount | source of funds | tag |
|---|---|---|---|
| FEMA Flood Mitigation Assistance (FMA) obligation, 2026-04-22 | $24,000,000 (51% of $46.8M eligible) | FEMA (DHS) | `[verified]` |
| Non-federal match | $22,800,000 (49%) | ODNR | `[verified]` |
| — FMA split: Eagle Creek basin | $19,000,000 | (of the $24M) | `[verified]` |
| — FMA split: benching | $5,000,000 | (of the $24M) | `[verified]` |
| Ohio Capital Budget grant | $60,000,000 total | Ohio General Assembly | `[verified]` |
| FRA RAISE grant (NS bridge) | $7,115,711 | USDOT / FRA, awarded to MWCD | `[verified]` |
| County sales tax (0.25%) | >$32M over ten years | Hancock County voters (2009) | `[verified]` |

At the 2026-06-30 bid opening, WFIN reported the "$24,000,000 combined with $20,000,000 remaining
in the State of Ohio grant will provide sufficient funds to execute both contracts."
`[search-rendered]` — the $20M is the *remaining state balance at bid time*, not a second match.

## The four projects

### 1. Phase 1 benching — complete (2024); LOMR submitted `[verified]`

Phase 1 ran the Blanchard River **between Howard Run and the Norfolk Southern railroad bridge**:
floodplain benching near **Swale Park**, **removal of four low-head dams downstream of Lye Creek**,
and instream **riffle construction** at the low-head-dam sites (`about-us`, verbatim "four"; the
LOMR notice says "several"). Completed **2024**.

On **2025-09-18** the City of Findlay, the Hancock County Commissioners, and **Stantec** submitted
a **Letter of Map Revision (LOMR)** to FEMA on the completed Phase 1 work (`findlayohio.gov`
`News/2009/1375`, 403; search-rendered):

- **375 parcels (~15 acres) completely removed** from FEMA's Special Flood Hazard Area (SFHA).
- **985 parcels (~67 acres) remain in the SFHA but with a reduced 100-year water-surface elevation.**
- FEMA review → a Letter of Final Determination makes the changes official; "expected to take
  6 months." No effective date set as of submission `[open]`.

The Phase 1 **construction contractor and price are `[open]`** — not disclosed in any reachable
source. (Do **not** attribute the "$2.56 million" figure to Phase 1: that belongs to the U.S. 68 /
SR 15 roundabout, an ODOT-administered project.)

### 2. Phase 2 downtown benching — bid 2026-06-30, award pending `[verified]`

The soil-remediation precursor ran **December 2025 – February 2026**, implemented by **CEC (Civil &
Environmental Consultants Inc.)** and **Buckeye Elm Contracting**. It removed soil contaminated with
**lead, arsenic, mercury, cadmium, and PAHs** from historic industrial use — "approximately 7,325
tons of impacted soil, 1,070 tons of glass fill material, and 432 tons of asphalt," disposed at the
Hancock County Landfill (`wfin.com`, 403; search-rendered). A contract dollar value for the
remediation is `[open]`.

The main Phase 2 (Additional Hydraulic Improvements) contract **bid 2026-06-30** `[search-rendered]`:

| bidder | bid | note |
|---|---|---|
| Helms & Sons | $3,699,040 | apparent low |
| Eagle Bridge | $3,912,345 | |
| Fenson | $3,989,515 | |
| (engineer's estimate) | $6,170,000 | |

### 3. Eagle Creek Dry Storage Basin — bid 2026-06-30, award pending `[verified]`

An **~765-acre** dry-storage impoundment within the dam alignment, bounded by **Township Road 76 to
the west and US-68 to the east**, in **Eagle Township ~4 miles south of downtown Findlay**
(`hancockcountyflooding.com/eagle-creek-dry-storage`, read direct). Final Design complete; **property
acquisition complete** (easements/permits in progress); the **ODNR Division of Water Resources Dam
Safety Program construction permit is in hand** (permit number `[open]`). Modeled effect: a
**~2,550 CFS (16%) peak-flow reduction** on the Blanchard River during the 1% ACE event, **~2.2 ft of
base-flood-elevation lowering** near the Blanchard/Eagle Creek confluence downtown, and **~1,830
parcels / 1,400 acres out of the regulatory floodplain**. Ohio Capital Budget grants of $60M are
cited on this page; annual O&M ~$100k–$150k; construction 18–24 months, potential start late 2026.

The construction contract **bid 2026-06-30** `[search-rendered]`:

| bidder | bid | note |
|---|---|---|
| Miller Brothers Construction | $32,075,000 | apparent low |
| Beaver Excavating | $33,107,304 | |
| RD Jones Excavating | $36,591,992 | |
| (engineer's estimate) | $42,376,000 | |

### 4. Norfolk Southern bridge replacement `[verified]`

Replacing a >100-year-old NS bridge, **widening the span from 150 ft to 300 ft** to pass flood flow;
"expected to lower flood levels by 0.3 ft at Main Street in a 100-year storm event"
(`hancockcountyflooding.com/norfolk-southern-railroad`, read direct; Sen. Brown's release states
"0.4 feet immediately upstream" — a different location/metric). Estimated total **~$16.7M**
(page reads "$16,700,00" — a dropped trailing zero). Funding: the **$7,115,711 FRA RAISE grant** to
MWCD (Sen. Brown release), **$5M** from the county 0.25% sales tax, and the City "makes up the
difference" (**~$4.6M**, arithmetically $16.7M − $7.1M − $5.0M, not separately quoted `[inference]`).
The **~$2M bench under the span** uses FEMA funds and "will not be bid until the NS bridge
construction is nearly complete."

## Watch item — the 2026-07-14 votes (award NOT yet reported)

As of ingest (**2026-07-14**), **neither vote had a published outcome**:

- The **MWCD Board of Directors** was to consider award recommendations for both cornerstone
  contracts (Eagle Creek + Phase 2 benching) at its **9:00 a.m., 2026-07-14 meeting in Defiance**.
  Miller Brothers and Helms & Sons are **apparent low bidders only** — an award is `[open]`.
- The **Norfolk Southern** bid opening was **extended to 2026-07-14 at NS headquarters in Atlanta**;
  outcome `[open]`.

These are cross-filed as a time-sensitive lead (`AWARD-2026-07-14`). Do not upgrade "apparent low"
to "awarded" without the board minutes.

## The assessment question — RESOLVED: method not finalized `[verified] → [open]`

How the Eagle Creek basin's O&M is funded — and specifically **whether MWCD levies a Blanchard-
subdistrict assessment on landowners** — is answered on the record by the program FAQ, verbatim:

> "The annual operation and maintenance expenses are estimated at $100,000. The method for covering
> this expense has yet to be finalized but may include funding through grants, the City of Findlay,
> the County, or assessments."

So: **an assessment is one of four listed possibilities, not an enacted instrument.** No source —
FAQ, `maumeewatershed.com`, or any reachable conservancy-court record — states that a Blanchard
subdistrict assessment has been levied. The question stays `[open]` (method pending), now with a
citation. The 2018 BCA models storage-basin O&M at $75,000/yr for Eagle Creek specifically.

**Disambiguation.** The Hancock County "**Proposed Assessments — Revised 11-4-24**" document is the
**Howard Run petition ditch** — an ORC Chapter 6131 county ditch improvement administered by the
**Board of Commissioners** (petitioned 2019-06-27, approved at the final hearing **2025-01-16**),
**not** an MWCD flood-program assessment. Same ORC-chapter family, different instrument, different
body. Do **not** cite Howard Run as the flood-program O&M mechanism. `[verified]`

## Conservancy-court plan amendment — located (July 2021) `[inference]`

In **July 2021** the MWCD Conservancy Court (the 15 counties' Common Pleas judges) voted to **add the
Eagle Creek Floodwater Storage Basin to the District's official plan**, after a **May 2021** meeting
at which the panel voted to table it. The exact July 2021 date and wording are **secondary/search-
corroborated**, not verbatim from a retrieved primary article (WTOL timed out; WFIN 403; The Courier
paywalled). A **case/record number is `[open]`.** Cross-filed as a records-request lead
(`CONSERVANCY-COURT-2021`).

## Eminent domain — located, unresolved `[open]`

The eminent-domain-firm writeup (Sever Walker Padgitt) describes **"two private property owners"**
contesting a taking for the flood-control basins on grounds that MWCD **"did not have the right to
take the land and did not follow eminent domain procedures according to Ohio state law"**, with "the
district court case … not yet … resolved." The Courier frames the dispute as "whether the Maumee
Watershed Conservancy District has the authority to proceed with the project without further approval
of the court." **Landowner names, case number, court/docket, and filing date are all `[open]`**, and
the writeup references an older "three large basins" plan and never names Eagle Creek specifically —
so even the identification with the Eagle Creek appropriation is `[inference]`. Local reporting
separately indicates ~700 acres for the basin were largely assembled by purchase, with ~100 acres
still under negotiation. Cross-filed as `EMINENT-DOMAIN-DOCKETS`.

## USACE federal thread `[reference]` / `[open]`

The Corps' 2015 recommended plan, the **Western Diversion of Eagle Creek**, "was deemed unlikely to
meet Federal funding requirements because of its negative cost benefit ratio and low community
support" (FAQ, verbatim). The numeric 2015 BCR is **not public** in any reachable source `[open]`.
A USACE LRD **Review Plan for a Blanchard River Watershed feasibility study was published 2024-01-11**
(structured in [`flood/usace-blanchard-review-plan-2024.epa.yaml`](flood/usace-blanchard-review-plan-2024.epa.yaml));
whether it signals a renewed federal effort or is archival is `[inference]`/`[open]` (cross-filed
`USACE-2024-REVIEW`). Keep the failed federal 2015 BCR separate from the local program's 2.94 BCR.

## Discrepancies preserved (do not silently reconcile)

- **Floodway vs floodplain.** FEMA release: "1,290 parcels / 1,500 acres from the regulatory
  **floodway**." Basin project page: "~1,830 parcels / 1,400 acres from the regulatory
  **floodplain**." LOMR notice: 375 removed / 985 reduced from the **SFHA**. Three different
  accountings — kept distinct.
- **Nov-2024 vs Apr-2026.** The November-2024 conditional-approval reporting is a *different event*
  from the 2026-04-22 final obligation; do not merge its figures.
- **State-money framing.** ODNR match "$22.8M" (total) vs WFIN's "$20M remaining in the State of
  Ohio grant" (balance at bid time) — different things.
- **O&M figures.** FAQ "$100,000"/yr vs the 2018 BCA's $155k–$172.7k/yr (which include the unbuilt
  Potato Run and Blanchard River basins) — the sources do not reconcile these explicitly.

## The network tie

Downstream relief at **Ottawa** is entirely upstream-derived: the committed one-river control
[`data/reference/network/findlay-ottawa-comparison.yaml`](../../reference/network/findlay-ottawa-comparison.yaml)
takes its infrastructure arc from this chain, and the Eagle Creek basin sits on the same tributary as
profile gage **04188496** upstream of the WPCC-relevant reach. Post-construction, the low-flow/flood
regime the receiving-water screens cite may shift — flagged for the hydrology sub-issue (#1458) as
`[inference]`.
