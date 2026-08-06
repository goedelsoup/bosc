# Grid reliability events (structured reads)

**Collection:** `grid/` · reviewed extractions of
[`data/documents/grid/`](../../documents/grid/)

Structured event and project records for bulk-power-system reliability events and
utility-siting projects relevant to the corridor's power story (Epic #1172; issue
#1476). Each record carries provenance tags (`[verified]` / `[reference]` /
`[inference]` / `[open]`) and cites the source file/page in the mirrored
`data/documents/grid/` collection.

The collection root is **basin-shared** — it reads into Lima's reference build.
Per-site grid records live in a **slug-scoped subdirectory** (`findlay/`), which
is what keeps another watershed point's siting docket out of Lima's Allen-County
record; the subdirectory is named in that site's `SiteProfile.corpus_relpaths`.

## Contents

| File | Event / project |
|---|---|
| [`pjm-202c-emergency-2026.event.yaml`](pjm-202c-emergency-2026.event.yaml) | PJM hot-weather FPA §202(c) emergency (June–July 2026): DOE Orders 202-26-33 (data-center backup-generation dispatch authority) and 202-26-32 (specified-resources dispatch). |
| [`aep-lyka-transmission-2026.project.yaml`](aep-lyka-transmission-2026.project.yaml) | AEP Ohio "Lyka Transmission Project": 345kV substation + ~4mi line, Sugar Creek Township — no OPSB case filed yet (planned "Early 2027"); Google/Bistrozzi customer attribution `[inference]` only. |

### `bowling-green/` — Wood County power instrument (issue #1437)

| File | Subject |
|---|---|
| [`bowling-green/apollo-power-generation-facility.yaml`](bowling-green/apollo-power-generation-facility.yaml) | The **Apollo Power Generation Facility**, OPSB **25-0973-EL-BLN**: 350 MW net behind-the-meter gas generation (21 turbines + 6 reciprocating engines, 491 MW gross derated) plus 119.5 MW / 239 MWh of Tesla Megapack storage, certified by *automatic approval* on the accelerated letter-of-notification track with no public hearings, and barred by Condition 15 from any PJM interconnection. Carries the 34 conditions, the corrected case suffix, and the docket's access-blocked negative. |

The air half of this instrument is **not** here — it mirrors its own source agency at
[`../oepa/bowling-green/`](../oepa/bowling-green/) (permit-to-install P0139272, issued
2026-06-02), and the standing watches at
[`../bowling-green/power-watch.yaml`](../bowling-green/power-watch.yaml).

### `findlay/` — Hancock County grid posture (issue #1464)

| File | Subject |
|---|---|
| [`findlay/rocky-ford-138kv-2024.project.yaml`](findlay/rocky-ford-138kv-2024.project.yaml) | The Rocky Ford 138 kV pair, Cass Township: OPSB **24-0707-EL-BLN** (station, $8.7M) + **24-0706-EL-BNR** (cut-in and tie line, $2.214M), both IPP-reimbursed. A *generation* interconnection for Border Basin I's solar plant (PJM AE1-146), not a load one. Also resolves "Central Findlay" as a jurisdictional negative — 69 kV is below the 100 kV OPSB threshold. |
| [`findlay/aep-dct-tariff-posture.yaml`](findlay/aep-dct-tariff-posture.yaml) | AEP Ohio **Schedule DCT** read verbatim off P.U.C.O. No. 22 Original Sheet Nos. 223-1..223-7, and which terms bite at a >25,000 kW crypto-mining load behind a private transmission-voltage substation. Origin PUCO 24-508-EL-ATA; on appeal as Ohio S.Ct. 2025-1458. |
| [`findlay/megawatt-hub-interconnection.gap.yaml`](findlay/megawatt-hub-interconnection.gap.yaml) | The **+300 MW "standalone interconnection site"**: the claim's provenance (one sentence in a withdrawn Form S-1) and the per-source negative for its instrument, including the Hancock-Wood cooperative re-check. |
| [`findlay/behind-the-meter-generation.yaml`](findlay/behind-the-meter-generation.yaml) | One Power's Hancock County behind-the-meter fleet — 15.0 MW of Wind for Industry at three manufacturers' plants, Whirlpool's Net Zero project, the hub's digital substation — against Schedule DCT's netting and interconnection-agreement obligations. |

