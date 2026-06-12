# `frontend/functions/` — Cloudflare Pages Functions

Server-side endpoints that deploy **alongside** the static Astro build on Cloudflare
Pages (one origin). Cloudflare routes a file here to the matching path —
`api/submit.ts` → `POST /api/submit`. Files/dirs prefixed `_` (e.g. `api/_lib/`) are
**not** routed; they're shared modules.

Today this is just the **submissions endpoint** (tips/corrections → an inert GitHub
issue). The contract, abuse model, identity, and bootstrap are in
[`docs/submissions-api.md`](../../docs/submissions-api.md).

## Constraints

- **Workers runtime, not Node.** Use Web platform globals only (`fetch`, `Request`,
  `Response`, `FormData`, `URL`, `crypto.subtle`, `atob`/`btoa`). No `node:` imports.
  The endpoint deliberately has **no dependencies** — GitHub App JWTs are signed with
  Web Crypto (`api/_lib/github.ts`), not an SDK.
- **Typecheck:** `npm run check` runs `tsc -p functions/tsconfig.json` (WebWorker libs).
  This tree is **excluded** from the Astro project's tsconfig so `astro check` doesn't
  typecheck Workers code with DOM/Astro libs.
- **Pure logic is split out** (`api/_lib/schema.ts`, `api/_lib/issue.ts`, and the window
  math in `api/_lib/ratelimit.ts`) so it's testable without the runtime
  (`node --experimental-strip-types`).

## Not live yet

The endpoint returns `503` until `SUBMISSIONS_ENABLED=true` and the secrets are set in
the Cloudflare project (App id/key, Turnstile secret) — see the bootstrap in the doc.
The frontend form mirrors this: it only renders when `PUBLIC_TURNSTILE_SITE_KEY` is set
at build time, otherwise it shows a disabled placeholder.
