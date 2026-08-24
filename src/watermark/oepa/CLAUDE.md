# CLAUDE.md — `watermark.oepa`

Ohio EPA document acquisition. Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

Three modules, and the order matters: `portal` finds the **state permit number**,
`fetch` turns that number into a committed PDF, `discovery` is the older keyword route.

## The federal→state permit-id gap (why `portal.py` exists)

ECHO knows a facility by its **federal** NPDES id (`OH0021806`) and by name. The DAM
permit URL (`fetch.dam_url`) is keyed by the **Ohio state** permit number (`1PD00011`).
Nothing in ECHO carries that number, so before `portal.py` a site's WWTP permit could only
be found by keyword luck — `oepa discover`'s Serper path returned mostly `MH`/`MP`/`IH`
package plants when every municipal WWTP in the corpus is a `PD`/`PE`-class permit.

**A county × `NPDES` sweep of the eDocument portal *is* the crosswalk**: match an ECHO
facility name against `PortalDoc.entity`, read `PortalDoc.permit_id`, hand it to
`watermark oepa fetch --permit-id`. `watermark oepa portal --site <slug>` does the sweep.

## Portal mechanics that cost real time to learn

`edocpub.epa.ohio.gov` is ASP.NET WebForms — no auth, no rate limit observed — but **five**
of its behaviours fail *silently*, returning a 200 with plausible-looking content. Four are
search-form mechanics and are listed here; the fifth answers a **document** request with an
empty 200 and lives under "Two fetch routes" below. That fifth one is the worst of the family:
the other four produce a wrong *result*, which a reader can notice, while it produces a *file*
that exists and is empty — which reads as successful acquisition.

- **A criterion row's connector must stay `Or` unless that row has a value.** Setting
  `And` on an *empty* row makes the portal discard the whole criteria set and return an
  unfiltered page: a CHAMPAIGN × NPDES sweep came back with Franklin County 401-wetlands
  rows. `_search_form` ands only populated rows; `test_oepa_portal.py` locks this down.
- **The doc-type select cannot be set on the initial search.** `ctl00$search$ddlDocType`
  is postback-activated; sending a real id (`111`) returns **HTTP 500**, and only the
  `-1` all-types default is postable. Doc type is therefore filtered **client-side**
  (`permits_only`), so one cached all-types sweep backs every filtered view.
- **County (`…_104_1`) and Program (`…_109_1`) ARE plain selects**, which is what makes a
  name-independent sweep possible at all.
- **The pager exists only on the results page.** Sending it with the initial search is a
  500. Search first, then page against the *results* ViewState.

## A county sweep is a floor, never an enumeration

The portal caps a single query at **2000 rows**, and its pages **overlap** — a GREENE ×
NPDES walk served 600/600/600/200 rows but only **1665 distinct** docids, so the result
order is not a stable partition. Both facts are reported as `PortalSweep.truncated`
(`_is_truncated`), and the CLI prints `⚠ TRUNCATED` and records a `coverage` block in the
manifest. **Never read a truncated sweep as a county's full record.**

To resolve one facility, search by `entity` instead: the text fields take a bare term as a
*prefix* match and support `*` wildcards, so `entity="*XENIA*"` is the contains-search and
stays far under the cap. The field operator is Equal/Not-Equal only — there is no
"contains" operator, and an exact `"XENIA WWTP"` returns nothing.

## Two fetch routes, and the DAM does not have everything

`fetch.dam_url(permit_id)` is the preferred route — deterministic, and the URL basename is
a real filename. But **a permit number resolved from the portal may have no DAM document
at all**: `1IN00274` (the WPAFB bioslurper NPDES) 404s there while the portal serves it
fine at `ViewDocument.aspx?docid=2090290`. So a 404 from the DAM is *not* evidence the
permit doesn't exist — fall back to `PortalDoc.url`.

All three of that route's hazards are now enforced in `fetch.py` rather than left to the
caller — they were warnings here for a while, and a warning does not survive a 261-document
fetch:

