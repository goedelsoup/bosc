# CLAUDE.md — `watermark.civic`

Civic-records subsystem: political-subdivision meeting minutes/agendas, per network site.
Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

**Two sites are ingested today**: Lima (Allen County, the reference build, six bodies flat)
and **Findlay** (Hancock County — the epic-#1520 pilot, #1839: a 32-body registry and two
nested meeting trees, `allen-township` on WordPress and `hancock-county-commissioners` on
CivicPlus). Meeting the peer's real data cost three Lima-locks their fixtures had hidden —
the generic fetcher's date parser, the summarizer's prompt, and the read path's unstated
depth contract. Each is called out below.

- **Registry is the spine, and it resolves per active site.** `registry.py`'s
  `registry_path(settings)` selects the authoritative
  `data/reference/subdivisions/<site>/subdivisions.yaml` for the active site —
  **including peer sites**, which slug-scope under their own `<slug>/` directory. The
  linked flat
  [`data/reference/subdivisions/subdivisions.yaml`](../../../data/reference/subdivisions/)
  is **Lima's legacy registry**: the reference build keeps its flat committed layout so
  the litigation corpus is never relocated (which site owns that layout is decided by
  `watermark.sites.is_reference_site`, not a hardcoded slug). Each registry enumerates
  its own site's meeting-holding bodies and declares its owner in `meta.site`;
  `load_registry` parses it into `Subdivision` models and refuses a registry whose
  `meta.site` disagrees with `settings.site` — no silent cross-site read. Add a body to
  the site's registry, not in code (epic #1520, phase 1 #1521).
- **Grounded vs. discovered — never blur them.** `name`/`type`/`governing_body`/
  `meeting_schedule`/`office` are verbatim from a committed county roster
  (`grounded_from`); `publishing.*` is a live-web finding with its own
  `discovered:` provenance. `platform: unknown` means *not yet looked*, never
  *publishes nothing* — and never fabricate a `records_url`.
- **Discovery reuses the connector cache.** `discovery.py` fetches through the neutral
  `watermark.connectors.cached_get` (connector name `subdivision_discovery`), against civic's
  own `civic_*` cache root + fixtures (`tests/fixtures/civic/`, set via `civic_offline`/
  `civic_fixtures_dir`) — the same offline/fixture discipline as every subsystem's
  connectors, so tests never hit the network. The browser request policy (headers,
  timeout, redirects) has one home, `_http._browser_request`, shared by the cached page
  fetch and the downloader's raw-bytes stream. `classify_platform` / `find_records_links`
  are pure and unit-tested without fixtures.
- **`discover` is read-only.** It prints/exports findings for review; it does not
  rewrite the curated registry. Fold confirmed results into the YAML by hand.
