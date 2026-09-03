# Source-document object store (R2)

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

## Security notes

- Credentials are S3 API tokens — environment only, never committed.
- Captured third-party web evidence may embed secrets/tokens; that is **evidence**, not a
  leak to redact (see the root `CLAUDE.md`). The *public* gate is the allowlist + the PII
  pass, not source-byte redaction.
- The store and the Function are dark-until-enabled, mirroring the
  [submissions](./submissions-api.md) and [ask](./ask-api.md) seams.
