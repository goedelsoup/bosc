# City of Lima PRR — production batches 1–2 (2026-08-22 / 2026-08-24)

The first response from the **City of Lima**, the campaign's fourth agency custodian after the
Allen County Commissioners, the Allen County Sanitary Engineer and the Allen SWCD, and the one the
[corpus-completeness audit](../corpus-completeness-audit.md) had tracked since 2026-07-14 as *"the
un-requested municipal water & wastewater custodian"* ([#1536](https://github.com/watermark-directory/the-watermark-directory/issues/1536)).
Twenty-two files across two batches two days apart.

- **Custody:** [`bosc-prr-production-2026-08-lima.custody-manifest.yaml`](bosc-prr-production-2026-08-lima.custody-manifest.yaml)
- **Item-by-item map:** [`bosc-prr-production-2026-08-lima.response-index.yaml`](bosc-prr-production-2026-08-lima.response-index.yaml)
- **Extractions:** [`prr-production-2026-08-lima/`](prr-production-2026-08-lima/)

## Headline

**Four of eleven items drew responsive records; seven drew nothing, and the City said nothing about
why.** No cover letter, no itemised response, no privilege log, no exemption claim, no statement
that any record does not exist.

The production is strongest exactly where the record was already public — Part B, the ammonia
exceedances Ohio EPA had already noticed — and empty exactly where the City is the sole custodian:
the capacity analysis (C.4), data-center service (C.6), the pretreatment program (D.7–D.9), and the
CSO long-term control plan (E.10). That is an observation about the distribution of what arrived,
not a finding about intent, and it is testable: a follow-up narrowed to those seven items either
produces them or forces an explicit exemption claim.

Two of the twenty-two files are records the request **expressly did not ask for** — the issued
permit and the July 2026 NOV — and both are byte-identical to documents the corpus already held
from Ohio EPA. They were not re-committed; the checksums are recorded in the custody manifest.

## What is genuinely new

### The bench data closes the effluent chain to its source

Six weekly lab workbooks (weeks of 2026-01-18 through 2026-02-22) carry the daily **duplicate
analyses of the final effluent** behind the reported ammonia numbers. This is the corpus's first
primary analytical record for any facility. Everything in it until now was a *reported* value — the
permittee's DMR submission read back out of EPA ECHO.

February reconciles across three independent layers — the City's own lab, the City's self-reported
noncompliance form, and EPA's record:

| Statistic | Recomputed from bench duplicates | EPA ECHO |
|---|---|---|
| February monthly average (n = 20) | 4.0061 mg/l | 4.007 |
| Week 2026-02-01 – 02-07 | 7.5209 mg/l | 7.521 |
| Week 2026-02-08 – 02-14 | 5.2368 mg/l | (City form: 5.2) |

Against permit limits of 1.7 mg/l (30-day average) and 2.6 mg/l (7-day maximum). Sampling is Sunday
through Thursday; the tie-out over exactly those twenty days is itself evidence that no produced
week is missing days.

**Where each figure comes from.** No value in that table is transcribed — each is recomputed from
the daily rows in
[`lima-wwtp-ammonia-benchsheets-2026.lab.yaml`](prr-production-2026-08-lima/lima-wwtp-ammonia-benchsheets-2026.lab.yaml),
whose `daily_mg_l` block carries one row per sample date with both replicate analyses verbatim and
the **workbook each row was read from**. The workbooks have no page numbering — they are
spreadsheets — so the row address is the sample date within the `Ammonia Benchseet` tab of the
named file, and that is what the extraction records:

| Table row | Source rows | Workbook(s) |
|---|---|---|
| February monthly average (n = 20) | all 20 February sample dates | `Ammonium_Results_Week_of_{02_01,02_08,02_15,02_22}_26.xlsx` |
| Week 2026-02-01 – 02-07 (5 days) | 02-01 … 02-05 | `Ammonium_Results_Week_of_02_01_26.xlsx` |
| Week 2026-02-08 – 02-14 (5 days) | 02-08 … 02-12 | `Ammonium_Results_Week_of_02_08_26.xlsx` |

The ECHO column is the committed
[`lima-wwtp-OH0026069.dmr.yaml`](../oepa/lima-wwtp-OH0026069.dmr.yaml) (EPA ECHO effluent chart,
2023-01 – 2026-06). The permit limits are the **winter** ammonia-N limits recorded independently at
[`2PE00000.npdes.yaml`](../oepa/2PE00000.npdes.yaml) — *"ammonia-N summer 2.4 / 1.6 mg/l, winter
2.6 / 1.7 mg/l"* — and they are the same numbers the City printed on its own noncompliance forms.

Two things fall out that the reported record does not carry:

