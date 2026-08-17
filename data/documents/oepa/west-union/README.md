# `oepa/west-union/` — Ohio EPA's Buck Canyon file

**Source:** Ohio EPA eDocument public portal · **Pulled:** 2026-08-17 · **32 documents, 133 MB**

Custody, hashes and per-document findings:
[`filename-map.yaml`](filename-map.yaml).

## What is here

Two instrument families, both complete as the portal serves them:

| Family | Permit | Docs | Span |
|---|---|---|---|
| **Level Two Isolated Wetland Permit** | `DSW401252171W` / Ohio EPA ID `252171W` | 28 | application 2025-12-15 → **grant 2026-06-08** |
| **NPDES construction stormwater** | `0GC04922*AG` under general permit `OHC000006` | 4 | **approved 2026-06-08**, expires 2028-04-22 |

## What it settles

**The site map exists, and it prints a number.** `edoc-4147396.pdf` — Kimley-Horn's *Site
Location Map, Buck Canyon, Sprigg Township* — carries **DISTURBED AREA = 535.00 AC** and a drawn
boundary between Ginger Ridge Road, US-52 and the Ohio River. The register listed this document
as `[open]`.

**68 Yards, LLC has a principal and an address.** The granted wetland permit is issued to
**Carrie Tillman, 68 Yards, LLC, 16 N. Green Street, Chicago, IL 60607**. The corpus previously
had the name and nothing else.

**⚠️ The state calls it a light industrial park.** The permit's own project description is
*"Construct a light industrial park."* Adams County's government domain calls the same site an
AWS campus. Both are primary sources; the corpus records the discrepancy and resolves neither.

**Two new parties.** *Kimley-Horn and Associates* is the site civil engineer (Columbus office);
*Walbridge* — via facility contact Tom Cucuz — appears on the NOI as the builder. Ramboll, already
known from the federal file, is the environmental consultant. Three firms, three roles.

**The delineation report is in the state file.** `edoc-3940065.pdf` is the 554-page
*Jurisdictional Waters Delineation Report* the USACE email production named and did not include.
It reached the corpus by a state route rather than a federal one.

## ⚠️ Three cautions

**The two wetland accounts are separate and must never be summed.** This permit authorizes
**0.74 ac of seven ISOLATED wetlands** (B, D, F, H, I, J, K) outside federal jurisdiction. The
USACE NWP 39 verification authorizes **0.06 ac of two JURISDICTIONAL wetlands** (E, G) plus 1,893
linear feet of four streams. Different authorities, non-overlapping ids.

**Two coordinates are on the record.** The NPDES NOI gives **38.651394 / -83.665142**; the USACE
§106 correspondence gives **38.646748 / -83.659828**. About 600 m apart. Both transcribed from
their own source; not reconciled.

**One document is truncated by the agency.** `edoc-3940059.pdf` arrives at exactly 2,097,152
bytes with the server's own `Content-Length` agreeing on every attempt — a valid `%PDF` header, no
`%%EOF`, refused by both pypdf and pdfium. It is kept as received, under chain of custody, as
evidence of the portal defect. **Nothing may be cited from it**, and what it was is unknown.

## The route (and a correction)

The register recorded this portal as **method-blocked** for this site after a 2026-08-05 attempt
whose controls all returned identical default grids. **That is superseded** — see the corrected
section in
[`data/extracted/west-union/data-centers.md`](../../../extracted/west-union/data-centers.md).

Working recipe: ASP.NET WebForms, scrape `__VIEWSTATE` / `__VIEWSTATEGENERATOR` /
`__EVENTVALIDATION`, POST with a cookie jar. Entity Name is
`ctl00$search$KeywordPanel1$txtValue_-1_1_106_1`; **County and Program are plain selects**
(`ddlValue_-1_1_104_1` / `ddlValue_-1_1_109_1`). Results paginate ten at a time via
`ctl00$results$DocHitList$DocHitList_CurrentPageNum` — and note those pager fields exist only on
the results page, so sending them with the initial search returns HTTP 500. Documents fetch at
`ViewDocument.aspx?docid=<n>` with **no `Content-Disposition`**, which is why the docid is the
filename.

## What is not read yet

Shelved, hashed, and unread beyond page 1: the 554-page delineation report, the 196-page SWP3, the
37-page Ramboll technical response, the seven ORAM v5.0 wetland scoring forms, and the mitigation
plan. Only the granted permit is extracted
([`data/extracted/oepa/west-union/252171W.iwp.yaml`](../../../extracted/oepa/west-union/252171W.iwp.yaml)),
and even that stops at page 3 of 9 — the mitigation terms and Part IV notifications are untranscribed.

## Publication status

**Published** (2026-08-17). These files landed inside the already-cleared `oepa` collection and
auto-published on its standing basis, which was then **amended** rather than left to stand: the
`- oepa` entry in [`data/site/published-documents.yaml`](../../../site/published-documents.yaml)
previously asserted the collection carried *"no private PII"*, and this pull breaks that.

⚠️ **The NPDES applicant of record is an individual.** Derek Harmon's home address and personal
telephone are printed on the NOI, the approval letter and the site map. Published knowingly, on
the same footing as the Bowling Green OPSB service-list home address: a permit applicant's contact
block is intrinsic to the instrument, Ohio EPA publishes these exact PDFs itself, and the
documents are load-bearing. Recorded there rather than left to be discovered.
