# Allen County (Ohio) Board of Elections — committed reference dataset

Publicly available election records for **Allen County, Ohio** (county seat: Lima),
captured for litigation research. Everything here is copied **verbatim** from the
authoritative source named below — no figure is computed, estimated, inferred, or
filled in. Where a value is missing it is left empty, never guessed.

**As-of capture date:** 2026-06-06.

## Authoritative sources

1. **Allen County Board of Elections** — `https://allen.boe.ohio.gov/`
   (the county BOE; mirror at `https://boe.allencountyohio.com/`). 204 N. Main,
   Lima OH 45801-4457, (419) 223-8530. Official results are posted under
   `https://allen.boe.ohio.gov/category/election-results/` and
   `https://allen.boe.ohio.gov/election-reports/`. The result documents themselves
   are hosted as PDFs on the BOE's Dropbox; each PDF's exact download URL is recorded
   in [`source-pdf/SOURCES.txt`](source-pdf/SOURCES.txt).
2. **Ohio Secretary of State** — `https://www.ohiosos.gov/` and the SoS Data Portal
   `https://data.ohiosos.gov/`. Attempted as the canonical machine-readable source
   for county/precinct results and voter-registration counts. **Could not be pulled
   automatically — see Gaps.**

The BOE election reports are produced by **Electionware** (the county's election
management system); the summary reports are the same per-contest canvass the BOE
certifies. PDFs carry a clean embedded text layer, which is what the CSVs below
were parsed from.

## What is here

### `results-csv/` — parsed countywide canvass (machine-readable)

One row per `(election, section, contest, choice)`. Columns:
`election, election_date, section, contest, choice, total, vote_pct, election_day,
absentee, provisional`. `section` is `statistics` (registration/ballots/turnout)
or `contest` (a race or issue). Values are copied verbatim from the source PDF's
text layer; `total` keeps the source thousands-commas (e.g. `33,201`) and `vote_pct`
keeps the printed percent (e.g. `70.87%`). Empty cells = the source printed nothing
in that column for that row (e.g. turnout rows print only a percent).

| file | source PDF | contests | choice rows | stat rows |
|------|-----------|---------:|------------:|----------:|
| [`2024-general-summary.csv`](results-csv/2024-general-summary.csv) | `2024_GEN_SUMMARY_OFFICIAL.pdf` | 20 | 150 | 4 |
| [`2026-primary-summary.csv`](results-csv/2026-primary-summary.csv) | `2026_PRIMARY_SUMMARY_OFFICIAL.pdf` | 103 | 132 | 12 |
| [`2019-general-summary.csv`](results-csv/2019-general-summary.csv) | `G2019_OFFICIAL_SUMMARY.pdf` | 64 | 425 | 4 |

(2026 is a partisan **primary**, so a race appears once per party ballot — e.g.
`Dem For Governor…` and `Rep For Governor…` are separate contest rows. That is the
source structure, not duplication.)

### `registration-turnout.csv` — cross-election statistics block

The 20 `statistics` rows from the three summaries pulled into one file: registered
voters (total, and by party for the 2026 primary), ballots cast (total / by category),
blank ballots, precincts reporting, and total voter turnout. Verbatim from the
summary PDFs. Example values, all as printed:

- 2024 General: Registered Voters - Total **66,201**; Ballots Cast - Total **46,845**;
  Voter Turnout - Total **70.76%**.
- 2026 Primary: Registered Voters - Total **63,151**; Ballots Cast - Total **12,815**;
  Voter Turnout - Total **20.29%**.
- 2019 General: Registered Voters - Total **64,568**; Ballots Cast - Total **12,496**;
  Voter Turnout - Total **19.35%**.

### `source-pdf/` — the official BOE PDFs (primary-source records)

15 PDFs, unaltered bytes, with [`SHA256SUMS.txt`](source-pdf/SHA256SUMS.txt) for
chain-of-custody and [`SOURCES.txt`](source-pdf/SOURCES.txt) for the exact download
URL + any filename normalization. These cover the three elections the BOE currently
posts:

