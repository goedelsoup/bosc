# CLAUDE.md — `watermark.retrieval`

The in-process RAG layer: chunk the committed corpus, embed it, and serve
cosine-similarity retrieval to the research agent. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md).

- **Four modules.** `ingestion.py` (three iterators → `Chunk`s), `embeddings.py` (pluggable
  embedding providers), `store.py` (`CorpusStore`, the LanceDB wrapper), `__init__.py` (the
  public surface: `Chunk`, `CorpusStore`, `SearchResult`, `EmbeddingProvider`, `get_provider`).
- **Ingestion is three corpus sources, each with stable provenance (`ingestion.py`).**
  `iter_document_chunks` (`data/documents/**`, one chunk per PDF page via the text layer),
  `iter_reference_chunks` (`data/reference/**`, README/CSV/YAML/JSON — CSV rows kept whole),
  `iter_extracted_chunks` (`data/extracted/**` YAML, **site-scoped by the site's
  `effective_corpus_scope`** via the same `relpath_in_scope` predicate the export path uses, so
  a peer whose records live under a collection prefix — `idem/fort-wayne`, `oepa/urbana` — is
  reachable, not just its bare `<site>/` subdir (#1504); Lima indexes the whole tree **minus every
  registered peer's subtree** (#1505), so a peer's slug-scoped record is indexed once, under that
  peer, not double-indexed under Lima). Chunk ids
  are hierarchical (`<kind>::<relpath>::<i>`)
  so re-indexing is deterministic/dedupable; each chunk carries `site`, `collection`, `doc_kind`,
  `source_path`, `page`, and a `provenance` dict. Long text splits on paragraphs at a max width.
- **Embeddings are offline-first and pluggable (`embeddings.py`).** The default provider is
  local `sentence-transformers` (all-MiniLM-L6-v2, 384-dim) — no API key, no network at query
  time (the model downloads once to the HF cache). `get_provider(settings)` is memoized per
  `(provider, model)` so the model loads once per process — this matters because the agent calls
  retrieval on every `retrieve_corpus` tool use. Swap backends behind the `EmbeddingProvider` ABC.
- **The store is LanceDB, rebuilt not committed (`store.py`).** One `corpus` table under the
  git-ignored `data/cache/lancedb/` (regenerable — never committed). `query(text, site=…,
  collection=…, doc_kind=…, limit=…)` embeds the query and returns scored `SearchResult`s
  (score = `1 - distance`), with filters as escaped WHERE clauses. Writes are **rebuild or
  per-site update only** (`rebuild()` drops+recreates; `update_site(slug, chunks)` replaces one
  site's rows) — no partial-row edits.
- **Three vector surfaces — same backend, deliberately different content; don't conflate them.**
  All three embed with the *same* `get_provider` here (all-MiniLM-L6-v2, 384-dim) so they share
  one semantic space and never drift model-to-model — but each indexes a different projection of
  the corpus and serves a different consumer:
  - **this package** (`data/cache/lancedb/`) — the **raw corpus chunks**; backs the in-process
    research agent's `retrieve_corpus` tool (`watermark.agent`).
  - **`watermark.site.embeddings`** (`ask-embeddings` bundle asset) — the **build-time bundle
    feeds**; the canonical index for the **public `/api/ask`** Pages Function
    (`web/functions/api/ask.ts`, [`docs/ask-api.md`](../../../docs/ask-api.md)), which runs BM25
    (± an optional Workers-AI vector upgrade, RRF-merged) over the feeds and refuses
    deterministically when retrieval is empty. **This is the canon for `/ask`; the yidam index
    below is additive and never touches it.**
  - **`watermark.site.yidam_index`** (`.yidam/index/`) — the projected **yidam corpus-mirror
    nodes** (the method-layer graph — entities/relationships/concepts/people/leads/hypotheses/
    `[open]` claims); powers the `yidam_semantic_search` tool served through `yidam serve --mcp`
    (#1564). Built by `watermark corpus-mirror --index` and lazily by the MCP server. Reuses
    this `get_provider`, so it is *reconciled* with the `/ask` embeddings by construction.
- **CLI:** `watermark index` (`cli/retrieval.py`) rebuilds the LanceDB index from all sources
  (`--no-documents`/`--no-reference`/`--no-extracted`, `--collection`, `--site` for a scoped
  update). Tests are hermetic: the sentence-transformers provider is stubbed with deterministic
  vectors against a real LanceDB temp dir — no network, no committed index fixtures.
