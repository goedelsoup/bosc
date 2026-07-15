# CLAUDE.md — `watermark.civic`

Civic-records subsystem: Allen County political-subdivision meeting minutes/agendas.
Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

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
  content-type, source URL, listing-derived date). `watermark subdivisions download
  <slug> [--limit N] [--dry-run]`. Chain of custody: on-disk names are as-received
  (Content-Disposition → URL basename); a differing byte is never overwritten
  (kept beside the original, flagged `conflict`); manifest dates are
  `evidence: listing` — **not** content-verified until the OCR step reads the file.
- **New binary types need LFS.** `.doc/.docx/.xls/.xlsx/.rtf` were added to
  `.gitattributes` alongside the existing `.pdf` (American Twp posts `.docx`).
- **Index → timeline** (`indexer.py` + `keywords.py`; `watermark subdivisions index
  <slug> [--ocr]`). Reads the download manifest, extracts each file's text (PDF text
  layer / DOCX / HTML; **`--ocr` also renders + OCRs image-only scans** via
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
  (Lima's `datacenter`/`bosc`/`bistrozzi`/`google`; **empty for a peer** until it
  declares its own — no `subdivision_meeting` flooding meanwhile), read via
  `active_profile(settings)` and threaded into both the timeline and `summarize`
  (`keywords.is_corridor_relevant(hits, subjects)` takes the vocabulary as an argument, so
  `keywords` stays pure — no module constant, no `pipeline`→`civic` import). Generic township
  topics (rezoning/easement/annexation/solar/...) and ambiguous names (`hume`, `amazon`) stay
  in the index `hits` as searchable corpus but don't flood the chronology. Site picks the
  category up automatically.
- **Pipeline complete:** `discover → fetch → download → index → timeline`. The OCR
  pass for image-only scans is now wired (`index --ocr` / `summarize --ocr`,
  tesseract-backed); the commissioners corpus was fully OCR'd this way (991/991,
  #135). Open follow-ons: CivicPlus full-archive year crawl, headless fetch for WAF
  bodies, and folding the OCR text into a committed per-page parquet (the index keeps
  only hits, not text).
