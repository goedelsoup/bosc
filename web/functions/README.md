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
  — owner-scoped CRUD for reader-authored Stories, backed by **Databricks Lakebase** (managed
  Postgres — the first relational store), reached from the Workers runtime through a Cloudflare
  **Hyperdrive** binding `STORIES_HYPERDRIVE` via postgres.js (`_lib/pg.ts`). The store speaks a
  driver-agnostic `PgLike` slice (`_lib/storiesStore.ts`), so the same SQL runs against Hyperdrive in
  production and pglite (in-memory Postgres) in tests. Schema in [`../migrations/`](../migrations/),
  applied out-of-band to Lakebase (psql / the Databricks SQL editor) in filename order. Writes run the
  server-side write path: compile the source against the build-time `/stories-catalog.json` catalog
  (`_lib/catalogAsset.ts`), validate every handle, and **transactionally** (`db.begin`) upsert the
  Story + replace its refs. Ships dark behind `STORIES_ENABLED`; the Hyperdrive binding is commented
  in `wrangler.toml` until provisioned.
- the **Stories sharing + moderation endpoints** (epic #1090 / #1098): publishing mints an
  unguessable `share_id` and is **early-access-gated** (a `standard` user saves drafts but can't make
  a Story public); `GET api/stories/shared/[shareId]` is the **only unauthenticated read** and serves
  a *published, un-removed* Story's public projection (no owner id / editable source); `POST
  api/stories/report` lets a public visitor flag a shared story (rate-limited + Turnstile-verified
  when `TURNSTILE_SECRET` is set) onto an admin review queue; `api/admin/stories` (admin role only) is
  the queue + takedown/restore. An admin `moderation='removed'` flip takes a story down instantly and
  survives an owner edit; an unpublished/removed story is never reachable by its share URL.
- the **Stories revalidation job** (epic #1090 / #1099): `POST api/admin/stories {action:"revalidate"}`
  (admin, also cron-drivable) walks every Story behind the current `catalog_version`, re-resolves each
  cited handle against the live catalog, **auto-heals** renamed handles via a curated map
  (`src/lib/handleRenames.ts` — rewrites the ref + the stored SDM), and flags the rest `stale` so the
  author is nudged in their account view. Idempotent; the pure core is `src/lib/revalidate.ts` and the
  job is `_lib/revalidateStories.ts`.

## Constraints

- **Workers runtime, not Node.** Use Web platform globals only (`fetch`, `Request`,
  `Response`, `FormData`, `URL`, `crypto.subtle`, `atob`/`btoa`). No `node:` imports.
  The submit/ask/doc endpoints deliberately have **no dependencies** — GitHub App JWTs are
  signed with Web Crypto (`api/_lib/github.ts`), not an SDK. The **one** runtime dependency is
  `postgres` (postgres.js), scoped to the Stories store (`api/_lib/pg.ts`): it's the driver that
  speaks the Postgres wire protocol to Databricks Lakebase over a Cloudflare Hyperdrive socket —
  there's no Web-Crypto substitute for a SQL client. It runs in the Workers runtime via
  `cloudflare:sockets` (auto-detected); nothing else in this tree pulls a package.
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