### `wilmington/` — Clinton County power instruments (issue #1469)

| File | Subject |
|---|---|
| [`wilmington/clinton-delivery-point.interconnection.yaml`](wilmington/clinton-delivery-point.interconnection.yaml) | **PJM M-3 Need Dayton-2025-002** — AES Ohio's disclosed customer request "in the vicinity of its Clinton Substation near Wilmington, OH", ramping 35 MW (1/2028) to **500 MW** (1/2030), and the $589.8M two-need solution portfolio priced around it. Establishes that the widely repeated **"1.5 GW" is Fayette County's**, not Wilmington's — it is Need Dayton-2025-001 at the Fayette Substation in Jeffersonville, one slide earlier in the same deck. Locates the Clinton Substation on the county parcel record and measures it against the committed corridor geometry. |
| [`wilmington/fayette-clinton-345kv.project.yaml`](wilmington/fayette-clinton-345kv.project.yaml) | The **Fayette to Clinton 345 kV line**, OPSB **25-0871-EL-BLN**, read from the statutory service copy the City of Wilmington published: LON submitted 2026-03-19, ~29 miles single-circuit on double-circuit-capable monopoles, 200-ft ROW. Carries the three conflicting lengths (29 / 30 / 27 mi), the qualitative need statement that names no customer and no megawatt, and the seven intervention petitions of 2026-04-03. |
| [`wilmington/clinton-substation-extension-2021.project.yaml`](wilmington/clinton-substation-extension-2021.project.yaml) | The **retired premise**: the "Clinton 345kV Substation Extension" issue #1469 lists as a data-center instrument is OPSB **21-0679-EL-BNR**, **in service June 2022**, needed for 69 kV reliability and for solar deliverability along the Stuart–Clinton corridor. Recovered from a single Wayback capture after AES unpublished the page. |

The standing watch is at [`../wilmington/power-watch.yaml`](../wilmington/power-watch.yaml),
and the campus register it corrects is
[`../wilmington/data-centers.md`](../wilmington/data-centers.md) §4.

### `van-wert/` — Van Wert County transmission (issue #1408)

| File | Subject |
|---|---|
| [`van-wert/van-wert-haviland-138kv.project.yaml`](van-wert/van-wert-haviland-138kv.project.yaml) | The **Van Wert–Haviland line**, OPSB **25-0697-EL-BLN** (filed 2025-08-25, approved 2025-11-21, unbuilt) read through **26-0729-EL-BLN**, the route-adjustment LON of 2026-07-27. A 10.9-mile 69 kV rebuild as double circuit *designed* at 138 kV and *initially operated at 69 kV*, $45,877,232 recovered through the FERC formula rate and allocated to the AEP Zone. Its Statement of Need names the **Van Wert Mega Site** and counts **30 requests for transmission service** there in the past year; its affected-properties table carries a transmission easement across committed campus parcel `17-034718.0000`. Names no data center, no QTS entity and no megawatt figure. |

**Discipline notes.**

- The PJM 2026 record establishes a `[verified]` region-wide authorization for
  reliability-triggered data-center backup dispatch, but tracks the Bistrozzi
  P0138965 facility's own genset runtime as `[open]` — that facility is
  pre-operational and no facility-level runtime record exists. No runtime hours are
  fabricated (omission over invention).
- The Lyka record establishes AEP Ohio's own project scope/schedule as
  `[verified]` (its own fact sheet), but tracks the Google/Bistrozzi customer
  attribution as `[inference]` only — AEP names no customer in any captured
  material; the identification rests on secondary local press. No customer or
  MW/interconnection figure is fabricated.
