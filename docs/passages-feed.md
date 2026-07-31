# The `passages` feed + `search_passages` — design (#1589)

> Spike + feat. Phase 3 of the MCP corpus-retrieval epic (#1579). Status: **implemented** on
> this branch — the `passages` + `passage-embeddings` feeds (`watermark.site.passages` +
> `watermark.site.embeddings`) and the `search_passages` web MCP tool. §3 records the surface
> decision the spike had to make.

## 1. The problem

The public MCP server retrieves at **item level**: a `search_corpus` hit or a `get_document`
fetch returns a whole normalized record (~18–24k tokens). But the answer to "what does the
permit's effluent-limit page actually say?" is one page of one PDF. There was no way to pull
**the exact supporting page with a citation** — especially for PDFs, where one relevant page
should not require the full extracted document.

`search_passages` returns page-cited excerpts:

```text
search_passages(query="total phosphorus effluent limit",
                document_ids=["oepa/2PE00000.pdf"])
   → { document_id: "oepa/2PE00000.pdf", page: 12, text: "… total phosphorus 0.5 mg/L …", score }
```

## 2. What existed today (the reason this is a spike, not a wiring job)

Page-level passage retrieval already existed — but **only on the Python agent side**:
`watermark.retrieval.ingestion.iter_document_chunks` chunks one passage per PDF page →
`sentence-transformers` (all-MiniLM-L6-v2, 384-dim) → a **git-ignored** LanceDB `CorpusStore`
→ the `retrieve_corpus` agent tool. None of that ships to the browser. The web surface's
`ask-embeddings` feed is **row-level** (one vector per bundle record/event/entity), not per
page. So the passage index the web tool needs did not exist in the bundle.

The retrieval machinery the web tool *could* reuse, though, was already symmetric:

| piece | where | note |
|---|---|---|
| corpus embedding | `watermark.site.embeddings` | all-MiniLM-L6-v2, 384-dim, L2-normalised |
| query embedding | `hybridRetrieve.ts` (`@cf/…/all-minilm-l6-v2`) | **same model**, at request time via Workers AI |
| hybrid rank kernel | `retrieval.ts` (`search`/`vectorSearch`/`rrf`) | BM25 + vector RRF, degrades to BM25 |
| response envelope | `mcpGovern.ts` | `{ results, token_estimate, truncated, next_cursor }` |

## 3. The surface decision

The issue posed a fork: **export a passage feed into the bundle**, or **expose the agent-side
`CorpusStore` via a service path**. We chose the **bundle feed**, because:

- Cloudflare Pages Functions are serverless with no persistent store — LanceDB can't run there,
  and the agent index is git-ignored / never deployed. A service path means new always-on origin
  infrastructure, breaking the static-bundle architecture.
- The entire embedding stack is already reusable (same model both sides + the RRF kernel + the
  Workers-AI query embed), so a bundle feed is a small, additive change.
- **Scope is bounded by the public-publish allowlist** (`data/site/published-documents.yaml`,
  #280): the passage index covers only documents whose bytes are already served publicly. That
  same default-deny allowlist that prevents leaking non-published source text *also* keeps the
  feed small — the agent-side full-corpus index would have leaked non-published pages **and**
  blown the size budget.

### Size (why the allowlist scope fits)

The full corpus is ~11,600 PDF pages (~80 MB of embeddings as JSON) — over Cloudflare's 25 MB
per-file limit. The **published** set is the whole OEPA collection + the PRR bundle + a permit:
~2,500 pages across every site → `passages.ndjson` ≈ 6 MB text (committed, ~1.5 MB packed);
`passage-embeddings.ndjson` ≈ 7 MB. Both far under the limit; no sharding needed.

## 4. LFS independence — the committed artifact

The source PDFs are **Git-LFS-tracked**, and the frontend build (CI **and** the Cloudflare Pages
deploy) checks out **without LFS** (`pages.yml`: `# No LFS (intentional)`). So extracting passage
text from the raw PDFs *at export time* would read pointer files and ship an **empty** feed in
production — `search_passages` would be dark. Mirroring how `data/extracted/**` is the committed,
reviewed artifact of the LFS `data/documents/**`, passages are therefore a committed artifact:

- **`watermark passages`** (`watermark.site.passages.extract_published_passages`) extracts every
  published PDF's pages — run **with `git lfs pull`**, out-of-band — into one global committed
  `data/site/passages.ndjson` (documents are corpus-global; the allowlist + exhibit auto-includes
  are resolved exactly as the export does, over the whole tree).
- **The export never re-reads the PDFs.** `_passages_feed` reads `data/site/passages.ndjson` and
  keeps the passages whose document is a *published PDF in this bundle's `documents` feed* — so the
  per-site feed stays scoped to the site **and** the publish allowlist, and the build is
  LFS-independent. Regenerate the artifact whenever the allowlist or the source PDFs change.

## 5. The feeds

Two additive feeds (contract `1.26.0`), built as a post-pass over the assembled `documents` feed:

- **`passages`** — one `PassageItem` per **text-bearing** page of each **published** PDF:
  `{ id: "<document_id>#p<page>", document_id, collection, title, page, section, text }`.
  `document_id` is the `DocumentItem.rel` (the join key to `documents` / `get_document`); `page`
  is 1-indexed; `text` is the pypdf text-layer extraction verbatim. **Image-only pages are
  omitted** (no excerpt to index). `section` is required-but-nullable (matches the web `PassageRow`).
- **`passage-embeddings`** — the all-MiniLM-L6-v2 vector companion (`{ id, embedding }`), the
  passage-level peer of `ask-embeddings`, gated by `--no-embeddings` like it.

Both are **always emitted** (empty when the committed artifact is absent or embeddings are skipped)
via `_retrieval_collection_feed`, whose schema is **row-count-independent** (always the per-row
object schema + NDJSON payload) so the committed schema can't flip between the array and NDJSON
forms as the row count changes — keeping the drift guard deterministic.

## 6. The tool

`search_passages({ query, document_ids?, …governance knobs })` (`searchPassages.ts`) loads the
`passages` feed, optionally filters to `document_ids`, ranks the pool with the shared hybrid
kernel (BM25 + `passage-embeddings` vector RRF, via a `hybridSearch` that now takes an
`embeddingsUrl` override pointing at `/feeds/passage-embeddings.json`), and returns page-cited
hits `{ id, document_id, collection, title, page, section, text, score, citation }` inside the
governed envelope. An over-cap excerpt is trimmed to the room left after its citation — the page
cite is never dropped. Degrades to BM25-only when Workers AI or the embeddings feed is absent.

`citation` is the uniform structured-provenance object every MCP tool now attaches (#1584,
`functions/api/_lib/mcpCitation.ts`). `search_passages` is the **only** tool that populates its
`quote`: the excerpt IS the document's own text layer, so it is genuinely verbatim — and the
quote is a bounded lead excerpt rather than a copy of the whole page, which would double the
response of the one tool that can fill it.

## 7. Honesty / limits

- The excerpt is the **PDF text layer**, not re-OCR — for scanned documents it is garbled
  (per the root CLAUDE.md, never trust its digits). Treat it as a **locator** for the cited page,
  not a transcription; open the page itself with `get_document`. The tool description says so.
- HTML captures in the allowlist are not indexed (PDF pages only); `section` is always `null`
  today (page chunks carry no sub-page heading). Both are additive follow-ups.
- The committed `data/site/passages.ndjson` includes the PRR bundle's whole published set — the
  board-minute and OPC pages **and** the recorded real-estate instruments (pp. 91–295, private
  parties' signatures/addresses). Those are already disclosed public record and served publicly, so
  the artifact re-keys already-public content; the passage set is kept exactly aligned with the
  publish allowlist (no separate per-page curation). Narrowing it (e.g. excluding the instrument
  pages) would be an allowlist-level decision.