- **Per-platform fetchers dispatch on `Platform`** (`fetchers/`, via
  `fetch_meetings`), each returning a `MeetingDoc` inventory. Pure parse/extract
  functions are unit-tested with fixtures; `fetch` pulls through the shared
  `_http.get_page` cache (each fetcher has its own connector namespace:
  `civicplus`, `subdivision_records`). Unsupported platforms raise
  `FetcherNotImplementedError` (caught by the CLI), never a silent empty.
  - `civicplus` — Agenda Center (Lima, LACRPC, and Hancock County's own board + Fostoria).
    Reads the *index* (recent meetings
    per body across several years); the full archive via `POST UpdateCategoryList`
    per (category, year) is a follow-on. `fetch` logs the doc count so the index
    view is never mistaken for the complete record.
  - `generic` — records-page link scraper for WordPress/Wix/Revize/Squarespace/static bodies
    (and any `unknown` body that still has a `records_url`). Matches document-file
    links, percent-decodes the href, parses dates from the link text/filename, and
    classifies minutes/agenda. A JS-rendered or embedded list yields an honest
    empty result — never a fabricated entry.
    **The date is read from the link text + the file's own BASENAME, never the whole href**
    (`_date_signal`, #1839). A CMS puts bookkeeping in the path: WordPress files everything
    under `/wp-content/uploads/<YYYY>/<MM>/`, and against a body whose filenames are bare US
    dates that prefix wins — Allen Township's `/uploads/2026/05/01-06-2026.pdf` matched
    `05/01-06` and dated a January-2026 meeting to **2006-05-01**, inventing a decade of
    chronology. The upload month is when the clerk uploaded the file, never when the body met.
    `_classify_kind` still reads the whole href (Allen County's `/m######-` convention is
    anchored on the path separator); only the date signal is narrowed.
- **Meeting trees nest per site (`layout.py`, #1520/#1522).** A body slug keys the meeting
  namespace, and where that namespace lives is `meetings_dir(root, body_slug, settings)`: Lima —
  the reference build — keeps the flat legacy `<body>/meetings/` (chain of custody, never
  relocated), and every **peer** nests one level deeper under its **site** slug,
  `<site>/<body>/meetings/`, so the peer's default corpus scope `(slug,)` owns the whole subtree
  for free and Lima's whole-tree-minus-peers scope excludes it (the `<site>` segment is a peer
  prefix). Which site owns the flat layout is `watermark.sites.is_reference_site`, not a hardcoded
  slug (same rule as the registry). **Every write path** (`downloader`/`indexer`/`summarize`/
  `audit` + the CLI) routes both roots (`documents_dir`, `extracted_dir`) through this helper;
  **every read path** funnels through `pipeline.corpus.iter_meeting_artifacts` (two bounded globs
  over the one- and two-segment depths, then `relpath_in_scope`) — timeline, `load_committed_summaries`,
  and the entity fold-in — so a tree lands in **exactly one** site. `retrieval.iter_extracted_chunks`
  and `load_corpus` already `rglob` + scope-gate, so they pick up the nested tree without change.
  **Those two globs are a contract, and it is stated** (#1839): they cover a prefix of exactly
  one or two segments, which is all `meetings_dir` can produce. A tree filed deeper — a peer
  filing under a jurisdiction-prefixed collection, `idem/fort-wayne/<body>/meetings/`, three
  segments — would be **silently invisible**: no error, just a body that never reaches the
  timeline or the bundle. `meetings_dir` now asserts its own output against
  `pipeline.corpus.assert_meeting_layout_depth`, so widening the write layout without widening
  the read globs fails loudly.
- **Fetchers return a `MeetingDoc` inventory, not files.** `downloader.py` is the
  step that pulls the binaries into the body's meeting subtree (raw, LFS, immutable — flat for
  Lima, `<site>/`-nested for a peer, above) and writes a non-destructive **download manifest**
  under the parallel `data/extracted/…/meetings/download-manifest.yaml` (sha256, bytes,
  content-type, source URL, listing-derived date). `watermark subdivisions download
  <slug> [--limit N] [--dry-run]`. Chain of custody: on-disk names are as-received
  (Content-Disposition → URL basename); a differing byte is never overwritten
  (kept beside the original, flagged `conflict`); manifest dates are
  `evidence: listing` — **not** content-verified until the OCR step reads the file.
- **New binary types need LFS.** `.doc/.docx/.xls/.xlsx/.rtf` were added to
  `.gitattributes` alongside the existing `.pdf` (American Twp posts `.docx`).
- **Index → timeline** (`indexer.py` + `keywords.py`; `watermark subdivisions index
  <slug> [--ocr]`). Reads the download manifest, extracts each file's text (PDF text
  layer / DOCX / HTML — the DOCX and HTML readers are `watermark.documents.office`'s, shared with
  the corpus retrieval path since #1757, not a second copy; **`--ocr` also renders + OCRs
  image-only scans** via
  `ocr_pdf`, needs the tesseract binary — without it, or without `--ocr`, image-only
  scans get `text_method: none`, honestly surfaced in `counts`). The OCR text is used
  to scan/verify but is **not persisted** — only `hits` + `char_count` land in the
  index. Confirms the listing date against the file's own text
  (`date_verified` + `date_evidence`; conservative — null when the body doesn't
  restate the date), and scans for corridor topics (`keywords.scan_text`). Writes
  `data/extracted/<slug>/meetings/meeting-index.yaml`. The timeline
  (`pipeline/timeline.py:_subdivision_meeting_events`) surfaces **only** meetings
  whose text names one of the **active site's** corridor subjects as `category:
  subdivision_meeting` (agenda+minutes collapse via a shared `ref`). That vocabulary
  is per-site (#1523): the single source of truth is `SiteProfile.corridor_subjects`
  (Lima's `datacenter`/`bosc`/`bistrozzi`/`google`, Findlay's own
  `datacenter`/`one_power`/`mara_holdings`; **empty for a peer** until it
  declares its own — no `subdivision_meeting` flooding meanwhile), read via
  `active_profile(settings)` and threaded into both the timeline and `summarize`
  (`keywords.is_corridor_relevant(hits, subjects)` takes the vocabulary as an argument, so
  `keywords` stays pure — no module constant, no `pipeline`→`civic` import). Generic township
  topics (rezoning/easement/annexation/solar/...) and ambiguous names (`hume`, `amazon`) stay
  in the index `hits` as searchable corpus but don't flood the chronology. Site picks the
  category up automatically. A new site's terms go in `keywords._TERMS` (the shared scan
  vocabulary) and are then *selected* by that site's `corridor_subjects` — write the pattern
  narrowly enough to survive its own town: Findlay's `mara_holdings` requires the full name
  because a bare `\bmara\b` is a coin-flip against a surname, and MARA Holdings is not
  Marathon Petroleum, which is headquartered there.
- **A hit is not a finding.** `summarize.py` runs the analyze stage over the selected meetings,
  and its prompt is built per site (`build_instructions(county, hits)`, #1839) — the active
  profile's county and *this document's own* hits. It used to be hardcoded to Lima ("an Allen
  County, Ohio township or village … codename Project BOSC / Bistrozzi LLC / a hyperscale data
  center, possibly Google"), and told that, the model read Hancock County minutes and explained
  a pair of Cooperative Economic Development Agreements as being for "a hyperscale data center"
  — a link those minutes never draw. The prompt now also *requires* the model to report a bare
  mention as a bare mention. That guard earns its keep immediately: four of the six
  data-center hits in Hancock County's commissioners record are the county's OWN General Fund
  budget line of that name (an HVAC change order, two intra-fund transfers), and the summaries
  say so.
- **Pipeline complete:** `discover → fetch → download → index → timeline`. The OCR
  pass for image-only scans is now wired (`index --ocr` / `summarize --ocr`,
  tesseract-backed); the commissioners corpus was fully OCR'd this way (991/991,
  #135). Open follow-ons: CivicPlus full-archive year crawl, headless fetch for WAF
  bodies, and folding the OCR text into a committed per-page parquet (the index keeps
  only hits, not text).
