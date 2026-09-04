# Source-document object store (R2)

> **The corpus bytes are also in a yidam artifact vault** (epic #2141). This file documents the
> **rel-keyed** store the `/api/doc` Function streams; the content-addressed vault that replaces
> Git-LFS, and the `watermark documents hydrate` dev loop for getting bytes back into a working
> tree, are in [artifact-vault.md](artifact-vault.md).

The corpus under `data/documents/**` is ~5 GB across ~1,600 files — too large to commit
to the static build, but the new site needs to **serve the real bytes** so a reader can
open the actual deed, permit, or plan (epic #274). The store that holds those bytes is
**Cloudflare R2** (S3-compatible), bound to the same Pages deploy as the existing
`/api/submit` and `/api/ask` Functions.

This file is the runbook: how the store is provisioned, how the bytes get there, and how
the dev loop works. The pieces:

- **R2 bucket** — `watermark-documents` (prod) + `watermark-documents-dev` (preview/dev). Bound as
  `DOCS` in [`web/wrangler.toml`](../web/wrangler.toml). *(B1 / #277.)*
- **`watermark objectstore sync`** — uploads `data/documents/**` into a bucket, incrementally
  and LFS-aware. *(B3 / #279.)*
- **`/api/doc/<rel>` Pages Function** — streams a file from R2 and enforces the public
  publish allowlist server-side. *(B2 / #278 — pairs with the C1 allowlist.)*

## Exposure model (default-deny in public)

The object store serves **every** file in dev/preview so the viewer works on the whole
corpus. The **public** site stays a default-deny allowlist
(`data/site/published-documents.yaml`, C1 / #280), expanded only after a redaction/PII
pass (C2 / #281). Chain of custody holds throughout: the sync tool only *reads* source
bytes — it never alters, renames, or copies one into a mutable tree.

## One-time provisioning

### 1. Create the buckets

```sh
npx wrangler r2 bucket create watermark-documents
npx wrangler r2 bucket create watermark-documents-dev
```

The binding is already declared in `web/wrangler.toml`:

```toml
[[r2_buckets]]
binding = "DOCS"
bucket_name = "watermark-documents"
preview_bucket_name = "watermark-documents-dev"
```

### 2. S3 API token (for the sync tool)

`watermark objectstore sync` talks to R2 over its **S3-compatible API**. In the Cloudflare
dashboard (R2 → Manage R2 API Tokens) create a token with object read/write on the
buckets, and note the **Access Key ID**, **Secret Access Key**, and your **account id**.

**The key and the secret are secrets; the account id is not.** The two credentials live in
the environment and never in `wrangler.toml` or git. The **account id is an identifier** —
it appears in every R2 dashboard URL, and a request carrying it without the key pair fails —
so it is committable, and `.yidam/config.toml` commits it as part of the vault's S3 endpoint
(#2144). This paragraph used to call all three secrets, which read as a prohibition on the
one value that is not one. Read every one of them through
`watermark.config.get_settings()` (never `os.environ` directly):

```sh
export WATERMARK_DOCUMENTS_OBJECT_STORE_ACCOUNT_ID="<account-id>"
export WATERMARK_DOCUMENTS_OBJECT_STORE_ACCESS_KEY_ID="<access-key-id>"
export WATERMARK_DOCUMENTS_OBJECT_STORE_SECRET_ACCESS_KEY="<secret>"
# Optional overrides (defaults shown):
# export WATERMARK_DOCUMENTS_OBJECT_STORE_BUCKET="watermark-documents"
# export WATERMARK_DOCUMENTS_OBJECT_STORE_DEV_BUCKET="watermark-documents-dev"
# export WATERMARK_DOCUMENTS_OBJECT_STORE_ENDPOINT="https://<acct>.r2.cloudflarestorage.com"
```

### 3. The `DOCS_ENABLED` kill switch

The `/api/doc` Function ships **dark**: it returns `503` until an operator sets
`DOCS_ENABLED = "true"` in the Cloudflare dashboard (Pages → Settings → Variables) — the
same pattern as `SUBMISSIONS_ENABLED` / `ASK_ENABLED`. It's a dashboard variable, **not**
in `wrangler.toml`, so it flips without a redeploy.

## Populating the store — `watermark objectstore sync`

```sh
watermark objectstore sync --dry-run                 # list what would upload (sizes), upload nothing
watermark objectstore sync --target local            # → watermark-documents-dev (the dev/preview bucket)
watermark objectstore sync --target remote            # → watermark-documents (prod)
watermark objectstore sync --target local --collection recorder   # scope to one collection
```

Behaviour:

- **Key** = the `data/documents` rel (the as-received chain-of-custody name).
- **Incremental** — an object whose remote size + ETag already match is skipped, so a
  rerun with no changes uploads nothing.
- **LFS-aware** — an unresolved Git-LFS pointer is **reported and skipped**, never
  uploaded as a 130-byte stub. Run `git lfs pull` first to upload the real bytes.
- **Type-stamping** — each object gets its `Content-Type` plus `media_type` /
  `render_class` metadata (from the documents feed, #275), so `/api/doc` serves the right
  type without re-sniffing.

## The dev loop

To view documents in the local interactive stack, just run it — it seeds the local R2 first:

```sh
git lfs pull                     # materialize the bytes (LFS) you want to serve
mise run //web:dev:stack    # build → seed published docs into local R2 → wrangler pages dev
# visit the viewer; /api/doc/<rel> now streams the real bytes
```

The seed step ([`web/scripts/seed-r2.mjs`](../web/scripts/seed-r2.mjs)) writes the
**published** docs through wrangler's `getPlatformProxy()` into the *same* local R2 that
`wrangler pages dev` reads — so this needs **no Cloudflare creds**. (`wrangler pages dev` has no
`--remote`, and its local R2 can't be filled with `wrangler r2 object put`, so this is the path
that actually works.) To serve a wider set, seed a whole collection then restart the stack:

```sh
cd frontend && npm run seed:r2 -- --collection recorder   # or pass explicit data/documents rels
```

**`watermark objectstore sync --target local` is a different thing:** it uploads to the **remote**
`watermark-documents-dev` bucket that Cloudflare **preview deployments** bind — *not* the local stack.
Run it before a preview deploy, not for local dev. The doc-serving logic (gate, ranges,
content-type) is also covered offline by `functions/_test/docRoute.test.ts`. See
[`web/README.md`](../web/README.md) → *Local dev & testing*.

## Production

The Pages deploy (`.github/workflows/pages.yml`) carries the `DOCS` binding from
`wrangler.toml`. Once the prod bucket is populated (`watermark objectstore sync --target
remote`), the allowlist (C1) is in place, and a redaction pass (C2) has run, an operator
flips `DOCS_ENABLED = "true"` to open `/api/doc` to the public for the allowlisted files.

## Checking that production actually serves it — `watermark objectstore audit`

```sh
watermark objectstore audit                   # probe the production origin (no credentials)
watermark objectstore audit --via store       # also HEAD the bucket: absent object vs gate rejection
watermark objectstore audit --base https://<preview>.pages.dev
```

**Nothing verified the promise until #2149, and the promise was 93% false.** `DocumentItem.published`
is an assertion about this store, and `available` is read from the *working tree* — where an
unresolved LFS pointer counts as available on purpose, because the bytes are supposed to be here. So
a published document renders as a download nothing has ever tried. Measured 2026-09-04: of the 392
documents the deployed build offered, **26 could be downloaded.**

The audit compares three sets and names which one broke, because the failures have different fixes:

| | |
|---|---|
| **offered** | what this commit's `web/sites/<slug>` bundles publish, unioned over the exported sites |
| **gate** | what the deployed `/published-documents.json` admits |
| **served** | what `HEAD /api/doc/<rel>` answers `200` for |

- **unserved** — in the gate, and 404. Production offers a download it cannot serve; always a bug.
  **Exits 1.**
- **absent from the store** (`--via store`) — no object at all. No deploy fixes this; a sync does.
  **Exits 1.**
- **not yet in the deployed gate** — the deploy is behind this commit. Routine, and **reported
  rather than failed**: a merged clearance waiting on a manual deploy is this repo's normal state,
  and a check that failed on it would be muted inside a week. A count far larger than recent commits
  explain is the shape of a *scoping* bug — which is exactly how #2149 read.

`/api/doc` answers 404 for both "not allowlisted" and "not in the store", so the API probe alone
cannot tell those apart. That is what `--via store` is for, and why the two are never summed.

⚠️ **A preview URL is not a valid target for the gate half.** `enforcePublishGate` only enforces
when `CF_PAGES_BRANCH == "main"`, so a preview deployment serves whatever the bucket holds and the
gate comparison reads as vacuously clean. Point `--base` at a preview to measure *store coverage*
only.

`.github/workflows/doc-serving.yml` runs the API probe daily. It needs no credentials and no LFS —
it reads committed bundles and a public origin, and never opens a source byte.

### Should the sync run in a workflow? Not yet — and #2141 is why

#2149 asked whether populating the store belongs in CI "rather than a human's memory". The answer
today is **no**, and the reason is not effort:

- The sync needs the **real bytes**, so it cannot run on an `lfs: false` checkout. A workflow that
  pulled them would move ~3.7 GB of metered Git-LFS bandwidth per run — which is a large part of why
  this drifted in the first place.
- The rel-keyed keyspace it fills is **being retired** (#2145): the corpus already lives in a
  content-addressed yidam vault, and `/api/doc` moves to resolving `rel → sha256`. Automating an
  upload path that is scheduled for deletion buys nothing.
- After #2147 the working tree is filled **from the vault**, not from LFS. At that point a workflow
  *can* hydrate cheaply, over the keyspace that is staying — so automation becomes worth building
  exactly when it stops being expensive.

What replaces the memory in the meantime is the audit above: a human still runs the sync, but a red
workflow names the files rather than a reader finding them. That is the part that was missing.

### The gate is network-global; the `documents` feed is per-site

`/published-documents.json` is one asset at the domain root, and `documents` is a per-site feed.
Until #2149 the route read it with a bare `loadFeed("documents")` — and a global route runs outside
the active-site ALS, so that resolved **Lima's** bundle and the gate 404'd every other site's
published documents before R2 was ever asked: 252 of 392 unreachable by construction, at any deploy
freshness. `@watermark/core`'s `docGate.ts` now unions across `exportedSiteSlugs()`, and stops
there — a non-selectable site mints no pages, so admitting its documents would open bytes no page
links, which is the opposite of default-deny.

## Security notes

- Credentials are S3 API tokens — environment only, never committed.
- Captured third-party web evidence may embed secrets/tokens; that is **evidence**, not a
  leak to redact (see the root `CLAUDE.md`). The *public* gate is the allowlist + the PII
  pass, not source-byte redaction.
- The store and the Function are dark-until-enabled, mirroring the
  [submissions](./submissions-api.md) and [ask](./ask-api.md) seams.