- **2024 General (Nov 5, 2024):** summary, precinct, SOVC (statement of votes cast
  by precinct), most-populous candidate races, most-populous questions/issues, and
  the post-election audit results.
- **2026 Primary / Special (May 5, 2026):** summary, SOVC by precinct, most-populous
  candidate races, most-populous questions/issues.
- **2019 General (Nov 5, 2019):** summary, precinct, SOVC overlaps, audit, and the
  Pandora-Gilboa School Board recount.

### `parse_summary.py`

Regenerates the four CSVs from the summary PDFs' text layer (run `pdftotext -layout`
on the three `*_SUMMARY*.pdf` first into a `txt/` dir, then run this). Kept so the
committed CSVs are reproducible; it copies numbers through verbatim and writes any
line it cannot confidently classify to a sidecar rather than guessing.

## GAPS (what could not be obtained, and why)

- **Ohio Secretary of State machine-readable data — BLOCKED.** Every SoS endpoint
  (`www.ohiosos.gov`, `data.ohiosos.gov` election + voter-registration dashboards,
  and the `www6.ohiosos.gov` ORDS **County Voter Files** FTP download page) returned
  an **HTTP 403 "Website Maintenance" interstitial** to automated requests on
  2026-06-06 — a WAF/bot block, not a real maintenance page. So the following were
  **not** captured here: the SoS statewide-canvass county XLSX files, the
  precinct-level result dashboards, the daily voter-registration snapshots (DATA Act
  archive), and the bulk **county voter file** (the full registered-voter roster with
  party/precinct/history, normally a weekly CSV). These remain available by manual
  browser download from the SoS Data Portal and should be pulled that way.
- **Precinct-level vote counts are only in PDF.** The BOE's `*_PRECINCT*` and `*_SOVC*`
  PDFs hold the per-precinct numbers, but they are large multi-page cross-tab matrices
  (one column per precinct) that do **not** parse cleanly to tabular CSV. They are
  committed here as source PDFs (with text layer) but were **not** flattened to CSV;
  doing so reliably needs per-contest layout handling beyond this pass. The countywide
  totals for every contest ARE in the parsed CSVs.
- **Polling-place / precinct master list — not published as a file.** The BOE site has
  no downloadable polling-location or precinct list; the count "88 precincts" appears
  in the summaries ("Election Day Precincts Reporting 88 of 88") but the precinct
  names/polling addresses are only inside the precinct/SOVC PDFs. The SoS precinct
  dashboard (blocked above) would be the structured source.
- **Voter-lookup / list tools are interactive only.** The county apps
  `https://lookup.boe.ohio.gov/vtrapp/allen/vtrlookup.aspx` (registration lookup),
  `…/vtrreport.aspx` (voter lists & labels), and `…/avreport.aspx` (absentee lists &
  labels) are ASP.NET postback forms (JS-driven, no direct file URL), so no bulk
  data could be pulled from them automatically. Noted, not scraped.
- **Write-in candidate labels in the CSVs may be garbled.** A handful of write-in
  presidential/judicial slate names wrap across lines in the PDF; the text-layer
  reflow occasionally attaches a wrapped name fragment to the adjacent row's label.
  The **vote numbers** for these rows are still correct (and are uniformly 0–6 votes);
  only the long write-in `choice` text may be mis-stitched. Named ballot candidates,
  totals, overvotes/undervotes, and contest totals are clean. Verify any write-in
  label against the source `*_SUMMARY*.pdf` before relying on it.
- **Coverage is limited to the three elections the BOE currently posts** (2019 Gen,
  2024 Gen, 2026 Primary). The BOE archive page does not link a 2025 general, 2022,
  2020, etc.; the BOE's "Past Election Reports" Dropbox folder
  (`https://www.dropbox.com/sh/cmdyyc1cncx62gw/AACf0gH2ydvhsH7f3BusjuNPa`) was not
  enumerated in this pass and may hold older elections.

## Regenerating

Raw downloads are cached (git-ignored) under `data/cache/allen-boe/`. To refresh:
re-download the PDFs from the URLs in `source-pdf/SOURCES.txt`, run
`pdftotext -layout` on the summary PDFs, then `python3 parse_summary.py`.
