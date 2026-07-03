# `frontend/functions/` — Cloudflare Pages Functions

Server-side endpoints that deploy **alongside** the static Astro build on Cloudflare
Pages (one origin). Cloudflare routes a file here to the matching path —
`api/submit.ts` → `POST /api/submit`. Files/dirs prefixed `_` (e.g. `api/_lib/`) are
**not** routed; they're shared modules.

Two endpoints live here:

- the **submissions endpoint** (`api/submit.ts`, tips/corrections → an inert GitHub
  issue) — contract, abuse model, identity, bootstrap in
  [`docs/submissions-api.md`](../../docs/submissions-api.md);
- the **ask endpoint** (`api/ask.ts`, "Ask the corpus" → a Claude-grounded, cited answer
  over the build-time `ask-index`) — contract, grounding/refusal policy, abuse model, and
  bootstrap in [`docs/ask-api.md`](../../docs/ask-api.md). It calls the Anthropic Messages
  API directly over `fetch` (no SDK) and streams the answer back as SSE.
- the **user-Stories endpoints** (`api/stories.ts` + `api/stories/[id].ts`, epic #1090 / #1095)
  — owner-scoped CRUD for reader-authored Stories, backed by the **D1** binding `STORIES_DB`
  (the first relational binding; schema in [`../migrations/`](../migrations/), applied with
  `wrangler d1 migrations apply STORIES_DB`). Writes run the server-side write path: compile the
  source against the build-time `/stories-catalog.json` catalog (`_lib/catalogAsset.ts`), validate
  every handle, and **transactionally** upsert the Story + replace its refs (`_lib/storiesStore.ts`).
  Ships dark behind `STORIES_ENABLED`; the D1 binding is commented in `wrangler.toml` until provisioned.

## Constraints

- **Workers runtime, not Node.** Use Web platform globals only (`fetch`, `Request`,
  `Response`, `FormData`, `URL`, `crypto.subtle`, `atob`/`btoa`). No `node:` imports.
  The endpoint deliberately has **no dependencies** — GitHub App JWTs are signed with
  Web Crypto (`api/_lib/github.ts`), not an SDK.
- **Typecheck:** `npm run check` runs `tsc -p functions/tsconfig.json` (WebWorker libs).
  This tree is **excluded** from the Astro project's tsconfig so `astro check` doesn't
  typecheck Workers code with DOM/Astro libs.
- **Pure logic is split out** into `api/_lib/` (submit's `schema.ts`/`issue.ts` + the
  window math in `ratelimit.ts`; ask's `retrieval.ts` BM25, `ask.ts` prompt/citation
  assembly, `sse.ts`/`anthropicStream.ts` parsing, and `budget.ts`) so it's testable
  without the runtime. Those modules are unit-tested from `src/lib/*.test.ts` via vitest
  (`npm test`), including the ask faithfulness eval (`askEval*.test.ts`).

## Testing & local dev

Two tiers, both in [`frontend/README.md`](../README.md) → *Local dev & testing*:

- **Automated (offline, in CI):** the route handlers here are driven end-to-end by
  `src/lib/{submit,ask,doc}Route.test.ts` (over `src/lib/_routeHarness.ts`) — a faked `Env`
  + a stubbed `fetch`, so the full path (gates → validate → rate-limit → Turnstile → the
  external call → response) runs under `npm test` with no wrangler, no network, no spend.
- **Interactive:** `mise run //frontend:dev:stack` serves these Functions under
  `wrangler pages dev` with the externals mocked by default (`scripts/dev-mocks.mjs`, the
  `GITHUB_API_BASE` / `ANTHROPIC_API_BASE` seam in `_lib/{github,anthropic}.ts`, dummy
  Turnstile keys, local KV/R2).

## Not live yet

Each endpoint returns `503` until its kill switch is `=true` and its secrets are set in
the Cloudflare project — `SUBMISSIONS_ENABLED` (App id/key, Turnstile secret) for submit;
`ASK_ENABLED` (`ANTHROPIC_API_KEY`, Turnstile secret) for ask. Both frontend pages mirror
this: they render the live form only when `PUBLIC_TURNSTILE_SITE_KEY` is set at build
time, otherwise a disabled placeholder. See the bootstrap in each doc.