- **ECHO drops a distinct exceedance event.** The City's February form lists *six* exceeded limits
  covering **two separate weekly events** (283 kg/day + 7.5 mg/l, and 270 kg/day + 5.2 mg/l). ECHO's
  monthly rollup reports only the worse week. On this parameter the permittee's self-report is
  finer-grained than the federal record, so counting discrete events from ECHO alone undercounts.
- **Three of the twenty February days carry a failed QC check.** 02-22, 02-23 and 02-24 are flagged
  *"Estimate; matrix spike failed"*, with the workbook comments recording each spike as low, low and
  high. Those estimates are inside the 4.007 mg/l the City reported, and ECHO carries that value
  with no qualifier. They are low-value days, so excluding them would *raise* the average — the
  point is not that the number is wrong, but that a qualifier in the City's lab record does not
  survive into the record everyone downstream reads.

**January does not reconcile, and the gap is specific.** The week of 2026-01-25 has **five**
scheduled sample days under the Sunday–Thursday regime, and four of them carry a numeric result:

| Sample date | Replicates (mg/l) | Mean |
|---|---|---|
| 2026-01-25 (Sun) | 1.169, 1.175 | 1.172 |
| 2026-01-26 (Mon) | 9.379, 9.486 | 9.4325 |
| 2026-01-27 (Tue) | 10.034, 9.894 | 9.964 |
| 2026-01-28 (Wed) | 12.119, 12.162 | 12.1405 |
| 2026-01-29 (Thu) | — row present, analyst initialled, **concentration cell blank** | — |

The blank day is excluded from the denominator, so the week's four numeric rows mean **8.1772 mg/l**
— which does not reproduce ECHO's reported 7.117. 01-30 and 01-31 are a **Friday and a Saturday**:
their absence is the sampling schedule, not a gap in the production. The weeks of 01/04 and 01/11
were not produced at all, so January's reported 2.2413 mg/l monthly average cannot be recomputed
either. If 7.117 is the mean of all five scheduled days, the blank 01-29 result would have to be
2.876 mg/l — arithmetic, not evidence, recorded to make the gap precise.

### The renewal application is a collection-system inventory

The 2022-03-01 application (EPA Forms 1 / 2A / 2S, Application ID 256207483) is the other side of a
permit the corpus has held since July: what the **City** told Ohio EPA about its own works. It
supplies an inventory that exists nowhere else in the corpus — **20 CSO outfalls and 34 constructed
sanitary-relief points**, each with coordinates and receiving water.

**Seventeen of them discharge to Pike Run** (7 CSO outfalls, 10 sanitary-relief points) — the
receiving water of the BOSC campus's 60-inch storm outfall. This is a shared-receiving-water
finding, not a claim that the campus discharges sanitary flow there, and the form reports the
points' existence, not how often they activate. Activation frequency lives in the annual CSO
reports, which were **not** produced.

It also corrects a corpus reading: the permit's *"CSOs reduced to five events per year"* is a
performance cap, and ECHO's five overflow outfalls are the monitoring subset. Neither was ever the
inventory.

Other load-bearing items, each with its caveat:

- **An undated 90%-of-design year.** Annual average daily flow is reported as 13.04 / 13.02 /
  **16.65 MGD** against an 18.5 MGD design. The form does not label its years. Filed 2022-03-01,
  "This Year" most plausibly means 2021 — but that is inference, and the difference decides the
  headroom question: 16.65 leaves ~1.85 MGD, ECHO's 13.07 mean leaves ~5.4 MGD.
- **The City documented an error in its own filed form.** Form 2A reports 60 combined-system lift
  stations; the applicant's free-text note says there is one (Baxter Street) and *"the form keeps
  reverting back to 60."* A general caution about STREAMS filings: read the notes before citing a
  field.
- **The tertiary bypass was used 85 times** in the year before filing, against zero uses of the
  plant and secondary bypasses. No volumes given.
- **No loading increase was sought at renewal**, and no expansion was planned during the permit's
  life. Filed 2022 — before the campus existed on this record.

### The biosolids agreement links the City to the campus's sanitary route

The City ↔ Allen County agreement (executed by the County 2023-12-05; the filename's `6_3_24` is
the *scan* date) has the City processing biosolids from all three County plants — including
**American Bath**, the plant the County's 2.5 MGD "Project Bosc Pump Station and Forcemain" is
designed to feed. $0.08/gal, capped at 3,000,000 gal/yr and 7% solids, with Exhibit A metals
ceilings and a ten-year bar on County termination once the City builds for the County's material.

