# CLAUDE.md — `bosc.civic`

Civic-records subsystem: Allen County political-subdivision meeting minutes/agendas.
Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

- **Registry is the spine.** The committed, hand-reviewed
  [`data/reference/subdivisions/subdivisions.yaml`](../../../data/reference/subdivisions/)
  enumerates every meeting-holding body. `registry.py` loads it into `Subdivision`
  models. Add a body there, not in code.
- **Grounded vs. discovered — never blur them.** `name`/`type`/`governing_body`/
  `meeting_schedule`/`office` are verbatim from a committed county roster
  (`grounded_from`); `publishing.*` is a live-web finding with its own
  `discovered:` provenance. `platform: unknown` means *not yet looked*, never
  *publishes nothing* — and never fabricate a `records_url`.
- **Discovery reuses the connector cache.** `discovery.py` fetches through
  `bosc.hydrology.connectors._cache.cached_get` (connector name
  `subdivision_discovery`) — the same offline/fixture discipline as the hydrology
  connectors, so tests never hit the network. `classify_platform` /
  `find_records_links` are pure and unit-tested without fixtures.
- **`discover` is read-only.** It prints/exports findings for review; it does not
  rewrite the curated registry. Fold confirmed results into the YAML by hand.
- **Per-platform fetchers dispatch on `Platform`** (`fetchers/`, via
  `fetch_meetings`), each returning a `MeetingDoc` inventory. Pure parse/extract
  functions are unit-tested with fixtures; `fetch` pulls through the shared
  `_http.get_page` cache (each fetcher has its own connector namespace:
  `civicplus`, `subdivision_records`). Unsupported platforms raise
  `FetcherNotImplementedError` (caught by the CLI), never a silent empty.
  - `civicplus` — Agenda Center (Lima, LACRPC). Reads the *index* (recent meetings
    per body across several years); the full archive via `POST UpdateCategoryList`
    per (category, year) is a follow-on. `fetch` logs the doc count so the index
    view is never mistaken for the complete record.
  - `generic` — records-page link scraper for WordPress/Wix/Revize/static bodies
    (and any `unknown` body that still has a `records_url`). Matches document-file
    links, percent-decodes the href, parses dates from the link text/filename, and
    classifies minutes/agenda. A JS-rendered or embedded list yields an honest
    empty result — never a fabricated entry.
- **Fetchers return a `MeetingDoc` inventory, not files.** `downloader.py` is the
  step that pulls the binaries into `data/documents/<slug>/meetings/` (raw, LFS,
  immutable) and writes a non-destructive **download manifest** under
  `data/extracted/<slug>/meetings/download-manifest.yaml` (sha256, bytes,
  content-type, source URL, listing-derived date). `bosc subdivisions download
  <slug> [--limit N] [--dry-run]`. Chain of custody: on-disk names are as-received
  (Content-Disposition → URL basename); a differing byte is never overwritten
  (kept beside the original, flagged `conflict`); manifest dates are
  `evidence: listing` — **not** content-verified until the OCR step reads the file.
- **New binary types need LFS.** `.doc/.docx/.xls/.xlsx/.rtf` were added to
  `.gitattributes` alongside the existing `.pdf` (American Twp posts `.docx`).
- **Index → timeline** (`indexer.py` + `keywords.py`; `bosc subdivisions index
  <slug>`). Reads the download manifest, extracts each file's text (PDF text layer /
  DOCX / HTML — **no OCR**: image-only scans get `text_method: none`, honestly
  surfaced in `counts`), confirms the listing date against the file's own text
  (`date_verified` + `date_evidence`; conservative — null when the body doesn't
  restate the date), and scans for corridor topics (`keywords.scan_text`). Writes
  `data/extracted/<slug>/meetings/meeting-index.yaml`. The timeline
  (`pipeline/timeline.py:_subdivision_meeting_events`) surfaces **only** meetings
  with a corridor `hit` as `category: subdivision_meeting` (agenda+minutes collapse
  via a shared `ref`); the rest stay in the index as searchable corpus. Site picks
  the category up automatically.
- **Pipeline complete:** `discover → fetch → download → index → timeline`. Open
  follow-ons: OCR pass for scanned PDFs (no tesseract dep — e.g. Shawnee's minutes
  are image-only), CivicPlus full-archive year crawl, headless fetch for WAF bodies.
