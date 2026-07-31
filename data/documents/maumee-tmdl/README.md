# Maumee Watershed Nutrient TMDL (original records)

**Collection:** `maumee-tmdl/` · immutable source evidence

The Ohio EPA **Maumee Watershed Nutrient TMDL** (Total Maximum Daily Load) report,
its nine final appendices, fact sheet, and responsiveness summary, plus the US EPA
federal approval / decision package. The receiving-water / nutrient-loading
authority behind the hydrology axis's assimilative-capacity reasoning. Raw bytes
are never edited.

## Source & provenance

Retrieved 2026-06-06 via curl. Two source groupings (full per-file detail and
content-verified dates in [`MANIFEST.yaml`](MANIFEST.yaml)):

- **US EPA** (`epa.gov`) — the federal approval / decision package (transmittal
  letter, decision document, attachments).
- **Ohio EPA** (`epa.ohio.gov`) — the TMDL report, Appendices 1–9, fact sheet,
  FAQs, and the official-draft responsiveness summary.

## Biennial reporting

`2024_Maumee_Biennial_Report_Final_clean.pdf` — the **Maumee Watershed Nutrient TMDL Biennial
Report, December 2024**, added 2026-07-31 (issue 1460; provenance in
[`filename-map.yaml`](filename-map.yaml)). It is the TMDL's own progress record, and pp. 13-14
publish the first reported season of the phosphorus general permit `OHP000001`: 39 facilities, a
Cumulative Load Limit of **64,170 kg-TP** for March-July 2024 (including a 1,400 kg allowance for
future growth) against a reported Cumulative Load of **43,304 kg-TP** — 20,866 kg of headroom.

That group figure is what determines whether any *individual* over-allocation plant is in violation,
so it is the number to track alongside Appendix 4's per-facility allocations. The report publishes
**only** the group total, not per-facility 2024 loads; Appendix 4's per-facility series stops at
2021.

## Caveats

- `content_verified_date` is drawn only from each document's own text layer; years
  appearing solely as bibliographic citations are **not** treated as the document's
  date. Every file was verified to begin with the `%PDF-` magic bytes.
- Appendix 4 (Individual NPDES Wasteload Allocations) overlaps the
  [ECHO NPDES inventory](../../reference/echo/README.md); cross-check rather than
  assume agreement.