The caveat matters as much as the finding: this is a **solids** pathway, not a hydraulic one.
Campus wastewater treated at American Bath would not arrive at the Lima WWTP as flow — only the
resulting biosolids would, in proportion to the solids that stream actually generates, which for
cooling-tower blowdown is not the domestic-sewage ratio. Nothing produced quantifies it, and the
3,000,000 gal/yr cap binds regardless of source.

### Ten capacity letters, none for the campus

The acceptance-letter series (2023-08-31 → 2026-06-04, nine signed by Eric Bontrager, P.E.) is the
City's routine capacity-commitment instrument. All ten were read. **None names 4110 N. Cole Street,
Bistrozzi LLC, Google, Project BOSC, a data center, or any large water-cooling user.** The largest
identified user is the Procter and Gamble Reservoir Road expansion.

Read this carefully. It is a negative result about **this production**, not a verified negative
about the world, and three readings stay open:

1. the campus never sought *City* sanitary service — consistent with the County's own forcemain
   routing to American Bath;
2. responsive records exist under an instrument other than an acceptance letter;
3. the production is incomplete.

Because the City asserted no exemption and made no no-records statement, (1) is **not**
established.

Two traps in this series worth naming so they are excluded on the record rather than cited later:

- The 2024-05-29 letter covers a force main on **Bluelick Road and Slabtown Road** — the Cole
  St / Bluelick corridor named in the Lima `SiteProfile`. It is a **2-inch low-pressure force
  main**: residential grinder-pump scale, orders of magnitude below campus service and below the
  County's 2.5 MGD forcemain. The road matches; the infrastructure does not.
- Two letters concern **Harding Highway** parcels (2640, and 2550 as recently as 2026-06-04).
  Neither names a user, a load, or a use. An 8-inch gravity sewer is ordinary commercial service.

One juxtaposition is worth recording without over-reading it: the City's most recent capacity
letter (2026-06-04) asserts the WWTP *"is capable of handling the additional flow"* six weeks before
Ohio EPA issued the NOV finding the same plant in significant noncompliance for ammonia. These are
different questions — hydraulic capacity for added flow versus treatment performance against an
effluent limit — and the letters make no treatment claim. What would turn the juxtaposition into a
contradiction is a capacity analysis reconciling the two. Part C item 4 asked for exactly that, and
none was produced.

## One open discrepancy the production does not resolve

The 2026-07-16 NOV cites effluent limit violations for low-level mercury, E. coli, TSS, dissolved
oxygen, pH-minimum, **CBOD5** and ammonia. Six of the seven appear in the corpus's ECHO exceedance
record for 2023-01 → 2026-06; **CBOD5 appears nowhere in it.** Either the violation predates the
pulled window, ECHO is incomplete, or the NOV's parameter list is over-inclusive. Not resolvable
from what was produced.

## What to ask for next

Narrowed to what this production establishes exists, or leaves provably incomplete:

1. **The missing January bench weeks** (01/04, 01/11) and **the blank 2026-01-29 result** — the one
   datum that would let January's reported weekly maximum be verified.
2. **March 2026 forward** — bench data and any noncompliance report. ECHO shows a March TSS
   exceedance; the request's DMR-correction clause already reaches March.
3. **The City's response to the NOV**, due roughly 2026-08-15 — before both production dates.
4. **The application's own named attachments** — `Lima WWTP Storm Drainage Plan.pdf`,
   `Process Flow Diagram.pdf`, `Labeled Plant Map.jpg`. Their existence is established on the face
   of a produced document, which makes them the hardest items in the request to leave unanswered.
5. **The seven silent items** — C.4, C.6, D.7, D.8, D.9, E.10, and the correspondence halves of A.2
   and F.11 — re-served item by item, so that a non-response has to become either a production or a
   stated exemption.

## Notes on custody

- **`mtime` is not evidence in this production.** Unlike the 2026-07-24 Sanitary Engineer batch (a
  file-server tree off a USB drive, where mtime was the county's last-write time), these arrived as
  electronic-delivery downloads: every file in a batch carries the identical download timestamp.
  Each manifest row instead carries a `document_date` verified from the document's own content.
- **The ten acceptance letters and the biosolids agreement have no text layer.** They are Konica
  Minolta scans, read by OCR and reviewed against the images. Handwriting was not read from script:
  signers are identified from typed name blocks, and the County resolution number on the biosolids
  signature page is recorded as `null` rather than guessed.
- **The corpus was already carrying an internal duplicate.** The checksum pass that matched the
  City's `2PE00000.pdf` also showed that `data/documents/oepa/2PE00000.pdf` and
  `data/documents/oepa/lima/edoc-2363112.pdf` are the same bytes. Both are cited by existing
  extractions and both were left in place; the fact is recorded in the custody manifest.
