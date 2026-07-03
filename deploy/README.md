# `deploy/` — site deployment infrastructure (Pulumi)

A dedicated Pulumi stack for the BOSC site's deployment resources — kept separate from the
GitHub repo-config stack ([`.github/config`](../.github/config)) because they have
different providers and credentials, lifecycles, and blast radius. Change the config by
editing [`index.ts`](index.ts) and running `pulumi up` (locally or via the
[`deploy-infra` workflow](../.github/workflows/deploy-infra.yml)).

Two providers: **Cloudflare** (the KV namespace + Turnstile widget + the Pages
custom-domain attach) and **AWS** (the Route53 record — only when a custom domain is set).

## What it manages

### Submissions (#74 / epic #240)

- **`cloudflare.WorkersKvNamespace` — `RATE_LIMIT`** — per-IP rate limiter store (Phase 5).
  Bind its id in `web/wrangler.toml`; until then, rate limiting is off (fail-open).
- **`cloudflare.TurnstileWidget`** — guards the public form. Exports the public site key
  and the (sensitive) secret key. Serves on the custom domain + pages.dev preview.
- **`cloudflare.R2Bucket` — `SUBMISSION_ATTACHMENTS`** (#243) — pre-upload target for
  submission file attachments. Missing → `/api/attach` returns 503.
  Separate from `DOCS` to keep the evidence chain isolated.
- **`cloudflare.WorkersKvNamespace` — `SUBMISSION_CONTACT`** (#242) — private submitter
  contact store, keyed `contact:<issue-number>`, TTL-bounded. Optional: if not bound
  the contact field is accepted but not retained.

### Auth — Cognito identity (#919 / #924)

Gated on the `authEnabled` config flag (defaults false). Set it once to provision; do
not flip it back — removing the pool destroys all users and sessions.

- **`aws.cognito.UserPool`** — email-based pool with the `admin_sites` custom attribute
  (per-site curator scope) and email-verification enforced.
- **`aws.cognito.UserPoolDomain`** — Hosted UI domain
  (`<cognitoDomainPrefix>.auth.<cognitoRegion>.amazoncognito.com`). Upgrade to a custom
  domain in the console after creation (requires an ACM cert in us-east-1).
- **`aws.cognito.UserPoolClient`** — public client (no secret), PKCE Authorization Code
  grant only. Callback URLs include the live site domain (when `siteDomain` is set) and
  `http://localhost:4321` for local dev.
- **`aws.cognito.UserPoolGroup` × 3** — `standard`, `site-admin`, `admin` privilege tiers.

Always created (cheap; activation gate is wiring in `wrangler.toml`):

- **`cloudflare.WorkersKvNamespace` — `JWKS_CACHE`** — Cognito public-key cache (1-hour
  TTL), avoiding a cold JWKS fetch on every JWT verification.
- **`cloudflare.WorkersKvNamespace` — `AUTH_PREFS`** — per-user profile + notification
  prefs, keyed by Cognito `sub` (#921).

### User-authored Stories — Hyperdrive → Lakebase (#1090 / #1138)

Gated on the `stories` toggle in [`features.yaml`](features.yaml) (defaults false).

- **`cloudflare.HyperdriveConfig` — `STORIES_HYPERDRIVE`** — a pooled Postgres path from the
  Workers runtime to Databricks **Lakebase** (the `/api/stories` Functions can't open a raw
  Postgres socket; they go through Hyperdrive via postgres.js). Its origin is parsed from the
  **secret** `storiesLakebaseUrl` connection string. Provisioned only when `stories=true`;
  a `stories=true` with no `storiesLakebaseUrl` set fails `pulumi up` (a config guard).

  Set the secret out of band (Databricks issues a **short-lived OAuth token** as the Postgres
  password, so the whole URL is sensitive — never commit it):

  ```bash
  pulumi config set --secret bosc-deploy:storiesLakebaseUrl \
    postgres://<user>:<oauth-token>@<host>:5432/<database>
  ```

  Then export the id into wrangler: `pulumi stack output storiesHyperdriveId` → the
  `[[hyperdrive]]` `id` in `web/wrangler.toml`. **Token refresh:** Hyperdrive caches the origin
  credentials, so a rotated OAuth token needs a fresh `pulumi up` to re-push it — prefer a
  Databricks service principal with a longer-lived credential, or a scheduled re-apply.

  The toggle also writes `STORIES_ENABLED` (the Functions kill switch) and
  `PUBLIC_STORIES_ENABLED` (the Astro build-time UI gate) to the Pages project, mirroring `rum`.

### Custom domain exchange (when `siteDomain` is set)

- **`cloudflare.PagesDomain`** — attaches `siteDomain` to the `the-watermark-directory` Pages project (the
  Cloudflare side: "expect this hostname, issue a cert once DNS validates").
- **`aws.route53.Record`** — a CNAME `siteDomain` → `the-watermark-directory.pages.dev` (the AWS side).
  Decided shape ([#240](https://github.com/watermark-directory/the-watermark-directory/issues/240)): a **subdomain**,
  because a bare apex can't point cross-provider at pages.dev (a CNAME is illegal at the
  apex, and a Route53 ALIAS only targets AWS resources). For an apex you'd move DNS to
  Cloudflare or add a redirect — neither is wired here.

**Not** managed here: the **Pages project** itself. It is wrangler-deployed
([`pages.yml`](../.github/workflows/pages.yml)) with its env/bindings in
[`web/wrangler.toml`](../web/wrangler.toml); managing that config in both Pulumi
and wrangler would drift on every deploy. `PagesDomain` only *attaches* to the existing
project by name, so the two don't fight.

> **CAA note:** if the Route53 zone carries `CAA` records, they must permit Cloudflare's
> CA (currently Google Trust Services / Let's Encrypt) or the edge cert won't issue.

## Outputs → where they go

`pulumi up` exports the values the rest of the seam wires in:

### Submissions

| Output | Wire it into |
| --- | --- |
| `rateLimitKvNamespaceId` | `web/wrangler.toml` → `[[kv_namespaces]]` `id` (RATE_LIMIT) |
| `turnstileSiteKey` | the `PUBLIC_TURNSTILE_SITE_KEY` **build** repo variable (public) |
| `turnstileSecretKey` | the `TURNSTILE_SECRET_KEY` Function secret (`pulumi stack output turnstileSecretKey --show-secrets`) |
| `submissionAttachmentsBucketName` | `web/wrangler.toml` → `[[r2_buckets]]` `bucket_name` (SUBMISSION_ATTACHMENTS) |
| `submissionAttachmentsBucketDevName` | `web/wrangler.toml` → `[[r2_buckets]]` `preview_bucket_name` (SUBMISSION_ATTACHMENTS) |
| `submissionContactKvNamespaceId` | `web/wrangler.toml` → `[[kv_namespaces]]` `id` (SUBMISSION_CONTACT) |
| `siteUrl` | the `PAGES_SITE_URL` repo variable for the build |
| `siteDomainStatus` | watch for `active` — Cloudflare validated the domain + issued the cert |
| `route53RecordFqdn` | sanity-check the managed DNS record |

### Auth

| Output | Wire it into |
| --- | --- |
| `cognitoUserPoolId` | `web/wrangler.toml` `[vars]` `COGNITO_USER_POOL_ID` |
| `cognitoClientId` | `web/wrangler.toml` `[vars]` `COGNITO_CLIENT_ID` **and** `PUBLIC_COGNITO_CLIENT_ID` build var |
| `cognitoDomain` | `web/wrangler.toml` `[vars]` `COGNITO_DOMAIN` **and** `PUBLIC_COGNITO_DOMAIN` build var |
| `cognitoRegionOut` | `web/wrangler.toml` `[vars]` `COGNITO_REGION` |
| `jwksCacheKvNamespaceId` | `web/wrangler.toml` → `[[kv_namespaces]]` `id` (JWKS_CACHE) |
| `authPrefsKvNamespaceId` | `web/wrangler.toml` → `[[kv_namespaces]]` `id` (AUTH_PREFS) |

### Stories

| Output | Wire it into |
| --- | --- |
| `storiesHyperdriveId` | `web/wrangler.toml` → `[[hyperdrive]]` `id` (STORIES_HYPERDRIVE); `not-configured` until `stories=true` |

## Stack config (`Pulumi.prod.yaml`, committed — no secrets)

| Key | Default | Meaning |
| --- | --- | --- |
| `cloudflareAccountId` | *(required, unset)* | Cloudflare account that owns the resources |
| `pagesProject` | `the-watermark-directory` | the wrangler-deployed Pages project a custom domain attaches to |
| `siteDomain` | *(unset)* | the live subdomain, e.g. `watermark.example.org` — **late-bound** |
| `route53ZoneId` | *(unset)* | the Route53 hosted-zone id that owns `siteDomain` |
| `siteDomains` | `["the-watermark-directory.pages.dev"]` | preview hostnames for Turnstile (custom domain folded in automatically) |
| `authEnabled` | `false` | set `true` to provision Cognito resources — **destructive to remove** |
| `cognitoDomainPrefix` | `watermark-auth` | Hosted UI subdomain prefix (→ `<prefix>.auth.<region>.amazoncognito.com`) |
| `cognitoRegion` | `us-east-1` | AWS region for the User Pool (must match the AWS provider region) |

Until `siteDomain` is set the stack manages KV + R2 + Turnstile only and the site stays on
`watermark.pages.dev`. Until `authEnabled` is set the Cognito pool is not created (the
JWKS_CACHE and AUTH_PREFS KV namespaces are always created — they're cheap and needed before
the auth wiring can be tested).

Provider auth: the Cloudflare **token** is never committed — supply it via
`CLOUDFLARE_API_TOKEN` (or the `cloudflare:apiToken` Pulumi secret), scoped to **Workers
KV Storage: Edit** + **Turnstile: Edit** + **Pages: Edit** (the last for the domain
attach). AWS uses the standard credential chain (env / an OIDC role) and is only exercised
when `siteDomain` + `route53ZoneId` are set.

## Prerequisites

- Node.js LTS (managed by mise) — run `npm install` in this directory (installs
  `@pulumi/cloudflare` **and** `@pulumi/aws`).
- The Pulumi CLI + the **S3 state backend** in the project's AWS account
  (`pulumi login s3://<bucket>/bosc-deploy`); Pulumi locks within the bucket, so no
  DynamoDB table is needed. Secrets are encrypted with **awskms** (a small KMS key), not a
  shared passphrase. A local `pulumi login --local` still works for dry runs.

## Bootstrap (one-time)

```bash
# 0. Once per account: a state bucket + a KMS key for secret encryption.
aws s3api create-bucket --bucket <bucket> --region <region>
KMS_ARN=$(aws kms create-key --description bosc-pulumi-secrets --query KeyMetadata.Arn --output text)

cd deploy
npm install
pulumi login s3://<bucket>/bosc-deploy
pulumi stack init prod --secrets-provider "awskms://${KMS_ARN}"
pulumi config set bosc-deploy:cloudflareAccountId <account-id>
export CLOUDFLARE_API_TOKEN=...                # KV + Turnstile + Pages edit scope
pulumi preview                                 # KV + Turnstile (no domain yet)
pulumi up
pulumi stack output                            # read the ids/keys to wire in
pulumi stack output turnstileSecretKey --show-secrets

# Later, once the domain is chosen — the Route53↔Cloudflare exchange:
pulumi config set bosc-deploy:siteDomain   watermark.example.org
pulumi config set bosc-deploy:route53ZoneId Z0123456789ABC
pulumi up                                      # PagesDomain + the Route53 CNAME
pulumi stack output siteDomainStatus           # poll until "active"
```

## CI

[`../.github/workflows/deploy-infra.yml`](../.github/workflows/deploy-infra.yml) runs
`pulumi preview` on PRs that touch this directory (commenting the plan) and `pulumi up`
on `main`. It needs:

- **`CLOUDFLARE_API_TOKEN`** (secret) — the Cloudflare provider token (KV + Turnstile +
  Pages edit).
- **`DEPLOY_AWS_ROLE_ARN`** (variable) — an AWS IAM role assumed via **OIDC** (no static
  keys), with access to the S3 state bucket, the awskms key, and Route53 for the zone.
- **`PULUMI_BACKEND_URL`** (variable) — `s3://<bucket>/bosc-deploy`.
- **`DEPLOY_AWS_REGION`** (variable, optional) — defaults to `us-east-1`.
- **`DEPLOY_PULUMI_STACK`** (variable) — the S3-backend stack name, just `prod`.

`DEPLOY_PULUMI_STACK` doubles as the on-switch: the job is gated on it, so until it's set
the workflow is **skipped** (not failed) on PRs that touch this directory. Set it with the
AWS role + backend URL + the Cloudflare secret together to activate it.
