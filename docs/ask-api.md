# The ask seam — "Ask the corpus"

The **ask endpoint** lets a visitor ask a natural-language question about the BOSC
record and get a **Claude-generated answer grounded in the extracted corpus, with
citations back to source documents** (Epic [#207](https://github.com/watermark-directory/the-watermark-directory/issues/207)).
The corpus is litigation evidence; the bar is *faithful, cited, and refuses when the
record is silent* — never a confident hallucination.

This document **is the contract**: the request/response schema, the grounding and
refusal policy, the abuse + cost model, and the bootstrap. It mirrors
[`docs/submissions-api.md`](submissions-api.md) and reuses that endpoint's `_lib/` abuse
stack.

> **An answer is a *guide to the record*, never the record.** The endpoint reads only the
> committed content bundle (`watermark export`); it never writes to `data/**`. Answers are
> generated text over retrieved sources and may be incomplete or wrong — every claim
> carries a citation so a reader can verify it against the source. The model is instructed
> to answer **only** from the retrieved sources and to say "I don't find that in the
> record" rather than guess. This mirrors the data-discipline rules in `CLAUDE.md`:
> prefer omission over invention.

## Architecture

The site is hosted on **Cloudflare Pages**; the endpoint is a **Pages Function**
colocated with the static build, so the `/ask` page posts **same-origin** (no CORS) and
the Anthropic key lives as a platform secret, never in the browser. The Python
`ResearchAgent` / `watermark ask` CLI (Agent SDK + in-process corpus tools) stays the
**local/CLI** research path and is *not* wired to the edge.

```
                   ┌─ Cloudflare Pages (one origin) ──────────────────────────┐
  visitor ───────► │  static Astro build  (web/dist)                     │
                   │    └─ /ask-index.json  (build-time BM25 corpus, #209)     │
                   │                                                           │
  /ask question ─► │  POST /api/ask  ──  Pages Function                        │
                   │    1. kill switch + parse/length-cap                      │
                   │    2. per-IP rate limit + daily budget guard (KV)         │
                   │    3. verify Turnstile (server secret)                    │
                   │    4. BM25 top-K over /ask-index.json                     │
                   │    5. empty retrieval ⇒ refuse (no model call)            │
                   │    6. else: grounding prompt → Anthropic Messages API     │
                   │    7. answer + structured citations  (JSON or SSE)        │
                   └───────────────────────────┬───────────────────────────────┘
                                               │  reads the bundle; never writes
                                               ▼
                          /ask page resolves each citation → record/timeline/entity page
```

Retrieval is **keyword/BM25 over the exported bundle** — no embeddings / vector store in
v1. The index (`/ask-index.json`) is emitted at build time over the citation-bearing
feeds (records, timeline, entities, people, places, meetings, concepts, documents); each
unit carries the item's provenance and a deep link to the page it lives on.

## The request contract

`POST /api/ask` with a JSON body. Allowlist-validated server-side
(`web/functions/api/_lib/askSchema.ts`): any field not named here is **rejected**.

| Field | Type | Req. | Notes |
| --- | --- | :---: | --- |
| `question` | string | ✓ | The question. Trimmed; **3–1000 chars** (a Q&A box, not an essay prompt). |
| `turnstile_token` | string | ✓ | Cloudflare Turnstile token. Verified server-side, then discarded. |

Send `Accept: text/event-stream` to receive the answer **streamed** as SSE (below);
otherwise the full answer is returned as one JSON object.

### Response — JSON (non-streaming)

```jsonc
{
  "answer": "The six Tetra Tech OPC estimates total … [1].",  // markdown; [n] cite markers
  "citations": [
    {
      "marker": 1,                                  // the [n] in the answer
      "id": "records:aedg/roundabouts.summary.opc.yaml",
      "feed": "records",
      "title": "Roundabouts OPC — summary",
      "url": "/site/records/opc/",                  // root-absolute deep link (pre-base)
      "source": "data/documents/aedg/PRR-01-bundle.ocr.pdf",
      "page": 318,
      "source_kind": "document",
      "verified": true
    }
  ],
  "refused": false,                                 // true ⇒ "not in the record"
  "model": "claude-opus-4-8",
  "usage": { "input_tokens": 1234, "output_tokens": 210 }
}
```

The `/ask` page resolves each citation's `url` (prefixed with the site base) to the
matching record/timeline/entity/document page, so every cited claim links back to a
verifiable page. Markers the model emits that don't resolve to a returned citation are
**flagged in the UI, not silently dropped**.

### Response — SSE (`Accept: text/event-stream`)

A `text/event-stream` of four event types:

| event | data | when |
| --- | --- | --- |
| `meta` | `{ "searched": n, "candidates": [...] }` | once, **before** any token — the count of records grounding the answer + the *candidate* citations (every retrieved source, numbered in prompt order) |
| `delta` | `{ "text": "…" }` | each token chunk as it arrives |
| `done` | `{ "citations": [...], "refused": bool, "model": "…", "usage": {…} }` | end of stream — the *cited subset* reconciled over the full answer |
| `error` | `{ "error": "…" }` | a mid-stream failure (the answer so far stays rendered) |

`candidates` and the final `citations` share the same per-marker metadata (same
`AskCitation` shape), so a `[n]` the answer uses links identically whether resolved live
or at `done`. The page uses `meta.candidates` to resolve `[n]` markers to links
**incrementally** as tokens stream (#331), shows a "Searching *n* records…" hint from
`meta.searched`, and on `done` re-renders with the cited subset + the "Sources used" list.
A `meta` frame leads **every** stream, including the deterministic empty-retrieval refusal
(`searched: 0`).

### Errors

| Status | Meaning |
| --- | --- |
| `400` | malformed JSON, or the question is missing / too short / too long / has unexpected fields |
| `403` | missing or failed Turnstile verification |
| `429` | per-IP rate limit exceeded (`Retry-After` header) |
| `503` | endpoint disabled (`ASK_ENABLED` ≠ `true`), the daily budget is spent, or fail-closed (no budget KV bound and `ASK_ALLOW_UNCAPPED` ≠ `true`) |
| `500` | misconfigured (no `ANTHROPIC_API_KEY` / `TURNSTILE_SECRET_KEY`) or the index is unavailable |
| `502` | the upstream model call failed |

## Grounding & refusal policy

The system prompt (`web/functions/api/_lib/ask.ts`) holds the model to the
data-discipline rules:

- Answer **only** from the numbered sources injected into the prompt (the BM25 top-K).
  Never use outside knowledge or fill gaps with inference.
- **Cite every factual claim** with the bracketed marker of its source (`[1]`, `[2][3]`).
- If the sources don't contain the answer, reply with exactly **"I don't find that in the
  record."** and cite nothing — silence in the record is a finding, not a gap to fill.
- Quote figures/dates exactly, preserving the `~` approximate marker; no speculation.

Two layers enforce refusal: when **retrieval is empty** the endpoint refuses
deterministically *before any model call* (cheap + certain); when retrieval returns
loosely-matching context, the **model** is relied on to refuse, and that behavior is
guarded by the eval below.

### Faithfulness eval (CI guard)

`web/src/lib/askEval*.test.ts` (set in `askEval.fixtures.ts`):

- **Fixture tier** — deterministic, runs in CI via `npm test`: in-corpus questions must
  surface the right source (grounding); out-of-corpus questions must retrieve nothing
  (→ deterministic refusal); the prompt must instruct strict grounding + the refusal.
- **Live tier** — gated on `ANTHROPIC_API_KEY` (skipped in normal CI): calls the real
  model and asserts grounded answers cite, and **hallucination-bait that does retrieve
  context is still refused**. Run with `ANTHROPIC_API_KEY=… npm test -- askEval.live`.

## Abuse & cost

A public, **paid** LLM endpoint. Controls (reusing submit's `_lib/`):

- **Cloudflare Turnstile** — required on every request, verified server-side. First line.
- **Per-IP rate limit** — a fixed-window KV counter (default **10 / IP / hour**,
  `ASK_RATE_LIMIT_MAX` / `ASK_RATE_LIMIT_WINDOW_SEC`); over-limit → `429` + `Retry-After`.
  **Opt-in and fail-open**: with no `ASK_RATE_LIMIT` KV namespace bound it's off, and a KV
  error allows the request (Turnstile stays the primary gate). A configured `"0"` blocks all.
- **Hard cost guards** — `max_tokens` cap (`ASK_MAX_TOKENS`, default 1024) + the input
  size cap, plus an **account-wide daily output-token budget** (`ASK_DAILY_TOKEN_BUDGET`,
  default 200k; `"0"` = hard stop) counted in a KV namespace (`ASK_BUDGET`, falling back to
  `ASK_RATE_LIMIT` — so it's enforceable independently of per-IP limiting, #587); over budget →
  `503` until the next UTC day. **Fail-closed (#587):** with the endpoint enabled but *no*
  budget KV bound, the paid route returns `503` rather than spend unbounded — set
  `ASK_ALLOW_UNCAPPED="true"` to deliberately run uncapped. Token usage / cost is logged
  per request.
- **Empty-retrieval shortcut** — an off-topic question costs **no** model call.

## Runtime & deploy

- **Function:** `web/functions/api/ask.ts` — a Cloudflare Pages Function routed to
  `/api/ask`. Workers runtime, Web globals only, no SDK/Node deps; the Anthropic Messages
  API is called directly over `fetch`. Pure logic (BM25, prompt/citation assembly, SSE
  parsing, budget) lives in `api/_lib/`.
- **Index:** `/ask-index.json` is emitted by the Astro static endpoint
  `src/pages/ask-index.json.ts` over `src/lib/askIndex.ts`. The Function fetches it as a
  static asset and caches it per isolate.
- **Page:** `web/src/pages/ask.astro` + `src/scripts/ask.ts` — framework-free, in the
  zero-React style of submit. Renders the live form only when `PUBLIC_TURNSTILE_SITE_KEY`
  is set at build time, else a not-yet-live placeholder pointing at browsing the corpus.
- **Build/deploy:** unchanged — `watermark export` → `pnpm run build` → Wrangler uploads
  `web/dist` + `web/functions/` to **Cloudflare Pages** (`pages.yml`). This is
  production; the GitHub Pages deploy was never flipped and Cloudflare supersedes it.

### Environment

| Name | Where | What |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Cloudflare (Function **secret**) | the Anthropic Messages API key ([#124](https://github.com/watermark-directory/the-watermark-directory/issues/124)) |
| `TURNSTILE_SECRET_KEY` | Cloudflare (Function **secret**) | server-side Turnstile verification — **shared** with submit |
| `ASK_ENABLED` | Cloudflare (Function var) | on / kill switch — anything but `true` ⇒ `503` and the form shows disabled |
| `PUBLIC_TURNSTILE_SITE_KEY` | GitHub Actions **build** var (in `pages.yml`) | the Turnstile widget's public site key — read at build time by `ask.astro`; **shared** with submit, so setting it flips both forms live |
| `ASK_MODEL` | Cloudflare (Function var) | model id; default `claude-opus-4-8` |
| `ASK_MAX_TOKENS` | Cloudflare (Function var) | answer-length cap; default `1024` |
| `ASK_TOP_K` | Cloudflare (Function var) | retrieval depth; default `6` |
| `ASK_RATE_LIMIT` | Cloudflare (**KV** binding) | per-IP rate limit (and the budget counter's fallback KV); absent ⇒ per-IP limit off |
| `ASK_RATE_LIMIT_MAX` / `ASK_RATE_LIMIT_WINDOW_SEC` | Cloudflare (Function var) | per-IP window; default `10` / `3600` (`"0"` max = block all) |
| `ASK_BUDGET` | Cloudflare (**KV** binding, optional) | daily-budget counter namespace; falls back to `ASK_RATE_LIMIT` |
| `ASK_DAILY_TOKEN_BUDGET` | Cloudflare (Function var) | account-wide daily output-token cap; default `200000` (`"0"` = hard stop) |
| `ASK_ALLOW_UNCAPPED` | Cloudflare (Function var) | `"true"` lets the enabled endpoint run with **no** budget KV (else it fail-closes to `503`, #587) |
| `ASK_INDEX_URL` | Cloudflare (Function var) | optional override for the ask-index asset URL (sharded/CDN index) |

The non-secret vars and the `ASK_RATE_LIMIT` KV binding are documented (commented) in
[`web/wrangler.toml`](../web/wrangler.toml); secrets and the kill switch are set
in the Cloudflare dashboard, never in `wrangler.toml`.

## Bootstrap (one-time)

Nothing is live until these steps are done: until then the endpoint returns `503`
(`ASK_ENABLED` unset) and the form shows a disabled placeholder. The Cloudflare secrets
can only be set once the Pages project exists (see `docs/submissions-api.md` Phase 1).

1. **Provision the Anthropic key** ([#124](https://github.com/watermark-directory/the-watermark-directory/issues/124)).
   In the Cloudflare Pages project → Settings → environment variables (production), set
   `ANTHROPIC_API_KEY` as a **secret**.
2. **Turnstile** — reuse the submit endpoint's `TURNSTILE_SECRET_KEY` secret +
   `PUBLIC_TURNSTILE_SITE_KEY` build var (they're shared). If submit is already live,
   nothing to do here.
3. **Bind the rate-limit + budget KV — REQUIRED before flipping `ASK_ENABLED` on.** The daily
   budget is **fail-closed (#587)**: an enabled endpoint with no budget KV bound (`ASK_BUDGET`,
   or its `ASK_RATE_LIMIT` fallback) returns `503` rather than spend unbounded. The per-IP rate
   limit stays opt-in (off without `ASK_RATE_LIMIT`). To run the **paid** endpoint deliberately
   uncapped (e.g. a private dry-run) set `ASK_ALLOW_UNCAPPED="true"` — otherwise bind the KV:

   ```sh
   npx wrangler kv namespace create ASK_RATE_LIMIT   # prints the namespace id
   ```

   Uncomment the `[[kv_namespaces]]` block with that id, then redeploy. Override the
   defaults with the `ASK_RATE_LIMIT_*` / `ASK_DAILY_TOKEN_BUDGET` vars if needed.
4. **Flip it on (last step).** Set `ASK_ENABLED=true` (plain var). With
   `PUBLIC_TURNSTILE_SITE_KEY` set at build time, the next build renders the live form.

### Verify

Dry-run with the **Turnstile test keys** first (site key `1x00000000000000000000AA`,
secret `1x0000000000000000000000000000000AA` always pass). With the always-pass secret
set, post a question (JSON form):

```sh
curl -sS -X POST https://<host>/api/ask \
  -H 'content-type: application/json' \
  -d '{"question":"What do the roundabout cost estimates total?","turnstile_token":"dummy"}'
```

Expect `200` with a cited `answer` (and `refused:false`), or `refused:true` +
`"I don't find that in the record."` for an off-topic question. Then swap in the **real**
Turnstile keys.

### Turning it off

Set `ASK_ENABLED` to anything but `true` (the endpoint returns `503`; the form shows the
placeholder on the next build), or unset `ANTHROPIC_API_KEY`.

## Local testing

Two ways to exercise this endpoint locally without spending tokens, both detailed in
[`web/README.md`](../web/README.md) → *Local dev & testing*:

- **Automated:** `src/lib/askRoute.test.ts` drives `onRequestPost` end-to-end — the gates,
  the deterministic no-model refusal, and both the JSON and SSE answer paths (real retrieval
  and real stream parsing) — with a stubbed `fetch`, under `npm test`. No model call.
- **Interactive:** `mise run //web:dev:stack` serves the `/ask` page + endpoint under
  `wrangler pages dev`; the Messages API is mocked (`scripts/dev-mocks.mjs` via
  `ANTHROPIC_API_BASE`, JSON + SSE), so answers stream from a canned response at no cost.

## Status — what's live

| Part | State |
| --- | --- |
| This contract (schema, grounding/refusal policy, abuse + cost model) | **defined** (#216) |
| Retrieval index (`/ask-index.json`, BM25, citation-keyed) | **built** (#209) |
| `/api/ask` Function (retrieve → ground → Anthropic → cite; JSON + SSE) | **built** — dormant until bootstrapped (`ASK_ENABLED`) |
| Abuse + cost controls (Turnstile, per-IP rate limit, token/budget cap) | **built** (#211 — rate limit/budget opt-in via the `ASK_RATE_LIMIT` KV binding) |
| `/ask` page + citation-resolution UI | **built** — disabled placeholder until `PUBLIC_TURNSTILE_SITE_KEY` is set |
| Faithfulness eval (fixture tier in CI; live tier gated) | **built** (#215) |
| `ANTHROPIC_API_KEY` provisioning | depends on [#124](https://github.com/watermark-directory/the-watermark-directory/issues/124) |
| Go-live (`ASK_ENABLED=true` + secrets) | manual bootstrap, above — the last step |
| Embeddings / vector retrieval | **deferred** — keyword/BM25 is the v1 decision |