- The Findlay set records an **absence per source** rather than a finding. The
  +300 MW is asserted once, by the developer, in a registration statement that
  was withdrawn before it went effective — so it is a disclosed development
  claim, never documented grid capacity, and it stays out of the site's
  `SiteFacility` power basis. Crucially the PUCO route is logged as
  **access-blocked, not empty**: `dis.puc.state.oh.us` returns an
  application-firewall page to automated retrieval, so that docket is unsearched
  and no inference may be drawn from its silence.
- The Bowling Green record likewise **records a blocked route rather than an
  absence**, and for the same host: `dis.puc.state.oh.us` serves an F5/BIG-IP
  JavaScript bot-challenge to automated retrieval, so the Apollo application, the
  ODNR review letter, the data-request responses, the public comments and the
  Board's own approval entry were not obtained and nothing is inferred from their
  silence. The Staff Report itself was captured from a **news organization's
  mirror**, and that custody chain is stated in the capture manifest rather than
  hidden. It also **corrects the case number** that issue #1437, this repo's site
  profile and OPSB's own press release all had wrong — the docket is `-EL-BLN`, the
  letter-of-notification track, not `-EL-BGN`.
- The Van Wert record turns a **blocked route into a served one without pretending
  they are the same thing.** `dis.puc.state.oh.us` refused automated retrieval for a
  fourth time (244-byte "Request Rejected"), so the filings were taken from **the
  applicant's own project site**, which publishes the complete Letter of
  Notification and the statutory public notice. That is a primary instrument — the
  filing itself, with its own cover date and case caption — but it is *the
  applicant's copy*, and it cannot show what the Board did with it, who intervened,
  or what Staff said. Case status stays behind the block and nothing is inferred
  from it. The record also **keeps the two halves of the Mega Site finding
  together**: AEP's own Statement of Need names the site (retiring a press-only
  linkage), and the same 612 pages contain zero occurrences of "QTS" or "data
  center" (so the campus load stays ungrounded and the facility domain stays
  `seeded`). A transmission easement across a campus parcel is a **crossing**, not
  an interconnection, and is recorded as such.
- The Wilmington set **inverts its own issue's central premise and says so in the
  record.** Issue #1469 carried the "1.5 GW" as a Wilmington figure known only
  from press analysis, and asked for the underlying PJM filing. The filing exists
  — PJM's TEAC Dayton Supplemental deck of 2026-07-07 — and it puts the 1.5 GW at
  the **Fayette** Substation in Jeffersonville, **Fayette County**, one slide
  before the Wilmington need, which is **500 MW**. AES Ohio's own project pages
  attach the same 1.5 GW to "the Jeffersonville, Ohio area" in its own words. The
  repo had carried the error on one side of its corpus (`wilmington/`) while
  already holding the right counties on the other (`urbana/`), so the two
  contradicted each other; both are reconciled against the deck and the Urbana
  file's own source attribution is corrected in place. The set also **retires the
  issue's second instrument** — the Clinton substation extension is a completed
  2021-22 reliability-and-solar project, not a data-center one — and keeps the
  guardrail it was given while refining it: Lynchburg remains generation-side
  context, but the existing Clinton–Lynchburg 345 kV line is being *relocated* as
  a priced line item of the customer solution, which is a relation worth stating
  rather than collapsing in either direction. What it does **not** do is close the
  facility domain. Need Dayton-2025-002 names a substation and a city and never a
  customer; the Clinton Substation parcel is 53 m from an Ardent/TAC petitioned
  tract and 1.03 mi from the nearest AWS holding, so the 500 MW is not
  attributable to either campus and the campus IT load stays a screening
  `[inference]` — the Van Wert shape, answered the Van Wert way.
- The Findlay set also **corrects issue #1464's own research notes** where the
  primary text does not support them — the `~$2.2M` is the line project alone
  (the station is $8.7M), the ten wind turbines sit behind Whirlpool's, Ball
  Metal's and Valfilm's meters rather than at the Megawatt Hub, Whirlpool's
  14.4 MW + 6.0 MW is a *Net Zero* project rather than Wind-for-Industry, and
  the OnSite/AEP/Basalt Bloom fuel-cell release mentions neither Findlay nor One
  Power. Corrections are stated in the records, not silently applied.
