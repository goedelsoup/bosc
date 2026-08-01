# Village of Ottawa, OH — site source documents (original records)

**Collection:** `ottawa/` · immutable source evidence

Primary instruments specific to the Ottawa watershed point (Putnam County, Blanchard River)
that are **not** Ohio EPA NPDES permits — those live in [`../oepa/ottawa/`](../oepa/ottawa/).
Raw bytes are never edited; structured reads live in
[`data/extracted/ottawa/`](../../extracted/ottawa/).

## Contents

### `drinking-water/` — the intake side

`2024-CCR.pdf` — the Village's annual **Consumer Confidence Report**, served from the Village's
own DocumentCenter.

⚠️ **The filename is wrong about the year and is kept wrong.** The document's running header on
all six pages reads *"2025 Consumer Confidence Report"*, its title block reads *"2025 Calendar
Year Drinking Water Consumer Confidence Report"*, and it is dated *"Date Distributed: July 1,
2026."* It is the **2025-data-year** report. Only the URL slug says 2024. Per the chain-of-custody
rule the as-received name stands and the content-verified date (`2026-07-01`) is read from the
text layer — see [`drinking-water/filename-map.yaml`](drinking-water/filename-map.yaml). The
2024-data-year CCR is **not** held.

Three public notices are bound into it and are the reason it is in the corpus at all:

| Bound notice | Subject |
|---|---|
| TTHM drinking-water violation | Q4-2025 locational running annual average **83.4 ppb** against the 80 ppb MCL; individual results ranged **37.9–129.4 ppb** |
| Failure to certify lead service-line notification (Template 3b) | The 40 CFR 141.85(e) / 141.90(f)(4) reporting violation, Ohio EPA warning letter 2025-10-21, cured 2026-01-09 |
| UCMR 5 results (2024) | All six regulated PFAS non-detect; lithium and four unregulated PFAS detected |

The report is also itself a corrective instrument: it carries the four corrections Ohio EPA
required by NOV of **2025-11-13** to the preceding CCR.

Structured read:
[`drinking-water/oh6900711-2025-ccr.epa.yaml`](../../extracted/ottawa/drinking-water/oh6900711-2025-ccr.epa.yaml).

### `warn/` — the dislocation side

`RKIndustries.pdf` — the **only ODJFS WARN Act notice filed from Putnam County, Ohio** in the
2024–2026 window, served from the Ohio DAM's `jfs.ohio.gov/warn` tree. RK Industries, Inc. noticed
the expected closure of its automotive production stamping, robotic mig welding and spot welding
operation at **725 N Locust St** on **2024-05-16**, ceasing **2024-07-14**, **~80 employees**, none
represented by a union. ODJFS notice **007-24-042**.

Two handling notes:

- **It is a scan.** Unlike the Findlay WARN pair, this PDF carries no body text layer — `pypdf`
  returns only the receipt stamp `"Received: 5/16/2024 @ 1:18pm"` and nothing from page 2. The
  structured read is a **300 DPI vision transcription**, and says so in its `method`/`dpi` fields.
- **Every headcount in it is handwritten** into a blank the printed document left empty (body 80,
  General Labor 68, TOTAL 80). They agree with each other, with the typed positions (12, so
  68 + 12 = 80) and with the ODJFS index row — but the letter says "approximately," and the
  extraction carries `~80`.

It was found by the #1423 facility-posture sweep, which queried the ODJFS lists record-by-record
looking for a *data-center arrival* and found a *manufacturer's departure*. Structured read:
[`warn/rk-industries-ottawa-2024.warn.yaml`](../../extracted/ottawa/warn/rk-industries-ottawa-2024.warn.yaml);
the register that found it is
[`data-centers.md`](../../extracted/ottawa/data-centers.md).

## Why this collection sits beside `oepa/ottawa/`

The Village of Ottawa draws its drinking water from the Blanchard River and discharges its
treated sewage to the same river about a mile and a half downstream. The instruments for the two sides
are issued under different statutes by different Ohio EPA divisions and are filed here
accordingly — the SDWA side in this collection, the CWA side in `oepa/ottawa/`. The standing
watch that reads them together is
[`data/extracted/ottawa/water-watch.yaml`](../../extracted/ottawa/water-watch.yaml).