- Portal documents have **no `Content-Disposition`** and no filename in the URL *path* (the
  docid is a query parameter), so the as-received basename was `ViewDocument.aspx` for
  **every** document the portal serves. `_basename` now names them `edoc-<docid>.pdf`,
  matching the hand-curated west-union/urbana trees. Without it a bulk fetch writes one
  file and N-1 `conflict` rows reporting "same name, different bytes" — a false collision,
  since those documents never shared a name.
- At least one docid is served **truncated at exactly 2 MiB** with the server's own
  `Content-Length` agreeing, so neither a short read nor a length check exposes it.
  `_pdf_is_complete` requires the trailing `%%EOF` and the fetch is recorded `truncated`
  **instead of written** — `data/documents/**` is litigation evidence, and a silently
  half-copied PDF is the one outcome it cannot tolerate. A `truncated` row means re-fetch
  and compare, never retry-and-commit.
- **A docid the portal cannot serve is answered with an EMPTY 200, never a 404.** Verified
  2026-08-23 against `docid=4116210`: `HTTP 200`, `Content-Type: text/html`,
  `Content-Length: 0`, no body at all. `_pdf_is_complete` waved that through — its carve-out
  reads "a non-PDF response is left to the callers that already handle it", and
  `b"".startswith(b"%PDF-")` is `False`, so an *empty* body was a non-PDF and no caller
  handled it. The write path then hashed it to the empty-string digest `e3b0c442…`, named it
  `edoc-4116210.pdf` and recorded `downloaded` (#2091). `_refusal` is now the single gate in
  front of the write, with three distinct statuses because the manifest note has to say the
  right thing: **`empty`** (nothing was served — a negative result about the docid, *not* a
  transport failure to retry), **`not_a_document`** (an HTML page under a `.pdf` name), and
  **`truncated`** (a real PDF, cut short). None is hashed or written, and all log at WARNING —
  a bulk fetch reports per-document outcomes only in the manifest, which is read after the
  fact. The PDF magic is tested *before* the content type on purpose: a genuine PDF served
  under a wrong `Content-Type` is still committed, because the bytes decide what a document
  is, not the header.
  A **sweep of the whole corpus on 2026-08-23 came back clean** — 0 zero-byte files among
  4,583 under `data/documents/**`, and all 2,500 `.pdf` files start with `%PDF-`. The defect
  never reached the record; the fix is a guard, not a cleanup. Re-run it after any bulk fetch:
  `find data/documents -type f -size 0` and a `%PDF-` magic check over `*.pdf`.
- Gap-probing a docid range is exactly the workflow that hits this (#2074's "each is
  re-fetchable by docid"), so read an `empty` row as **this docid serves nothing**, and only
  re-fetch after confirming the docid against a portal sweep.

## The results table is variable-shape, and two fields lied about it

Positional reads of a portal row are the recurring defect in this module, twice over
(#2072). Anything read by offset needs a fixture test before it is trusted at volume:

- **The permit-number search field is a decoy.** The criterion row the portal *labels*
  "Package/Permit Number" (`…_121_1`) indexes nothing and answers every query with a
  well-formed empty 200. The permit number lives in **Secondary ID** (`…_111_1`). An empty
  result is indistinguishable from "no such permit", so the crosswalk's targeted lookup
  silently reported every permit as absent (`_DECOY_PERMIT_FIELD`).
- **A program name can contain the row separator.** `RCRA C - HAZARDOUS WASTE` and
  `GRANTS - CLEAN DIESEL` are 2 of the Program select's 45 options. Read as one segment,
  the program eats its own tail and every column right of it shifts left — the county
  landing in `program`, the permit number in `county`. `_read_program` resolves the real
  width first; an unrecognised program still reads as a single segment.

## Fetch discipline

`fetch.py` keeps the corpus's chain-of-custody rules: as-received names, sha256 dedup
(identical bytes → `skipped_existing`), a differing file kept *alongside* under a
`.<sha8>` suffix rather than overwritten, and provenance in `filename-map.yaml`. The
`_REVIEWED_KEYS` on a map entry are human-added and a re-fetch must not erase them.

A refused row (`empty` / `not_a_document` / `truncated`) has **no hash**, so it keys as
`(url, None)` and is retired by a later capture of the same URL under the same rule as an
`error` row — the docid a gap-probe eventually resolves must not leave a permanent row
behind describing a document the corpus does hold.
