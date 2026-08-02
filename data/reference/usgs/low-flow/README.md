# `data/reference/usgs/low-flow/` — the two published USGS low-flow reports for Ohio

Authoritative outside reference (`[reference]`, U.S. Government work, public domain). These are the
two published sources of **low-flow statistics for Ohio streams** — the same statistic
(`7Q10`, `1Q10`, `30Q10`, harmonic mean) the network's own screen derives and Ohio EPA's fact
sheets cite. They are committed as bytes because the network's derived denominators
(`../../hydrology/low-flow-7q10.derived.yaml`) are LP3 fits computed *here*, and a derived value
that has never been read against the published one is unfalsifiable (#1458).

Both are static published documents at permanent USGS URLs, so there is no connector and no
`watermark` regen subcommand: re-fetch is `curl -O <url>` and a sha256 compare against the table
below. Raw bytes only — nothing in this folder is edited, and the CSVs are the publisher's own
files, not a re-export.

## Files

| File | What | Retrieved | sha256 |
|---|---|---|---|
| `wri20014140.pdf` | **Straub, D.E., 2001, Low-Flow Characteristics of Streams in Ohio through Water Year 1997**: U.S. Geological Survey Water-Resources Investigations Report 01-4140 (421 PDF pages), prepared in cooperation with the Ohio Department of Natural Resources, Division of Water. The per-station appendix gives, for each gage, LOCATION / DRAINAGE AREA / TRIBUTARY TO / STREAMFLOW DATA USED / REMARKS plus the magnitude-and-frequency table (1-, 7-, 30-, 90-day minima at the 2/5/10/20/50-yr recurrences) and the harmonic mean. This is where a **published 7Q10 at a named gage** comes from. | 2026-08-02 | `2bde8abe…b45477` |
| `sir20245075.pdf` | **VonIns, B.L., and Koltun, G.F., 2024, Low-flow statistics computed for streamflow gages and methods for estimating selected low-flow statistics for ungaged stream locations in Ohio, water years 1975-2020 (ver. 1.1, October 2024)**: U.S. Geological Survey Scientific Investigations Report 2024-5075, 37 p., prepared in cooperation with the Ohio Water Development Authority and Ohio EPA. Its **table 1** is the load-bearing part for us: one row per gage with site type, drainage area and a published **low-flow regulation status** (`Regulated` / `Unregulated`) — a third-party classification of whether a gage's low flow is anthropogenically altered. | 2026-08-02 | `6051e97f…4ba0f1a` |
| `sir20245075_app1_table1.1.csv` | SIR 2024-5075 appendix 1, table 1.1 — the published duration + low-frequency statistics for the **180 continuous-record** gages, as the publisher's own CSV. | 2026-08-02 | `eee38fc3…770105` |
| `sir20245075_app2_table2.1.csv` | SIR 2024-5075 appendix 2, table 2.1 — the same for the **5 low-flow partial-record** gages. | 2026-08-02 | `0242e929…be9ad3` |

**The publisher prints two different report numbers for the same document — record both, correct
neither.** The publication is **SIR 2024-5075** (that is the pubs.usgs.gov page, the file name, the
suggested citation and DOI `10.3133/sir20245075`), but the **PDF's own cover page** prints
"Scientific Investigations Report 2024–5057", and the headnote of both appendix CSVs points at
`https://doi.org/10.3133/sir20245057`. So a citation to "SIR 2024-5057" and one to "SIR 2024-5075"
are the same instrument. We cite it as **2024-5075** (the publisher's own suggested citation) and
name the discrepancy wherever the bytes are quoted; the files keep their as-served names.

Source URLs (live 2026-08-02):

- <https://pubs.usgs.gov/wri/2001/4140/wri20014140.pdf>
- <https://pubs.usgs.gov/publication/sir20245075> → `sir20245075.pdf`,
  `sir20245075_app1_table1.1.csv`, `sir20245075_app2_table2.1.csv`
- data release: <https://doi.org/10.5066/P92GD1WL>

## What these are used for

The reviewed reads live in `../../hydrology/mainstem-gages.yaml` (per-gage `published:` /
`regulation:` / `cross_check_gages:` blocks, each citing a printed page or a table row here), and
the derivation copies them forward into `../../hydrology/low-flow-7q10.derived.yaml` so a derived
screening denominator is never displayed without the published statistic beside it.

## Gaps + caveats (read before citing)

- **The two reports do not cover the same period and are not interchangeable.** Straub's statistics
  end at **water year 1997**; SIR 2024-5075's analytical period is **water years 1975-2020** and its
  per-gage records are frequently much shorter than that (several Blanchard gages are WY2008-2020).
  A difference between them is at least as likely to be *period* as *method* — never read one as
  correcting the other.
- **A gage's absence here is not evidence about the stream.** SIR 2024-5075 states its inclusion
  rule (≥10 years of flow within WY1975-2020) and, separately, that gages "substantially affected"
  by regulation "were not used to develop the regression equations" — but *regulated gages are
  still listed and still have published statistics* (table 1 carries a `Regulated`/`Unregulated`
  column). So an absent gage is **not** explained by regulation, and the report gives no other
  reason. USGS 04189000 (Blanchard River near Findlay) is absent from table 1, table 1.1 and
  table 2.1 despite a continuous daily record since 1923; the reason is `[open]`.
- **`Regulated` is the authors' own judgment, and they say so**: "Categorizing each gage was not a
  definitive process… it was frequently difficult to determine the magnitude of the effect." Treat
  it as a cited third-party classification, not a measurement.
- **Neither report is a permit determination.** Ohio EPA computes the design low flow **at the
  outfall**, which is a different location from any gage; the binding number for a discharge is in
  that permit's own fact sheet (`../../hydrology/low-flow-7q10.yaml`).
- Straub's per-station tables are read from the PDF's **embedded text layer**, which mangles some
  columns of the flow-duration rows (e.g. `3 . 9 6 . 4` for `3.9  6.4`). The
  magnitude-and-frequency rows we cite were spot-checked against the rendered page image; the
  duration rows are **not** transcribed anywhere and should not be lifted from the text layer.
