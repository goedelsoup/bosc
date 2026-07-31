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

### `findlay/` — Hancock County grid posture (issue #1464)

| File | Subject |
|---|---|
| [`findlay/rocky-ford-138kv-2024.project.yaml`](findlay/rocky-ford-138kv-2024.project.yaml) | The Rocky Ford 138 kV pair, Cass Township: OPSB **24-0707-EL-BLN** (station, $8.7M) + **24-0706-EL-BNR** (cut-in and tie line, $2.214M), both IPP-reimbursed. A *generation* interconnection for Border Basin I's solar plant (PJM AE1-146), not a load one. Also resolves "Central Findlay" as a jurisdictional negative — 69 kV is below the 100 kV OPSB threshold. |
| [`findlay/aep-dct-tariff-posture.yaml`](findlay/aep-dct-tariff-posture.yaml) | AEP Ohio **Schedule DCT** read verbatim off P.U.C.O. No. 22 Original Sheet Nos. 223-1..223-7, and which terms bite at a >25,000 kW crypto-mining load behind a private transmission-voltage substation. Origin PUCO 24-508-EL-ATA; on appeal as Ohio S.Ct. 2025-1458. |
| [`findlay/megawatt-hub-interconnection.gap.yaml`](findlay/megawatt-hub-interconnection.gap.yaml) | The **+300 MW "standalone interconnection site"**: the claim's provenance (one sentence in a withdrawn Form S-1) and the per-source negative for its instrument, including the Hancock-Wood cooperative re-check. |
| [`findlay/behind-the-meter-generation.yaml`](findlay/behind-the-meter-generation.yaml) | One Power's Hancock County behind-the-meter fleet — 15.0 MW of Wind for Industry at three manufacturers' plants, Whirlpool's Net Zero project, the hub's digital substation — against Schedule DCT's netting and interconnection-agreement obligations. |

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
- The Findlay set also **corrects issue #1464's own research notes** where the
  primary text does not support them — the `~$2.2M` is the line project alone
  (the station is $8.7M), the ten wind turbines sit behind Whirlpool's, Ball
  Metal's and Valfilm's meters rather than at the Megawatt Hub, Whirlpool's
  14.4 MW + 6.0 MW is a *Net Zero* project rather than Wind-for-Industry, and
  the OnSite/AEP/Basalt Bloom fuel-cell release mentions neither Findlay nor One
  Power. Corrections are stated in the records, not silently applied.
